"""
webhook_relay/app.py — Relay minimo para recibir webhooks de rss.app en la nube.

No tiene NINGUNA logica de negocio (no clasifica, no conoce clientes/reglas):
solo recibe el POST de rss.app y lo guarda en memoria hasta que la PC local
lo venga a buscar via /pull (polling). Esto evita depender de ngrok — Railway
da una URL publica fija que no cambia entre despliegues.

La PC local sigue haciendo TODO el trabajo real (clasificacion, dedup, envio);
este servicio es solo un buzon intermedio porque la PC local no es alcanzable
desde internet directamente.
"""

import os
import time
import threading
from collections import deque

from flask import Flask, request, jsonify

app = Flask(__name__)

TOKEN = os.environ.get("RELAY_TOKEN", "")
MAX_ITEMS = 2000

_lock = threading.Lock()
_pending = deque(maxlen=MAX_ITEMS)


def _token_ok(req) -> bool:
    if not TOKEN:
        # Sin token configurado, no se puede validar — rechazar todo por seguridad.
        return False
    token = req.args.get("token") or req.headers.get("X-Relay-Token", "")
    return token == TOKEN


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "pending": len(_pending)}), 200


@app.route("/webhook", methods=["POST"])
def receive():
    """rss.app hace POST aca. La URL registrada en rss.app debe incluir
    ?client=<Nombre>&token=<RELAY_TOKEN> como query params."""
    if not _token_ok(request):
        return jsonify({"error": "unauthorized"}), 401

    client = request.args.get("client", "")
    try:
        payload = request.get_json(force=True, silent=False)
    except Exception:
        return jsonify({"error": "invalid json"}), 400

    with _lock:
        _pending.append({
            "client": client,
            "payload": payload,
            "received_at": time.time(),
        })

    return jsonify({"success": True}), 202


@app.route("/pull", methods=["GET"])
def pull():
    """La PC local llama esto cada pocos segundos para recoger lo acumulado
    y vaciar el buzon. Requiere ?token=<RELAY_TOKEN>."""
    if not _token_ok(request):
        return jsonify({"error": "unauthorized"}), 401

    with _lock:
        items = list(_pending)
        _pending.clear()

    return jsonify({"items": items, "count": len(items)}), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
