# 🛡️ Sistema de Alertas — Protecta Perú

Sistema automatizado que monitorea noticias vía **webhooks en tiempo real** y **polling RSS**, clasifica con IA, deduplica inteligentemente y envía alertas a WhatsApp por cliente/región. Registra todo en Google Sheets.

**Versión:** 2.0+  
**Última actualización:** 17 de Mayo 2026  
**Estado:** 🟢 Producción

---

## ⚡ Características Principales

✅ **Webhooks en Tiempo Real** - Notificaciones inmediatas desde rss.app (< 1 segundo de latencia)  
✅ **Polling RSS Fallback** - Consulta cada 5 minutos como respaldo  
✅ **Deduplicación 4 Niveles** - Detecta duplicados por URL, título hash, similitud Jaccard, describción  
✅ **Descripciones Optimizadas** - 20-25 palabras exactas, impactantes y directas  
✅ **Clasificación IA** - OpenAI, Claude, Gemini, Groq, OpenRouter  
✅ **Multi-Cliente** - 6+ clientes configurables (Antamina, Bechtel, Pisco, etc.)  
✅ **Integración WhatsApp** - Bridge Node.js local o proveedores externos  
✅ **Google Sheets** - Registro histórico de todas las alertas  
✅ **PostgreSQL** - BD persistente para deduplicación avanzada  

---

## 🔄 Flujo del Sistema

```
┌─ Webhooks (tiempo real)    ┐
│   rss.app → /webhook       │
│   Buffer: 500 items        │
└─────────────────────────────┘
           │
           ▼
┌─ Polling RSS (cada 5 min)  ┐
│   Fallback automático      │
└─────────────────────────────┘
           │
           ▼
    ┌──────────────────┐
    │ DEDUPLICADOR     │
    ├──────────────────┤
    │ 1. URL exacta    │
    │ 2. Hash título   │
    │ 3. Jaccard (60%) │
    │ 4. Descripción   │
    └────────┬─────────┘
             │
             ▼
      ┌─────────────────┐
      │ CLASIFICADOR    │
      │ (IA)            │
      │ - Nivel         │
      │ - Cliente       │
      │ - Ubicación     │
      │ - 3 Keywords    │
      └────────┬────────┘
             │
             ▼
      ┌─────────────────┐
      │ FORMATEADOR     │
      │                 │
      │ Título +        │
      │ Resumen 20-25w  │
      │ Emoji + Fecha   │
      └────────┬────────┘
             │
        ┌────┴────┐
        ▼         ▼
    WhatsApp  Google Sheets
    (directo) (histórico)
```

---

## 📊 Niveles de Alerta

| Nivel | Emoji | Criterio |
|-------|-------|----------|
| **CRIT** | 🔴 | Homicidios, balaceras, derrames, bloqueos operacionales, minería ilegal |
| **ALRT** | 🟡 | Accidentes viales, huaicos, huelgas, robos, incendios, protestas |
| **INFO** | 🟢 | Inversiones, obras, acuerdos, reuniones, producción positiva |
| **IGNORAR** | ✗ | Deportes, farándula, sin ubicación, fuera de zonas |

---

## 📁 Estructura de Archivos

