# Sistema de Alertas — Protecta Perú

Sistema automatizado que monitorea noticias vía **webhooks en tiempo real** y **polling RSS**, clasifica con IA, deduplica inteligentemente y envía alertas a WhatsApp por cliente/región. Registra todo en Google Sheets.

**Versión:** 3.0  
**Última actualización:** 26 de Agosto, 2026  
**Estado:** Producción

---

## Características Principales

- **Webhooks en Tiempo Real** — Notificaciones inmediatas desde rss.app, con modo directo (ngrok) o modo relay (servicio externo tipo Railway, sin depender de un túnel local)
- **Polling RSS Fallback** — Consulta cada 5 minutos como respaldo
- **Clasificación en dos etapas** — pre-filtro barato (`prompts/pre_filtro_prompt.md`, con razonamiento breve) descarta ruido evidente antes del clasificador completo (`prompts/classifier_prompt.md`), bajando el costo de OpenAI sin perder alertas reales
- **Deduplicación 7 Niveles** — URL exacta, content hash, firma de evento, Jaccard título, Levenshtein, Jaccard descripción, IA semántica — con chequeo y registro atómico (evita duplicados por condición de carrera en posts casi simultáneos)
- **Clasificación IA** — OpenAI GPT-4o-mini (proveedor activo)
- **Multi-Cliente** — 6 bundles RSS + 17 clientes válidos (ver tabla abajo)
- **Integración WhatsApp** — Bridge Node.js local (whatsapp-web.js)
- **Google Sheets** — Registro histórico de todas las alertas (RSS y webhook)
- **SQLite local** — Deduplicación y cola de alertas en `data/dedup.db` / `data/queue.db`, sin depender de un servidor de base de datos externo ni de sus cuotas
- **Resiliente a caídas de infraestructura** — si la base de datos local falla, el sistema sigue enviando alertas (sin dedup temporalmente) en vez de caerse por completo

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
      │ PRE-FILTRO IA   │  Barato (~2.5K tokens), con
      │ RUIDO/POSIBLE   │  razonamiento breve — descarta
      └────────┬────────┘  turismo/empleo/deportes/etc.
               │ POSIBLE
               ▼
      ┌─────────────────┐
      │ CLASIFICADOR    │
      │ (OpenAI)        │
      │ - Nivel         │
      │ - Cliente       │
      │ - Ubicación     │
      │ - Rubro         │
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
│   ├── classifier.py           # Pre-filtro + clasificación IA (OpenAI) + filtros duros
│   ├── formatter.py            # Formato WhatsApp / Sheets
│   ├── deduplicator.py         # Dedup 7 niveles (SQLite local)
│   ├── router.py               # Routing cliente → grupo
│   │
│   ├── PROMPTS
│   │   ├── prompts/classifier_prompt.md   # Prompt principal (nivel, cliente, ubicación, rubro...)
│   │   └── prompts/pre_filtro_prompt.md   # Prompt barato de descarte (RUIDO/POSIBLE)
│   │
│   ├── FUENTES
│   │   ├── rss_fetcher.py      # RSS polling (rss.app)
│   │   ├── webhook_handler.py  # Procesa webhooks entrantes
│   │   ├── webhook_server.py   # Flask server (modo directo) + poller (modo relay)
│   │   └── webhook_relay/      # Servicio externo opcional (Railway) sin logica de negocio —
│   │                           # recibe el webhook y tu PC lo va a buscar por polling
│   │
│   └── ENVÍO
│       ├── sender_whatsapp.py  # WhatsApp bridge sender
│       ├── sender_sheets.py    # Google Sheets logging
│       └── alert_queue.py      # Cola persistente (SQLite local)
│
├── CONFIGURACIÓN
│   ├── .env                    # Variables de entorno (no commitear)
│   ├── .env.example            # Plantilla para .env
│   ├── requirements.txt        # Dependencias Python
│   ├── Procfile                # Heroku deployment
│   ├── start_autonomous.ps1    # Supervisor (arranca/reinicia bridge + main.py)
│   ├── run_system.bat          # Script Windows
│   ├── run_system.ps1          # Script PowerShell
│   │
│   └── whatsapp_bridge/        # Node.js WhatsApp bridge
│       ├── server.js
│       ├── package.json
│       └── Dockerfile
│
├── DATOS (local, no commitear — ver .gitignore)
│   └── data/
│       ├── dedup.db            # SQLite — deduplicación (posts vistos, alertas enviadas)
│       └── queue.db            # SQLite — cola de alertas pendientes de envío
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
- Node.js 18+ (para WhatsApp bridge)
- No requiere base de datos externa — usa SQLite local automáticamente

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
RSS_API_KEY=...
RSS_API_SECRET=...
BRIDGE_TOKEN=tu_token_secreto
WEBHOOKS_ENABLED=true
WEBHOOK_PORT=5000
# (opcional) modo relay en vez de ngrok — ver sección Webhooks
# WEBHOOK_RELAY_URL=https://tu-relay.up.railway.app
# WEBHOOK_RELAY_TOKEN=el_mismo_secreto_del_relay
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
| `RSS_API_KEY` | Sí | Clave de API rss.app |
| `RSS_API_SECRET` | Sí | Secreto de API rss.app |
| `BRIDGE_TOKEN` | Sí | Token de autenticación del bridge WhatsApp |
| `BRIDGE_URL` | No | URL del bridge (default: `http://localhost:3000`) |
| `WEBHOOKS_ENABLED` | No | Activar recepción de webhooks (default: `true`) |
| `WEBHOOK_HOST` / `WEBHOOK_PORT` | No | Host/puerto del servidor local en modo directo (default: `0.0.0.0` / `5000`) |
| `WEBHOOK_SECRET` | No | Secreto HMAC para validar webhooks de rss.app (modo directo) |
| `WEBHOOK_RELAY_URL` | No | URL del servicio relay externo (ej. Railway) — si está seteada, usa **modo relay** (polling) en vez de exponer un servidor local con ngrok |
| `WEBHOOK_RELAY_TOKEN` | Si `WEBHOOK_RELAY_URL` | Token compartido con el relay (debe coincidir con `RELAY_TOKEN` del servicio `webhook_relay/`) |
| `WEBHOOK_RELAY_POLL_SECONDS` | No | Cada cuántos segundos se consulta el relay (default: `5`) |
| `WHATSAPP_PROVIDER` | No | `bridge` o `simulate` (default: `bridge`) |
| `USE_RSS_FEED` | No | Usar RSS en lugar de scraper (default: `true`) |
| `SHEETS_ENABLED` | No | Activar logging en Google Sheets (default: `false`) |
| `SPREADSHEET_ID` | Si SHEETS_ENABLED | ID del Google Sheets |
| `HEARTBEAT_URL` | No | URL de watchdog externo (UptimeRobot, etc.) |

