# Arquitectura del Sistema — Funcionalidad por Archivo

**Última actualización:** 24 de Mayo, 2026

---

## Módulos Principales

### `main.py` — Orquestador Central

Coordina todo el flujo de alertas en un loop continuo.

**Funciones clave:**
- `process_page(page_name, ...)` — Obtiene, clasifica y encola alertas de un cliente RSS
- `process_region(region, ...)` — Itera sobre clientes en modo RSS o páginas en modo scraper
- `retry_unsent(queue, wa_sender, dedup)` — Reintenta alertas fallidas por bridge caído
- `flush_all_pending(queued_ids, ...)` — Envía inmediatamente las alertas encoladas en el ciclo actual
- `run_forever()` — Loop principal (ciclo cada 5 minutos)

**Flujo por ciclo:**
1. Limpia cache RSS (`fetcher.clear_cache()`)
2. Procesa webhooks entrantes desde `webhook_queue`
3. Reintenta alertas `sent=0` de las últimas 4 horas
4. Itera sobre cada cliente RSS: obtiene posts → clasifica → deduplica → encola → envía
5. Limpia alertas enviadas antiguas (`queue.cleanup_old(days=2)`)

**Locks de concurrencia:**
- `_send_lock` — Un envío a la vez
- `_dedup_lock` — Dedup atómica (check + mark en el mismo bloque)
- `_ai_lock` — Una clasificación IA a la vez

---

### `config.py` — Configuración Centralizada

Almacena todos los parámetros del sistema. Se valida en `__init__()` al arrancar.

**Configuraciones importantes:**
```python
USE_RSS_FEED = True                    # Usar RSS en lugar de scraper Facebook
INTERVAL_MINUTES = 5                   # Polling cada 5 minutos
WHATSAPP_PROVIDER = "bridge"           # "bridge" o "simulate"
AI_PROVIDER = "openai"                 # Solo "openai" implementado actualmente

RSS_BUNDLES = {
    "Antamina":                     "_vv3HkItEzKqytLHk",
    "Bechtel / Newmont":            "_dtKCh5CjRws0ai8H",
    "Clientes Sur":                 "_vuHd6hNkLlFj0nPK",
    "Clientes Norte":               "_i5tst4lPDJ5oTSW4",
    "Pisco":                        "_XgBrvIyMIWm5YzLP",
    "Ninguno (Coyuntura Nacional)": "_pM02KT2QspbdR8os",
}

CLIENTE_TO_WHATSAPP_GROUP = {
    "Antamina": "Antamina",
    # ... mapeos nombre cliente → nombre de grupo WA
}
```

**Validaciones al arrancar (`__init__`):**
- `OPENAI_API_KEY` presente
- `RSS_API_KEY` y `RSS_API_SECRET` presentes si `USE_RSS_FEED=True`
- `BRIDGE_TOKEN` presente
- Consistencia entre `PAGE_TO_CLIENT`, `RSS_BUNDLES` y `CLIENTES_VALIDOS`

---

### `rss_fetcher.py` — Extractor de Noticias

Obtiene posts desde la API de rss.app. Adaptador compatible con `FacebookScraper`.

**Clase principal:** `RSSFetcher`

**Métodos:**
- `fetch_posts(client_or_bundle)` — Obtiene posts de un cliente (mapea a bundle ID) o bundle ID directo
- `_normalize_post(item, client)` — Convierte item RSS a formato interno
- `clear_cache()` — Limpia cache entre ciclos (llamado por `main.py` al inicio de cada ciclo)

**Formato normalizado de post:**
```python
{
    "text":        "Título\n\nDescripción",   # Para clasificar
    "image_url":   "https://...",             # URL de imagen (puede ser vacío)
    "url":         "https://...",             # Link original (Facebook)
    "date":        "2026-05-24T14:30:00Z",   # Fecha de publicación (ISO 8601)
    "author":      "Nombre del medio",        # Autor/fuente
    "source_page": "RSS Bundle",              # Para el prompt del clasificador
    "is_video":    False,
    "source":      "Antamina RSS",
    "bundle_id":   "_vv3HkItEzKqytLHk",
    "client":      "Antamina",
}
```

**Filtros aplicados:**
- Solo noticias con `date_published` presente (sin fecha → rechazar)
- Solo noticias de las últimas 2 horas (`max_age_hours=2`)
- Máximo 50 items por bundle por ciclo

**Cache:**
- `_bundle_items_cache` evita re-consultas API en el mismo ciclo
- Se limpia automáticamente al inicio de cada ciclo

---

### `classifier.py` — Clasificación con IA

Analiza el contenido de cada post y genera el objeto `alert` estructurado.

**Clase:** `AlertClassifier`

**Proveedor activo:** OpenAI (`gpt-4o-mini`, `temperature=0`, `response_format: json_object`)

