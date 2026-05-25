# Sistema de Alertas — Protecta Perú

Sistema automatizado que monitorea noticias vía **webhooks en tiempo real** y **polling RSS**, clasifica con IA, deduplica inteligentemente y envía alertas a WhatsApp por cliente/región. Registra todo en Google Sheets.

**Versión:** 2.1  
**Última actualización:** 24 de Mayo, 2026  
**Estado:** Producción

---

## Características Principales

- **Webhooks en Tiempo Real** — Notificaciones inmediatas desde rss.app (< 1 segundo de latencia)
- **Polling RSS Fallback** — Consulta cada 5 minutos como respaldo
- **Deduplicación 7 Niveles** — URL exacta, content hash, firma de evento, Jaccard título, Levenshtein, Jaccard descripción, IA semántica
- **Clasificación IA** — OpenAI GPT-4o-mini (proveedor activo)
- **Multi-Cliente** — 6 bundles RSS configurados (Antamina, Bechtel/Newmont, Clientes Sur, Clientes Norte, Pisco, Coyuntura Nacional)
- **Integración WhatsApp** — Bridge Node.js local (whatsapp-web.js)
- **Google Sheets** — Registro histórico de todas las alertas
- **PostgreSQL** — BD persistente para deduplicación avanzada y cola de alertas

---

## Flujo del Sistema

```
┌─ Webhooks (tiempo real)    ┐
│   rss.app → /webhook       │
│   Buffer: 500 items        │
└────────────────────────────┘
           │
           ▼
┌─ Polling RSS (cada 5 min)  ┐
│   RSSFetcher por cliente   │
└────────────────────────────┘
           │
           ▼
    ┌──────────────────┐
    │ DEDUPLICADOR     │  7 niveles
    ├──────────────────┤  (URL, hash, firma,
    │ 0. URL exacta    │   Jaccard título,
    │ 0.5 Content hash │   Levenshtein,
    │ 1. Firma evento  │   Jaccard desc,
    │ 2.5 Lugar+Subcat │   IA semántica)
    │ 3. Hash título   │
    │ 4. Jaccard/Leven │
    │ 5. Jaccard desc  │
    │ 6. IA semántica  │
    └────────┬─────────┘
             │
             ▼
      ┌─────────────────┐
      │ CLASIFICADOR    │
      │ (OpenAI)        │
      │ - Nivel         │
      │ - Cliente       │
      │ - Ubicación     │
      │ - 3 Keywords    │
      └────────┬────────┘
             │
             ▼
      ┌─────────────────┐
      │ FORMATEADOR     │
      │ Título +        │
      │ Resumen breve   │
      │ Emoji + Fecha   │
      └────────┬────────┘
             │
        ┌────┴────┐
        ▼         ▼
    WhatsApp  Google Sheets
    (directo) (histórico)
```

---

## Niveles de Alerta

| Nivel | Emoji | Criterio |
|-------|-------|----------|
| **CRIT** | 🔴 | Homicidios, balaceras, derrames, bloqueos operacionales, minería ilegal |
| **ALRT** | 🟡 | Accidentes viales, huaicos, huelgas, robos, incendios, protestas |
| **INFO** | 🟢 | Inversiones, obras, acuerdos, reuniones, producción positiva |
| **IGNORAR** | — | Deportes, farándula, sin ubicación clara, fuera de zonas operativas |

---

## Estructura de Archivos

```
alertas-protecta/
│
├── CORE
│   ├── main.py                 # Orquestador + scheduler
│   ├── config.py               # Configuración central
│   ├── classifier.py           # Clasificación IA (OpenAI)
│   ├── formatter.py            # Formato WhatsApp / Sheets
│   ├── deduplicator.py         # Dedup 7 niveles (PostgreSQL)
│   ├── router.py               # Routing cliente → grupo
│   │
│   ├── FUENTES
│   │   ├── rss_fetcher.py      # RSS polling (rss.app)
│   │   ├── webhook_handler.py  # Procesa webhooks entrantes
│   │   └── webhook_server.py   # Flask server (puerto 5000)
│   │
│   └── ENVÍO
│       ├── sender_whatsapp.py  # WhatsApp bridge sender
│       ├── sender_sheets.py    # Google Sheets logging
│       └── alert_queue.py      # Cola persistente (PostgreSQL)
│
├── CONFIGURACIÓN
│   ├── .env                    # Variables de entorno (no commitear)
│   ├── .env.example            # Plantilla para .env
│   ├── requirements.txt        # Dependencias Python
│   ├── Procfile                # Heroku deployment
│   ├── run_system.bat          # Script Windows
│   ├── run_system.ps1          # Script PowerShell
│   │
│   └── whatsapp_bridge/        # Node.js WhatsApp bridge
│       ├── server.js
│       ├── package.json
│       └── Dockerfile
│
├── DOCUMENTACIÓN
│   ├── README.md               # Este archivo
│   ├── ARQUITECTURA.md         # Diseño técnico detallado
│   ├── FLUJO_SISTEMA.md        # Flujo paso a paso
│   ├── GUIA_USO.md             # Guía de operación
│   └── QUICK_START.md          # Inicio rápido
│
└── alertas.log                 # Logs detallados (no commitear)
```

