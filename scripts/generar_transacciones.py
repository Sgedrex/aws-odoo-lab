"""Genera transacciones ficticias en Odoo a través de la API JSON-2."""
import os
import random
from datetime import datetime

import requests
from dotenv import load_dotenv

load_dotenv()
URL = os.environ["ODOO_URL"]
HEADERS = {
    "Authorization": f"bearer {os.environ['ODOO_API_KEY']}",
    "X-Odoo-Database": os.environ["ODOO_DB"],
}
random.seed(42)


def llamar(modelo, metodo, **parametros):
    """Llama a cualquier método de cualquier modelo: /json/2/<modelo>/<método>."""
    respuesta = requests.post(f"{URL}/json/2/{modelo}/{metodo}",
                              headers=HEADERS, json=parametros, timeout=60)
    if not respuesta.ok:
        raise RuntimeError(f"{modelo}.{metodo} falló ({respuesta.status_code}): {respuesta.text[:500]}")
    return respuesta.json()


# Datos de referencia que se leen una sola vez
CLIENTES = llamar("res.partner", "search_read",
                  domain=[["customer_rank", ">", 0]], fields=["id"], order="id asc")
PROVEEDORES = llamar("res.partner", "search_read",
                     domain=[["supplier_rank", ">", 0]], fields=["id"], order="id asc")
PRODUCTOS = llamar("product.product", "search_read",
                   domain=[["sale_ok", "=", True], ["type", "=", "consu"]],
                   fields=["id"], order="id asc")
ALMACENES = llamar("stock.warehouse", "search_read",
                   domain=[], fields=["id", "code", "in_type_id"], order="id asc")
ALMACEN_CENTRAL = next(a["id"] for a in ALMACENES if a["code"] == "CEN")


def fechar_movimientos(pickings, fecha):
    """Pone la fecha indicada a una recepción o entrega ya validada y a sus movimientos."""
    texto = fecha.strftime("%Y-%m-%d %H:%M:%S")
    llamar("stock.picking", "write", ids=pickings,
           vals={"date_done": texto, "scheduled_date": texto})
    movimientos = [m for p in llamar("stock.picking", "read", ids=pickings, fields=["move_ids"])
                   for m in p["move_ids"]]
    llamar("stock.move", "write", ids=movimientos, vals={"date": texto})
    lineas = [l for m in llamar("stock.move", "read", ids=movimientos, fields=["move_line_ids"])
              for l in m["move_line_ids"]]
    llamar("stock.move.line", "write", ids=lineas, vals={"date": texto})


def crear_venta(referencia, fecha):
    """Crea y confirma una venta; si la referencia ya existe, no hace nada (idempotencia)."""
    existentes = llamar("sale.order", "search", domain=[["client_order_ref", "=", referencia]])
    if existentes:
        print(f"{referencia}: ya existe, se omite")
        return existentes[0]

    productos = random.sample(PRODUCTOS, random.randint(1, 4))
    lineas = [[0, 0, {"product_id": p["id"], "product_uom_qty": random.randint(1, 5)}]
              for p in productos]
    ids = llamar("sale.order", "create", vals_list=[{
        "partner_id": random.choice(CLIENTES)["id"],
        "client_order_ref": referencia,
        "warehouse_id": ALMACEN_CENTRAL,
        "order_line": lineas,
    }])
    llamar("sale.order", "action_confirm", ids=ids)
    llamar("sale.order", "write", ids=ids,
           vals={"date_order": fecha.strftime("%Y-%m-%d %H:%M:%S")})
    print(f"{referencia}: creado con id {ids[0]}")
    return ids[0]


def facturar_venta(venta_id, fecha):
    """Factura una venta confirmada y publica la factura con la fecha indicada."""
    venta = llamar("sale.order", "read", ids=[venta_id], fields=["name", "invoice_ids"])[0]
    if venta["invoice_ids"]:
        print(f"{venta['name']}: ya está facturada, se omite")
        return venta["invoice_ids"]

    asistente = llamar("sale.advance.payment.inv", "create", vals_list=[{
        "advance_payment_method": "delivered",
        "sale_order_ids": [[6, 0, [venta_id]]],
    }])
    llamar("sale.advance.payment.inv", "create_invoices", ids=asistente)
    facturas = llamar("sale.order", "read", ids=[venta_id], fields=["invoice_ids"])[0]["invoice_ids"]
    llamar("account.move", "write", ids=facturas, vals={"invoice_date": fecha.strftime("%Y-%m-%d")})
    llamar("account.move", "action_post", ids=facturas)
    print(f"{venta['name']}: facturada")
    return facturas

def entregar_venta(venta_id, fecha):
    """Reserva stock y valida la entrega de una venta; si no hay stock suficiente, la deja pendiente."""
    venta = llamar("sale.order", "read", ids=[venta_id], fields=["name", "picking_ids"])[0]
    pendientes = [p["id"] for p in llamar("stock.picking", "read", ids=venta["picking_ids"],
                                          fields=["state"]) if p["state"] not in ("done", "cancel")]
    if not pendientes:
        print(f"{venta['name']}: ya está entregada, se omite")
        return

    llamar("stock.picking", "action_assign", ids=pendientes)  # botón "Comprobar disponibilidad"
    for entrega in llamar("stock.picking", "read", ids=pendientes, fields=["name", "state"]):
        if entrega["state"] != "assigned":
            print(f"{venta['name']}: {entrega['name']} sin stock suficiente, queda pendiente")
            continue
        resultado = llamar("stock.picking", "button_validate", ids=[entrega["id"]])
        if resultado is not True:
            print(f"{venta['name']}: {entrega['name']} pidió confirmación extra: {resultado}")
            continue
        fechar_movimientos([entrega["id"]], fecha)
        print(f"{venta['name']}: {entrega['name']} entregada")

def crear_compra(referencia, fecha, almacen):
    """Crea, confirma y recibe una compra en el almacén indicado, con la fecha indicada."""
    existentes = llamar("purchase.order", "search", domain=[["partner_ref", "=", referencia]])
    if existentes:
        print(f"{referencia}: ya existe, se omite")
        return existentes[0]

    productos = random.sample(PRODUCTOS, random.randint(3, 6))
    lineas = [[0, 0, {"product_id": p["id"], "product_qty": random.randint(20, 60)}]
              for p in productos]
    ids = llamar("purchase.order", "create", vals_list=[{
        "partner_id": random.choice(PROVEEDORES)["id"],
        "partner_ref": referencia,
        "picking_type_id": almacen["in_type_id"][0],
        "order_line": lineas,
    }])
    llamar("purchase.order", "button_confirm", ids=ids)
    texto_fecha = fecha.strftime("%Y-%m-%d %H:%M:%S")
    llamar("purchase.order", "write", ids=ids,
           vals={"date_order": texto_fecha, "date_approve": texto_fecha})

    recepciones = llamar("purchase.order", "read", ids=ids, fields=["picking_ids"])[0]["picking_ids"]
    resultado = llamar("stock.picking", "button_validate", ids=recepciones)
    if resultado is not True:
        print(f"{referencia}: la recepción pidió confirmación extra: {resultado}")
    fechar_movimientos(recepciones, fecha)  # NUEVO: la recepción toma la fecha de la compra
    print(f"{referencia}: compra creada y recibida en {almacen['code']}")
    return ids[0]


if __name__ == "__main__":
    venta = llamar("sale.order", "search", domain=[["client_order_ref", "=", "SEED-TEST-0001"]])[0]
    entregar_venta(venta, datetime(2026, 8, 16, 15, 0))