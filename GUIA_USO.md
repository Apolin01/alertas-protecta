# Sistema Alertas Protecta — Guía de Uso

**Última actualización:** 24 de Mayo, 2026

---

## Requisitos Previos

| Componente | Versión mínima | Uso |
|------------|---------------|-----|
| Python | 3.11+ | Sistema principal |
| Node.js | 18+ | WhatsApp bridge |
| PostgreSQL | 14+ | Deduplicación y cola (Neon, Railway, o local) |

**Instalar dependencias:**
```bash
# Python
pip install -r requirements.txt

# Node.js (solo primera vez)
cd whatsapp_bridge
npm install
cd ..
```

---

## Ejecución

### Opción 1: Automática (Windows — RECOMENDADO)

```bash
run_system.bat
```

Abre dos ventanas automáticamente:
- **Ventana 1**: WhatsApp Bridge (Node.js)
- **Ventana 2**: Sistema de Alertas (Python)

### Opción 2: Manual (dos terminales)

**Terminal 1 — Bridge de WhatsApp:**
```bash
cd whatsapp_bridge
node server.js
```
Espera hasta ver:
```
✓ WhatsApp Bridge escuchando en puerto 3000
```

**Terminal 2 — Sistema de Alertas:**
```bash
python main.py
```

### Opción 3: Solo simulación (sin bridge)

```bash
# En .env o config.py:
WHATSAPP_PROVIDER=simulate

python main.py
```

Los mensajes se muestran en los logs pero no se envían a WhatsApp.

---

## Configuración Principal

### Cambiar modo WhatsApp

En `.env`:
```
WHATSAPP_PROVIDER=simulate   # Solo logs
WHATSAPP_PROVIDER=bridge     # Envío real (requiere bridge corriendo)
```

### Cambiar frecuencia de polling

En `config.py`:
```python
INTERVAL_MINUTES = 5   # Cada 5 minutos procesa todos los bundles
```

### Agregar o quitar bundles RSS

En `config.py`:
```python
RSS_BUNDLES = {
    "Antamina":                     "_vv3HkItEzKqytLHk",
    "Bechtel / Newmont":            "_dtKCh5CjRws0ai8H",
    # Agregar nuevo cliente:
    "Nueva Empresa":                "_nuevo_bundle_id",
}
```

### Ajustar agresividad de deduplicación

En `deduplicator.py`:
```python
JACCARD_THRESHOLD_TITULO = 0.35    # Bajar = más agresivo (menos duplicados escapan)
DEDUP_WINDOW_HOURS = 24            # Horas que considera como "reciente"
DEDUP_SAME_LOCATION_HOURS = 0.25   # 15 min: mismo lugar+subcategoria = duplicado
```

---

## Flujo de Datos

```
RSS Feed API (rss.app)
    ↓  Últimas 2h, máx 50 items
RSSFetcher
    ↓  Posts normalizados
Deduplicator.already_processed()  — Descarta URLs ya vistas
    ↓  Posts nuevos
Classifier (OpenAI)
    ↓  alert dict con nivel, cliente, ubicación
Deduplicator.is_duplicate_alert()  — 7 niveles de dedup
    ↓  Alertas únicas
Formatter
    ↓  Mensaje WhatsApp + fila Sheets
Router
    ↓  Grupos destino
AlertQueue (PostgreSQL)
    ↓  Encolado
WhatsAppBridge (node server.js)
    ↓
Grupos WhatsApp reales
```

---

## Troubleshooting

### "No se puede conectar al bridge"

1. Verificar que `node server.js` esté corriendo en Terminal 1
2. Comprobar que el puerto 3000 esté libre:
   ```bash
   netstat -ano | findstr :3000
   ```
3. Si WhatsApp desconectó, re-escanear el QR al reiniciar el bridge

### "OPENAI_API_KEY no está configurada"

Agregar al `.env`:
```
OPENAI_API_KEY=sk-...tu-key-aqui...
```