---

## Instalación Rápida

### 1. Requisitos
- Python 3.11+
- PostgreSQL (Neon, Railway, o local)
- Node.js 18+ (para WhatsApp bridge)

### 2. Clonar y Configurar
```bash
git clone https://github.com/bryn14-tech/alertas-rss.git
cd alertas-protecta
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
```

### 3. Configurar `.env`
```bash
# Copiar plantilla
cp .env.example .env

# Editar .env con tus valores reales:
OPENAI_API_KEY=sk-...
DATABASE_URL=postgresql://user:pass@host/db
RSS_API_KEY=...
RSS_API_SECRET=...
BRIDGE_TOKEN=tu_token_secreto
WEBHOOKS_ENABLED=true
WEBHOOK_PORT=5000
```

### 4. Iniciar Sistema
```bash
# Terminal 1: Sistema de alertas Python
python main.py

# Terminal 2: WhatsApp bridge Node.js
cd whatsapp_bridge && npm install && node server.js
```

Resultado esperado:
```
[WEBHOOKS] ✓ Servidor escuchando en 0.0.0.0:5000
CICLO 1 — 24-05-2026 08:00 PE
[RSS] Bundle _vv3HkItEzKqytLHk devolvió 12 items
[Antamina] Clasificando: Incidente en Chaupiloma...
[ENVIO] ✓ Enviado a 'Antamina'
```

---

## Variables de Entorno (`.env`)

| Variable | Requerida | Descripción |
|----------|-----------|-------------|
| `OPENAI_API_KEY` | Sí | Clave para clasificación IA |
| `DATABASE_URL` | Sí | Conexión PostgreSQL |
| `RSS_API_KEY` | Sí | Clave de API rss.app |
| `RSS_API_SECRET` | Sí | Secreto de API rss.app |
| `BRIDGE_TOKEN` | Sí | Token de autenticación del bridge WhatsApp |
| `BRIDGE_URL` | No | URL del bridge (default: `http://localhost:3000`) |
| `WEBHOOKS_ENABLED` | No | Activar servidor webhook (default: `true`) |
| `WEBHOOK_PORT` | No | Puerto del servidor webhook (default: `5000`) |
| `WEBHOOK_SECRET` | No | Secreto HMAC para validar webhooks de rss.app |
| `WHATSAPP_PROVIDER` | No | `bridge` o `simulate` (default: `bridge`) |
| `USE_RSS_FEED` | No | Usar RSS en lugar de scraper (default: `true`) |
| `SHEETS_ENABLED` | No | Activar logging en Google Sheets (default: `false`) |
| `SPREADSHEET_ID` | Si SHEETS_ENABLED | ID del Google Sheets |
| `HEARTBEAT_URL` | No | URL de watchdog externo (UptimeRobot, etc.) |

---

## Configuración Principal (`config.py`)

### Bundles RSS configurados

| Cliente | Bundle ID | Región |
|---------|-----------|--------|
| Antamina | `_vv3HkItEzKqytLHk` | Ancash |
| Bechtel / Newmont | `_dtKCh5CjRws0ai8H` | Cajamarca |
| Clientes Sur | `_vuHd6hNkLlFj0nPK` | Ica, Arequipa |
| Clientes Norte | `_i5tst4lPDJ5oTSW4` | La Libertad |
| Pisco | `_XgBrvIyMIWm5YzLP` | Pisco |
| Ninguno (Coyuntura Nacional) | `_pM02KT2QspbdR8os` | Nacional |

### Ajustes operativos

```python
INTERVAL_MINUTES = 5          # Polling cada 5 minutos
WHATSAPP_PROVIDER = "bridge"  # "bridge" | "simulate"
AI_PROVIDER = "openai"        # Solo "openai" implementado actualmente
```

---

## Ejemplo: De Webhook a WhatsApp

### 1. Webhook llega (rss.app)
```json
{
  "id": "evt_xyz",
  "type": "feed_update",
  "feed": {"id": "_vv3HkItEzKqytLHk"},
  "data": {
    "items_new": [{
      "title": "Incidente en Chaupiloma",
      "description_text": "...",
      "url": "https://..."
    }]
  }
}
```

### 2. Procesamiento
```
webhook_handler.process_webhook()
  → normalizar item
  → mapear bundle → cliente (Antamina)
  → encolar en webhook_queue

main.py ciclo
  → deduplicator.already_processed() → False
  → classifier.classify() → ALRT
  → deduplicator.is_duplicate_alert() → False
  → formatter.format_whatsapp() → mensaje
  → queue.push() → encolado
  → sender_whatsapp.send() → enviado
```