> Solo OpenAI está implementado. `claude`, `gemini` y `groq` están documentados en config pero devuelven error si se configuran.

**Correcciones duras (post-IA):**
- `fix_dept_by_city()` — Corrige departamento según ciudad (ej. "Chimbote" → "ANCASH")
- `fix_client_by_dept()` — Corrige cliente según departamento inequívoco; fuerza IGNORAR si falta ubicación granular en CRIT/ALRT
- `fix_client_by_provincia()` — Corrección fina por provincia (ej. "PISCO" → cliente "Pisco")
- `is_lima_valida()` — Filtro Lima: solo acepta Barranca, Supe, Huaura, Huaral

**Output JSON por post:**
```python
{
    "nivel":            "CRIT|ALRT|INFO|IGNORAR",
    "cliente":          "Antamina",
    "rubro":            "Minería",
    "relevancia":       "Alto|Medio|Bajo",
    "tipo":             "Noticia|Comunicado|...",
    "region":           "ANCASH HUARI",
    "departamento":     "ANCASH",
    "provincia":        "HUARI",
    "distrito":         "SAN MARCOS",
    "categoria":        "Seguridad-Delincuencia",
    "subcategoria":     "Detención",
    "palabras_clave":   ["Detención", "Robo", "Ancash"],  # Siempre 3
    "titulo":           "Extracto del titular",
    "resumen_whatsapp": "Resumen breve del hecho",
    "tags":             ["..."],
    "source_url":       "https://...",
    "source_page":      "RSS Bundle",
}
```

---

### `deduplicator.py` — Evita Duplicados

Previene enviar la misma noticia dos veces. Usa PostgreSQL como backend.

**Clase:** `Deduplicator`

**7 niveles de verificación (en orden de rapidez):**

| Nivel | Método | Ventana |
|-------|--------|---------|
| 0 | URL exacta | 24h |
| 0.5 | Content hash exacto (dept+prov+subcat+keywords) | 24h |
| 1 | Firma de evento (ubicación+keyword+número) | 1h |
| 2.5 | Mismo dept+prov+subcategoria | 15 min |
| 3 | Hash de título normalizado | 24h |
| 4 | Jaccard título (≥35%) + Levenshtein (≥60%) | 24h |
| 5 | Jaccard descripción (≥40%) | 6h |
| 6 | IA semántica (GPT) — solo si similitud media 0.30-0.35 | 6h |

**Tablas PostgreSQL:**
```sql
-- URLs ya vistas (dedup temprano antes de IA)
CREATE TABLE processed (
    hash     TEXT PRIMARY KEY,
    url      TEXT,
    seen_at  TEXT
);

-- Alertas enviadas (dedup multi-nivel)
CREATE TABLE sent_alerts (
    id               SERIAL PRIMARY KEY,
    content_hash     TEXT,
    titulo_hash      TEXT,
    titulo_norm      TEXT,
    descripcion_norm TEXT,
    departamento     TEXT,
    provincia        TEXT,
    subcategoria     TEXT,
    cliente          TEXT,
    resumen          TEXT,
    url              TEXT,
    sent_at          TEXT,
    UNIQUE(titulo_hash, departamento)
);
```

**Dedup temprano (antes de IA):**
`already_processed()` verifica por hash de URL antes de llamar al clasificador. Si ya fue procesada, se omite sin gastar tokens IA. Se ejecuta con `_dedup_lock` para evitar race conditions en multithreading.

---

### `formatter.py` — Formateo de Mensajes

Genera los dos formatos de salida a partir del objeto `alert`.

**Formatos:**

1. **`format_whatsapp(alert, post, config)`** — Mensaje para WhatsApp
   ```
   *ALRT 🟡 24-05-26 ANCASH HUARI SAN MARCOS - DETENCION - ROBO*
   Policía detiene a cinco sujetos involucrados en asaltos en San Marcos.
   - FUENTE: https://tinyurl.com/xyz123
   ```

2. **`format_tabla(alert, post, config)`** — Indexación para BD
   ```
   24-05-26_ANCASH_HUARI_SAN MARCOS_Seguridad-Delincuencia_Detención-Robo-Ancash_Titular
   ```

3. **`format_sheets_row(alert, post, config)`** — Lista de celdas para Google Sheets

**Utilidades:**
- `shorten_url(url)` — Acorta via TinyURL (con fallback a URL original)
- `_normalize_ubication(dept, prov, dist, config)` — Normaliza ubicación contra `DEPT_PROV_DIST` de config
- `_strip_camel(text)` — Convierte CamelCase → PALABRAS SEPARADAS

---

### `router.py` — Routing a Grupos WhatsApp

Determina a qué grupos WhatsApp enviar cada alerta según el cliente clasificado.

