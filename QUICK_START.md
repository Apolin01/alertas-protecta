# INICIO RÁPIDO — 3 Opciones

**Última actualización:** 24 de Mayo, 2026

---

## Opción 1: Todo automático (RECOMENDADO — Windows)

```bash
run_system.bat
```

Espera 10 segundos — abre dos ventanas y el sistema comienza a funcionar.

---

## Opción 2: Manual en 2 terminales

**Terminal 1 — WhatsApp Bridge:**
```bash
cd whatsapp_bridge
node server.js
```
Espera hasta ver: `✓ WhatsApp Bridge escuchando en puerto 3000`

**Terminal 2 — Sistema de Alertas:**
```bash
python main.py
```

---

## Opción 3: Solo Python (sin bridge — modo simulación)

Cambiar en `.env`:
```
WHATSAPP_PROVIDER=simulate
```

Luego:
```bash
python main.py
```

Los mensajes se muestran en logs pero **no se envían** a WhatsApp real.

---

## Si no ves nada en WhatsApp

**1. ¿El bridge está corriendo?**
```
# Terminal 1 debe mostrar:
✓ WhatsApp Bridge escuchando en puerto 3000
```

**2. ¿WhatsApp está conectado?**
```
# Al iniciar node server.js por primera vez, aparece un QR.
# Escanéalo con WhatsApp → Dispositivos Vinculados → Vincular dispositivo
```

**3. ¿El proveedor es `bridge` y no `simulate`?**
```bash
# En .env:
WHATSAPP_PROVIDER=bridge
```

**4. ¿Hay errores en los logs?**
```bash
# Ver últimas 50 líneas:
tail -50 alertas.log
```

---

## Archivos Principales

| Archivo | Función |
|---------|---------|
| `run_system.bat` | Ejecutar todo (RECOMENDADO) |
| `main.py` | Programa principal |
| `config.py` | Bundles RSS, clientes, mapeos |
| `.env` | Claves secretas (no commitear) |
| `alertas.log` | Logs del sistema |
| `GUIA_USO.md` | Documentación completa |

---

## Checklist Antes de Empezar

- [ ] Python 3.11+ instalado (`python --version`)
- [ ] Node.js 18+ instalado (`node --version`)
- [ ] Dependencias Python: `pip install -r requirements.txt`
- [ ] Dependencias Node: `cd whatsapp_bridge && npm install`
- [ ] `.env` tiene `OPENAI_API_KEY`
- [ ] `.env` tiene `DATABASE_URL` (PostgreSQL)
- [ ] `.env` tiene `RSS_API_KEY` y `RSS_API_SECRET`
- [ ] `.env` tiene `BRIDGE_TOKEN`
- [ ] `WHATSAPP_PROVIDER=bridge` en `.env`

---

## Comandos útiles para monitorear

```bash
# Ver logs en tiempo real
tail -f alertas.log

# Ver solo alertas enviadas
grep "Bridge OK\|SIMULADO" alertas.log | tail -20

# Ver solo duplicados detectados
grep "DUPLICADO\|NIVEL" alertas.log | tail -20

# Ver errores
grep "ERROR\|CRITICAL" alertas.log | tail -20
```

---

**¿Es la primera vez?** Lee [GUIA_USO.md](GUIA_USO.md) para documentación completa.  
**¿Problemas técnicos?** Ver tabla de resolución en [FLUJO_SISTEMA.md](FLUJO_SISTEMA.md).
