import os
import uuid
import aiofiles
import aiohttp
import base64
import requests
from fastapi import FastAPI, Request
from dotenv import load_dotenv

load_dotenv()

# 1) Descargar archivos desde URL
async def download_file(url: str, path: str):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                resp.raise_for_status()
                content = await resp.read()
                content_type = resp.headers.get('Content-Type', 'unknown')
                print(f"Archivo descargado: {len(content)} bytes, Content-Type: {content_type}")
                
                if len(content) == 0:
                    raise Exception("El archivo descargado está vacío")
                
                async with aiofiles.open(path, 'wb') as f:
                    await f.write(content)
        
        # Verificar que el archivo se guardó correctamente
        file_size = os.path.getsize(path)
        print(f"Archivo guardado en {path}: {file_size} bytes")
        return path
    except Exception as e:
        print(f"Error descargando archivo desde {url}: {e}")
        raise

# 2) Enviar imagen a OpenAI GPT-4o con visión
def analyze_image_with_gpt4o(image_path: str, prompt: str = "Analiza la imagen y dame una descripcion breve de su contenido"):
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY no está definida")

    try:
        with open(image_path, "rb") as image_file:
            encoded_image = base64.b64encode(image_file.read()).decode("utf-8")
    except Exception as e:
        print(f"Error leyendo imagen: {e}")
        raise

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "gpt-4o",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{encoded_image}"
                        }
                    }
                ]
            }
        ],
        "max_tokens": 1000
    }

    try:
        response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
        # Validar estructura de respuesta
        if "choices" in data and data["choices"] and "message" in data["choices"][0] and "content" in data["choices"][0]["message"]:
            return data["choices"][0]["message"]["content"]
        else:
            raise Exception("Respuesta inesperada de OpenAI: " + str(data))
    except Exception as e:
        print(f"Error procesando imagen con GPT-4o: {e}")
        raise

# 3) Procesar los datos del mensaje recibido
async def process_request_data(form_data: dict):
    try:
        msg = form_data["message"]["add"][0]
        lead_id = int(msg["entity_id"])
        text = msg.get("text", "").strip()
        att = msg.get("attachment")
    except (KeyError, IndexError, ValueError) as e:
        print(f"Error procesando datos del mensaje: {e}")
        raise

    result_text = text

    if att and att.get("type") == "picture":
        # result_text += "\n[Se adjuntó una imagen]:"
        url = att.get("link")
        filename = att.get("file_name")
        if url and filename:
            # Generar nombre único con UUID
            file_extension = os.path.splitext(filename)[1] if filename else ".png"
            unique_filename = f"{uuid.uuid4()}{file_extension}"
            temp_path = f"/tmp/{unique_filename}"
            try:
                await download_file(url, temp_path)
                vision_summary = analyze_image_with_gpt4o(temp_path)
                result_text += f"\n[Resumen IA de imagen:]\n{vision_summary}"
            except Exception as e:
                result_text += f"\n[Error al procesar imagen con IA: {e}]"
            finally:
                if os.path.exists(temp_path):
                    os.remove(temp_path)

    if att and att.get("type") == "voice":
        url = att.get("link")
        filename = att.get("file_name")
        if url and filename:
            # Generar nombre único con UUID
            file_extension = os.path.splitext(filename)[1] if filename else ".ogg"
            unique_filename = f"{uuid.uuid4()}{file_extension}"
            temp_path = f"/tmp/{unique_filename}"
            try:
                await download_file(url, temp_path)
                # Aquí podrías agregar lógica para procesar el audio si es necesario
                transcription = await transcribe_audio(temp_path)
                result_text += f"\n[Transcripción de audio:]\n{transcription}"
                if os.path.exists(temp_path):
                    os.remove(temp_path)    
            except Exception as e:
                result_text += f"\n[Error al descargar audio: {e}]"

    return {"lead_id": lead_id, "text": result_text}

# 4) Parseo de formularios anidados tipo Kommo
def parse_nested_form(form):
    result = {}
    try:
        for key, value in form.items():
            keys = key.replace("]", "").split("[")
            d = result
            for part in keys[:-1]:
                if part.isdigit():
                    part = int(part)
                if isinstance(d, list):
                    while len(d) <= part:
                        d.append({})
                    d = d[part]
                else:
                    if part not in d:
                        d[part] = [] if keys[keys.index(part) + 1].isdigit() else {}
                    d = d[part]
            last_key = keys[-1]
            if last_key.isdigit():
                last_key = int(last_key)
                while len(d) <= last_key:
                    d.append({})
                d[last_key] = value
            else:
                d[last_key] = value
    except Exception as e:
        print(f"Error parseando formulario anidado: {e}")
        raise
    return result

