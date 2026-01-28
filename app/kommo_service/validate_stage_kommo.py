import os
import aiofiles
import aiohttp
import base64
import requests
from fastapi import FastAPI, Request
from dotenv import load_dotenv

load_dotenv()

# 2) Enviar imagen a OpenAI GPT-4o con visión
def validate_stage_kommo(lead_id):
    token = os.getenv("TOKEN_KOMMO")
    subdomain = os.getenv("SUBDOMAIN_KOMMO")
    if not token or not subdomain:
        raise ValueError("TOKEN_KOMMO o SUBDOMAIN_KOMMO no está definida")

    url = f"https://{subdomain}.kommo.com/api/v4/leads/{lead_id}"
    headers = {
        "accept": "application/json",
        "Authorization": f"Bearer {token}"
    }

    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        raise Exception(f"Error al obtener el lead: {response.text}")

    try:
        data = response.json()
    except Exception as e:
        raise Exception("Respuesta de Kommo no es JSON válida")

    status_id = data.get("status_id")
    pipeline_id = data.get("pipeline_id")
    return status_id == 93482383  and pipeline_id == 12109475
