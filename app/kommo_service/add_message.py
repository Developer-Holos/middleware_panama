import os
import requests
import logging
import json

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def add_message(lead_id: int, text: str):
    logger.info(f"=== Iniciando add_message ===")
    logger.info(f"lead_id: {lead_id} (tipo: {type(lead_id)})")
    logger.info(f"text: {text}")
    logger.info(f"Longitud del texto: {len(text)}")

    msj_client_field_id = 955666  # ID del campo personalizado para mensajes del cliente
    logger.info(f"ID del campo personalizado: {msj_client_field_id}")
    token = os.getenv("TOKEN_KOMMO")
    subdomain = os.getenv("SUBDOMAIN_KOMMO")

    if not token or not subdomain:
        logger.error("Error: Faltan variables de entorno")
        raise ValueError("TOKEN_KOMMO o SUBDOMAIN_KOMMO no está definida")

    url = f"https://{subdomain}.kommo.com/api/v4/leads/{lead_id}"
    logger.info(f"URL: {url}")
    logger.info(f"Subdomain: {subdomain}")
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    try:
        logger.info("Obteniendo datos del lead...")
        response = requests.get(url, headers=headers)
        logger.info(f"Status code GET: {response.status_code}")
        
        if response.status_code != 200:
            logger.error(f"Error en GET: {response.text}")
            return {"status": "error", "message": f"Error obteniendo lead: {response.status_code} - {response.text}"}

        data = response.json()
        logger.info(f"Respuesta completa del lead: {json.dumps(data, indent=2, ensure_ascii=False)}")
        
        custom_fields_values = data.get("custom_fields_values")
        logger.info(f"custom_fields_values: {custom_fields_values}")
        logger.info(f"Tipo de custom_fields_values: {type(custom_fields_values)}")

        # Escenario 1: custom_fields_values es None
        if custom_fields_values is None:
            logger.info("ESCENARIO 1: No hay campos personalizados, creando nuevo campo")
            custom_field_update = [{
                "field_id": msj_client_field_id,
                "values": [{"value": text}]
            }]
        else:
            # Escenario 2: Buscar si existe el campo específico
            logger.info(f"ESCENARIO 2/3: Buscando campo {msj_client_field_id} en campos existentes")
            field_found = False
            for field in custom_fields_values:
                field_id = field.get("field_id")
                logger.info(f"Comparando: field_id={field_id} (tipo: {type(field_id)}) con {msj_client_field_id} (tipo: {type(msj_client_field_id)})")
                if field_id == msj_client_field_id:
                    field_found = True
                    logger.info("Campo encontrado, actualizando valor existente")
                    current_value = field.get("values", [{}])[0].get("value", "")
                    logger.info(f"Valor actual del campo: '{current_value}'")
                    new_value = f"{current_value}\n{text}" if current_value else text
                    logger.info(f"Nuevo valor que se agregará: '{new_value}'")
                    custom_field_update = [{
                        "field_id": msj_client_field_id,
                        "values": [{"value": new_value}]
                    }]
                    break
            
            # Escenario 3: No se encontró el campo específico
            if not field_found:
                logger.info("ESCENARIO 3: Campo no encontrado, creando nuevo campo")
                custom_field_update = [{
                    "field_id": msj_client_field_id,
                    "values": [{"value": text}]
                }]

        # Actualizamos el campo
        payload = {"custom_fields_values": custom_field_update}
        logger.info(f"Payload del PATCH: {json.dumps(payload, indent=2, ensure_ascii=False)}")
        
        update_response = requests.patch(url, headers=headers, json=payload)
        logger.info(f"Status code PATCH: {update_response.status_code}")
        logger.info(f"Respuesta PATCH completa: {update_response.text}")
        
        if update_response.status_code not in (200, 201):
            logger.error(f"Error en PATCH: {update_response.status_code} - {update_response.text}")
            return {
                "status": "error", 
                "message": f"Error actualizando lead: {update_response.status_code} - {update_response.text}"
            }

        logger.info("✓ Mensaje agregado correctamente")
        return {"status": "ok", "message": "Mensaje agregado correctamente"}

    except requests.exceptions.RequestException as e:
        logger.error(f"Error de conexión: {e}")
        return {"status": "error", "message": f"Error de conexión: {str(e)}"}
    except ValueError as e:
        logger.error(f"Error procesando JSON: {e}")
        return {"status": "error", "message": f"Error procesando JSON: {str(e)}"}
    except Exception as e:
        logger.error(f"Error inesperado: {e}", exc_info=True)
        return {"status": "error", "message": f"Error inesperado: {str(e)}"}