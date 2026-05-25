# Flujo General del Sistema — Alertas Protecta 2026

**Última actualización:** 24 de Mayo, 2026

---

## Diagrama de Flujo Completo

```
┌─────────────────────────────────────────────────────────────────┐
│                  ALERTAS PROTECTA PERU 2026                     │
│             RSS Multi-Bundle + Webhooks en Tiempo Real          │
└─────────────────────────────────────────────────────────────────┘

                         ┌─────────────────┐
                         │  INICIO (main)  │
                         └────────┬────────┘
                                  │
                    ┌─────────────▼────────────┐
                    │  Loop cada 5 min (config) │
                    └─────────────┬────────────┘
                                  │
                    ┌─────────────▼────────────┐
                    │  fetcher.clear_cache()    │  ← Noticias frescas cada ciclo
                    └─────────────┬────────────┘
                                  │
                    ┌─────────────▼────────────┐
                    │  Procesar webhook_queue   │  ← Si hay webhooks pendientes
                    └─────────────┬────────────┘
                                  │
                    ┌─────────────▼────────────┐
                    │  retry_unsent()           │  ← Alertas fallidas (bridge caído)
                    └─────────────┬────────────┘
                                  │
                    ┌─────────────▼────────────────┐
                    │  get_clients_for_rss()        │
                    │  [Antamina, Cajamarca, ...]   │
                    └─────────────┬────────────────┘
                                  │
        ┌─────────────────────────┴──────────────────────────┐
        │ Para cada cliente (secuencial):                     │
        └─────────────────────────┬──────────────────────────┘
                                  │
                                  ▼
    ┌─────────────────────────────────────────────────────────┐
    │ rss_fetcher.fetch_posts("Antamina")                     │
    │ ├─ Mapea Antamina → "_vv3HkItEzKqytLHk" (bundle)       │
    │ ├─ GET rss.app/v1/bundles/{id}                          │
    │ ├─ Filtra: solo items con fecha, últimas 2 horas        │
    │ ├─ Normaliza cada item en formato estándar              │
    │ └─ Retorna lista de posts con text, url, date, etc.     │
    └──────────────────────────┬──────────────────────────────┘
                               │
                ┌──────────────▼──────────────┐
                │  process_page()             │
                │  Itera sobre posts          │
                └──────────────┬──────────────┘
                               │
        ┌──────────────────────┴──────────────────────┐
        │ Para cada post:                             │
        └──────────────────────┬──────────────────────┘
                               │
                               ▼
    ┌──────────────────────────────────────────────────┐
    │  DEDUP TEMPRANO (antes de IA)                    │
    │                                                  │
    │  deduplicator.already_processed(post)            │
    │  ├─ Hash de URL normalizada                      │
    │  ├─ Consulta tabla `processed` en PostgreSQL     │
    │  └─ Si ya vista → saltar (sin gastar tokens IA)  │
    │     Si nueva → mark_processed() + continuar      │
    └──────────────────────────┬───────────────────────┘
                               │
                               ▼
    ┌─────────────────────────────────────────────────────┐
    │ classifier.classify(post)                           │
    │                                                     │
    │ INPUT: {                                            │
    │   "text":        "Título + descripción",            │
    │   "source_page": "RSS Bundle",                      │
    │   "date":        "2026-05-24T...",                  │
    │ }                                                   │
    │                                                     │
    │ PROCESO:                                            │
    │ 1. Envía a OpenAI gpt-4o-mini (json_object mode)   │
    │ 2. Retry automático: rate limit (429), errores 5xx  │
    │ 3. Correcciones duras post-IA:                      │
    │    - fix_dept_by_city() → Chimbote → ANCASH         │
    │    - fix_client_by_dept() → ANCASH → Antamina       │
    │    - fix_client_by_provincia() → PISCO → "Pisco"    │
    │    - is_lima_valida() → filtra Lima urbana          │
    │    - Regla ubicación: CRIT/ALRT sin granularidad    │
    │      → nivel = IGNORAR                              │
    │                                                     │
    │ OUTPUT: alert dict completo                         │
    └──────────────────────────┬──────────────────────────┘
                               │
                ┌──────────────┴──────────────┐
                │                             │
         nivel == IGNORAR            nivel == ALRT/CRIT/INFO
                │                             │
           saltar post                        ▼
                               ┌──────────────────────────────┐
                               │ deduplicator.is_duplicate_alert() │
                               │                                    │
                               │  7 niveles (con _dedup_lock):      │
                               │  0   URL exacta → sent_alerts      │
                               │  0.5 Content hash → sent_alerts    │
                               │  1   Firma evento (lugar+keyword)  │
                               │  2.5 Mismo dept+prov+subcat 15min  │
                               │  3   Hash título + dept            │
                               │  4   Jaccard ≥35% / Leven ≥60%    │
                               │  5   Jaccard descripción ≥40%      │
                               │  6   IA semántica (GPT fallback)   │
                               └──────────────┬───────────────────────┘
                                              │
                        ┌─────────────────────┴──────────────────────┐
                        │                                             │
                 DUPLICADO → saltar                      NO DUPLICADO → continuar
                                                                      │
                                              ┌───────────────────────▼──────────────┐
                                              │ router.get_whatsapp_groups(cliente)   │
                                              │ (Antamina) → ["Antamina"]             │
                                              └───────────────────────┬──────────────┘
                                                                      │
                                              ┌───────────────────────▼──────────────┐
                                              │ formatter.format_whatsapp()           │
                                              │                                       │
                                              │ *ALRT 🟡 24-05-26 ANCASH HUARI       │
                                              │  SAN MARCOS - DETENCION - ROBO*      │
                                              │ Descripción del evento...             │
                                              │ - FUENTE: https://tinyurl.com/...    │
                                              └───────────────────────┬──────────────┘
                                                                      │
                                              ┌───────────────────────▼──────────────┐
                                              │ queue.push(group, msg, img, alert)   │
                                              │ deduplicator.mark_alert_sent(alert)  │
                                              └───────────────────────┬──────────────┘
                                                                      │
                                              ┌───────────────────────▼──────────────┐
                                              │ flush_all_pending()                  │
                                              │ sender_whatsapp.send()               │
                                              └───────────────────────┬──────────────┘
                                                                      │
                                                          ┌───────────┴──────────┐
                                                          │                      │
                                                  mode="bridge"          mode="simulate"
                                                          │                      │
                                              POST /send localhost:3000    Solo loguea
                                              node server.js                (testing)
                                                          │
                                              Grupo real de WhatsApp
```