```
alertas-protecta/
│
├── CORE (Código principal)
│   ├── main.py                 # Orquestador + scheduler
│   ├── config.py               # Configuración central
│   ├── classifier.py           # Clasificación IA
│   ├── formatter.py            # Formato WhatsApp (20-25 palabras)
│   ├── deduplicator.py         # Dedup 4 niveles
│   ├── router.py               # Routing cliente → grupo
│   │
│   ├── FUENTES
│   │   ├── rss_fetcher.py      # RSS polling
│   │   ├── webhook_handler.py  # Procesa webhooks
│   │   └── webhook_server.py   # Flask server (puerto 5000)
│   │
│   └── ENVÍO
│       ├── sender_whatsapp.py  # WhatsApp sender
│       ├── sender_sheets.py    # Google Sheets logging
│       └── alert_queue.py      # Cola de alertas
│
├── CONFIGURACIÓN
│   ├── .env                    # Variables de entorno
│   ├── requirements.txt        # Dependencias Python
│   ├── Procfile               # Heroku deployment
│   ├── run_system.bat         # Script Windows
│   ├── run_system.ps1         # Script PowerShell
│   │
│   └── whatsapp_bridge/       # Node.js WhatsApp bridge
│       ├── server.js
│       ├── package.json
│       └── Dockerfile
│
├── DOCUMENTACIÓN
│   ├── README.md               # Este archivo
│   ├── ARQUITECTURA.md        # Diseño detallado
│   ├── FLUJO_SISTEMA.md       # Flujo paso a paso
│   ├── GUIA_USO.md            # Guía de usuario
│   └── QUICK_START.md         # Inicio rápido
│
└── LOG
    └── alertas.log            # Logs detallados
```

---

## 🚀 Instalación Rápida

### 1. Requisitos
- Python 3.11+
- PostgreSQL (recomendado) o SQLite (fallback)
- Node.js (para WhatsApp bridge)

### 2. Clonar y Configurar
```bash
git clone https://github.com/bryn14-tech/alertas-rss.git
cd alertas-protecta
python -m venv .venv
source .venv/Scripts/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configurar .env
```bash
# Copiar plantilla
cp .env.example .env

# Editar .env con tus valores:
OPENAI_API_KEY=sk-...
DATABASE_URL=postgresql://user:pass@localhost/alertas
WEBHOOKS_ENABLED=true
WEBHOOK_PORT=5000
```

### 4. Iniciar Sistema
```bash
# Terminal 1: Python main
python main.py

# Terminal 2: WhatsApp bridge (opcional)
cd whatsapp_bridge && npm install && node server.js
```

**Resultado esperado:**
```
[WEBHOOKS] ✓ Servidor escuchando en 0.0.0.0:5000
Ciclo 1 — Procesando...
[DEDUP] ✓ Nivel 2 (Hash título) → DUPLICADO
[CLASIFICADOR] ✓ Clasificado
[ENVIO] ✓ Enviado a 'Antamina'
```

---

## ⚙️ Configuración Principal

Ver [QUICK_START.md](QUICK_START.md) para variables más comunes.

| Variable | Default | Descripción |
|----------|---------|-------------|
| `WEBHOOKS_ENABLED` | `true` | Activar servidor webhook Flask |
| `WEBHOOK_PORT` | `5000` | Puerto del servidor webhook |
| `USE_RSS_FEED` | `true` | Usar RSS en lugar de Facebook scraper |
| `INTERVAL_MINUTES` | `5` | Polling cada 5 minutos |
| `AI_PROVIDER` | `openai` | openai\|claude\|gemini\|groq\|openrouter |
| `WHATSAPP_PROVIDER` | `bridge` | bridge\|simulate |

---

## 📊 Ejemplo: De Webhook a WhatsApp

### 1. Webhook llega (rss.app)
```json
{
  "id": "evt_xyz",
  "type": "feed_update",
  "feed": {"id": "_vv3HkItEzKqytLHk"},  // Antamina
  "data": {
    "items_new": [{
      "title": "Incidente en Chaupiloma",
      "description": "...",
      "url": "https://..."
    }]
  }
}
```

### 2. Procesamiento
```
webhook_handler.process_webhook()
  → normalizar
  → mapear bundle → cliente (Antamina)
  → encolar en webhook_queue

main.py ciclo
  → deduplicator.is_duplicate_alert()
     → Jaccard título = 85% → ¡DUPLICADO! 🔴
     → Omitir este item
```

### 3. Envío Exitoso
```
[ENVIO] ✓ Enviado a 'Antamina'

