"""
inject_cache.py — Copia el cache de grupos del bridge local → Railway.

Uso:
  1. Asegúrate de que el bridge local esté corriendo: node server.js
  2. Ejecuta: python inject_cache.py
"""

import sys
import json
import requests

LOCAL_URL   = "http://localhost:3000"
RAILWAY_URL = "https://wa-bridge-production-2c52.up.railway.app"
TOKEN       = "protecta2026"
HEADERS     = {"x-auth-token": TOKEN}

print("=" * 55)
print("Inyector de cache de grupos — Protecta Perú")
print("=" * 55)

# 1. Obtener grupos del bridge local
print(f"\n[1] Obteniendo grupos de {LOCAL_URL}/groups ...")
try:
    r = requests.get(f"{LOCAL_URL}/groups", headers=HEADERS, timeout=15)
    r.raise_for_status()
    data = r.json()
except Exception as e:
    print(f"    ERROR: No se pudo conectar al bridge local: {e}")
    print("    Asegúrate de que 'node server.js' esté corriendo localmente.")
    sys.exit(1)

groups = data.get("all_groups", {})
if not groups:
    print("    ERROR: El bridge local no tiene grupos en cache.")
    print("    Asegúrate de que el bridge local haya cargado los grupos primero.")
    sys.exit(1)

print(f"    ✅ {len(groups)} grupos obtenidos:")
for name in groups:
    print(f"       • {name}")

# 2. Enviar a Railway
print(f"\n[2] Enviando cache a Railway ({RAILWAY_URL}/set-cache) ...")
try:
    r = requests.post(
        f"{RAILWAY_URL}/set-cache",
        headers={**HEADERS, "Content-Type": "application/json"},
        json={"groups": groups},
        timeout=15
    )
    r.raise_for_status()
    result = r.json()
    print(f"    ✅ Cache inyectado. Total en Railway: {result.get('total', '?')} grupos")
except Exception as e:
    print(f"    ERROR al enviar a Railway: {e}")
    sys.exit(1)

# 3. Verificar estado en Railway
print(f"\n[3] Verificando estado en Railway ...")
try:
    r = requests.get(f"{RAILWAY_URL}/status", timeout=10)
    s = r.json()
    print(f"    WhatsApp listo : {s.get('ready')}")
    print(f"    Grupos en cache: {s.get('groups_cached')}")
except Exception as e:
    print(f"    No se pudo verificar: {e}")

print("\n✅ Listo. Railway puede enviar mensajes ahora.")
