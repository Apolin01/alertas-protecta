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


def _fallback_image(message: str, alert: dict | None) -> str:
    """Genera una imagen de respaldo (data URI) para cuando la imagen real
    del post fallo al descargar (link caido/expirado — comun en posts
    compartidos). Usa el dict `alert` completo (nivel, titulo, resumen,
    categoria, palabras_clave) para que la imagen tenga el color y el
    resumen correctos, igual que la imagen de respaldo que ya se genera
    cuando el post nunca trajo imagen. Si no hay `alert` disponible, cae a
    un parseo simple del texto ya formateado."""
    try:
        from whatsapp_image import generate_alert_image_data_uri
        if alert:
            return generate_alert_image_data_uri(alert)
        nivel = "INFO"
        for n in ("CRIT", "ALRT", "INFO"):
            if n in message[:20]:
                nivel = n
                break
        partes = message.split("*", 2)
        cuerpo = partes[2].strip() if len(partes) >= 3 else message
        cuerpo = cuerpo.split(" - *FUENTE:")[0].strip()
        return generate_alert_image_data_uri({"nivel": nivel, "titulo": cuerpo[:200]})
    except Exception as e:
        log.debug(f"No se pudo generar imagen de respaldo: {e}")
        return ""


# Mensajes de error del bridge que significan que el WebSocket a WhatsApp se
# cayó DURANTE el envío (sock.sendMessage lanzó antes de que WhatsApp recibiera
# nada). A diferencia de un 500 genérico, aquí SÍ es seguro reintentar: no se
# entregó. Sin esto, estas caídas de conexión se marcaban "enviada / no
# confirmar" y la alerta se perdía (Sheets la tenía, WhatsApp no).
_BRIDGE_ERR_NO_ENTREGADO = (
    "econnreset", "econnrefused", "epipe", "connection closed",
    "connection terminated", "socket hang up", "timed out", "timeout",
    "not connected", "no esta conectado", "lost connection", "websocket",
    "stream errored", "connection lost",
)


def _bridge_500_es_reintentable(resp) -> bool:
    """True si el 500 del bridge es una caída de conexión (no se entregó nada,
    seguro reintentar); False si es un 500 ambiguo (pudo haberse entregado)."""
    try:
        err = str(resp.json().get("error", "")).lower()
    except Exception:
        err = (resp.text or "").lower()[:300]
    return any(p in err for p in _BRIDGE_ERR_NO_ENTREGADO)


class WhatsAppSender:
    def __init__(self, config: Config):
        self.config = config
        self.provider = getattr(config, "WHATSAPP_PROVIDER", "simulate")
        self._twilio_client = None

    # ─────────────────────────────────────────────
    def send(self, group_name: str, message: str, image_url: str = "", alert: dict | None = None) -> bool | None:
        """Envía un mensaje. Resultado de tres estados:

            True  → entregado y confirmado por el bridge.
            False → NO entregado, con certeza (el bridge respondió que no
                    pudo, o ni siquiera se le pudo abrir conexión).
                    Solo en este caso es seguro reintentar.
            None  → desenlace desconocido (timeout o error inesperado). El
                    bridge pudo haber entregado el mensaje igualmente, así
                    que reintentar produciría un duplicado en el grupo.

        `alert`: dict completo de la alerta (nivel, titulo, resumen_whatsapp,
        etc.) — opcional, se usa SOLO para generar la imagen de respaldo si
        la imagen real falla al descargar.
        """
        if self.provider == "simulate":
            return self._send_simulate(group_name, message, image_url)
        elif self.provider == "bridge":
            return self._send_bridge(group_name, message, image_url, alert)
        else:
            log.error(f"Provider desconocido: {self.provider}")
            return False

    # ─────────────────────────────────────────────
    # WHATSAPP BRIDGE (whatsapp-web.js local)
    # Envía directo a grupos reales de WhatsApp
    # El bridge debe estar corriendo: node server.js
    # ─────────────────────────────────────────────
    def _send_bridge(self, group_name: str, message: str, image_url: str = "", alert: dict | None = None) -> bool | None:
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

                if data.get("image_download_failed"):
                    # El bridge NO mando nada todavia (evita duplicar el texto).
                    # Reintentamos una vez con una imagen de respaldo generada
                    # localmente; si tampoco se puede generar, reintentamos sin
                    # imagen para al menos entregar el texto.
                    log.warning(
                        f"Imagen real no se pudo descargar para '{group_name}' "
                        f"(link caido/expirado) — reintentando con imagen de respaldo"
                    )
                    fallback = _fallback_image(message, alert)
                    resp2 = requests.post(
                        f"{bridge_url}/send",
                        headers={"x-auth-token": bridge_token, "Content-Type": "application/json"},
                        json={"group_name": group_name, "message": message, "image_url": fallback},
                        timeout=90
                    )
                    if resp2.status_code == 200:
                        data2 = resp2.json()
                        img_str = "✓ con imagen de respaldo" if data2.get("with_image") else "solo texto"
                        log.info(f"Bridge OK ({img_str}, reintento) → {data2.get('group', group_name)}")
                        return True
                    if _bridge_500_es_reintentable(resp2):
                        log.error(f"Bridge error {resp2.status_code} en reintento (conexión caída, NO entregado): {resp2.text[:200]}")
                        return False
                    log.error(f"Bridge error {resp2.status_code} en reintento (sin confirmar): {resp2.text[:200]}")
                    return None

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
                if _bridge_500_es_reintentable(resp):
                    # El WebSocket a WhatsApp se cayó durante el envío — sendMessage
                    # lanzó ANTES de que WhatsApp recibiera nada. Seguro reintentar.
                    log.error(f"Bridge error {resp.status_code} (conexión caída, NO entregado): {resp.text[:200]}")
                    return False
                # 500 ambiguo: sendMessage lanzó, pudo fallar antes o DESPUÉS de
                # que WhatsApp aceptara. Desenlace no confirmable → no reintentar.
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