*ALRT 🟡 17-05-26 ANCASH - SEGURIDAD - DETENCION*
En acción policial: Detenidos cinco sujetos involucrados en asaltos 
comercios zonas urbanas Ancash requiere intervención inmediata.
- FUENTE: https://tinyurl.com/xyz123
```

---

## 📈 Métricas de Rendimiento

| Métrica | Valor |
|---------|-------|
| Latencia webhooks | < 1 segundo |
| Deduplicación | 85%+ de duplicados detectados |
| Descripciones | Exactamente 20-25 palabras |
| Ciclo polling | 5 minutos |
| API calls/hora | 0-5 (vs 12 anterior) |
| DB storage | ~1 KB por alerta |

---

## 🔧 Troubleshooting

### Q: "Connection refused :5000"
```bash
# Puerto en uso?
netstat -ano | findstr :5000
# Cambiar en .env:
WEBHOOK_PORT=5001
```

### Q: "Bundle not found"
```bash
# Verificar que el feed_id está en config.py
# RSS_BUNDLES = { "Antamina": "_vv3HkItEzKqytLHk", ... }
```

### Q: Mensajes duplicados en WhatsApp
```bash
# Ver logs de dedup
tail -f alertas.log | grep Dedup

# Si sigue pasando, ajustar thresholds en deduplicator.py
JACCARD_THRESHOLD_TITULO = 0.55  # Más sensible
```

---

## 📚 Documentación Adicional

- [ARQUITECTURA.md](ARQUITECTURA.md) - Diseño técnico completo
- [FLUJO_SISTEMA.md](FLUJO_SISTEMA.md) - Flujo detallado paso a paso
- [GUIA_USO.md](GUIA_USO.md) - Cómo usar el sistema
- [QUICK_START.md](QUICK_START.md) - Inicio rápido (5 minutos)

---

## 🤝 Contribuciones

Para reportar bugs o sugerencias:
1. Abre un issue en GitHub
2. Describe el problema con detalles
3. Incluye logs de `alertas.log`

---

## 📝 Changelog Reciente

### v2.0 (Mayo 17, 2026)
- ✨ **Webhooks en tiempo real** desde rss.app
- ✨ **Deduplicación 4 niveles** (Jaccard + Levenshtein)
- ✨ **Descripciones optimizadas** (20-25 palabras exactas)
- 🔧 Flask server integrado
- 🔧 Logging mejorado

### v1.0
- RSS polling cada 5 minutos
- Clasificación IA (OpenAI/Claude)
- Envío WhatsApp + Google Sheets

---

**Desarrollado para Protecta Perú — Sistema de Alertas Automatizado**

### Pasos:

**1.** Ve a [console.cloud.google.com](https://console.cloud.google.com)

**2.** Crea un proyecto (o usa uno existente)

**3.** Activa estas dos APIs:
   - Google Sheets API
   - Google Drive API

**4.** Ve a **Credenciales → Crear credenciales → Cuenta de servicio**
   - Dale un nombre (ej: `protecta-alertas`)
   - Rol: Editor

**5.** Entra a la cuenta de servicio creada → pestaña **Claves** → **Agregar clave → JSON**
   - Descarga el archivo → renómbralo `credentials.json`
   - Ponlo en la carpeta raíz del proyecto

**6.** Copia el email de la cuenta de servicio (tiene este formato: `nombre@proyecto.iam.gserviceaccount.com`)

**7.** Abre el Google Sheets → botón **Compartir** → pega ese email con rol **Editor**

El `SPREADSHEET_ID` ya está configurado en `config.py` con el ID del Sheets de Protecta.

---

## Configurar Apify (scraping Facebook)

Facebook bloquea scrapers directos. Apify es la solución más estable.

**1.** Crea cuenta en [apify.com](https://apify.com)  
   El plan gratuito incluye ~$5/mes de créditos, suficiente para este uso.

**2.** Ve a **Settings → Integrations → API token**

**3.** Pega el token en `.env` como `APIFY_TOKEN=apify_api_...`

**4.** Agrega las páginas a monitorear en `config.py`:
```python
FACEBOOK_PAGES = [
    "RPPNoticias",
    "LaRepublica.pe",
    "andina.pe.noticias",
    # páginas regionales de Ancash, Cajamarca, Ica, etc.
]
```

Sin token Apify, el sistema corre con 4 posts de prueba internos.

---

## Configurar WhatsApp

Elige una opción y actualiza `WHATSAPP_PROVIDER` en `config.py`.

### Opción A — CallMeBot (gratis, para empezar rápido)
> Solo envía a números individuales, no a grupos directamente. Útil para un número "relay" que reenvía al grupo.

1. Desde WhatsApp, escribe a `+34 644 66 05 45`: `I allow callmebot to send me messages`
2. Recibirás tu API key por WhatsApp
3. En `config.py`:
```python
WHATSAPP_PROVIDER = "callmebot"
```
4. En `.env`:
```
CALLMEBOT_PHONE=+51987654321
CALLMEBOT_APIKEY=123456
```

### Opción B — Meta Cloud API (oficial, soporta grupos)
1. Crea una [Meta Business Account](https://business.facebook.com)
2. Ve a [developers.facebook.com](https://developers.facebook.com) → nuevo app → WhatsApp
3. Obtén el `Phone Number ID` y `Access Token`
4. En `config.py`:
```python
WHATSAPP_PROVIDER = "meta"
```
5. En `.env`:
```
META_WA_TOKEN=EAABsbCS...
META_PHONE_ID=123456789
```

### Opción C — Twilio
1. Crea cuenta en [twilio.com](https://twilio.com) → activa WhatsApp sandbox
2. En `config.py`:
```python
WHATSAPP_PROVIDER = "twilio"
```
3. En `.env`:
```
TWILIO_SID=ACxxxxx
TWILIO_TOKEN=xxxxxxx
```

### Registrar los números de grupo
En `config.py`, actualiza `WHATSAPP_GROUPS` con los números reales:
```python
WHATSAPP_GROUPS = {
    "Antamina":            "+51987654321",
    "Bechtel / Newmont":   "+51987654322",
    "Clientes Sur":        "+51987654323",
    "Clientes Norte":      "+51987654324",
    "Agrícola Santa Azul": "+51987654325",
    "Pisco":               "+51987654326",
    "Petrotal":            "+51987654327",
    "Coyuntura Nacional":  "+51987654328",
}
```

---

## Clientes configurados

Los 20 clientes del sistema coinciden exactamente con el dropdown del Google Form:

| Cliente | Región | Rubro |
|---|---|---|
| Antamina | Ancash, Huánuco, Pasco | Minería |
| Bechtel / Newmont | Cajamarca | Minería |
| Petrotal | Loreto, Ucayali | Hidrocarburos |
| Pisco | Ica Pisco (zona costera) | Pesca |
| Agrícola Santa Azul | Lima Barranca, Supe, Huaura | Agroindustria |
| Agrícola Huarmey | Ancash Huarmey | Agroindustria |
| Agrícola 3P | La Libertad | Agroindustria |
| Agrícola Chapi | Ica | Agroindustria |
| Campos Andino | La Libertad / Costa norte | Agroindustria |
| Campos del Sur | Ica / Arequipa | Agroindustria |
| Don Ricardo | Zona sur | Agroindustria |
| Hortifrut | Costa norte | Agroindustria |
| Mission | Costa norte | Agroindustria |
| RVR | Zona sur | Agroindustria |
| SunFruits | Costa norte | Agroindustria |
| Vanguard | Zona sur/norte | Agroindustria |
| Uvica | Zona sur | Agroindustria |
| Clientes Sur | Ica, Arequipa | Agroindustria |
| Clientes Norte | La Libertad, Lambayeque, Piura | Agroindustria |
| Ninguno (Coyuntura Nacional) | Nacional / Perú | — |

---

## Formato de salida

### Mensaje WhatsApp
```
*ALRT 🟡* - 15-05-26 CAJAMARCA JAEN - POLITICA - GOBIERNO
Presidente Balcazar se reune con ronderos en Jaen para escuchar demandas y evaluar desarrollo rural.
- FUENTE: https://facebook.com/post/...
```

```
*CRIT 🔴* - 10-05-26 LIMA BARRANCA SUPE - SEGURIDAD - BALACERA
Se reportan disparos durante una despedida fúnebre en El Porvenir. Heridos en la escena, policía acude al lugar.
- FUENTE: https://facebook.com/post/...
```

### Fila en Google Sheets (Tabla_Informacion)
```
15/05/2026 14:35:00 | protecta.dev@gmail.com | Agrícola Santa Azul | Agroindustria |
Medio | https://... | 10-05-26_LIMA_BARRANCA_SUPE_Seguridad_Balacera_Se reportan... |
Sistema Automático | Incidente | CRIT | LIMA BARRANCA | LIMA | BARRANCA | SUPE | ...
```

---

## Lógica del Sistema y Cómo Funciona

El sistema de alertas de Protecta Perú es un proceso automatizado que monitorea páginas de Facebook, clasifica noticias relevantes usando IA, y distribuye alertas a grupos de WhatsApp y Google Sheets según el cliente y región afectados. A continuación, se detalla la lógica completa paso a paso.

### Arquitectura General

El sistema sigue un flujo secuencial:

1. **Recolección** (Scraping): Obtiene posts de Facebook vía Apify.
2. **Deduplicación**: Evita procesar noticias ya enviadas usando una base de datos SQLite.
3. **Clasificación**: Usa IA (Claude, OpenAI, etc.) para analizar el contenido y asignar nivel, cliente, región, etc.
4. **Enrutamiento**: Determina a qué grupos de WhatsApp enviar basado en el cliente.
5. **Formateo**: Genera mensajes para WhatsApp y filas para Google Sheets.
6. **Envío**: Distribuye las alertas inmediatamente después de procesar cada página.

El sistema corre en un loop infinito, rotando entre regiones (Antamina, Bechtel, Clientes Sur, etc.) y procesando páginas en lotes para equilibrar la carga y evitar sobrecargar Apify.

### Componentes Principales

#### 1. Configuración (`config.py`)
- **Regiones y rotación**: El sistema rota entre 7 regiones en orden fijo: Antamina, Bechtel / Newmont, Clientes Sur, Clientes Norte, Agrícola Santa Azul, Pisco, Coyuntura Nacional.
- **Páginas de Facebook**: Más de 200 páginas mapeadas a clientes/regiones (ej. páginas de Ancash → Antamina).
- **Clientes válidos**: 20 clientes como Antamina, Bechtel, Agrícola Santa Azul, etc., que coinciden con el dropdown del Google Form.
- **Mapeos**:
  - Región → Cliente (ej. ANCASH → Antamina).
  - Cliente → Grupo WhatsApp (ej. Antamina → grupo "Antamina").
  - Cliente → Rubro (ej. Antamina → Minería).
- **Límites**: 500 páginas por turno de región, 2 segundos de delay entre páginas, timeout de 45 segundos por página.

#### 2. Scraping (`scraper.py`)
- Usa Apify (API externa) para extraer posts de Facebook, ya que Facebook bloquea scrapers directos.
- Obtiene hasta 8 posts por página.
- Filtra posts sin texto o que son solo videos sin descripción.
- Retorna datos como texto, URL, fecha, imagen, etc.
- Si no hay token Apify, usa posts de prueba internos para simulación.

#### 3. Deduplicación (`deduplicator.py`)
- Usa SQLite (`alertas_dedup.db`) para almacenar hashes de URLs y alertas enviadas.
- Genera un hash único por alerta (basado en cliente, nivel, subcategoría, etc.).
- Evita reenviar la misma noticia si ya fue procesada.
- Marca alertas como enviadas después del envío exitoso.

#### 4. Clasificación (`classifier.py`)
- **IA usada**: Claude (Anthropic), OpenAI, Gemini o Groq. Configurable en `AI_PROVIDER`.
- **Prompt detallado**: Incluye reglas estrictas para niveles, clientes, ubicaciones, etc.
- **Niveles de alerta**:
  - **CRIT 🔴**: Homicidios, balaceras, denuncias a clientes, bloqueos, derrames tóxicos, secuestros.
  - **ALRT 🟡**: Accidentes en vías, huaicos, huelgas, incendios, robos.
  - **INFO 🟢**: Inauguraciones, inversiones, reuniones positivas.
  - **IGNORAR**: Sin impacto operacional, fuera de zonas, deportes, etc.
- **Correcciones duras**:
  - Mapea ciudades a departamentos correctos (ej. Chimbote → Ancash).
  - Fuerza cliente por departamento (ej. Cajamarca → Bechtel).
  - Filtro Lima: Solo procesa si menciona Barranca, Supe, Huaura, Huaral.
  - Regla de ubicación obligatoria: CRIT/ALRT requieren departamento + provincia/distrito.
- **Salida JSON**: Nivel, cliente, rubro, relevancia, tipo, región, departamento, provincia, distrito, fecha, categoría, palabras clave (siempre 3), título, resumen WhatsApp, subcategoría, tags.
- **Categorías fijas**: Agro-Agua-Medioambiente, Coyuntura Social, Coyuntura Política, Economía-Desarrollo, Protestas-Paros-Bloqueos, Seguridad-Delincuencia.

#### 5. Enrutamiento (`router.py`)
- Basado en el cliente clasificado, mapea a grupos WhatsApp.
- Ej. Cliente "Antamina" → grupo "Antamina".
- Si no hay mapeo exacto, busca coincidencias parciales.
- Retorna lista de grupos (generalmente uno por cliente).

#### 6. Formateo (`formatter.py`)
- **WhatsApp**: Mensaje con emoji de nivel, fecha, región, subcategoría, resumen (máx. 2 oraciones), fuente (URL acortada).
  - Ej: `*ALRT 🟡* - 15-05-26 CAJAMARCA JAEN - POLITICA - GOBIERNO Presidente Balcazar se reúne... - FUENTE: https://...`