# 5) Detectar formato de audio basándose en magic bytes
def detect_audio_format(content: bytes) -> str:
    """Detecta el formato real del archivo de audio basándose en los magic bytes"""
    if len(content) < 12:
        return 'unknown'
    
    # OGG: empieza con "OggS"
    if content[:4] == b'OggS':
        return 'ogg'
    
    # MP3: empieza con ID3 o frame sync (0xFF 0xFB, 0xFF 0xFA, 0xFF 0xF3, 0xFF 0xF2)
    if content[:3] == b'ID3' or (content[0] == 0xFF and (content[1] & 0xE0) == 0xE0):
        return 'mp3'
    
    # M4A/MP4: tiene "ftyp" en los bytes 4-7
    if content[4:8] == b'ftyp':
        # Verificar si es M4A específicamente
        ftyp_brand = content[8:12]
        if ftyp_brand in [b'M4A ', b'mp41', b'mp42', b'isom', b'M4B ']:
            return 'm4a'
        return 'm4a'  # Tratar todos los ftyp como m4a para audio
    
    # WAV: empieza con "RIFF" y tiene "WAVE"
    if content[:4] == b'RIFF' and content[8:12] == b'WAVE':
        return 'wav'
    
    # FLAC: empieza con "fLaC"
    if content[:4] == b'fLaC':
        return 'flac'
    
    # WebM: empieza con 0x1A 0x45 0xDF 0xA3 (EBML header)
    if content[:4] == b'\x1a\x45\xdf\xa3':
        return 'webm'
    
    print(f"Formato no reconocido. Primeros bytes: {content[:12].hex()}")
    return 'm4a'  # Default a m4a ya que es común en WhatsApp

# 6) Transcribir audio usando OpenAI Whisper
async def transcribe_audio(file_path: str) -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY no está definida")
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"El archivo {file_path} no existe")

    url = "https://api.openai.com/v1/audio/transcriptions"
    headers = {
        "Authorization": f"Bearer {api_key}"
    }

    try:
        # Leer el contenido del archivo de forma asíncrona
        async with aiofiles.open(file_path, 'rb') as f:
            file_content = await f.read()
        
        print(f"Archivo a transcribir: {len(file_content)} bytes")
        print(f"Primeros bytes (hex): {file_content[:20].hex() if len(file_content) >= 20 else file_content.hex()}")
        
        # Verificar que el archivo no esté vacío
        if len(file_content) == 0:
            raise Exception("El archivo de audio está vacío")
        
        # Detectar el formato real del archivo basándose en magic bytes
        detected_format = detect_audio_format(file_content)
        print(f"Formato detectado: {detected_format}")
        
        # Usar el formato detectado para el filename y content-type
        format_info = {
            'ogg': {'ext': '.ogg', 'content_type': 'audio/ogg'},
            'm4a': {'ext': '.m4a', 'content_type': 'audio/mp4'},
            'mp3': {'ext': '.mp3', 'content_type': 'audio/mpeg'},
            'wav': {'ext': '.wav', 'content_type': 'audio/wav'},
            'flac': {'ext': '.flac', 'content_type': 'audio/flac'},
            'webm': {'ext': '.webm', 'content_type': 'audio/webm'},
        }
        
        info = format_info.get(detected_format, {'ext': '.m4a', 'content_type': 'audio/mp4'})
        filename = f"audio{info['ext']}"
        content_type = info['content_type']
        
        print(f"Enviando a OpenAI como: {filename} ({content_type})")

        data = aiohttp.FormData()
        data.add_field('file', file_content, filename=filename, content_type=content_type)
        data.add_field('model', 'whisper-1')

        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, data=data) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"Error transcribiendo el audio: {response.status} - {error_text}")

                json_response = await response.json()
                if 'text' in json_response:
                    return json_response['text']
                else:
                    raise Exception(f"Respuesta inesperada de OpenAI: {json_response}")
    except Exception as e:
        print(f"Error en transcribe_audio: {e}")
        raise
