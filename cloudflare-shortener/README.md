# Acortador propio (Cloudflare Workers)

Reemplaza a clck.ru/da.gd/is.gd con un acortador 100% tuyo, gratis, sin vista
previa y sin depender de servicios gratuitos ajenos que se caen o bloquean.

## Setup (una sola vez, ~10 min, sin instalar nada)

1. Crea una cuenta gratis en https://dash.cloudflare.com/sign-up (no pide tarjeta).
2. En el menú lateral: **Workers & Pages** → **Create** → **Create Worker**.
   - Ponle un nombre, ej. `protecta-shortener`.
   - Click **Deploy** (deja el código de ejemplo, lo vamos a reemplazar).
3. Click **Edit code**. Borra todo y pega el contenido de `worker.js` (este
   mismo folder). Click **Save and Deploy**.
4. En la pestaña **Settings** del Worker → **Variables**:
   - **KV Namespace Bindings** → **Add binding**:
     - Variable name: `LINKS`
     - KV namespace: **Create a namespace** → nómbralo `protecta_links` → Save.
   - **Environment Variables** → **Add variable**:
     - Name: `API_TOKEN`
     - Value: cualquier texto secreto largo que inventes (ej. genera uno en
       https://1password.com/password-generator/, 32+ caracteres).
     - Click el ícono de "Encrypt" para que quede como secret.
5. Copia la URL pública de tu Worker (aparece arriba, algo como
   `https://protecta-shortener.tu-usuario.workers.dev`).

## Conectarlo al sistema

Agrega estas dos líneas a tu `.env`:

```
SHORTENER_URL=https://protecta-shortener.tu-usuario.workers.dev
SHORTENER_TOKEN=el-mismo-secreto-que-pusiste-en-API_TOKEN
```

Reinicia el sistema (`run_system.bat`) y listo — `formatter.py` lo usa como
primera opción, con clck.ru/da.gd/is.gd como respaldo si por algo no está
configurado o falla.

## Probarlo manualmente (opcional)

```bash
curl -X POST https://tu-worker.workers.dev/create \
  -H "Authorization: Bearer TU_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"url":"https://www.bbc.com/mundo"}'
```

Debería responder `{"short_url":"https://tu-worker.workers.dev/AbC123"}`.
Abrir ese link en el navegador debe llevarte directo a bbc.com/mundo, sin
ninguna página intermedia.