- **Google Sheets**: Fila con columnas del Form (marca temporal, email, cliente, rubro, relevancia, link, noticia en formato tabla, operador, tipo, + metadatos).
  - Formato tabla: `FECHA_DEPARTAMENTO_PROVINCIA_DISTRITO_CATEGORIA_PALABRAS-CLAVE_TITULO` (separado por _).

#### 7. Envío
- **WhatsApp** (`sender_whatsapp.py`): Usa un "bridge" (servidor Node.js con whatsapp-web.js) para enviar mensajes a grupos. Soporta CallMeBot, Meta API, Twilio.
- **Sheets** (`sender_sheets.py`): Inserta filas en Google Sheets usando Service Account. Solo si `SHEETS_ENABLED=true`.
- **Cola de alertas** (`alert_queue.py`): Almacena mensajes pendientes en SQLite. Reintenta envíos fallidos (últimas 4 horas).

#### 8. Loop Principal (`main.py`)
- **Rotación por región**: Procesa páginas en lotes de 500 por región, avanzando offset para cubrir todas.
- **Envío inmediato**: Después de procesar cada página, envía alertas pendientes.
- **Reintentos**: Al inicio de cada ciclo, reintenta alertas no enviadas por fallos previos.
- **Heartbeat**: Ping a UptimeRobot/healthchecks.io para monitoreo.
- **Ciclos**: Cada 5 minutos (configurable), indefinidamente.
- **Manejo de errores**: Logs detallados, continúa si una página falla.

