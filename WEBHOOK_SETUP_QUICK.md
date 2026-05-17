# ⚡ Quick Start — Webhooks

> **TL;DR:** Del polling cada 5 minutos a notificaciones en tiempo real

## 🚀 Setup en 5 minutos

### Paso 1: Instalar Flask

```bash
pip install flask
```

### Paso 2: Configurar .env

```bash
# Copia .env.webhooks.example a .env y actualiza:
WEBHOOKS_ENABLED=true
WEBHOOK_HOST=0.0.0.0
WEBHOOK_PORT=5000
```

### Paso 3: Iniciar main.py

```bash
python main.py
```

**Output esperado:**
```
[WEBHOOKS] Iniciando servidor webhook...
[WEBHOOKS] ✓ Servidor escuchando en 0.0.0.0:5000
```

### Paso 4: Configurar en rss.app

1. Login: https://rss.app/dashboard
2. **Settings → Webhooks → New Webhook**
3. **URL:** `http://tuservidor.com:5000/webhook`
   - **Localhost (testing):** `http://localhost:5000/webhook`
   - **Producción:** Reemplazar con IP/dominio público
4. **Seleccionar bundles:** Antamina, Bechtel, Clientes, etc.
5. **Save**

### Paso 5: Testear

```bash
python test_webhook.py
```

✓ **¡Listo!** Sistema en tiempo real activado.

---

## 📊 Comparación

| Métrica | Polling (Antes) | Webhooks (Ahora) |
|---------|:---------------:|:----------------:|
| Latencia | ~5 minutos | < 1 segundo |
| API Calls/hora | 12 | 0-5 |
| Tiempo real | ✗ | ✓ |
| Fallback automático | N/A | ✓ (opcional) |

---

## 🔍 Verificar que está funcionando

```bash
# Ver logs
tail -f alertas.log | grep WEBHOOK

# Esperar a que llegue una noticia a cualquiera de tus feeds RSS
# Resultado en logs:
# [WEBHOOK] ✓ evt_xxx | Items: 1 | Encolado
# [WEBHOOK] Clasificando: ...
# [ENVIO] ✓ Enviado a 'Antamina'
```

---

## ⚙️ Desactivar Webhooks

Si quieres volver a polling:

```bash
WEBHOOKS_ENABLED=false
```

---

## 📌 Notas Importantes

- ✅ Webhooks NO interrumpen el polling existente
- ✅ Deduplicación automática evita mensajes duplicados
- ✅ Los items encolados se procesan en el siguiente ciclo
- ⚠️ Si el servidor cae, usa fallback a polling

---

## 🚨 Troubleshooting

### "Connection refused"

```bash
# Verificar que puerto 5000 está disponible
netstat -ano | findstr :5000  # Windows
lsof -i :5000                  # Mac/Linux

# Si está ocupado, cambia el puerto:
WEBHOOK_PORT=5001
```

### "Bundle not found"

```bash
# Verifica que el feed_id en rss.app coincida con RSS_BUNDLES en config.py
# Ejemplo: _vv3HkItEzKqytLHk → Antamina
```

---

## 📚 Documentación Completa

Ver [WEBHOOKS.md](WEBHOOKS.md) para:
- Estructura detallada del webhook
- API endpoints completa
- Configuración avanzada
- Troubleshooting exhaustivo
- Monitoreo en producción

---

## 🎯 Próximos Pasos

1. ✓ Webhooks funcionando localmente
2. → Pruebas con rss.app real
3. → Desplegar en producción
4. → Monitoreo 24/7
5. → Optimizar alerts según feedback

