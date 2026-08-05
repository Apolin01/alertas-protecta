"""
sender_whatsapp.py — Envío a WhatsApp vía Twilio.
Soporta texto + imagen adjunta del post de Facebook.

Twilio sandbox permite media_url para imágenes públicas.
Si la imagen no es pública o no existe, envía solo el texto.
"""

import logging
import requests
from urllib.parse import quote
from twilio.rest import Client as TwilioClient
from config import Config

log = logging.getLogger(__name__)


class WhatsAppSender:
    def __init__(self, config: Config):
        self.config = config
        self.provider = getattr(config, "WHATSAPP_PROVIDER", "simulate")
        self._twilio_client = None

    # ─────────────────────────────────────────────
    def send(self, group_name: str, message: str, image_url: str = "") -> bool | None:
        """Envía un mensaje. Resultado de tres estados:

            True  → entregado y confirmado por el bridge.
            False → NO entregado, con certeza (el bridge respondió que no
                    pudo, o ni siquiera se le pudo abrir conexión).
                    Solo en este caso es seguro reintentar.
            None  → desenlace desconocido (timeout o error inesperado). El
                    bridge pudo haber entregado el mensaje igualmente, así
                    que reintentar produciría un duplicado en el grupo.
        """
        if self.provider == "simulate":
            return self._send_simulate(group_name, message, image_url)
        elif self.provider == "bridge":
            return self._send_bridge(group_name, message, image_url)
        else:
            log.error(f"Provider desconocido: {self.provider}")
            return False

    # ─────────────────────────────────────────────
    # WHATSAPP BRIDGE (whatsapp-web.js local)
    # Envía directo a grupos reales de WhatsApp
    # El bridge debe estar corriendo: node server.js
    # ─────────────────────────────────────────────
    def _send_bridge(self, group_name: str, message: str, image_url: str = "") -> bool | None:
        """
        Llama al servidor Node.js local que tiene WhatsApp conectado.
        El bridge resuelve el nombre del grupo al chatId real.
        """
        bridge_url   = getattr(self.config, "BRIDGE_URL",   "http://localhost:3000")
        bridge_token = getattr(self.config, "BRIDGE_TOKEN", "protecta2026")

        # Limitar imagen base64 a 400 KB para evitar timeouts
        img_payload = image_url or ""
        if img_payload.startswith("data:") and len(img_payload) > 400_000:
            log.debug("Imagen base64 muy grande — se omite para no hacer timeout")
            img_payload = ""

        try:
            resp = requests.post(
                f"{bridge_url}/send",
                headers={"x-auth-token": bridge_token, "Content-Type": "application/json"},
                json={
                    "group_name": group_name,
                    "message":    message,
                    "image_url":  img_payload,
                },
                timeout=90
            )

            if resp.status_code == 200:
                data = resp.json()
                img_str = "✓ con imagen" if data.get("with_image") else "solo texto"
                log.info(f"Bridge OK ({img_str}) → {data.get('group', group_name)}")
                return True
            elif resp.status_code == 503:
                # El bridge rechaza ANTES de tocar sendMessage — no se entregó nada.
                log.error("Bridge: WhatsApp no conectado. Corre 'node server.js' y escanea el QR.")
                return False
            elif resp.status_code == 404:
                # Grupo desconocido, también rechazado antes de enviar.
                log.error(f"Bridge: grupo '{group_name}' no encontrado. {resp.json().get('hint','')}")
                return False
            else:
                # 500 = sendMessage lanzó excepción. Pudo fallar antes o DESPUÉS
                # de que WhatsApp aceptara el mensaje: desenlace no confirmable.
                log.error(f"Bridge error {resp.status_code} (sin confirmar): {resp.text[:200]}")
                return None

        except requests.exceptions.ConnectionError:
            # Nunca se abrió la conexión: el mensaje no salió.
            log.error(
                f"No se puede conectar al bridge en {bridge_url}. "
                f"Asegurate de que 'node server.js' este corriendo."
            )
            return False
        except requests.exceptions.Timeout:
            # El bridge tardó más de 90s. Enviar una imagen a WhatsApp puede
            # superar ese margen: lo más probable es que SÍ se haya entregado.
            # Reintentar aquí es exactamente lo que duplica los mensajes.
            log.warning(
                f"Bridge no respondió en 90s para '{group_name}'. "
                f"Se asume entregado — no se reintenta para evitar duplicado."
            )
            return None
        except Exception as e:
            log.error(f"Bridge excepcion (sin confirmar): {e}")
            return None

    # ─────────────────────────────────────────────
    # MODO SIMULACIÓN
    # ─────────────────────────────────────────────
    def _send_simulate(self, group_name: str, message: str, image_url: str = "") -> bool:
        log.info(f"\n{'─'*55}")
        log.info(f"[SIMULADO → {group_name}]")
        log.info(message)
        if image_url:
            log.info(f"[imagen] {image_url}")
        log.info(f"{'─'*55}")
        return True

    def _validate_image_url(self, url: str) -> str:
        """
        Verifica que la URL de imagen sea accesible y sea un tipo válido.
        Retorna la URL si es válida, o "" si no.
        Twilio acepta: image/jpeg, image/png, image/gif, image/webp
        """
        if not url or not url.startswith("http"):
            return ""

        # Extensiones conocidas que Twilio acepta
        valid_extensions = (".jpg", ".jpeg", ".png", ".gif", ".webp")
        url_lower = url.lower().split("?")[0]

        # Si la URL tiene extensión conocida, confiar en ella
        if any(url_lower.endswith(ext) for ext in valid_extensions):
            return url

        # Si no tiene extensión clara, hacer HEAD request para verificar
        try:
            resp = requests.head(url, timeout=5, allow_redirects=True)
            content_type = resp.headers.get("Content-Type", "")
            if resp.status_code == 200 and "image" in content_type:
                return url
            log.debug(f"Imagen no válida ({resp.status_code}, {content_type}): {url[:60]}")
            return ""
        except Exception:
            log.debug(f"No se pudo verificar imagen: {url[:60]}")
            return ""

