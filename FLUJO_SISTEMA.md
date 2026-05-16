# 🔄 Flujo General del Sistema - Alertas Protecta 2026

## 📊 Diagrama de Flujo Completo

```
┌─────────────────────────────────────────────────────────────────────┐
│                    ALERTAS PROTECTA PERU 2026                       │
│                        RSS MULTI-BUNDLE                             │
└─────────────────────────────────────────────────────────────────────┘

                           ┌─────────────────┐
                           │  INICIO (main)  │
                           └────────┬────────┘
                                    │
                    ┌───────────────┴────────────────┐
                    │  Loop cada 5 minutos (config) │
                    └───────────────┬────────────────┘
                                    │
                    ┌───────────────▼────────────────┐
                    │  get_clients_for_rss()        │
                    │  [Antamina, Cajamarca, ...]   │
                    └───────────────┬────────────────┘
                                    │
        ┌───────────────────────────┴───────────────────────────────┐
        │ Para cada cliente:                                         │
        │ (procesamiento secuencial, no paralelo)                   │
        └───────────────────────────┬───────────────────────────────┘
        │                           │
        ▼                           ▼
    ┌──────────────────────────────────────────────────────┐
    │ rss_fetcher._fetch_posts("Antamina")                │
    │ ├─ Mapea Antamina → "_vv3HkItEzKqytLHk" (bundle)  │
    │ ├─ Consulta API: rss.app/bundles/{id}              │
    │ ├─ Obtiene 50 posts/noticias máximo                │
    │ ├─ Normaliza cada post en formato estándar         │
    │ └─ Devuelve lista de posts con:                    │
    │    - text, url, image_url, date, author, etc.     │
    └──────────────────────────┬───────────────────────────┘
                               │
                ┌──────────────▼──────────────┐
                │  process_page()             │
                │  Itera sobre 50 posts       │
                └──────────────┬──────────────┘
                               │
        ┌──────────────────────┴──────────────────────┐
        │ Para cada post:                             │
        └──────────────────────┬──────────────────────┘
        │
        ▼
    ┌─────────────────────────────────────────────────────┐
    │ classifier.classify(post)                           │
    │                                                     │
    │ INPUT: {                                            │
    │   "text": "Título + descripción",                  │
    │   "image_url": "https://...",                      │
    │   "url": "https://...",                            │
    │   "author": "Nombre"                              │
    │ }                                                   │
    │                                                     │
    │ PROCESO:                                            │
    │ 1. Envía a OpenAI/Claude para análisis            │
    │ 2. Obtiene clasificación:                          │
    │    - Nivel: CRIT/ALRT/INFO/IGNORAR               │
    │    - Categoría: VIOLENCIA, DESASTRES...           │
    │    - Subcategoría: HOMICIDIO, TERREMOTO...        │
    │    - Ubicación: DEPARTAMENTO → PROVINCIA...       │
    │    - Cliente: ANTAMINA (detectado de región)      │
    │    - Palabras clave: TAGS                          │
    │                                                     │
    │ OUTPUT: alert dict con clasificación completa     │
    └─────────────────────────┬───────────────────────────┘
                              │
        ┌─────────────────────┴─────────────────────┐
        │                                           │
        ▼                                           ▼
    IGNORA (skip)                    ┌───────────────────────┐
    (IGNORAR)                        │ dedup.is_duplicated() │
                                     │ (Evita repetir)       │
                                     ├─────────────────────┐ │
                                     │ 1. URL exacta?  │ Skip  
                                     │ 2. Mismo evento?     │ │
                                     │ 3. Jaccard 65%?      │ │
                                     └───────────────────────┘
                                     │
                ┌────────────────────┴────────────────────┐
                │                                         │
                ▼ (No duplicado)                     ▼ (Duplicado)
            ┌──────────────────────────────┐    Skip + Log
            │ formatter.format_whatsapp()  │
            │                              │
            │ Genera mensaje legible:      │
            │ "                            │
            │ *ALRT 🟡 16-05-26 ANCASH - │
            │  DETENCION - SEGURIDAD*     │
            │                              │
            │ Resumen de la noticia...     │
            │ - FUENTE: https://tiny...   │
            │ "                            │
            └──────────────┬───────────────┘
                           │
            ┌──────────────▼──────────────┐
            │ router.get_whatsapp_groups()│
            │ (Antamina) → ["Antamina"]   │
            └──────────────┬──────────────┘
                           │
            ┌──────────────▼──────────────────────┐
            │ queue.push(group, message, img, +) │
            │ Encola para envío                    │
            └──────────────┬──────────────────────┘
                           │
            ┌──────────────▼──────────────────────────┐
            │ flush_all_pending()                    │
            │ (Al terminar el cliente)               │
            │                                        │
            │ Para cada grupo pendiente:             │
            │  ├─ wa_sender.send(group, msg, img)   │
            │  └─ (Si success) mark_sent()          │
            └──────────────┬───────────────────────────┘
                           │
        ┌──────────────────▼──────────────────────┐
        │ sender_whatsapp (2 modos)               │
        └──────────────────┬──────────────────────┘
                           │
        ┌──────────────────┴─────────────────────────────┐
        │                                                 │
        ▼ mode="bridge"                          ▼ mode="simulate"
    ┌──────────────────────────────────┐    ┌─────────────────────┐
    │ POST /send a localhost:3000      │    │ Solo loguea         │
    │                                  │    │ (testing)           │
    │ {                                │    │                     │
    │  "group_name": "Antamina",      │    │ Output:             │
    │  "message": "*ALRT 🟡...",      │    │ [SIMULADO → ...]    │
    │  "image_url": "https://imag..."  │    │                     │
    │ }                                │    └─────────────────────┘
    │                                  │
    │ server.js recibe:                │
    │ ├─ Descarga imagen (si URL)      │
    │ ├─ Convierte a base64            │
    │ ├─ Envia a WhatsApp Web API      │
    │ ├─ Busca grupo "Antamina"        │
    │ └─ Envía texto + imagen          │
    │                                  │
    │ Response:                         │
    │ {                                │
    │   "success": true,               │
    │   "group": "Antamina",           │
    │   "with_image": true             │
    │ }                                │
    └──────────────────┬───────────────┘
                       │
        ┌──────────────▼──────────────────┐
        │ WhatsApp Real                    │
        │ 💬 Mensaje enviado al grupo      │
        │ 🖼️  Con imagen adjunta           │
        └────────────────────────────────────┘
```

