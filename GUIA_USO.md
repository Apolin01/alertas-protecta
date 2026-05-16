# 🚀 Sistema Alertas Protecta - Guía de Uso

## 📋 Requisitos Previos

1. **Node.js 14+** - Para el bridge de WhatsApp
2. **Python 3.8+** - Para el procesamiento de alertas
3. **npm** - Gestor de paquetes Node (incluido con Node.js)
4. **Dependencias instaladas:**
   ```bash
   # Python
   pip install -r requirements.txt
   
   # Node.js (solo primera vez)
   cd whatsapp_bridge
   npm install
   cd ..
   ```

---

## ⚡ Ejecución Rápida

### 🟢 OPCIÓN 1: Ejecución Automática (RECOMENDADO)

```bash
run_system.bat
```

Esto abre **dos ventanas** automáticamente:
- **Ventana 1**: WhatsApp Bridge (Node.js)
- **Ventana 2**: Sistema de Alertas (Python)

¡Listo! El sistema comienza a procesar y enviar mensajes automáticamente.

---

### 🟠 OPCIÓN 2: Ejecución Manual (dos terminales)

Si prefieres hacerlo manualmente o usar PowerShell/Terminal:

**Terminal 1 - Bridge de WhatsApp:**
```bash
cd whatsapp_bridge
node server.js
```
Espera a que veas:
```
✓ WhatsApp Bridge escuchando en puerto 3000
```

**Terminal 2 - Sistema de Alertas:**
```bash
python main.py
```

---

## 🧪 Testing Rápido

Para **probar cambios sin procesar todos los bundles** (mucho más rápido):

```bash
# Modo simulación (sin enviar a WhatsApp)
python test_quick.py

# Modo envío real (solo 3 items que van a WhatsApp)
python test_quick.py --send
```

**Ventajas:**
- ⚡ 3 items por bundle (en lugar de 50)
- 📊 Resultado en ~30 segundos
- 🔍 Ideal para debugging

---

## 📊 Opciones de Configuración

### Cambiar modo WhatsApp

En `config.py`:

```python
# SIMULACIÓN (solo logs, perfecto para testing)
WHATSAPP_PROVIDER = "simulate"

# ENVÍO REAL (requiere bridge corriendo)
WHATSAPP_PROVIDER = "bridge"
```

### Cambiar frecuencia de polling

En `config.py`:

```python
INTERVAL_MINUTES = 5  # Cada 5 minutos procesa todos los bundles
```

### Cambiar bundles procesados

En `config.py`:

```python
RSS_BUNDLES = {
    "Antamina": "_vv3HkItEzKqytLHk",
    "Bechtel / Newmont": "_dtKCh5CjRws0ai8H",
    # ... agregar o remover según necesites
}
```

---

## 🔧 Troubleshooting

### ❌ Error: "No se puede conectar al bridge"

**Solución:**
1. Asegurate que `node server.js` esté corriendo en Terminal 1
2. Verifica que el puerto 3000 no esté en uso:
   ```bash
   netstat -tuln | findstr :3000   # En Windows PowerShell
   ```

### ❌ Error: "OPENAI_API_KEY no está configurada"

**Solución:** 
Agrega a tu `.env`:
```
OPENAI_API_KEY=sk-...tu-key-aqui...
```

O en `config.py`:
```python
OPENAI_API_KEY = "sk-...tu-key-aqui..."
```

### ❌ Las noticias NO tienen imágenes

**Solución:**
Ejecuta `test_quick.py --send` para verificar. Si las imágenes siguen sin aparecer:
1. Verifica que `rss_fetcher.py` esté usando `"image_url"` (no `"thumbnail"`)
2. Revisa los logs para ver si hay errores de URL

### ❌ El sistema se detiene después de un ciclo

**Solución:**
`main.py` está diseñado para **correr continuamente**. Si se detiene:
1. Revisa los logs en `alertas.log`
2. Verifica errores de conexión a rss.app
3. Ejecuta `python main.py` nuevamente

---

## 📝 Flujo de Datos

```
┌─────────────────┐
│  RSS Feed API   │
│   (rss.app)     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  RSS Fetcher    │
│ (extrae 50 items)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Classifier (AI) │
│ (nivel, región) │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Deduplicator   │
│  (evita dups)   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Formatter     │
│(formato WhatsApp)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│    Router       │
│ (qué grupo)     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  WhatsApp Bridge│
│ (node server.js)│
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  WhatsApp Grupos│
│  (mensajes)     │
└─────────────────┘
```

---

## 📦 Estructura de Archivos

```
alertas-protecta-bryan-branch/
├── run_system.bat              ← 🟢 EJECUTAR ESTO
├── test_quick.py               ← Para testing rápido
├── main.py                      ← Orquestador principal
├── config.py                    ← Configuración (bundles, API keys)
├── rss_fetcher.py               ← Extrae noticias de RSS
├── classifier.py                ← Clasificación con IA
├── deduplicator.py              ← Evita duplicados
├── formatter.py                 ← Formato para WhatsApp
├── router.py                    ← Routing a grupos
├── sender_whatsapp.py           ← Envío real/simulado
├── alert_queue.py               ← Cola de alertas
├── whatsapp_bridge/
│   ├── server.js                ← Bridge Node.js
│   ├── package.json
│   └── ...
└── README.md                    ← Este archivo
```

---

## 🎯 Casos de Uso

### 1️⃣ Testing rápido de un cambio
```bash
python test_quick.py
```
(ver resultado en 30 segundos)

### 2️⃣ Testing con envío real a WhatsApp
```bash
# Primero asegurate que el bridge esté corriendo
run_system.bat
# O manualmente: cd whatsapp_bridge && node server.js

# Luego en otra terminal:
python test_quick.py --send
```

### 3️⃣ Producción (procesar continuamente)
```bash
run_system.bat
```
(el sistema procesa cada 5 minutos indefinidamente)

### 4️⃣ Solo simulación (sin bridge)
```bash
# Cambiar en config.py: WHATSAPP_PROVIDER = "simulate"
python main.py
```
(los mensajes solo se muestran en logs)

---

## 🔒 Seguridad

**NUNCA publicar:**
- `RSS_API_KEY` y `RSS_API_SECRET` (en config.py)
- `OPENAI_API_KEY` (en .env)
- `DATABASE_URL` (en .env)
- Credenciales de WhatsApp

**Recomendación:**
Usa variables de entorno en lugar de hardcodear:
```python
import os
API_KEY = os.environ.get("RSS_API_KEY", "default_value")
```

---

## 📞 Soporte

Si algo no funciona:
1. Revisa los logs en `alertas.log`
2. Ejecuta `test_quick.py` para aislar el problema
3. Verifica que todas las dependencias estén instaladas
4. Asegurate que las APIs estén disponibles (rss.app, OpenAI)

---

**Última actualización:** 16 de Mayo, 2026
**Sistema:** Alertas Protecta v2.0 (RSS Feed)
