# 🏗️ Arquitectura del Sistema - Funcionalidad por Archivo

## 📌 Módulos Principales

### **main.py** — Orquestador Central
**Responsabilidad:** Coordina todo el flujo de alertas

**Funciones clave:**
- `process_page(page_name)` - Procesa posts de un bundle RSS
- `process_region()` - Itera sobre clientes configurados
- `retry_unsent()` - Reintenta alertas fallidas (bridge caído)
- `flush_all_pending()` - Envía alertas encoladas a WhatsApp
- `run_forever()` - Loop principal que ejecuta cada 5 minutos

**Flujo:**
1. Obtiene posts del RSS (50 por cliente)
2. Clasifica cada post (requiere OpenAI)
3. Deduplica contra alertas previas
4. Formatea para WhatsApp
5. Encola y envía inmediatamente

---

### **config.py** — Configuración Centralizada
**Responsabilidad:** Almacena todos los parámetros del sistema

**Configuraciones importantes:**
```python
USE_RSS_FEED = true                    # Usar RSS en lugar de scraper
INTERVAL_MINUTES = 5                   # Polling cada 5 minutos
WHATSAPP_PROVIDER = "bridge"           # "bridge" o "simulate"
RSS_BUNDLES = {
    "Antamina": "_vv3HkItEzKqytLHk",
    "Bechtel / Newmont": "_dtKCh5CjRws0ai8H",
    # ... 6 clientes totales
}
CLIENTE_TO_WHATSAPP_GROUP = {
    "Antamina": "Antamina",
    # ... mapeos a nombres de grupos
}
```

**APIs configuradas:**
- `RSS_API_KEY` / `RSS_API_SECRET` - rss.app
- `OPENAI_API_KEY` - Clasificación por IA
- `DATABASE_URL` - PostgreSQL (opcional)
- `WHATSAPP_PROVIDER` - Tipo de envío

---

### **rss_fetcher.py** — Extractor de Noticias
**Responsabilidad:** Obtiene posts desde rss.app API

**Clases:**
- `RSSFetcher` - Adaptador compatible con FacebookScraper

**Métodos principales:**
- `get_bundle_items(bundle_id, limit=50)` - Trae un bundle de rss.app
- `_fetch_posts(client)` - Obtiene posts normalizados de un cliente
- `_normalize_post(item, client)` - Convierte item RSS a formato interno
- `clear_cache()` - Limpia cache entre ciclos

**Formato normalizado:**
```python
{
    "text": "Título\n\nDescripción",      # Para clasificar
    "image_url": "https://...",           # URL de imagen
    "url": "https://...",                 # Link original
    "date": "2026-05-16T...",             # Publicación
    "author": "Nombre",                   # Autor/fuente
    "is_video": False,
    "client": "Antamina",                 # Cliente derivado
}
```

**Cache:**
- Local `_bundle_items_cache` evita re-consultas API en el mismo ciclo
- 50 items por bundle/ciclo

---

### **classifier.py** — Clasificación con IA (OpenAI)
**Responsabilidad:** Analiza contenido y genera alertas

**Clase:**
- `AlertClassifier` - Interfaz a Claude/GPT

**Genera (por post):**
```python
{
    "titulo": "Extracto del post",
    "resumen_whatsapp": "Resumen breve",
    "nivel": "CRIT|ALRT|INFO|IGNORAR",      # Severidad
    "categoria": "VIOLENCIA",               # Categoría
    "subcategoria": "HOMICIDIO",            # Subcategoría
    "palabras_clave": ["Lima", "Sicarios"], # Tags
    "departamento": "LIMA",                 # Región
    "provincia": "LIMA",
    "distrito": "SAN JUAN DE LURIGANCHO",
    "cliente": "Antamina",                  # Cliente asignado
}
```

**Niveles:**
- `CRIT` 🔴 - Crítico (seguridad inmediata)
- `ALRT` 🟡 - Alerta (requiere atención)
- `INFO` 🟢 - Información (noticioso)
- `IGNORAR` - No enviar

---

### **deduplicator.py** — Evita Duplicados
**Responsabilidad:** Previene enviar noticias repetidas

**Tipos de deduplicación:**
1. **Por URL exacta** - Misma noticia del mismo link
2. **Por similitud** - Mismo evento (dept + subcategoria)
3. **Jaccard 65%** - Similitud de contenido en últimas 12h

**Base de datos:**
- Tabla `processed` - URLs enviadas
- Tabla `alert_history` - Historial de alertas (dedup nivel 2)

**Fallback (sin BD):**
- Usa comparación local en memoria

---

### **formatter.py** — Formateo de Mensajes
**Responsabilidad:** Genera textos para WhatsApp y Google Sheets

