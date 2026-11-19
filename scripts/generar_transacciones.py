"""Genera seis meses de transacciones ficticias en Odoo a través de la API JSON-2."""
import os
import sys
import random
from datetime import datetime, timedelta

import requests
from dotenv import load_dotenv

load_dotenv()
URL = os.environ["ODOO_URL"]
HEADERS = {
    "Authorization": f"bearer {os.environ['ODOO_API_KEY']}",
    "X-Odoo-Database": os.environ["ODOO_DB"],
}

VENTAS_POR_MES = {6: 15, 7: 18, 8: 20, 9: 22, 10: 25, 11: 14}  # tendencia creciente
COMPRAS_POR_MES = 5
HOY = datetime(2026, 11, 18, 12, 0)  # ninguna fecha generada puede pasar de aquí


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


def crear_compra(referencia, fecha, almacen):
    """Crea, confirma y recibe una compra en el almacén indicado, con la fecha indicada."""
    existentes = llamar("purchase.order", "search", domain=[["partner_ref", "=", referencia]])
    if existentes:
        print(f"{referencia}: ya existe, se omite")
        return existentes[0]

    azar = random.Random(referencia)  # el mismo pedido sale igual en cada ejecución
    productos = azar.sample(PRODUCTOS, azar.randint(3, 6))
    lineas = [[0, 0, {"product_id": p["id"], "product_qty": azar.randint(20, 60)}]
              for p in productos]
    ids = llamar("purchase.order", "create", vals_list=[{
        "partner_id": azar.choice(PROVEEDORES)["id"],
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
    fechar_movimientos(recepciones, fecha)
    print(f"{referencia}: compra recibida en {almacen['code']} ({fecha:%Y-%m-%d})")
    return ids[0]


def crear_venta(referencia, fecha, almacen):
    """Crea y confirma una venta desde el almacén indicado; si ya existe, no hace nada."""
    existentes = llamar("sale.order", "search", domain=[["client_order_ref", "=", referencia]])
    if existentes:
        print(f"{referencia}: ya existe, se omite")
        return existentes[0]

    azar = random.Random(referencia)
    productos = azar.sample(PRODUCTOS, azar.randint(1, 4))
    lineas = [[0, 0, {"product_id": p["id"], "product_uom_qty": azar.randint(1, 5)}]
              for p in productos]
    ids = llamar("sale.order", "create", vals_list=[{
        "partner_id": azar.choice(CLIENTES)["id"],
        "client_order_ref": referencia,
        "warehouse_id": almacen["id"],
        "order_line": lineas,
    }])
    llamar("sale.order", "action_confirm", ids=ids)
    llamar("sale.order", "write", ids=ids,
           vals={"date_order": fecha.strftime("%Y-%m-%d %H:%M:%S")})
    print(f"{referencia}: venta desde {almacen['code']} ({fecha:%Y-%m-%d})")
    return ids[0]


def entregar_venta(venta_id, fecha):
    """Reserva stock y valida la entrega; si no hay stock suficiente, la deja pendiente."""
    venta = llamar("sale.order", "read", ids=[venta_id], fields=["name", "picking_ids"])[0]
    pendientes = [p["id"] for p in llamar("stock.picking", "read", ids=venta["picking_ids"],
                                          fields=["state"]) if p["state"] not in ("done", "cancel")]
    if not pendientes:
        return
    llamar("stock.picking", "action_assign", ids=pendientes)
    for entrega in llamar("stock.picking", "read", ids=pendientes, fields=["name", "state"]):
        if entrega["state"] != "assigned":
            print(f"  {entrega['name']}: sin stock suficiente, queda pendiente")
            continue
        resultado = llamar("stock.picking", "button_validate", ids=[entrega["id"]])
        if resultado is not True:
            print(f"  {entrega['name']}: pidió confirmación extra: {resultado}")
            continue
        fechar_movimientos([entrega["id"]], fecha)


def facturar_venta(venta_id, fecha):
    """Factura una venta confirmada y publica la factura con la fecha indicada."""
    venta = llamar("sale.order", "read", ids=[venta_id], fields=["name", "invoice_ids"])[0]
    if venta["invoice_ids"]:
        return venta["invoice_ids"]
    asistente = llamar("sale.advance.payment.inv", "create", vals_list=[{
        "advance_payment_method": "delivered",
        "sale_order_ids": [[6, 0, [venta_id]]],
    }])
    llamar("sale.advance.payment.inv", "create_invoices", ids=asistente)
    facturas = llamar("sale.order", "read", ids=[venta_id], fields=["invoice_ids"])[0]["invoice_ids"]
    llamar("account.move", "write", ids=facturas, vals={"invoice_date": fecha.strftime("%Y-%m-%d")})
    llamar("account.move", "action_post", ids=facturas)
    return facturas

def procesar_entregas_parciales():
    """Entrega lo disponible en las entregas que quedaron a medias y deja el resto en un backorder."""
    entregas = llamar("stock.picking", "search_read",
                      domain=[["picking_type_code", "=", "outgoing"],
                              ["state", "=", "assigned"],
                              ["sale_id.client_order_ref", "like", "SEED-%"]],
                      fields=["id", "name", "sale_id"], order="id asc")
    print(f"Entregas parciales por procesar: {len(entregas)}")
    for entrega in entregas:
        venta = llamar("sale.order", "read", ids=[entrega["sale_id"][0]], fields=["date_order"])[0]
        fecha = min(datetime.strptime(venta["date_order"], "%Y-%m-%d %H:%M:%S") + timedelta(days=1), HOY)

        resultado = llamar("stock.picking", "button_validate", ids=[entrega["id"]])
        if resultado is not True:
            # Odoo pregunta "¿Crear orden parcial?": respondemos que sí, igual que en pantalla
            contexto = resultado["context"]
            asistente = llamar("stock.backorder.confirmation", "create", vals_list=[{}], context=contexto)
            llamar("stock.backorder.confirmation", "process", ids=asistente, context=contexto)
        fechar_movimientos([entrega["id"]], fecha)
        print(f"{entrega['name']}: entregado lo disponible; el resto queda en backorder")

def planificar():
    """Arma la lista de eventos (compras y ventas) de junio a noviembre, ordenada por fecha."""
    azar = random.Random(2026)
    eventos = []
    n_compra = n_venta = 0
    for mes, n_ventas in VENTAS_POR_MES.items():
        ultimo_dia = 17 if mes == 11 else 28
        for i in range(COMPRAS_POR_MES):
            n_compra += 1
            fecha = datetime(2026, mes, azar.randint(1, 5), azar.randint(13, 21), azar.randint(0, 59))
            eventos.append((fecha, "compra", f"SEED-C-{n_compra:04d}", ALMACENES[i % len(ALMACENES)]))
        for _ in range(n_ventas):
            n_venta += 1
            fecha = datetime(2026, mes, azar.randint(6, ultimo_dia), azar.randint(13, 21), azar.randint(0, 59))
            eventos.append((fecha, "venta", f"SEED-V-{n_venta:04d}", azar.choice(ALMACENES)))
    eventos.sort(key=lambda evento: evento[0])  # orden cronológico: el stock llega antes de venderse
    return eventos


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "parciales":
        procesar_entregas_parciales()
    else:
        for fecha, tipo, referencia, almacen in planificar():
            if tipo == "compra":
                crear_compra(referencia, fecha, almacen)
            else:
                venta = crear_venta(referencia, fecha, almacen)
                entregar_venta(venta, min(fecha + timedelta(days=1), HOY))
                facturar_venta(venta, min(fecha + timedelta(days=random.Random(referencia).randint(0, 2)), HOY))
        print("Generación terminada")