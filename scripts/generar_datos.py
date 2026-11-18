"""Genera los datos maestros ficticios del laboratorio en CSV para importarlos en Odoo."""
import csv
import random
from pathlib import Path

random.seed(42)  # misma semilla = mismos datos en cada ejecución
SALIDA = Path(__file__).resolve().parent.parent / "data" / "seed"
SALIDA.mkdir(parents=True, exist_ok=True)

CIUDADES = ["Panamá", "San Miguelito", "La Chorrera", "Colón", "David", "Santiago", "Chitré"]

PROVEEDORES = [
    "Distribuidora Istmo, S.A.", "Importadora del Canal, S.A.", "Suministros Chiriquí, S.A.",
    "Comercial Azuero, S.A.", "Tecnología Pacífico, S.A.", "Papelera Central, S.A.",
    "Químicos del Atlántico, S.A.", "Alimentos Bocas, S.A.", "Ferretera Veraguas, S.A.",
    "Logística Darién, S.A.",
]
CLIENTES_EMPRESA = [
    "Supermercado La Esquina", "Farmacia Bienestar", "Hotel Bahía Azul", "Colegio San Marcos",
    "Clínica Santa Fe", "Restaurante El Fogón", "Constructora Horizonte", "Oficinas Punta Pacífica",
    "Minisuper Don Pepe", "Gimnasio Fuerza Total", "Cafetería Aroma", "Taller Mecánico Rápido",
]
CLIENTES_PERSONA = [
    "Ana Castillo", "Luis Herrera", "María Pinzón", "Carlos Batista",
    "Sofía Méndez", "Jorge Quintero", "Valeria Rodríguez", "Diego Samudio",
]

CATEGORIAS = {
    "Electrónica": ["Mouse inalámbrico", "Teclado USB", "Audífonos", "Cargador USB-C", "Cable HDMI",
                    "Memoria USB 64 GB", "Router Wi-Fi", "Webcam HD", "Parlante Bluetooth", "Batería externa"],
    "Oficina": ["Resma de papel carta", "Bolígrafos azules (caja)", "Folder manila (paquete)", "Grapadora",
                "Cinta adhesiva", "Marcadores de pizarra", "Libreta rayada", "Calculadora", "Archivador", "Post-it"],
    "Limpieza": ["Detergente líquido", "Cloro (galón)", "Desinfectante", "Papel toalla", "Papel higiénico (paquete)",
                 "Escoba", "Trapeador", "Bolsas de basura", "Jabón de manos", "Guantes de limpieza"],
    "Alimentos": ["Café molido", "Azúcar (2 kg)", "Arroz (5 lb)", "Aceite vegetal", "Agua embotellada (paquete)",
                  "Galletas surtidas", "Leche en polvo", "Atún enlatado", "Pasta", "Té en bolsitas"],
    "Ferretería": ["Martillo", "Destornillador", "Cinta métrica", "Tornillos (caja)", "Taladro",
                   "Pintura blanca (galón)", "Brocha", "Candado", "Extensión eléctrica", "Bombillo LED"],
}


def telefono():
    return f"+507 6{random.randint(100, 999)}-{random.randint(1000, 9999)}"


def correo(nombre):
    base = "".join(c for c in nombre.lower() if c.isalnum())[:20]
    return f"{base}@ejemplo.com"


# 1. Contactos: proveedores y clientes en un solo archivo (en Odoo comparten la tabla res_partner)
with open(SALIDA / "contactos.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["name", "is_company", "email", "phone", "city", "country_id/id",
                "customer_rank", "supplier_rank"])
    for nombre in PROVEEDORES:
        w.writerow([nombre, True, correo(nombre), telefono(), random.choice(CIUDADES), "base.pa", 0, 1])
    for nombre in CLIENTES_EMPRESA:
        w.writerow([nombre, True, correo(nombre), telefono(), random.choice(CIUDADES), "base.pa", 1, 0])
    for nombre in CLIENTES_PERSONA:
        w.writerow([nombre, False, correo(nombre), telefono(), random.choice(CIUDADES), "base.pa", 1, 0])

# 2. Categorías de producto
with open(SALIDA / "categorias.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["name"])
    for categoria in CATEGORIAS:
        w.writerow([categoria])

# 3. Productos: 10 por categoría, con costo y precio de venta con margen de 25 % a 60 %
with open(SALIDA / "productos.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["default_code", "name", "categ_id", "type", "is_storable",
                "standard_price", "list_price"])
    n = 1
    for categoria, productos in CATEGORIAS.items():
        for nombre in productos:
            costo = round(random.uniform(1.5, 80), 2)
            precio = round(costo * random.uniform(1.25, 1.60), 2)
            w.writerow([f"P{n:03d}", nombre, categoria, "consu", True, costo, precio])
            n += 1

print(f"Archivos generados en {SALIDA}")