---

## Línea de Tiempo de un Ciclo Completo (5 minutos)

| Tiempo | Acción | Duración estimada |
|--------|--------|-------------------|
| 00:00 | Inicio ciclo, `clear_cache()` | < 1s |
| 00:01 | Procesar webhooks en cola | 1-5s |
| 00:02 | `retry_unsent()` alertas fallidas | 1-10s |
| 00:05 | Fetch Antamina RSS (50 items, filtrar 2h) | 2-3s |
| 00:08 | Clasificar posts nuevos Antamina | 5-60s (según cantidad) |
| 00:10 | Enviar alertas Antamina a WhatsApp | 5-15s |
| 00:12 | Fetch + clasificar Bechtel/Newmont | ~mismo |
| ... | (4 clientes más) | ... |
| 04:50 | `queue.cleanup_old(days=2)` | < 1s |
| 05:00 | Esperar hasta completar el intervalo | — |

---

## Seguridad y Autenticación

### API RSS (rss.app)
```
Header: Authorization: Bearer {RSS_API_KEY}:{RSS_API_SECRET}
```

### OpenAI (clasificación)
```
Header: Authorization: Bearer {OPENAI_API_KEY}
```

### WhatsApp Bridge
```
Header: x-auth-token: {BRIDGE_TOKEN}
Validado por server.js en cada POST /send
```

### Webhooks entrantes
```
Header: X-Signature: HMAC-SHA256(payload, WEBHOOK_SECRET)
Validado por webhook_server.py si WEBHOOK_SECRET está configurado
```

### Google Sheets (si habilitado)
```
OAuth2 via Service Account (credentials.json)
Autenticado automáticamente por sender_sheets.py
```

---

## Persistencia y Base de Datos

### Tablas PostgreSQL

```sql
-- URLs ya vistas (dedup temprano — antes de IA)
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
    titulo_norm      TEXT,        -- Palabras tokenizadas para Jaccard
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

-- Cola de envío persistente
CREATE TABLE pending (
    id          SERIAL PRIMARY KEY,
    group_name  TEXT NOT NULL,
    message     TEXT NOT NULL,
    image_url   TEXT DEFAULT '',
    alert_json  TEXT DEFAULT '',
    created_at  TEXT NOT NULL,
    sent        INTEGER DEFAULT 0,
    sent_at     TEXT
);
```

### Limpieza automática
- `processed`: registros con más de 7 días → eliminados
- `sent_alerts`: registros fuera de la ventana dedup (48h) → eliminados
- `pending`: filas `sent=1` con más de 2 días → eliminadas

---

## Manejo de Errores

### API RSS no responde
- Timeout de 15 segundos por request
- Loguea error y continúa con el siguiente cliente
- No bloquea el ciclo completo