### Lógica de Procesamiento por Página
1. Scrapea posts de la página.
2. Para cada post:
   - Verifica duplicados.
   - Clasifica con IA (si no IGNORAR).
   - Determina grupos WhatsApp.
   - Formatea mensajes.
   - Encola para envío.
3. Envía inmediatamente todas las alertas de esa página.
4. Limpia cola antigua (>2 días).

### Seguridad y Validaciones
- **Filtros duros**: Ignora posts sin ubicación clara, fuera de zonas operativas, o con niveles bajos sin impacto.
- **Correcciones**: IA puede equivocarse en ubicaciones; el sistema corrige con mapas fijos.
- **Límites**: Semáforo para IA (1 concurrente), locks para envío.
- **Archivos sensibles**: `.env`, `credentials.json`, `alertas_dedup.db` no se suben a git.

---

## Ejecutar

### Modo normal (corre indefinidamente)
```bash
python main.py
```

### Un solo ciclo de prueba
```bash
python -c "from main import run_cycle; run_cycle()"
```

### Como servicio en Linux (para VPS)
Crea el archivo `/etc/systemd/system/alertas-protecta.service`:

```ini
[Unit]
Description=Sistema de Alertas Protecta Peru
After=network.target

[Service]
Type=simple
User=tu_usuario
WorkingDirectory=/ruta/completa/al/proyecto
ExecStart=/usr/bin/python3 main.py
Restart=always
RestartSec=30
StandardOutput=append:/ruta/completa/al/proyecto/alertas.log
StandardError=append:/ruta/completa/al/proyecto/alertas.log

[Install]
WantedBy=multi-user.target
```