> `DATABASE_URL` / PostgreSQL **ya no se usa** — la deduplicación y la cola de alertas viven en SQLite local (`data/dedup.db`, `data/queue.db`), sin configuración adicional.

---

## Configuración Principal (`config.py`)

### Bundles RSS configurados

| Cliente | Bundle ID | Región |
|---------|-----------|--------|
| Antamina | `_vv3HkItEzKqytLHk` | Ancash (solo AIO — ver abajo), Huánuco (solo Llata) |
| Bechtel / Newmont | `_dtKCh5CjRws0ai8H` | Cajamarca |
| Clientes Sur | `_vuHd6hNkLlFj0nPK` | Ica (Arequipa siempre bloqueada, ver `fix_arequipa_block`) |
| Clientes Norte | `_i5tst4lPDJ5oTSW4` | La Libertad |
| Pisco | `_XgBrvIyMIWm5YzLP` | Ica — provincia Pisco |
| Ninguno (Coyuntura Nacional) | `_pM02KT2QspbdR8os` | Nacional |

**Área de Influencia Operativa (AIO) de Antamina** — Ancash fuera de esta lista → IGNORAR:
- Huari: San Marcos, Chavín de Huántar, Huachis, San Pedro de Chana
- Bolognesi: Huallanca, Aquia, Chiquián, Cajacay, Antonio Raymondi, Colquioc, Huayllacayán
- Recuay: Catac, Pampas Chico, Marca, Llacllín, Pararín
- Huarmey: toda la provincia (puerto/mineroducto)
- Huánuco: solo distrito Llata (Huamalíes)
- Pasco: **no es zona de Antamina** (se ignora salvo coyuntura política nacional)

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