### Bridge de WhatsApp caído
- `sender_whatsapp.send()` retorna `False`
- Alerta queda en tabla `pending` con `sent=0`
- `retry_unsent()` la reintenta en cada ciclo siguiente (hasta 4 horas)
- Cuando el bridge vuelve, se envía automáticamente

### OpenAI rate limit (429)
- Espera el tiempo indicado en `retry-after` + 2s
- Hasta 4 reintentos con backoff progresivo
- Si agotan reintentos → loguea error y salta el post

### OpenAI error de red
- Espera 5s, 10s, 15s, 20s entre reintentos
- Mismo manejo para errores 5xx transitorios

### Clasificador retorna JSON inválido
- `json.JSONDecodeError` → loguea y salta el post
- Campos obligatorios faltantes → loguea y salta el post
- `palabras_clave` inválido → se rellena/recorta a exactamente 3 elementos

---

## Monitoreo y Logs

### Archivo `alertas.log`
```
2026-05-24 08:05:22 [INFO] CICLO 1 — 24-05-2026 08:05 PE
2026-05-24 08:05:23 [INFO] [RSS] Bundle _vv3... devolvió 12 items
2026-05-24 08:05:24 [INFO] [Antamina] Clasificando: #Ancash || ...
2026-05-24 08:05:30 [INFO] [Antamina] ALRT | Antamina | Seguridad
2026-05-24 08:05:31 [INFO] [Dedup] ✓ NIVEL 4 (Jaccard Título=0.38) → DUPLICADO
2026-05-24 08:05:32 [INFO] [COLA] Alerta guardada para 'Antamina'
2026-05-24 08:05:33 [INFO] Bridge OK (✓ con imagen) → Antamina
2026-05-24 08:05:45 [INFO] Ciclo 1 completo — Alertas enviadas: 2
```

### Qué monitorear diariamente
- Alertas procesadas vs enviadas (tasa de filtrado)
- Tasa de deduplicación (nivel que más activa)
- Errores de conexión a rss.app o OpenAI
- Fallos de envío al bridge (`sent=0` acumulados)

---

## Ejecución Recomendada

### Desarrollo / Testing
```bash
# Modo simulación (sin enviar a WhatsApp)
WHATSAPP_PROVIDER=simulate python main.py
```

### Producción Windows
```bash
run_system.bat
```

### Producción Linux (systemd)
```ini
# /etc/systemd/system/alertas-protecta.service
[Unit]
Description=Sistema de Alertas Protecta Peru
After=network.target

[Service]
Type=simple
WorkingDirectory=/ruta/al/proyecto
EnvironmentFile=/ruta/al/proyecto/.env
ExecStart=/usr/bin/python3 main.py
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable alertas-protecta
sudo systemctl start alertas-protecta
tail -f alertas.log
```

---

## Checklist Pre-Producción

- [ ] `.env` configurado con todas las claves reales
- [ ] `config.py` con bundle IDs correctos de rss.app
- [ ] `DATABASE_URL` apuntando a PostgreSQL activo
- [ ] WhatsApp bridge conectado (QR escaneado, `node server.js` corriendo)
- [ ] `WHATSAPP_PROVIDER = "bridge"` (no `"simulate"`)
- [ ] `OPENAI_API_KEY` configurado y con créditos
- [ ] `RSS_API_KEY` y `RSS_API_SECRET` rotados y configurados
- [ ] `BRIDGE_TOKEN` con valor secreto fuerte (no el default)
- [ ] Logs de un ciclo de prueba revisados
- [ ] Sistema ejecutando 24/7 (supervisord / systemd / nohup)

---

## Resolución de Problemas Comunes

| Síntoma | Causa probable | Solución |
|---------|---------------|----------|
| Sin mensajes en WhatsApp | Bridge caído | Reiniciar `node server.js`, escanear QR si caducó |
| Alertas sin imagen | image_url vacío o inaccesible | Normal si el post no tiene imagen; bridge envía solo texto |
| Clasificador lento o falla | Rate limit OpenAI | Esperar; el sistema reintenta automáticamente |
| Duplicados se envían | Umbral Jaccard muy alto | Bajar `JACCARD_THRESHOLD_TITULO` en deduplicator.py |
| Loop se congela | Timeout en API externa | Revisar `alertas.log`; reiniciar proceso |
| "DATABASE_URL no configurado" | `.env` incompleto | Agregar `DATABASE_URL` al `.env` |
| "Bundle not found" en webhook | `feed_id` no en `RSS_BUNDLES` | Agregar mapeo en `config.py → RSS_BUNDLES` |

---

**Sistema en ejecución:** 24/7  
**Verificar logs cada 24h:** `tail -100 alertas.log`