Luego activar:
```bash
sudo systemctl daemon-reload
sudo systemctl enable alertas-protecta
sudo systemctl start alertas-protecta
sudo systemctl status alertas-protecta
```

Para ver los logs en tiempo real:
```bash
tail -f alertas.log
```

---

## Agregar un nuevo cliente

**1.** En `config.py`, agrégalo a `CLIENTES_VALIDOS`:
```python
"Nueva Empresa",
```

**2.** Mapearlo a su región en `REGION_TO_CLIENTES`:
```python
"MOQUEGUA": ["Nueva Empresa"],
```

**3.** Mapearlo a su grupo WhatsApp en `CLIENTE_TO_WHATSAPP_GROUP`:
```python
"Nueva Empresa": "Grupo Nueva Empresa",
```

**4.** Agregar el grupo en `WHATSAPP_GROUPS`:
```python
"Grupo Nueva Empresa": "+51999999999",
```

**5.** Si tiene rubro distinto a Agroindustria, agrégalo en `CLIENTE_TO_RUBRO`:
```python
"Nueva Empresa": "Minería",
```

---

## Variables de entorno (.env)

```env
# Obligatorio para clasificar con IA
ANTHROPIC_API_KEY=sk-ant-...

# Para scraping real de Facebook
APIFY_TOKEN=apify_api_...

# ID del Google Sheets (ya configurado en config.py)
SPREADSHEET_ID=1hWfu3EymR5Li4qWQv3RcBaaJruI9wOA0m44KnTGnZhs

# WhatsApp - CallMeBot
# CALLMEBOT_PHONE=+51987654321
# CALLMEBOT_APIKEY=123456

# WhatsApp - Meta Cloud API
# META_WA_TOKEN=EAABsbCS...
# META_PHONE_ID=123456789

# WhatsApp - Twilio
# TWILIO_SID=ACxxxxx
# TWILIO_TOKEN=xxxxxxx
```

---

## Archivos que NO deben subirse a git

Crea un `.gitignore` con esto:
```
.env
credentials.json
alertas_dedup.db
alertas.log
__pycache__/
*.pyc
```

---

## Orden recomendado para el setup inicial

1. `pip install -r requirements.txt`
2. Poner `ANTHROPIC_API_KEY` en `.env`
3. Correr `python -c "from main import run_cycle; run_cycle()"` — validar que Claude clasifica bien
4. Configurar Google Sheets (Service Account + compartir hoja)
5. Probar inserción en Sheets con un ciclo real
6. Elegir API de WhatsApp y configurarla
7. Cambiar `WHATSAPP_PROVIDER` de `"simulate"` al provider elegido
8. Correr `python main.py` — sistema productivo