# 🛡️ Sistema de Alertas — Protecta Perú

Sistema automatizado que monitorea páginas de Facebook, clasifica noticias con Claude AI y distribuye alertas a grupos de WhatsApp según cliente/región, registrando todo en el mismo Google Sheets del formulario interno.

---

## Flujo del sistema

```
Facebook Pages
     │
     ▼  (Apify scraper, cada 20 min)
Recolector Python
     │
     ▼  (hash/URL → SQLite)
Deduplicador
     │
     ▼  (Claude AI)
Clasificador
  ├─ nivel:      CRIT 🔴 / ALRT 🟡 / INFO 🟢 / IGNORAR
  ├─ cliente:    Antamina / Bechtel / Agrícola Santa Azul / etc.
  ├─ rubro:      Minería / Agroindustria / Pesca / etc.
  ├─ relevancia: Alto / Medio / Bajo
  └─ tipo:       Noticia / Incidente
     │
     ├──▶ WhatsApp Groups  (por cliente)
     └──▶ Google Sheets    (Tabla_Informacion — mismo del Form)
```

---

## Niveles de alerta

| Nivel | Criterio |
|---|---|
| CRIT 🔴 | Homicidios, balaceras, denuncias a empresas cliente, bloqueo de operaciones, derrames tóxicos, secuestros |
| ALRT 🟡 | Accidentes en vías clave, huaicos, derrumbes, cortes de vía, huelgas convocadas, incendios, robos a empresas |
| INFO 🟢 | Inauguraciones, inversiones, avances de obra, reuniones con comunidades, producción positiva |
| IGNORAR | Deportes, farándula, publicidad, eventos sin impacto operacional |

---

## Estructura de archivos

```
alerta_system/
├── main.py              → Punto de entrada + scheduler (cada 20 min)
├── config.py            → Toda la configuración (clientes, grupos, regiones)
├── scraper.py           → Scraping de Facebook vía Apify
├── classifier.py        → Clasificación con Claude API
├── deduplicator.py      → Anti-duplicados con SQLite
├── formatter.py         → Formatos WhatsApp y Google Sheets
├── router.py            → Cliente → grupo WhatsApp
├── sender_whatsapp.py   → Envío WhatsApp (CallMeBot / Meta / Twilio)
├── sender_sheets.py     → Inserción en Google Sheets
├── requirements.txt
├── .env.example         → Plantilla de credenciales
├── .env                 → TUS credenciales (no subir a git)
├── credentials.json     → Service Account Google (no subir a git)
└── alertas_dedup.db     → SQLite auto-generado al correr
```

---

## Instalación paso a paso

### 1. Requisitos previos
- Python 3.11 o superior
- pip

### 2. Instalar dependencias
```bash
pip install -r requirements.txt
```

### 3. Crear archivo de credenciales
```bash
cp .env.example .env
```
Abre `.env` y rellena al menos `ANTHROPIC_API_KEY` para empezar a probar.

### 4. Probar en modo simulación (sin gastar nada)
```bash
python -c "from main import run_cycle; run_cycle()"
```
Esto usa posts de prueba internos y muestra en consola cómo quedarían los mensajes sin enviar nada real.

---

## Configurar Google Sheets

El sistema escribe en la misma hoja **Tabla_Informacion** que alimenta el Google Form.  
Las columnas respetan exactamente el orden del formulario:

```
Marca temporal | Email | Cliente | Rubro | Relevancia |
Link | Noticia (formato tabla) | Operador | Tipo
+ columnas extra de metadatos al final
```

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