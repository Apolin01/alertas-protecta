# Sistema de Alertas — Protecta Perú

Sistema automatizado que monitorea noticias vía **webhooks en tiempo real** y **polling RSS**, clasifica con IA, deduplica inteligentemente y envía alertas a WhatsApp por cliente/región. Registra todo en Google Sheets.

**Versión:** 2.2  
**Última actualización:** 02 de Junio, 2026  
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
| **IGNORAR** | — | Deportes, farándula, turismo/recreativo, publicidad, sin ubicación clara, fuera de zonas operativas |

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
| Agrícola Santa Azul | Agricola Santa Azul | Agroindustria |
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

### Grupo de WhatsApp no encontrado (error 404 del bridge)
El nombre en `CLIENTE_TO_WHATSAPP_GROUP` debe coincidir **exactamente** con la clave en `GROUP_MAP` de `server.js` (sin tildes, mismo uso de mayúsculas). Ver sección "Clientes Configurados" para los nombres correctos.

### El grupo "Coyuntura Nacional" no recibe mensajes
Verificar en `config.py`:
- `NACIONAL_ALLOWED_DEPTS` incluye `"NACIONAL"` y `"LIMA"`
- `NACIONAL_ALLOWED_CATEGORIES` incluye las categorías políticas relevantes
- `NACIONAL_MIN_LEVEL = "INFO"` (si solo llegan INFO-level, ALRT bloquea todo)

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

### v2.3 (Junio 09, 2026)
- **Filtro de empleo/reclutamiento** (`classifier.py`): convocatorias laborales, ofertas de trabajo y procesos CAS (nivel INFO) forzados a IGNORAR mediante filtro duro con constante `EMPLEO_TERMS` — no aplica a CRIT/ALRT para no bloquear accidentes laborales ni huelgas
- **Prompt mejorado** (`prompts/classifier_prompt.md`): IGNORAR ahora lista explícitamente reclutamiento/empleo con ejemplos (oportunidad laboral, convocatoria CAS, bolsa de trabajo)
- **Deduplicación cross-fuente** (`deduplicator.py`): NIVEL 6 (IA semántica) ahora también compara alertas de la **misma provincia** en una ventana de 2h (`DEDUP_SAME_PROVINCIA_HOURS`) sin importar la similitud léxica del título — captura el mismo evento narrado de forma muy distinta por distintas páginas (ej. "naufragio en Paracas" vs "búsqueda de pescadores" vs "familiares buscan a Kenny Díaz", los 3 reportando el mismo naufragio en San Andrés, Pisco)
- **RSS `max_age_hours`** (`rss_fetcher.py`): ampliado de 2h a 8h en `RSSFetcher.fetch_posts()` para capturar bundles de baja frecuencia (Coyuntura Nacional, Agrícola Santa Azul)
- **Constraint `sent_alerts`**: corregido `UNIQUE(titulo_hash, departamento)` faltante que hacía fallar `ON CONFLICT` y dejaba la deduplicación de contenido sin efecto
- **Elecciones nacionales habilitadas** (`prompts/classifier_prompt.md`): REGLA 7 y NIVELES→INFO actualizados para que resultados ONPE/JNE, conteo de actas y declaraciones de candidatos lleguen como mínimo INFO a "Ninguno (Coyuntura Nacional)" — antes el prompt los dejaba caer en IGNORAR
- **Enrutamiento de elecciones corregido** (`prompts/classifier_prompt.md`, REGLA 0 nueva, prioridad maxima): noticias de proceso electoral nacional van SIEMPRE a "Ninguno (Coyuntura Nacional)" / departamento=NACIONAL, evaluada ANTES que las reglas de ubicacion por departamento (REGLAS 1-9) — corrige envios incorrectos a "Bechtel / Newmont", "Antamina", "Clientes Sur", etc. cuando el conteo de votos mencionaba esos departamentos
- **Dedup de noticias en desarrollo** (`deduplicator.py`, `_ai_are_same_event`): el prompt de IA ahora reconoce actualizaciones consecutivas de una misma cobertura en vivo (ej. resultados electorales que cambian de líder cada pocos minutos) como duplicados, no solo el mismo evento exacto
- **Filtro de avisos municipales** (`classifier.py`): festivales, aniversarios, campañas de esterilización/vacunación de mascotas y charlas informativas (nivel INFO) forzados a IGNORAR mediante filtro duro con constante `AVISO_MUNICIPAL_TERMS` — no aplica a CRIT/ALRT para no bloquear denuncias de violencia real ni protestas. Prompt actualizado con ejemplos explícitos (Festival de la Chocoteja, campaña de esterilización, charla LEY 30364)
- **Tráfico de terrenos → ALRT** (`classifier.py`, `prompts/classifier_prompt.md`): noticias sobre tráfico/usurpación/invasión de terrenos o venta irregular de lotes (riesgo social para zonas agrícolas) ahora se elevan de INFO a ALRT mediante filtro duro con `TRAFICO_TERRENOS_TERMS`, aunque la noticia se enfoque en un funcionario o excandidato (ej. "exalcalde entregó títulos a traficantes de terrenos en Medio Mundo")

### v2.2 (Junio 02, 2026)
- **Filtro de turismo** (`classifier.py`): contenido turístico/recreativo (cataratas, hospedaje, tours, ecoturismo, alojamiento) forzado a IGNORAR mediante filtro duro post-IA con constante `TURISMO_TERMS` — actúa como red de seguridad cuando el prompt no lo bloquea
- **Prompt mejorado** (`prompts/classifier_prompt.md`): IGNORAR ahora lista explícitamente turismo con ejemplos (aviso de catarata con precios, publicidad de hospedaje, tours de aventura); REGLA 5 incluye excepción Huarmey (ANCASH provincia HUARMEY → "Agrícola Huarmey", no Antamina)
- **Corregido grupo WhatsApp Santa Azul** (`config.py`): `CLIENTE_TO_WHATSAPP_GROUP["Agrícola Santa Azul"]` corregido de `"Agrícola Santa Azul"` a `"Agricola Santa Azul"` (sin tilde) para coincidir con la clave en `GROUP_MAP` de `server.js` — el grupo no recibía mensajes por este desajuste
- **Nivel mínimo Coyuntura Nacional** (`config.py`): `NACIONAL_MIN_LEVEL` bajado de `"ALRT"` a `"INFO"` para que contenido político informativo (debates electorales, declaraciones de candidatos) llegue al grupo nacional
- **Bloqueo Arequipa** (`classifier.py`): nueva función `fix_arequipa_block()` — Arequipa nunca va a "Clientes Sur" ni a clientes agro; única excepción es coyuntura política nacional pura

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
