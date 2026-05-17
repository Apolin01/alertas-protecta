"""
webhook_server.py — Servidor Flask para recibir webhooks de rss.app
Se ejecuta en paralelo a main.py en un puerto separado (default: 5000)
"""

import os
import json
import logging
import threading
import time
from datetime import datetime, timezone, timedelta
from queue import Queue

from flask import Flask, request, jsonify

from webhook_handler import webhook_processor

log = logging.getLogger(__name__)

# Queue global para comunicarse con main.py
webhook_queue = Queue(maxsize=500)  # Buffer de hasta 500 webhooks


class WebhookServer:
    """
    Servidor Flask que:
    1. Recibe webhooks de rss.app
    2. Los procesa y valida
    3. Los encola para que main.py los consuma
    """
    
    def __init__(self, host: str = "0.0.0.0", port: int = 5000, 
                 secret: str = ""):
        self.app = Flask(__name__)
        self.host = host
        self.port = port
        self.secret = secret or os.environ.get("WEBHOOK_SECRET", "")
        self.stats = {
            "webhooks_received": 0,
            "webhooks_processed": 0,
            "webhooks_failed": 0,
            "items_received": 0,
        }
        
        self._setup_routes()
    
    def _setup_routes(self):
        """Configura rutas del servidor."""
        
        @self.app.route("/health", methods=["GET"])
        def health():
            """Health check endpoint."""
            return jsonify({
                "status": "ok",
                "timestamp": datetime.now(timezone(timedelta(hours=-5))).isoformat(),
                "queue_size": webhook_queue.qsize(),
                "stats": self.stats,
            }), 200
        
        @self.app.route("/webhook", methods=["POST"])
        def receive_webhook():
            """
            Endpoint principal para recibir webhooks.
            
            Expected headers:
            - Content-Type: application/json
            - (Opcional) X-Signature: HMAC-SHA256 de validación
            
            Expected JSON:
            {
                "id": "evt_...",
                "type": "feed_update",
                "feed": { ... },
                "data": { ... }
            }
            """
            try:
                # Log request info
                client_ip = request.remote_addr
                log.info(f"[WEBHOOK] Recibido desde {client_ip}")
                
                # Obtener payload
                raw_payload = request.get_data(as_text=True)
                
                # Validar firma (opcional)
                if self.secret:
                    signature = request.headers.get("X-Signature", "")
                    if not webhook_processor.validate_webhook_signature(
                        raw_payload, signature, self.secret
                    ):
                        log.warning(f"[WEBHOOK] Firma inválida desde {client_ip}")
                        return jsonify({"error": "Invalid signature"}), 401
                
                # Parsear JSON
                try:
                    payload = json.loads(raw_payload)
                except json.JSONDecodeError as e:
                    log.error(f"[WEBHOOK] JSON inválido: {e}")
                    return jsonify({"error": "Invalid JSON"}), 400
                
                # Procesar webhook
                result = webhook_processor.process_webhook(payload)
                
                self.stats["webhooks_received"] += 1
                
                if not result["valid"]:
                    self.stats["webhooks_failed"] += 1
                    log.warning(f"[WEBHOOK] Webhook inválido: {result['error']}")
                    return jsonify({
                        "success": False,
                        "error": result["error"]
                    }), 400
                
                # Encolar items para procesar
                if result["items_processed"] > 0:
                    event_data = {
                        "event_id": result["event_id"],
                        "feed_id": result["feed_id"],
                        "feed_title": result["feed_title"],
                        "client": result["client"],
                        "items_new": result["items_new"],
                        "items_changed": result["items_changed"],
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                    
                    try:
                        webhook_queue.put_nowait(event_data)
                        self.stats["webhooks_processed"] += 1
                        self.stats["items_received"] += result["items_processed"]
                        
                        log.info(
                            f"[WEBHOOK] ✓ Encolado: {result['items_processed']} items | "
                            f"Queue: {webhook_queue.qsize()}/{webhook_queue.maxsize}"
                        )
                        
                        return jsonify({
                            "success": True,
                            "event_id": result["event_id"],
                            "items_queued": result["items_processed"],
                        }), 202  # Accepted
                    
                    except Exception as e:
                        log.error(f"[WEBHOOK] Error encolando: {e}")
                        self.stats["webhooks_failed"] += 1
                        return jsonify({
                            "success": False,
                            "error": "Queue full or error"
                        }), 503
                else:
                    log.info(f"[WEBHOOK] Sin items para procesar")
                    return jsonify({
                        "success": True,
                        "event_id": result["event_id"],
                        "items_queued": 0,
                    }), 200
                
            except Exception as e:
                log.exception(f"[WEBHOOK] Error inesperado: {e}")
                self.stats["webhooks_failed"] += 1
                return jsonify({
                    "error": "Internal server error",
                    "detail": str(e)
                }), 500
        
        @self.app.route("/webhook/stats", methods=["GET"])
        def get_stats():
            """Retorna estadísticas de webhooks."""
            return jsonify({
                "stats": self.stats,
                "queue_size": webhook_queue.qsize(),
                "timestamp": datetime.now(timezone(timedelta(hours=-5))).isoformat(),
            }), 200
    
    def run(self, debug: bool = False, threaded: bool = True):
        """Inicia el servidor Flask."""
        log.info(f"[WEBHOOK_SERVER] Iniciando en {self.host}:{self.port}")
        self.app.run(
            host=self.host,
            port=self.port,
            debug=debug,
            threaded=threaded,
            use_reloader=False  # Importante: no recargar en threading
        )
    
    def run_in_thread(self):
        """Inicia el servidor en un thread separado."""
        thread = threading.Thread(
            target=lambda: self.run(debug=False, threaded=True),
            daemon=True,
            name="WebhookServer"
        )
        thread.start()
        log.info("[WEBHOOK_SERVER] Iniciado en thread daemon")
        return thread


# Función global para procesar webhooks desde main.py
def process_webhook_queue(processor_func):
    """
    Procesa los webhooks encolados (llamado por main.py).
    
    Args:
        processor_func: Función que procesa un post (de main.py)
        
    Ejemplo desde main.py:
        from webhook_server import process_webhook_queue
        process_webhook_queue(lambda post: classify_and_send(post))
    """
    processed = 0
    while not webhook_queue.empty() and processed < 10:  # Procesar máx 10 por ciclo
        try:
            event_data = webhook_queue.get_nowait()
            
            log.info(
                f"[WEBHOOK] Procesando evento {event_data['event_id']} "
                f"({event_data['client']})"
            )
            
            # Procesar items nuevos
            for item in event_data.get("items_new", []):
                try:
                    processor_func(item)
                except Exception as e:
                    log.error(f"[WEBHOOK] Error procesando item: {e}")
            
            processed += 1
            
        except Exception as e:
            log.error(f"[WEBHOOK] Error sacando de queue: {e}")
            break
    
    if processed > 0:
        log.info(f"[WEBHOOK] Procesados {processed} evento(s)")
    
    return processed


if __name__ == "__main__":
    # Para testing: ejecutar como standalone
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s"
    )
    
    server = WebhookServer()
    server.run(debug=True)
