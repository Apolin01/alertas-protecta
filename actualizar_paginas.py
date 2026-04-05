"""
actualizar_paginas.py — Lee el Excel de la matriz y actualiza FACEBOOK_PAGES en config.py.

Uso:
  python actualizar_paginas.py                          # usa BD_Matriz.xlsx del mismo directorio
  python actualizar_paginas.py "ruta/al/archivo.xlsx"  # ruta personalizada

Cada vez que agregues paginas al Excel, corre este script
y el config.py se actualiza automaticamente.
"""

import sys
import io
import re
import os
import openpyxl

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ─────────────────────────────────────────────
# CONFIGURACION
# ─────────────────────────────────────────────
CONFIG_FILE  = "config.py"
EXCEL_FILE   = sys.argv[1] if len(sys.argv) > 1 else None

# Buscar el Excel automaticamente si no se especifica
if not EXCEL_FILE:
    for f in os.listdir("."):
        if f.endswith(".xlsx") and "matriz" in f.lower():
            EXCEL_FILE = f
            break

if not EXCEL_FILE or not os.path.exists(EXCEL_FILE):
    print("ERROR: No se encontro el archivo Excel.")
    print("Uso: python actualizar_paginas.py 'BD_Matriz.xlsx'")
    sys.exit(1)

print(f"Leyendo: {EXCEL_FILE}")

# Mapeo pestana → cliente
TAB_TO_CLIENT = {
    "MINERIA ANCASH":                    "Antamina",
    "MINERIA CAJAMARCA":                 "Bechtel / Newmont",
    "AGRO SUR":                          "Clientes Sur",
    "AGRO NORTE":                        "Agro Norte",
    "AGRO NORTE-AGRICOLA SANTA AZUL":    "Agricola Santa Azul",
    "AGRO PISCO":                        "Pisco",
    "POLÍTICA":                          "Coyuntura Nacional",
}

STATUS_COL = {
    "MINERIA ANCASH": 10,
    "AGRO NORTE":     9,
}
DEFAULT_STATUS_COL = 9


def extract_page_id(url):
    if not url or not isinstance(url, str):
        return None
    url = url.strip().rstrip("/")
    if "/search/posts" in url or "q=" in url:
        return None
    m = re.search(r'profile\.php\?id=(\d+)', url)
    if m:
        return m.group(1)
    m = re.search(r'facebook\.com/([^/?#\s]+)', url)
    if m:
        slug = m.group(1)
        if slug not in ('home', 'groups', 'pages', 'events', 'hashtag', 'search'):
            return slug
    return None


# ─────────────────────────────────────────────
# LEER EXCEL
# ─────────────────────────────────────────────
wb = openpyxl.load_workbook(EXCEL_FILE, data_only=True)
results = {}
total   = 0

for sheet_name, client in TAB_TO_CLIENT.items():
    if sheet_name not in wb.sheetnames:
        print(f"  [SKIP] Pestana no encontrada: {sheet_name}")
        continue

    ws         = wb[sheet_name]
    sc         = STATUS_COL.get(sheet_name, DEFAULT_STATUS_COL)
    pages      = []
    seen       = set()

    for row in ws.iter_rows(min_row=6, values_only=True):
        nombre = row[3] if len(row) > 3 else None
        rrss   = row[5] if len(row) > 5 else None
        enlace = row[8] if len(row) > 8 else None
        estado = row[sc] if len(row) > sc else None

        if not nombre:
            continue
        if str(rrss or "").upper() != "FACEBOOK":
            continue
        if str(estado or "").strip().upper() != "ACTIVO":
            continue

        page_id = extract_page_id(str(enlace) if enlace else "")
        if not page_id:
            continue

        key = f"{client}:{page_id}"
        if key in seen:
            continue
        seen.add(key)

        pages.append({"nombre": str(nombre).strip(), "page_id": page_id})

    results[client] = pages
    total += len(pages)
    print(f"  {sheet_name}: {len(pages)} paginas ACTIVAS")

print(f"\nTotal: {total} paginas")

# ─────────────────────────────────────────────
# GENERAR BLOQUE FACEBOOK_PAGES
# ─────────────────────────────────────────────
lines = ["    FACEBOOK_PAGES = ["]
for client, pages in results.items():
    lines.append(f"\n        # ── {client} ({len(pages)} paginas) ──")
    for p in pages:
        nombre_clean = p['nombre'].replace("'", "").replace('"', '')
        lines.append(f'        "{p["page_id"]}",  # {nombre_clean}')
lines.append("    ]")

new_block = "\n".join(lines)

# ─────────────────────────────────────────────
# ACTUALIZAR config.py
# ─────────────────────────────────────────────
with open(CONFIG_FILE, "r", encoding="utf-8") as f:
    content = f.read()

old_block = re.search(
    r'    FACEBOOK_PAGES = \[.*?\]',
    content,
    re.DOTALL
)

if not old_block:
    print("ERROR: No se encontro FACEBOOK_PAGES en config.py")
    sys.exit(1)

content = content[:old_block.start()] + new_block + content[old_block.end():]

with open(CONFIG_FILE, "w", encoding="utf-8") as f:
    f.write(content)

print(f"\nconfig.py actualizado con {total} paginas.")
print("Reinicia el programa para aplicar los cambios.")