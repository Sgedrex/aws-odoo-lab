"""Prueba la conexión a la API JSON-2 de Odoo listando cinco proveedores."""
import os

import requests
from dotenv import load_dotenv

load_dotenv()  # carga las variables de .env en el entorno

URL = os.environ["ODOO_URL"]
DB = os.environ["ODOO_DB"]
API_KEY = os.environ["ODOO_API_KEY"]

HEADERS = {
    "Authorization": f"bearer {API_KEY}",  # la API key reemplaza al usuario y la contraseña
    "X-Odoo-Database": DB,                 # qué base usar, porque el servidor podría tener varias
}

respuesta = requests.post(
    f"{URL}/json/2/res.partner/search_read",  # formato: /json/2/<modelo>/<método>
    headers=HEADERS,
    json={
        "domain": [["supplier_rank", ">", 0]],  # filtro: solo proveedores
        "fields": ["name", "email", "city"],     # solo estas columnas
        "limit": 5,                               # como máximo 5 registros
    },
    timeout=30,
)
respuesta.raise_for_status()  # si Odoo devuelve un error, el script se detiene y lo muestra

for proveedor in respuesta.json():
    print(proveedor)