main.py ciclo (thread dedicado de webhooks, drena apenas llega)
  → deduplicator.already_processed() → False
  → classifier.pre_filtro_ia() → POSIBLE (si dice RUIDO, se descarta aquí sin gastar el prompt grande)
  → classifier.classify() → ALRT
  → deduplicator.is_duplicate_alert() + mark_alert_sent() → registrada (atómico, evita duplicados por carrera)
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

El rubro se determina por el **contenido de la noticia**, no por el cliente (ver filtro de
corrección por contenido en `classifier.py` — evita que todo lo de un grupo agro salga
"Agroindustria" aunque sea, por ejemplo, un operativo militar o de minería informal en la misma zona).

| Cliente | Grupo WhatsApp | Zona | Rubro por defecto |
|---------|---------------|------|-------------------|
| Antamina | Antamina | Ancash (AIO), Huánuco (Llata) | Minería |
| Bechtel / Newmont | Bechtel / Newmont | Cajamarca | Minería |
| Pisco | Pisco | Ica — provincia Pisco | Pesca |
| Ninguno (Coyuntura Nacional) | Coyuntura Nacional | Nacional | No es un rubro |
| **Agro Norte** (La Libertad) | Clientes Norte | La Libertad | Agroindustria |
| — Hortifrut | Clientes Norte | | |
| — Mission | Clientes Norte | | |
| **Agro Sur** (Ica) | Clientes Sur | Ica | Agroindustria |
| — Agrícola 3P | Clientes Sur | | |
| — Agrícola Chapi | Clientes Sur | | |
| — Campos Andino | Clientes Sur | | |
| — Campos del Sur | Clientes Sur | | |
| — Don Ricardo | Clientes Sur | | |
| — RVR | Clientes Sur | | |
| — SunFruits | Clientes Sur | | |
| — Uvica | Clientes Sur | | |
| — Vanguard | Clientes Sur | | |

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

## Modos de Webhook

### Modo directo (por defecto)
`main.py` levanta un servidor Flask local (puerto 5000) y rss.app le manda los eventos ahí
directamente. Como la PC no tiene IP pública, se necesita un túnel (ej. **ngrok**) para exponerlo
a internet, y esa URL hay que registrarla en los 6 webhooks de rss.app. Problema conocido: el
plan gratis de ngrok cambia de URL cada vez que se reinicia, así que hay que volver a actualizar
rss.app manualmente cada vez que el túnel se cae.

### Modo relay (recomendado si el túnel se cae seguido)
Un servicio externo mínimo y sin lógica de negocio (`webhook_relay/`, pensado para desplegar en
Railway u otro hosting) recibe los webhooks de rss.app y los guarda en memoria. Tu PC los va a
buscar por **polling** cada pocos segundos (`WEBHOOK_RELAY_POLL_SECONDS`) — así nunca necesitas
exponer tu propia PC a internet, y la URL del relay no cambia entre reinicios de tu máquina.

Para activarlo: despliega `webhook_relay/` (solo `app.py`, `requirements.txt`, `Procfile` — no
necesita nada más del proyecto), define `RELAY_TOKEN` en ese servicio, y en tu `.env` local
configura `WEBHOOK_RELAY_URL` + `WEBHOOK_RELAY_TOKEN` con la misma URL/token. Actualiza los
webhooks de rss.app para que apunten a `https://tu-relay/webhook?client=<Nombre>&token=<token>`.

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