**Formatos:**
1. **`format_whatsapp()`** - Mensaje para WhatsApp
   ```
   *ALRT 🟡 16-05-26 ANCASH - DETENCION - SEGURIDAD*
   Descripcción del evento...
   - FUENTE: https://tinyurl.com/...
   ```

2. **`format_tabla()`** - Indexación para BD
   ```
   16-05-26_ANCASH_HUARAZ_HUARAZ_DELITO_ROBO_Titular short
   ```

3. **`format_sheets_row()`** - Fila para Google Sheets
   - Timestamp, email, cliente, categoría, link...

**Funcionalidad extra:**
- `shorten_url()` - Convierte URLs largas a TinyURL
- Manejo de CamelCase → palabras legibles

---

### **router.py** — Routing a Grupos WhatsApp
**Responsabilidad:** Determina a qué grupos enviar cada alerta

**Lógica:**
```python
cliente = "Antamina"
grupos = router.get_whatsapp_groups(cliente)
# → ["Antamina"]  (desde CLIENTE_TO_WHATSAPP_GROUP)
```

**Fallback:**
- Si cliente no existe → busca por coincidencia parcial
- Si nada coincide → no envía, solo loguea warning

---

### **sender_whatsapp.py** — Envío a WhatsApp
**Responsabilidad:** Envía mensajes a grupos de WhatsApp

**Proveedores:**
1. **`bridge`** - Node.js local (whatsapp-web.js)
   - URL: `http://localhost:3000/send`
   - Requiere QR autenticado
   - Envía texto + imagen + multimedia

2. **`simulate`** - Modo simulación
   - Solo loguea, no envía
   - Útil para testing

**Request al bridge:**
```json
{
    "group_name": "Antamina",
    "message": "*ALRT 🟡 16-05-26...",
    "image_url": "https://..."
}
```

---

### **sender_sheets.py** — Envío a Google Sheets
**Responsabilidad:** Registra alertas en Google Sheets

**Funcionalidad:**
- Append row a hoja de cálculo
- Columnas: timestamp, email, cliente, nivel, categoría...
- Histórico de todas las alertas enviadas

---

### **alert_queue.py** — Cola de Alertas
**Responsabilidad:** Gestiona cola de envío

**BD Table: `alert_queue`**
```
id | group | message | image_url | sent | alert_json
1  | Antamina | *ALRT 🟡... | https://... | 0 | {...}
```

**Métodos:**
- `push()` - Añade alerta a cola
- `get_pending_by_ids()` - Recupera alertas sin enviar
- `mark_sent()` - Marca como enviada
- `get_recent_unsent()` - Para retry

---

## 🌐 Módulos Externos

### **whatsapp_bridge/** — Servidor Node.js
**Responsabilidad:** Conecta WhatsApp real vía whatsapp-web.js

**Archivo: `server.js`**
- Puerto: 3000
- Endpoint: `POST /send`
- Descarga imágenes desde URLs HTTP/HTTPS
- Convierte a base64 si es necesario
- Autentica con QR (primera ejecución)

**Requisitos:**
```bash
npm install
node server.js
# Escanear QR con WhatsApp
```

---

## 📋 Archivos de Configuración

### **requirements.txt** — Dependencias Python
- Para instalar: `pip install -r requirements.txt`

### **run_system.bat** — Control Windows
- Inicia ambos procesos (bridge + main) en paralelo
- Uso: `run_system.bat`

### **.env** — Variables de Entorno
- Almacena claves secretas
- Nunca commitear a Git

---

## 🔄 Flujo de Datos Inter-Módulos

```
rss_fetcher._fetch_posts()
    ↓ [posts normalizados]
classifier.classify()
    ↓ [alert dict]
deduplicator.is_duplicate_alert()
    ↓ [bool: es duplicado?]
formatter.format_whatsapp()
    ↓ [mensaje formateado]
router.get_whatsapp_groups()
    ↓ [lista de grupos]
alert_queue.push()
    ↓ [encolado]
flush_all_pending()
    ↓
sender_whatsapp.send()
    ↓
whatsapp_bridge (node server.js)
    ↓ [descarga imagen]
WhatsApp API
    ↓
Grupo real de WhatsApp
```

---

## ⚙️ Parámetros Ajustables

| Parámetro | Archivo | Efecto |
|-----------|---------|--------|
| `INTERVAL_MINUTES` | config.py | Frecuencia polling (5 min recomendado) |
| `WHATSAPP_PROVIDER` | config.py | "bridge" (real) o "simulate" (testing) |
| `RSS_BUNDLES` | config.py | Clientes y sus bundle IDs |
| `CLIENTE_TO_WHATSAPP_GROUP` | config.py | Mapeo cliente → grupo WhatsApp |
| `OPENAI_API_KEY` | .env | Clave para clasificación por IA |
| `DATABASE_URL` | .env | PostgreSQL/SQLite para persistencia |

---

**Última actualización:** 16 de Mayo, 2026