### "DATABASE_URL no está configurado"

Agregar al `.env`:
```
DATABASE_URL=postgresql://user:pass@host/db
```

### "RSS_API_KEY o RSS_API_SECRET faltan"

Agregar al `.env`:
```
RSS_API_KEY=tu_key_de_rss_app
RSS_API_SECRET=tu_secret_de_rss_app
```

### Las noticias no tienen imagen

Es normal cuando el post de Facebook no incluye imagen. El bridge envía solo texto en ese caso. No es un error.

### El sistema envía duplicados

```bash
# Ver qué nivel de dedup está activo:
grep -i "NIVEL\|DUPLICADO" alertas.log | tail -50

# Ajustar umbral en deduplicator.py:
JACCARD_THRESHOLD_TITULO = 0.30   # Más agresivo
```

### El sistema se detiene después de un ciclo

`main.py` está diseñado para correr continuamente. Si se detiene:
1. Revisar el final de `alertas.log` para ver el error
2. Verificar conexión a PostgreSQL y a rss.app
3. Ejecutar `python main.py` nuevamente

---

## Estructura de Archivos

```
alertas-protecta/
├── run_system.bat              ← Ejecutar todo (RECOMENDADO, Windows)
├── run_system.ps1              ← Alternativa PowerShell
├── main.py                     ← Orquestador principal
├── config.py                   ← Configuración (bundles, clientes, mapeos)
├── rss_fetcher.py              ← Extrae noticias de rss.app
├── classifier.py               ← Clasificación con OpenAI
├── deduplicator.py             ← Evita duplicados (7 niveles, PostgreSQL)
├── formatter.py                ← Formato WhatsApp y Sheets
├── router.py                   ← Routing cliente → grupo WA
├── sender_whatsapp.py          ← Envío real o simulado
├── sender_sheets.py            ← Google Sheets logging
├── alert_queue.py              ← Cola persistente (PostgreSQL)
├── webhook_handler.py          ← Procesa webhooks de rss.app
├── webhook_server.py           ← Flask server (puerto 5000)
├── .env                        ← Claves secretas (NO commitear)
├── .env.example                ← Plantilla
├── requirements.txt
├── whatsapp_bridge/
│   ├── server.js               ← Bridge Node.js WhatsApp
│   └── package.json
└── prompts/
    └── classifier_prompt.md    ← Prompt del clasificador (editable)
```

---

## Casos de Uso

### Producción continua
```bash
run_system.bat
# El sistema procesa cada 5 minutos indefinidamente
```

### Testing sin WhatsApp (ver clasificación)
```bash
# .env: WHATSAPP_PROVIDER=simulate
python main.py
# Ver resultado en alertas.log o consola
```

### Producción en Linux (24/7)
```bash
nohup python main.py >> alertas.log 2>&1 &
# O mejor: configurar como servicio systemd (ver FLUJO_SISTEMA.md)
```

---

## Seguridad

**NUNCA publicar en git:**
- `.env` (contiene todas las claves)
- `credentials.json` (Google Service Account)
- `fb_session/` (cookies WhatsApp)
- `alertas.log` (puede contener datos de alertas)

El `.gitignore` ya excluye estos archivos. Verificar con:
```bash
git status --short
# No debe mostrar .env ni credentials.json
```

**Si una clave se filtró:**
1. Rotar la clave en la plataforma correspondiente (OpenAI, rss.app, etc.)
2. Actualizar `.env` con la nueva clave
3. Si se commiteó en git: purgar el historial con `git filter-branch` o `bfg-repo-cleaner`

---

## Soporte

Si algo no funciona:
1. Revisar `alertas.log` para el error exacto
2. Verificar que todas las dependencias estén instaladas (`pip install -r requirements.txt`)
3. Confirmar que las APIs estén disponibles (rss.app, OpenAI)
4. Revisar [FLUJO_SISTEMA.md](FLUJO_SISTEMA.md) para la tabla de resolución de problemas
