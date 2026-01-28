import os
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
                async with aiofiles.open(path, 'wb') as f:
                    await f.write(await resp.read())
        return path
    except Exception as e:
        print(f"Error descargando archivo desde {url}: {e}")
        raise

# 2) Enviar imagen a OpenAI GPT-4o con visión
def analyze_image_with_gpt4o(image_path: str, prompt: str = "Extrae la información en formato JSON con los campos 'producto' y 'cantidad'."):
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
        result_text += "\n[Se adjuntó una imagen]"
        # url = att.get("link")
        # filename = att.get("file_name")
        # if url and filename:
        #     temp_path = f"/tmp/{filename}"
        #     try:
        #         await download_file(url, temp_path)
        #         vision_summary = analyze_image_with_gpt4o(temp_path)
        #         result_text += f"\n[Resumen IA de imagen:]\n{vision_summary}"
        #     except Exception as e:
        #         result_text += f"\n[Error al procesar imagen con IA: {e}]"
        #     finally:
        #         if os.path.exists(temp_path):
        #             os.remove(temp_path)

    if att and att.get("type") == "voice":
        url = att.get("link")
        filename = att.get("file_name")
        if url and filename:
            temp_path = f"/tmp/{filename}"
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

# 5) Transcribir audio usando OpenAI Whisper
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
        with open(file_path, 'rb') as audio_file:
            data = aiohttp.FormData()
            data.add_field('file', audio_file, filename=file_path, content_type='audio/mpeg')
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