### 3. Mensaje enviado a WhatsApp
```
*ALRT 🟡 24-05-26 ANCASH HUARI SAN MARCOS - SEGURIDAD - DETENCION*
Policía detiene a cinco sujetos involucrados en asaltos a comercios en San Marcos, Ancash.
- FUENTE: https://tinyurl.com/xyz123
```

---

## Clientes Configurados

| Cliente | Grupo WhatsApp | Rubro |
|---------|---------------|-------|
| Antamina | Antamina | Minería |
| Bechtel / Newmont | Bechtel / Newmont | Minería |
| Clientes Sur | Clientes Sur | Agroindustria |
| Clientes Norte | Clientes Norte | Agroindustria |
| Agrícola Santa Azul | Agrícola Santa Azul | Agroindustria |
| Agrícola Huarmey | Clientes Norte | Agroindustria |
| Pisco | Pisco | Pesca |
| Petrotal | Petrotal | Hidrocarburos |
| Ninguno (Coyuntura Nacional) | Coyuntura Nacional | — |

---

## Agregar un Nuevo Cliente

**1.** En `config.py`, agrégalo a `CLIENTES_VALIDOS`:
```python
"Nueva Empresa",
```

**2.** Añadir el bundle RSS en `RSS_BUNDLES`:
```python
"Nueva Empresa": "_bundle_id_de_rss_app",
```

**3.** Mapearlo a un grupo WhatsApp en `CLIENTE_TO_WHATSAPP_GROUP`:
```python
"Nueva Empresa": "Nombre del Grupo WA",
```

**4.** Si tiene rubro distinto a Agroindustria, agrégalo en `CLIENTE_TO_RUBRO`:
```python
"Nueva Empresa": "Minería",
```

---

## Troubleshooting

### "Connection refused :5000"
```bash
# Puerto en uso — cambiar en .env:
WEBHOOK_PORT=5001
```

### "Bundle not found"
```bash
# Verificar que el bundle_id esté en config.py → RSS_BUNDLES
```

### "DATABASE_URL no está configurado"
```bash
# Agregar al .env:
DATABASE_URL=postgresql://user:pass@host/db
```

### Mensajes duplicados en WhatsApp
```bash
# Ver logs de dedup:
tail -f alertas.log | grep Dedup

# Si sigue pasando, ajustar umbrales en deduplicator.py:
JACCARD_THRESHOLD_TITULO = 0.35   # Bajar = más sensible
DEDUP_WINDOW_HOURS = 24           # Subir = ventana más larga
```

### WhatsApp no conectado
```bash
# Verificar que el bridge esté corriendo:
cd whatsapp_bridge && node server.js
# Escanear el QR con WhatsApp si es primera vez
```

---

## Métricas de Rendimiento

| Métrica | Valor |
|---------|-------|
| Latencia webhooks | < 1 segundo |
| Deduplicación | 7 niveles (URL → IA semántica) |
| Ciclo polling | 5 minutos |
| Items por bundle | 50 (últimas 2 horas) |
| Ventana dedup | 24 horas |
| Almacenamiento BD | ~1 KB por alerta |

---

## Documentación Adicional

- [ARQUITECTURA.md](ARQUITECTURA.md) — Diseño técnico por módulo
- [FLUJO_SISTEMA.md](FLUJO_SISTEMA.md) — Flujo detallado paso a paso
- [GUIA_USO.md](GUIA_USO.md) — Operación y casos de uso
- [QUICK_START.md](QUICK_START.md) — Inicio rápido

---

## Changelog

### v2.1 (Mayo 24, 2026)
- Deduplicación ampliada a 7 niveles (añadido IA semántica)
- `_get_conn()` unificado en `alert_queue.py` y `deduplicator.py` con error descriptivo
- Cache RSS limpiado automáticamente entre ciclos (evitaba noticias estancadas)
- Corregido mapeo inverso bundle→cliente en `rss_fetcher.fetch_posts()`
- Agregado `source_page` a posts normalizados RSS (el clasificador lo usaba como "Desconocido")
- Eliminado `psycopg2-binary` duplicado en `requirements.txt`
- `.gitignore` actualizado con `.venv/` y `venv/`

### v2.0 (Mayo 17, 2026)
- Webhooks en tiempo real desde rss.app
- Deduplicación multi-nivel con PostgreSQL
- Flask webhook server integrado
- Filtro NACIONAL: solo política importante (ALRT/CRIT, departamentos permitidos)

### v1.0
- RSS polling cada 5 minutos
- Clasificación IA (OpenAI)
- Envío WhatsApp bridge + Google Sheets

---

**Desarrollado para Protecta Perú — Sistema de Alertas Automatizado**