### "No se pudo abrir la BD local" / errores de SQLite
```bash
# Verifica que exista (o se pueda crear) la carpeta data/ junto a main.py.
# Si la BD esta corrupta o quieres empezar de cero, borra los archivos y se
# recrean solos en el siguiente arranque:
rm data/dedup.db data/dedup.db-wal data/dedup.db-shm
rm data/queue.db data/queue.db-wal data/queue.db-shm
```
El sistema sigue funcionando (sin dedup temporalmente) aunque la BD falle — ver
"Resiliente a caídas de infraestructura" arriba.

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
| Latencia webhooks | Segundos (drenado continuo en thread dedicado, no atado al ciclo de RSS) |
| Deduplicación | 7 niveles (URL → IA semántica), chequeo + registro atómico |
| Ciclo polling | 5 minutos |
| Items por bundle | 50 (últimas 8 horas) |
| Ventana dedup | 24 horas |
| Almacenamiento BD | SQLite local, ~1 KB por alerta |
| Volumen típico | ~1,000-5,000 llamadas al clasificador/día según tráfico de noticias |
| Filtrado por pre-filtro | ~60-85% del volumen evaluado se descarta antes del prompt completo |
| Costo OpenAI aprox. | ~$2-4/día con tráfico normal (gpt-4o-mini, con prompt caching) |

---

## Documentación Adicional

- [ARQUITECTURA.md](ARQUITECTURA.md) — Diseño técnico por módulo
- [FLUJO_SISTEMA.md](FLUJO_SISTEMA.md) — Flujo detallado paso a paso
- [GUIA_USO.md](GUIA_USO.md) — Operación y casos de uso
- [QUICK_START.md](QUICK_START.md) — Inicio rápido

---

## Changelog

