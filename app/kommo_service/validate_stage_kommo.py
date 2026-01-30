import os
import aiofiles
import aiohttp
import base64
import requests
import logging
from fastapi import FastAPI, Request
from dotenv import load_dotenv

load_dotenv()

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 2) Enviar imagen a OpenAI GPT-4o con visión
def validate_stage_kommo(lead_id):
    logger.info(f"=== Validando stage para lead_id: {lead_id} ===")
    
    token = os.getenv("TOKEN_KOMMO")
    subdomain = os.getenv("SUBDOMAIN_KOMMO")
    if not token or not subdomain:
        raise ValueError("TOKEN_KOMMO o SUBDOMAIN_KOMMO no está definida")

    url = f"https://{subdomain}.kommo.com/api/v4/leads/{lead_id}"
    headers = {
        "accept": "application/json",
        "Authorization": f"Bearer {token}"
    }

    logger.info(f"Haciendo petición a: {url}")
    response = requests.get(url, headers=headers)
    logger.info(f"Status code de respuesta: {response.status_code}")
    
    if response.status_code != 200:
        raise Exception(f"Error al obtener el lead: {response.text}")

    try:
        data = response.json()
        logger.info(f"Datos recibidos de Kommo: {data}")
    except Exception as e:
        raise Exception("Respuesta de Kommo no es JSON válida")

    status_id = data.get("status_id")
    pipeline_id = data.get("pipeline_id")
    
    logger.info(f"status_id obtenido: {status_id} (tipo: {type(status_id)})")
    logger.info(f"pipeline_id obtenido: {pipeline_id} (tipo: {type(pipeline_id)})")
    logger.info(f"status_id esperado: 93482383")
    logger.info(f"pipeline_id esperado: 12109475")
    
    resultado = status_id == 93482383 and pipeline_id == 12109475
    logger.info(f"Resultado de validación: {resultado}")
    
    return resultado