**Lógica:**
```python
cliente = "Antamina"
grupos = router.get_whatsapp_groups(cliente)
# → ["Antamina"]  (desde CLIENTE_TO_WHATSAPP_GROUP en config)
```

Si el cliente no está en el mapeo exacto, intenta coincidencia parcial. Si no hay coincidencia, retorna `[]` y se loguea un warning.

---

### `sender_whatsapp.py` — Envío a WhatsApp

**Proveedores:**

1. **`bridge`** — Node.js local (whatsapp-web.js)
   - URL: `http://localhost:3000/send`
   - Headers: `x-auth-token: {BRIDGE_TOKEN}`
   - Envía texto + imagen (base64 si es necesario, max 400 KB)
   - Respuestas: 200 OK, 404 grupo no encontrado, 503 WA desconectado

2. **`simulate`** — Solo loguea, no envía (modo testing)

**Request al bridge:**
```json
{
    "group_name": "Antamina",
    "message":    "*ALRT 🟡 24-05-26...",
    "image_url":  "https://..."
}
```

---

### `sender_sheets.py` — Envío a Google Sheets

Registra alertas en la hoja `Tabla_Informacion` del Google Sheets configurado.

- Se activa solo si `SHEETS_ENABLED=true` y `SPREADSHEET_ID` está configurado
- Autenticación via Service Account (`credentials.json`)
- Crea la hoja si no existe, con las columnas correctas del Form

---

### `alert_queue.py` — Cola de Alertas

Cola persistente en PostgreSQL para alertas pendientes de envío.

**Tabla `pending`:**
```
id | group_name | message | image_url | alert_json | created_at | sent | sent_at
```

**Métodos:**
- `push(group, message, image_url, alert)` — Encola alerta, retorna ID
- `get_pending_by_ids(ids)` — Recupera alertas sin enviar por IDs del ciclo actual
- `mark_sent(alert_id)` — Marca como enviada
- `get_recent_unsent(max_age_hours=4)` — Para retry de bridge caído
- `cleanup_old(days=2)` — Limpia alertas enviadas antiguas

---

### `webhook_handler.py` — Procesador de Webhooks

Convierte el payload JSON de rss.app al formato interno de posts.

**Clase:** `WebhookProcessor`

**Validaciones:**
- Tipo del evento: solo `feed_update`
- Feed ID presente
- Mapeo `feed_id → cliente` via `RSS_BUNDLES` inverso

**Normaliza items** al mismo formato que `rss_fetcher._normalize_post()` para procesarlos con el mismo pipeline.

---

### `webhook_server.py` — Servidor Flask

Recibe webhooks de rss.app en un thread daemon.

**Endpoints:**
- `GET /health` — Estado del servidor y cola
- `POST /webhook` — Recibe eventos de rss.app
- `GET /webhook/stats` — Estadísticas de procesamiento

**Cola:** `webhook_queue` (máximo 500 items). Los webhooks se procesan en el siguiente ciclo de `main.py` via `process_webhook_queue()`.

---

## Flujo de Datos Inter-Módulos

```
rss_fetcher.fetch_posts()
    ↓ [posts normalizados]
deduplicator.already_processed()   ← DEDUP TEMPRANO (antes de IA)
    ↓ [posts no vistos]
classifier.classify()
    ↓ [alert dict]
deduplicator.is_duplicate_alert()  ← DEDUP MULTI-NIVEL (7 niveles)
    ↓ [no duplicado]
formatter.format_whatsapp()
    ↓ [mensaje formateado]
router.get_whatsapp_groups()
    ↓ [lista de grupos]
alert_queue.push()
    ↓ [encolado con ID]
deduplicator.mark_alert_sent()     ← REGISTRO para futuros ciclos
    ↓
flush_all_pending()
    ↓
sender_whatsapp.send()
    ↓
whatsapp_bridge (node server.js)
    ↓
Grupo real de WhatsApp
```

---

## Parámetros Ajustables

| Parámetro | Archivo | Efecto |
|-----------|---------|--------|
| `INTERVAL_MINUTES` | config.py | Frecuencia polling (5 min recomendado) |
| `WHATSAPP_PROVIDER` | config.py / .env | `"bridge"` (real) o `"simulate"` (testing) |
| `RSS_BUNDLES` | config.py | Clientes y sus bundle IDs de rss.app |
| `JACCARD_THRESHOLD_TITULO` | deduplicator.py | Umbral similitud título (0.35 = más agresivo) |
| `DEDUP_WINDOW_HOURS` | deduplicator.py | Ventana de dedup (24h por defecto) |
| `OPENAI_API_KEY` | .env | Clave para clasificación por IA |
| `DATABASE_URL` | .env | PostgreSQL para persistencia |
| `BRIDGE_TOKEN` | .env | Token de autenticación del bridge |