### v3.0 (Agosto 26, 2026) — control de costos, migración a SQLite, y varios fixes de precisión
- **Pre-filtro de dos etapas** (`classifier.py`, `prompts/pre_filtro_prompt.md` nuevo): antes de gastar el prompt completo (~10K tokens), un prompt barato (~2.5K tokens) con razonamiento breve decide RUIDO/POSIBLE. Bajó el gasto de OpenAI de ~$6/día a ~$2-4/día sin perder alertas reales — clave: dejarlo razonar 1-2 oraciones antes de responder (no forzar la respuesta en 5 tokens), igual que el prompt completo tenía "espacio para pensar" al llenar todo el JSON
- **Prompt principal reducido** (`prompts/classifier_prompt.md`): se sacó el bloque completo de "IGNORAR — ruido local" (turismo, empleo, avisos municipales, etc.) del prompt principal — ahora vive solo en el pre-filtro, bajando el prompt principal de ~10,700 a ~8,200 tokens antes de que fuera creciendo de nuevo con los fixes de precisión de este changelog
- **Migración de PostgreSQL a SQLite local** (`deduplicator.py`, `alert_queue.py`): la deduplicación y la cola de alertas ya no dependen de un servidor Postgres externo (Neon) ni de sus cuotas de cómputo — todo vive en `data/dedup.db` y `data/queue.db`, archivos locales sin configuración
- **Resiliencia a caídas de base de datos** (`deduplicator.py`, `alert_queue.py`, `main.py`): antes, si la BD fallaba al iniciar, todo el proceso crasheaba en loop infinito (pasó con Neon agotado). Ahora los constructores no crashean, y cada chequeo de duplicado atrapa `DBUnavailable` y sigue funcionando sin dedup en vez de morir
- **Bug de duplicados por condición de carrera, corregido de raíz** (`deduplicator.py`, `main.py`): dos posts casi simultáneos del mismo hecho podían pasar ambos el chequeo de duplicado antes de que cualquiera se registrara. `mark_alert_sent()` ahora retorna `True`/`False` según si realmente logró registrar la alerta (y no solo si la intentó), y `main.py` revisa ese resultado antes de enviar — el "perdedor" de la carrera ya no se manda
- **Bug de dedup por URL nunca activo, corregido**: `deduplicator.py` buscaba `alert["url"]`, pero `classifier.py` guarda el link como `alert["source_url"]` — el nivel 0 de dedup (URL exacta) estuvo desactivado desde siempre por este desajuste de nombres
- **Bug de Sheets faltante en el camino de webhooks**: `sh_sender.append_row()` solo se llamaba en el camino de RSS, nunca en el de webhooks — como la mayoría del tráfico llega por webhook, ~44% de las alertas no se registraban en Sheets
- **Drenado de webhooks desacoplado del ciclo de RSS** (`webhook_server.py`, `main.py`): antes se procesaban máx. 10 eventos de webhook por ciclo de 5 min; con tráfico alto la cola se llenaba (500) y rss.app recibía 503. Ahora un thread dedicado drena apenas llega cada evento
- **Modo relay de webhooks** (`webhook_relay/` nuevo, `webhook_server.py`, `config.py`): alternativa a ngrok para no depender de un túnel que cambia de URL en cada caída — un servicio externo mínimo recibe el webhook y la PC lo va a buscar por polling
- **Fixes de precisión geográfica en `classifier.py`/`classifier_prompt.md`**: ubicaciones inventadas quando no hay ninguna mencionada en el texto (ej. "ANCASH HUARMEY" puesto por defecto en noticias nacionales o conferencias sin lugar); sesgo por nombre de página/hashtag ignorando el hashtag real del texto (`fix_dept_by_hashtag`); caseríos/anexos de la zona de Antamina (Carhuayoc, Ayash, Juprog, Huaripampa, Pichiu, Yanacancha) mal asignados a Huarmey (`fix_antamina_anexos`); noticias de "Gobierno Regional [zona]"/GORE puestas como NACIONAL en vez de la región real (`fix_nacional_by_gore_mention`)
- **Filtro de "protesta genérica"**: una protesta/paro/marcha que NO menciona a ninguna empresa cliente ni una zona crítica se baja de CRIT a ALRT (REGLA 9 es para protestas CONTRA el cliente, no cualquier protesta social aunque el motivo de fondo sea grave)
- **Filtro de seguimiento posterior a homicidio, reforzado en Python**: red de seguridad independiente de que la IA declare bien `etapa_hecho` — si el texto dice "sepultan"/"entierro"/"piden justicia" junto con una palabra de muerte violenta, se fuerza IGNORAR
- **Rubro corregido por contenido, no por cliente**: el rubro por defecto de "Clientes Norte/Sur" es Agroindustria, pero eso hacía que operativos militares o hechos de minería en esa zona salieran mal etiquetados — ahora se corrige por palabras clave del texto (`classifier.py`) y el prompt explica que el rubro es el tema real de la noticia, no el del grupo de cliente
- **Filtro de obras de agua en zonas agro**: obras/trabajos de agua potable o riego en Pisco/La Libertad/Agro Sur Ica ahora cuentan como relevantes (mínimo INFO) aunque no haya conflicto — el agua es crítica para estos clientes
- **Reclasificación de clientes agro**: Agrícola 3P, Campos Andino y SunFruits movidos de "Agro Norte" (La Libertad) a "Agro Sur" (Ica) en `config.py` y el prompt — dato incorrecto desde antes
- **Pasco removido de Antamina**: el prompt decía "Pasco → Antamina" pero el código Python (`DEPARTAMENTOS_SIN_CLIENTE`, `DEPT_TO_CLIENT`) ya lo excluía desde antes — se corrigió el prompt para que coincida
- **Columna "Categoria" de Sheets sin forzar mayúsculas** (`formatter.py`): se guardaba todo en mayúsculas aunque el clasificador ya devuelve la categoría bien capitalizada (ej. "Agro-Agua-Medioambiente")
- **Bug de "Coyuntura Nacional" descartando categorías válidas no-políticas** (`classifier.py`): un filtro exigía que la categoría fuera literalmente "Coyuntura Politica" para que sobreviviera cualquier alerta nacional — mataba de forma incorrecta noticias nacionales legítimas de otra categoría (ej. economía/MINEM)

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