---

## ⏱️ Línea de Tiempo de una Ejecución Completa

### **Ciclo típico (5 minutos)**

| Tiempo | Acción | Duración |
|--------|--------|----------|
| 00:00 | `main.py` inicia loop | - |
| 00:01 | Obtiene posts de Antamina (50) | 2-3s |
| 00:02 | Clasifica con IA (2-3s cada) | ~80-100s |
| 00:03 | Deduplica y formatea | 5-10s |
| 00:04 | Envía a WhatsApp | 5-15s |
| 00:05 | Repite con Bechtel/Newmont | - |
| 00:10 | Repite con Clientes Sur | - |
| ... | ... (otros 6 clientes) | - |
| 05:00 | Completa ciclo, espera 5 min | - |
| 05:01 | Repite todo de nuevo | - |

---

## 🔐 Seguridad & Autenticación

### **1. API RSS (rss.app)**
```
Header: Authorization: Bearer {API_KEY}:{API_SECRET}
Cada request autenticado
```

### **2. OpenAI/Claude**
```
Header: Authorization: Bearer {OPENAI_API_KEY}
Usado en classifier.py
```

### **3. WhatsApp Bridge**
```
Header: x-auth-token: {BRIDGE_TOKEN}
Valida cada request POST /send
```

### **4. Google Sheets (si habilitado)**
```
OAuth2 con credenciales de servicio
sender_sheets.py autentica automáticamente
```

---

## 💾 Persistencia & Base de Datos

### **Tablas PostgreSQL/SQLite**

```sql
-- Alertas ya procesadas (dedup)
CREATE TABLE processed (
    id SERIAL,
    url TEXT UNIQUE,
    date_processed TIMESTAMP,
    client TEXT
);

-- Historial de alertas (dedup nivel 2)
CREATE TABLE alert_history (
    id SERIAL,
    dept TEXT,
    subcategoria TEXT,
    titulo TEXT UNIQUE,
    timestamp TIMESTAMP,
    similarity_hash TEXT
);

-- Cola de envío (si falla)
CREATE TABLE alert_queue (
    id SERIAL,
    group TEXT,
    message TEXT,
    image_url TEXT,
    sent BOOLEAN,
    alert_json JSON,
    created_at TIMESTAMP
);
```

### **Sin Base de Datos**
- SimpleDuplicateDetector en memoria
- Pierde historial entre reinicios
- Válido para testing

---

## 🚨 Manejo de Errores

