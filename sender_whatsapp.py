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

    def _get_twilio_client(self):
        if self._twilio_client is None:
            sid   = self.config.TWILIO_ACCOUNT_SID
            token = self.config.TWILIO_AUTH_TOKEN
            if not sid or not token:
                raise ValueError("TWILIO_SID o TWILIO_TOKEN no están en .env")
            self._twilio_client = TwilioClient(sid, token)
        return self._twilio_client

    # ─────────────────────────────────────────────
    def send(self, group_name: str, message: str, image_url: str = "") -> bool:
        if self.provider == "simulate":
            return self._send_simulate(group_name, message, image_url)
        elif self.provider == "bridge":
            return self._send_bridge(group_name, message, image_url)
        elif self.provider == "twilio":
            phone = self.config.WHATSAPP_GROUPS.get(group_name)
            if not phone:
                log.warning(f"Grupo '{group_name}' no tiene número en WHATSAPP_GROUPS.")
                return False
            return self._send_twilio(phone, message, image_url)
        elif self.provider == "callmebot":
            phone = self.config.WHATSAPP_GROUPS.get(group_name)
            if not phone:
                log.warning(f"Grupo '{group_name}' no tiene número en WHATSAPP_GROUPS.")
                return False
            return self._send_callmebot(phone, message)
        elif self.provider == "meta":
            phone = self.config.WHATSAPP_GROUPS.get(group_name)
            if not phone:
                log.warning(f"Grupo '{group_name}' no tiene número en WHATSAPP_GROUPS.")
                return False
            return self._send_meta(phone, message, image_url)
        else:
            log.error(f"Provider desconocido: {self.provider}")
            return False

    # ─────────────────────────────────────────────
    # WHATSAPP BRIDGE (whatsapp-web.js local)
    # Envía directo a grupos reales de WhatsApp
    # El bridge debe estar corriendo: node server.js
    # ─────────────────────────────────────────────
    def _send_bridge(self, group_name: str, message: str, image_url: str = "") -> bool:
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
                timeout=60
            )

            if resp.status_code == 200:
                data = resp.json()
                img_str = "con imagen" if data.get("with_image") else "solo texto"
                log.info(f"Bridge OK ({img_str}) → {data.get('group', group_name)}")
                return True
            elif resp.status_code == 503:
                log.error("Bridge: WhatsApp no conectado. Corre 'node server.js' y escanea el QR.")
                return False
            elif resp.status_code == 404:
                log.error(f"Bridge: grupo '{group_name}' no encontrado. {resp.json().get('hint','')}")
                return False
            else:
                log.error(f"Bridge error {resp.status_code}: {resp.text[:200]}")
                return False

        except requests.exceptions.ConnectionError:
            log.error(
                f"No se puede conectar al bridge en {bridge_url}. "
                f"Asegurate de que 'node server.js' este corriendo."
            )
            return False
        except Exception as e:
            log.error(f"Bridge excepcion: {e}")
            return False

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

