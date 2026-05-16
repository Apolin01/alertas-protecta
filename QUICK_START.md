# ⚡ INICIO RÁPIDO - 3 Opciones

## 🟢 OPCIÓN 1: Ejecuta TODO automático (RECOMENDADO)

```bash
run_system.bat
```

**Listo.** Espera 10 segundos y verás dos ventanas abiertas. El sistema comienza a funcionar automáticamente.

---

## 🟠 OPCIÓN 2: Manual en 2 terminales

**Terminal 1:**
```bash
cd whatsapp_bridge
node server.js
```

**Terminal 2:**
```bash
python main.py
```

---

## 🟡 OPCIÓN 3: Testing RÁPIDO (3 items nada más)

```bash
python test_quick.py
```

✓ Resultado en **30 segundos**  
✓ Perfecto para probar cambios  
✓ Con `--send` envía de verdad a WhatsApp:
```bash
python test_quick.py --send
```

---

## 🆘 Si no ves nada en WhatsApp

1. **¿El bridge está corriendo?**
   ```bash
   # Terminal 1 debe mostrar:
   # ✓ WhatsApp Bridge escuchando en puerto 3000
   ```

2. **¿Hay errores en los logs?**
   - Revisa la terminal 2 (main.py) para ver errores

3. **¿La configuración está correcta?**
   ```bash
   # Verifica en config.py:
   WHATSAPP_PROVIDER = "bridge"  # (no "simulate")
   ```

---

## 📋 Archivos Principales

| Archivo | Uso |
|---------|-----|
| `run_system.bat` | 🟢 Ejecutar todo (RECOMENDADO) |
| `test_quick.py` | 🧪 Testing rápido |
| `main.py` | Programa principal (no tocar) |
| `GUIA_USO.md` | Documentación completa |

---

## ✅ Checklist Antes de Empezar

- [ ] Python 3.8+ instalado (`python --version`)
- [ ] Node.js instalado (`node --version`)
- [ ] Dependencias: `pip install -r requirements.txt`
- [ ] Dependencias Node: `cd whatsapp_bridge && npm install`
- [ ] `config.py` tiene `WHATSAPP_PROVIDER = "bridge"`
- [ ] `.env` tiene `OPENAI_API_KEY` (opcional pero recomendado)

---

## 💡 Próximas Tareas

Después que todo esté funcionando:

1. **Agregar más bundles** → edita `config.py` en `RSS_BUNDLES`
2. **Cambiar frecuencia** → `INTERVAL_MINUTES = 5` (cada 5 min)
3. **Agregar Base de Datos** → configura `DATABASE_URL` en `.env`

---

**¿Es la primera vez?** Lee [GUIA_USO.md](GUIA_USO.md) para documentación completa.