### **Escenarios comunes**

#### 1. **API RSS no responde**
- ✗ Intenta conexión
- ⏱️ Timeout 15 segundos
- 📝 Loguea error
- ⏭️ Continúa con próximo cliente

#### 2. **Bridge de WhatsApp caído**
- ✗ POST /send falla
- 📝 Mensaje encolado en BD
- ⏰ `retry_unsent()` reintenta cada 5 min (hasta 4 horas)
- ✅ Cuando vuelve el bridge, envía automáticamente

#### 3. **Clasificador no responde**
- ✗ OpenAI timeout
- 📝 Loguea "Sin respuesta del clasificador"
- ⏭️ Salta el post

#### 4. **Imagen URL inaccesible**
- ✗ Descarga falla en bridge
- 📝 Envía solo texto, sin imagen
- ✅ Mensaje "con imagen=false"

---

## 🔄 Ciclos de Reintento

### **1. Retry de alertas sin enviar**
```python
retry_unsent()  # Cada 5 min
├─ Busca alertas con sent=0
├─ Máximo 4 horas atrás
└─ Intenta envio, actualiza sent=1
```

### **2. Reinicio de proceso**
Si `main.py` se congela O cae:
```bash
# Reinicia automáticamente (supervisord, systemd, etc.)
supervisorctl restart alertas_protecta
```

---

## 📈 Escalabilidad

### **Actual (single thread)**
- 1 cliente a la vez
- 50 posts/cliente
- ~2 min/cliente (con clasificación IA)
- **Total:** ~12 min para 6 clientes por ciclo

### **Paralelo (posible mejora)**
- Procesar N clientes en paralelo
- Reducer: -75% tiempo total
- Riesgo: rate limiting en OpenAI

---

## 📊 Monitoreo & Logs

### **Archivo principal: `alertas.log`**
```
2026-05-16 00:05:22 [INFO] [Antamina] Clasificando: #Ancash || ...
2026-05-16 00:05:30 [INFO] [Antamina] ALRT | Antamina | VIOLENCIA
2026-05-16 00:05:31 [INFO] [COLA] Alerta guardada para 'Antamina'
2026-05-16 00:05:32 [INFO] Bridge OK (con imagen) → Antamina
```

### **Métricas a revisar cada día**
- Alertas procesadas
- Tasa de deduplicación
- Errores en clasificación
- Fallos de envío a bridge

---

## 🚀 Ejecución Recomendada

### **Opción 1: Automática (Recomendado)**
```bash
run_system.bat
# O en Linux/Mac:
# chmod +x run_system.ps1 && pwsh run_system.ps1
```

### **Opción 2: Via supervisor (Producción)**
```ini
# /etc/supervisor/conf.d/alertas.conf
[program:alertas_bridge]
command=node /path/to/whatsapp_bridge/server.js
autostart=true
autorestart=true

[program:alertas_main]
command=python /path/to/main.py
autostart=true
autorestart=true
```

### **Opción 3: Docker (Futuro)**
```dockerfile
# Dockerfile (no incluido aún)
FROM python:3.10
# ... instalación de deps
CMD ["python", "main.py"]
```

---

## ✅ Checklist Pre-Producción

- [ ] `.env` configurado con todas las claves
- [ ] `config.py` con bundle IDs correctos
- [ ] WhatsApp conectado (QR escaneado en bridge)
- [ ] Base de datos PostgreSQL corriendo (si habilitado)
- [ ] `WHATSAPP_PROVIDER = "bridge"` (no "simulate")
- [ ] `OPENAI_API_KEY` configurado
- [ ] Test rápido ejecutado: `python test_quick.py --send`
- [ ] Revisados logs de `alertas.log`
- [ ] Sistema ejecutando 24/7 (supervisord/systemd/nohup)

---

## 📞 Resolución de Problemas

| Síntoma | Causa | Solución |
|---------|-------|----------|
| Sin mensajes a WhatsApp | Bridge caído | Reiniciar: `node server.js` |
| Alertas sin imagen | Image URL inaccesible | Verificar URL en logs |
| Clasificador lento | Rate limit OpenAI | Aumentar `time.sleep()` |
| Duplicados se envían | BD dedup desconectada | Verificar `DATABASE_URL` |
| Loop se congela | Timeout en API | Revisar `alertas.log` |

---

**Sistema en ejecución:** 24/7  
**Verificar logs cada 24h:** `tail -100 alertas.log`  
**Última actualización:** 16 de Mayo, 2026
