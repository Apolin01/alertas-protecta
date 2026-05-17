# 🪝 Webhooks — Documentación Completa

## 📋 Índice

1. [¿Qué son los Webhooks?](#qué-son-los-webhooks)
2. [Instalación](#instalación)
3. [Configuración](#configuración)
4. [Estructura del Webhook](#estructura-del-webhook)
5. [API de Webhooks](#api-de-webhooks)
6. [Testing](#testing)
7. [Troubleshooting](#troubleshooting)

---

## ¿Qué son los Webhooks?

Los **webhooks** permiten que rss.app notifique al sistema en **tiempo real** cuando hay nuevas noticias, en lugar de hacer polling cada 5 minutos.

### Ventajas

| Polling (Actual)    | Webhooks (Nuevo)      |
|-------------------|-------------------|
| Consulta cada 5 min | Notificación inmediata |
| Retrasos de ~5 min | Latencia < 1s |
| Más uso API | Menos requests |
| Siempre activo | Solo cuando hay cambios |

---

## Instalación

### 1. Requisitos

```bash
pip install flask>=2.3.0
```

O actualiza todas las dependencias:

```bash
pip install -r requirements.txt
```

### 2. Estructura de Archivos

Se crean automáticamente 2 archivos:

```
alertas-protecta/
├── webhook_server.py       ← Servidor Flask (nuevo)
├── webhook_handler.py      ← Procesador de webhooks (nuevo)
├── main.py                 ← Integración (actualizado)
├── config.py               ← Configuración (actualizado)
└── requirements.txt        ← Dependencias (actualizado)
```

---

## Configuración

### Via Variables de Entorno (.env)

```bash
# Habilitar/Deshabilitar webhooks
WEBHOOKS_ENABLED=true

# Dirección del servidor webhook
WEBHOOK_HOST=0.0.0.0           # 0.0.0.0 = escucha en todas las interfaces
WEBHOOK_PORT=5000              # Puerto (asegúrate que esté abierto)

# Validación (opcional)
WEBHOOK_SECRET=tu_secreto_aqui # Si rss.app lo proporciona

# Mantener polling como fallback
WEBHOOKS_WITH_POLLING_FALLBACK=true
```

### Configuración en config.py

```python
WEBHOOKS_ENABLED = os.getenv("WEBHOOKS_ENABLED", "true").lower() == "true"
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST", "0.0.0.0")
WEBHOOK_PORT = int(os.getenv("WEBHOOK_PORT", "5000"))
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")
WEBHOOKS_WITH_POLLING_FALLBACK = os.getenv("WEBHOOKS_WITH_POLLING_FALLBACK", "true").lower() == "true"
```

---

## Estructura del Webhook

### Formato Recibido (desde rss.app)

```json
{
  "id": "evt_bbMGHz1x5T0UCEos",
  "type": "feed_update",
  "feed": {
    "id": "q5JyPDGJvSe6pDuN",
    "title": "Business News - CNN",
    "source_url": "https://www.cnn.com/business",
    "rss_feed_url": "https://rss.app/feeds/q5JyPDGJvSe6pDuN.xml",
    "description": "...",
    "icon": "https://...",
    "is_active": true
  },
  "data": {
    "items_new": [
      {
        "url": "https://...",
        "title": "Retail credit cards reach all-time high",
        "description_text": "When you're making a purchase...",
        "thumbnail": "https://...",
        "date_published": "2024-09-12T17:52:59.000Z",
        "authors": [
          { "name": "Jeanne Sahadi" }
        ]
      },
      { ... }
    ],
    "items_changed": []
  }
}
```

### Mapeo a Sistema Interno

El webhook se procesa así:

```
Webhook rss.app
    ↓
webhook_handler.process_webhook()
    ↓ (mapeo bundle_id → cliente)
Cliente identificado: "Antamina"
    ↓
Items normalizados:
{
  "id": "https://...",
  "url": "https://...",
  "title": "...",
  "description": "...",
  "image_url": "...",
  "date_published": "2024-09-12T...",
  "client": "Antamina",
  "text": "title\n\ndescription",
  ...}
    ↓
webhook_queue (buffer de 500 items)
    ↓
main.py → process_webhook_post()
    ↓ (igual que polling)
classifier.classify()
deduplicator.is_duplicate()
formatter.format_whatsapp()
sender_whatsapp.send()
```

---

## API de Webhooks

### Endpoint Principal

```
POST /webhook
```

**Headers:**
```
Content-Type: application/json
X-Signature: (opcional) HMAC-SHA256 si tienes secreto configurado
```

**Response Success (202 Accepted):**
```json
{
  "success": true,
  "event_id": "evt_bbMGHz1x5T0UCEos",
  "items_queued": 2
}
```

**Response Error (400):**
```json
{
  "success": false,
  "error": "Bundle ID no configurado"
}
```

### Health Check

```
GET /health
```

**Response:**
```json
{
  "status": "ok",
  "timestamp": "2026-05-17T10:30:45-05:00",
  "queue_size": 3,
  "stats": {
    "webhooks_received": 150,
    "webhooks_processed": 145,
    "webhooks_failed": 5,
    "items_received": 1200
  }
}
```

### Estadísticas

```
GET /webhook/stats
```

---

## Testing

### 1. Verificar que el servidor esté corriendo

```bash
curl -X GET http://localhost:5000/health
```

### 2. Enviar webhook de prueba

```bash
curl -X POST http://localhost:5000/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "id": "evt_test_001",
    "type": "feed_update",
    "feed": {
      "id": "_vv3HkItEzKqytLHk",
      "title": "Antamina News",
      "source_url": "https://example.com",
      "rss_feed_url": "https://rss.app/feeds/_vv3HkItEzKqytLHk.xml",
      "description": "Test",
      "icon": "https://example.com/icon.png",
      "is_active": true
    },
    "data": {
      "items_new": [
        {
          "url": "https://example.com/news1",
          "title": "Test News",
          "description_text": "Esta es una noticia de prueba",
          "thumbnail": "https://example.com/image.jpg",
          "date_published": "2026-05-17T10:00:00Z",
          "authors": [
            { "name": "Test Author" }
          ]
        }
      ],
      "items_changed": []
    }
  }'
```

**Response esperada:**
```json
{
  "success": true,
  "event_id": "evt_test_001",
  "items_queued": 1
}
```

### 3. Monitorear logs

```bash
tail -f alertas.log | grep WEBHOOK
```

Output esperado:
```
2026-05-17 10:15:23 [INFO] [WEBHOOK] ✓ evt_test_001 | Feed: Antamina News | Cliente: Antamina | Items: 1
```

---

## Configurar en rss.app

### 1. Login en rss.app

https://rss.app/dashboard

### 2. Ir a Webhooks

Settings → Webhooks

### 3. Crear Webhook

- **Event Type:** Feed Update
- **Webhook URL:** `http://tuservidor.com:5000/webhook`
  - Si es local/testing: `http://localhost:5000/webhook`
  - Si está en producción: reemplaza con IP pública/dominio
  
- **Secret (opcional):** Tu secreto para validación HMAC
  - Si lo configuras: copia el mismo valor en `.env` como `WEBHOOK_SECRET`

### 4. Seleccionar Feeds

Selecciona los bundles/feeds para los que quieres webhooks:
- ✓ Antamina
- ✓ Bechtel / Newmont
- ✓ Clientes Sur
- ✓ etc.

### 5. Test

Haz clic en "Test Webhook" para enviar un evento de prueba

---

## Modos de Operación

### Modo 1: Solo Webhooks (Recomendado para Producción)

```bash
# .env
WEBHOOKS_ENABLED=true
WEBHOOKS_WITH_POLLING_FALLBACK=false
USE_RSS_FEED=true
```

- ✓ Tiempo real
- ✓ Menos consumo de API
- ⚠ Si el webhook server cae, no recibe alertas
- **Solución:** Configura uptime monitoring

### Modo 2: Webhooks + Polling Fallback (Recomendado para Testing)

```bash
# .env
WEBHOOKS_ENABLED=true
WEBHOOKS_WITH_POLLING_FALLBACK=true
USE_RSS_FEED=true
```

- ✓ Tiempo real con webhooks
- ✓ Fallback a polling cada 5 min si hay problemas
- ✗ Más consumo de API (pero con dedup automático)
- **Ideal para:** Transición o entorno de staging

### Modo 3: Solo Polling (Como Antes)

```bash
# .env
WEBHOOKS_ENABLED=false
USE_RSS_FEED=true
```

- ✓ Compatible con arquitectura actual
- ✗ Retrasos de ~5 min
- ✗ Más requests a API

---

## Troubleshooting

### ❌ "webhook_server no disponible"

**Problema:** Flask no instalado

**Solución:**
```bash
pip install flask>=2.3.0
```

---

### ❌ "Connection refused" en POST /webhook

**Problema:** Servidor no está escuchando

**Solución:**
```bash
# Verificar que el puerto no esté en uso (Windows)
netstat -ano | findstr :5000

# O Linux
lsof -i :5000

# Verificar que main.py está corriendo
python main.py
```

---

### ❌ Webhooks recibidos pero no procesados

**Problema:** main.py está corriendo pero queue no se procesa

**Causas posibles:**
1. `WEBHOOKS_ENABLED=false` en .env
2. main.py no tiene la integración (actualizar)
3. Semáforo de IA congestionado

**Debug:**
```bash
curl http://localhost:5000/webhook/stats
# Si queue_size > 0, items están encolados
```

---

### ❌ "Bundle ID no encontrado"

**Problema:** Feed enviado no está en `RSS_BUNDLES`

**Causa:** Bundle no configurado en config.py

**Solución:**
```python
# Agregar en config.py
RSS_BUNDLES = {
    "MiNuevoBunde": "_abcdef12345",  # Obtener ID de rss.app
}
```

---

### ❌ Firma HMAC inválida

**Problema:** rss.app rechaza conexión por validación

**Solución:**
1. Obtener el secreto de rss.app
2. Guardarlo en .env:
   ```
   WEBHOOK_SECRET=tu_secreto_proporcionado_por_rssfeed
   ```
3. Reiniciar main.py

---

### ❌ Retrasos en procesamiento

**Síntoma:** Webhooks recibidos pero clasificación lenta

**Causa:** Semáforo IA (`_ai_semaphore`) congestionado

**Solución:**
- Reducir `INTERVAL_MINUTES` (polling menos frecuente)
- O aumentar capacidad de clasificación paralela
- O usar modelo IA más rápido

---

## Monitoreo

### Logs Relevantes

```bash
# Ver todos los webhooks
grep WEBHOOK alertas.log

# Ver webhooks exitosos
grep "✓" alertas.log | grep WEBHOOK

# Ver errores de webhooks
grep ERROR alertas.log | grep WEBHOOK

# Ver cola de webhooks
grep "items_queued" alertas.log
```

### Endpoint de Estadísticas

```bash
# Cada 30s obtener stats de webhooks
watch -n 30 'curl -s http://localhost:5000/webhook/stats | jq .'
```

---

## Flujo Completo (Diagrama)

```
rss.app
  ↓ (evento en tiempo real)
  
POST /webhook
  ├── Validar firma (opcional)
  ├── Parsear JSON
  ├── webhook_processor.process_webhook()
  │   ├── Validar estructura
  │   ├── Mapear bundle_id → cliente
  │   ├── Normalizar items
  │   └── Retornar resultado
  ├── Encolar en webhook_queue
  └── Responder 202 Accepted
  
main.py (ciclo cada 5 min)
  ├── Procesar polling (si enabled)
  ├── process_webhook_queue()
  │   └── Por cada item en queue:
  │       ├── classifier.classify()
  │       ├── deduplicator.is_duplicate()
  │       ├── formatter.format_whatsapp()
  │       ├── router.get_whatsapp_groups()
  │       ├── queue.push()
  │       └── flush_all_pending()
  │           └── sender_whatsapp.send()
  └── Esperar 5 min para próximo ciclo
```

---

## ¿Preguntas?

Revisa:
1. `webhook_handler.py` - Lógica de procesamiento
2. `webhook_server.py` - Servidor Flask
3. `main.py` - Integración en loop principal
4. `alertas.log` - Logs detallados
