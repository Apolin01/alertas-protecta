"""
webhook_handler.py — Procesamiento de webhooks desde rss.app
Convierte webhooks a formato compatible con el flujo existente de main.py
"""

import logging
import json
from datetime import datetime
from typing import Dict, List, Optional
from config import Config

log = logging.getLogger(__name__)


class WebhookProcessor:
    """
    Procesa webhooks de rss.app y los convierte a posts normalizados
    para que sean procesados como si vinieran del RSS polling.
    """
    
    def __init__(self):
        self.config = Config()
        # Mapeo inverso: bundle_id → cliente
        self.bundle_to_client = {
            v: k for k, v in Config.RSS_BUNDLES.items()
        }
    
    def process_webhook(self, webhook_payload: Dict, client_hint: str = "") -> Dict:
        """
        Procesa un webhook de rss.app y extrae posts procesables.
        
        Args:
            webhook_payload: Payload JSON del webhook
            
        Returns:
            Dict con estructura:
            {
                "event_id": str,
                "feed_id": str,
                "feed_title": str,
                "client": str | None,
                "items_new": list[dict],
                "items_changed": list[dict],
                "items_processed": int,
                "valid": bool,
                "error": str | None
            }
        """
        result = {
            "event_id": None,
            "feed_id": None,
            "feed_title": None,
            "client": None,
            "items_new": [],
            "items_changed": [],
            "items_processed": 0,
            "valid": False,
            "error": None,
        }
        
        try:
            # Validar estructura básica
            if not webhook_payload:
                result["error"] = "Payload vacío"
                return result
            
            event_id = webhook_payload.get("id")
            event_type = webhook_payload.get("type")
            feed_info = webhook_payload.get("feed", {})
            data = webhook_payload.get("data", {})
            
            if not event_id or event_type != "feed_update":
                result["error"] = f"Webhook inválido: tipo={event_type}"
                return result
            
            feed_id = feed_info.get("id")
            if not feed_id:
                result["error"] = "Feed ID no encontrado en webhook"
                return result

            client = client_hint if client_hint in Config.RSS_BUNDLES else None
            if not client:
                # Fallback: intentar mapear igual por si acaso (no deberia
                # matchear nunca con el esquema actual de rss.app, pero no
                # cuesta nada dejarlo como red de seguridad).
                client = self.bundle_to_client.get(feed_id)
            if not client:
                log.warning(
                    f"[WEBHOOK] Sin cliente: client_hint='{client_hint}' invalido y "
                    f"feed {feed_id} no mapea a ningun bundle. Feed: {feed_info.get('title')}"
                )
                # Aún procesamos pero sin cliente asignado
            
            result["event_id"] = event_id
            result["feed_id"] = feed_id
            result["feed_title"] = feed_info.get("title", "Unknown Feed")
            result["client"] = client
            
            # Procesar items nuevos
            items_new = data.get("items_new", [])
            for item in items_new:
                normalized = self._normalize_webhook_item(item, client)
                if normalized:
                    result["items_new"].append(normalized)
            
            # Procesar items modificados (cambios en publicaciones existentes)
            items_changed = data.get("items_changed", [])
            for item in items_changed:
                # Los items changed pueden contener actualizaciones
                # Por ahora los procesamos igual que los nuevos
                normalized = self._normalize_webhook_item(item, client)
                if normalized:
                    result["items_changed"].append(normalized)
            
            result["items_processed"] = len(result["items_new"]) + len(result["items_changed"])
            result["valid"] = True
            
            log.info(
                f"[WEBHOOK] ✓ {event_id} | Feed: {result['feed_title']} | "
                f"Cliente: {client} | Items: {result['items_processed']}"
            )
            
            return result
            
        except Exception as e:
            result["error"] = f"Error procesando webhook: {str(e)}"
            log.exception(f"[WEBHOOK] Error: {e}")
            return result
    
    def _normalize_webhook_item(self, item: Dict, client: Optional[str]) -> Optional[Dict]:
        """
        Convierte un item del webhook a formato normalizado compatible
        con el flujo de procesamiento existente.
        
        Formato normalizado (compatible con rss_fetcher.py):
        {
            "id": str,
            "url": str,
            "title": str,
            "description": str,
            "image_url": str,
            "date_published": str (ISO 8601),
            "authors": list[dict],
            "source": str,
            "client": str | None,
            "is_video": bool,
            "text": str,  # Para clasificador: title + description
        }
        """
        try:
            url = item.get("url", "").strip()
            if not url:
                return None
            
            title = item.get("title", "").strip()
            description = item.get("description_text", "").strip()
            
            # Texto para clasificador (título + descripción)
            text = f"{title}\n\n{description}".strip()
            if not text:
                return None
            
            # Detectar si es video
            is_video = self._is_video_item(item)
            
            # Autores
            authors = item.get("authors", [])
            author_names = [a.get("name", "") for a in authors if a.get("name")]
            author_str = ", ".join(author_names) if author_names else "Unknown"
            
            normalized = {
                "id": url,  # URL sirve como ID único
                "url": url,
                "title": title,
                "description": description,
                "description_html": item.get("description_html", ""),
                "image_url": item.get("thumbnail", ""),
                "date_published": item.get("date_published", ""),
                "authors": authors,
                "source": "RSS Webhook",
                "client": client,
                "is_video": is_video,
                "text": text,  # Para clasificador
                "webhook_timestamp": datetime.utcnow().isoformat(),
            }
            
            return normalized
            
        except Exception as e:
            log.warning(f"[WEBHOOK] Error normalizando item: {e}")
            return None
    
    def _is_video_item(self, item: Dict) -> bool:
        """Detecta si un item es video basado en su contenido."""
        # Podría verificar URLs de video (youtube, vimeo, etc.)
        # Por ahora retornamos False (los RSS normalmente no incluyen videos)
        return False
    
    def validate_webhook_signature(self, payload: str, signature: str, secret: str) -> bool:
        """
        Valida la firma HMAC del webhook (si rss.app la proporciona).
        Este método puede implementarse si rss.app proporciona un secreto.
        
        Args:
            payload: Raw payload string
            signature: Header X-Signature del webhook
            secret: Secreto configurado en rss.app
            
        Returns:
            True si la firma es válida
        """
        import hmac
        import hashlib
        
        try:
            expected_sig = hmac.new(
                secret.encode(),
                payload.encode(),
                hashlib.sha256
            ).hexdigest()
            return hmac.compare_digest(signature, expected_sig)
        except Exception as e:
            log.warning(f"[WEBHOOK] Error validando firma: {e}")
            return False


# Instancia global
webhook_processor = WebhookProcessor()
