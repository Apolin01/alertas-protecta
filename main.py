"""
Sistema de Alertas Protecta Peru
- Rota entre clientes RSS: procesa cada cliente antes de pasar al siguiente
- Envia al instante despues de cada cliente, sin esperar a que termine el ciclo
"""

import os
import sys
import io
import time
import json
import logging
import threading
from datetime import datetime, timezone, timedelta
try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None

import requests

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from config import Config
from whatsapp_image import BRIDGE_BASE64_LIMIT, generate_alert_image_data_uri

from rss_fetcher import RSSFetcher as Fetcher

from classifier import AlertClassifier, es_ruido_evidente, log_prefiltro_stats
from deduplicator import Deduplicator, DBUnavailable
from formatter import AlertFormatter
from router import RegionRouter
from sender_whatsapp import WhatsAppSender
from sender_sheets import SheetsSender
from alert_queue import AlertQueue, DBUnavailable as QueueDBUnavailable

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("alertas.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ]
)
log = logging.getLogger(__name__)

try:
    from webhook_server import (
        WebhookServer, process_webhook_queue, webhook_queue,
        start_relay_poller_thread, start_webhook_drain_thread,
    )
    WEBHOOKS_AVAILABLE = True
except ImportError as e:
    log.warning(f"[INIT] webhook_server no disponible: {e}")
    log.warning("[INIT] Instala Flask: pip install flask>=2.3.0")
    WEBHOOKS_AVAILABLE = False

_send_lock = threading.Lock()
_dedup_lock = threading.Lock()
_ai_lock = threading.Lock()


def _build_peru_tz():
    if ZoneInfo is not None:
        try:
            return ZoneInfo("America/Lima")
        except Exception:
            pass
    return timezone(timedelta(hours=-5))

_TZ_PERU = _build_peru_tz()

def now_peru() -> datetime:
    return datetime.now(_TZ_PERU)

def _should_send_to_nacional(alert: dict, config: Config) -> bool:
    """Filtra si una alerta debe ir al grupo NACIONAL: departamento + categoría + nivel mínimo."""
    cliente = alert.get("cliente", "").strip()
    if cliente != "Ninguno (Coyuntura Nacional)":
        log.info(
            f"[NACIONAL FILTRO] ℹ Cliente='{cliente}' va a grupo NACIONAL "
            "(router lo asignó así, continuando con filtros normales)"
        )

    dept = (alert.get("departamento") or "").upper().strip()
    if dept not in config.NACIONAL_ALLOWED_DEPTS:
        log.info(
            f"[NACIONAL FILTRO] ✗ Departamento '{dept}' no permitido. "
            f"Permitidos: {config.NACIONAL_ALLOWED_DEPTS}"
        )
        return False

    cat = (alert.get("categoria") or "").lower().strip()
    allowed_cats = [c.lower() for c in config.NACIONAL_ALLOWED_CATEGORIES]
    if not any(ac in cat for ac in allowed_cats):
        log.info(
            f"[NACIONAL FILTRO] ✗ Categoría '{cat}' no es política. "
            f"Permitidas: {config.NACIONAL_ALLOWED_CATEGORIES}"
        )
        return False

    nivel = alert.get("nivel", "INFO")
    nivel_orden = {"INFO": 0, "ALRT": 1, "CRIT": 2}
    nivel_min_orden = nivel_orden.get(config.NACIONAL_MIN_LEVEL, 1)
    if nivel_orden.get(nivel, 0) < nivel_min_orden:
        log.info(
            f"[NACIONAL FILTRO] ✗ Nivel '{nivel}' < mínimo '{config.NACIONAL_MIN_LEVEL}'"
        )
        return False

    log.info(
        f"[NACIONAL FILTRO] ✓ ACEPTADA: {dept} | {cat} | {nivel}"
    )
    return True

def heartbeat(suffix: str = ""):
    """Pinga al watchdog externo (healthchecks.io / UptimeRobot). No hace nada si HEARTBEAT_URL no está configurado."""
    url = os.environ.get("HEARTBEAT_URL", "").strip()
    if not url:
        return
    try:
        requests.get(url + suffix, timeout=5)
    except Exception as e:
        log.debug(f"[Heartbeat] Falló ping: {e}")


# ─────────────────────────────────────────────────────────────
# REINTENTO — alertas que fallaron por bridge caído
# ─────────────────────────────────────────────────────────────
def retry_unsent(queue: AlertQueue, wa_sender: WhatsAppSender, dedup: Deduplicator):
    """Reintenta alertas sent=0 de las últimas 4h (bridge estaba caído)."""
    groups = queue.get_recent_unsent(max_age_hours=4)
    if not groups:
        return
    total = sum(len(v) for v in groups.values())
    log.info(f"[REINTENTO] {total} alerta(s) pendiente(s) de envios fallidos")
    for group, items in groups.items():
        for item in items:
            image_url = item.get("image_url", "") or ""
            try:
                alert_data = json.loads(item.get("alert_json", "{}") or "{}")
            except Exception:
                alert_data = {}
            if (
                not image_url and
                getattr(wa_sender.config, "WHATSAPP_PROVIDER", "bridge") == "bridge" and
                getattr(wa_sender.config, "ENABLE_IMAGE_FALLBACK", False)
            ):
                image_url = generate_alert_image_data_uri(alert_data)
                if image_url:
                    log.info(f"[REINTENTO] imagen fallback generada para bridge")

            with _send_lock:
                if not queue.claim(item["id"]):
                    continue
                ok = wa_sender.send(group, item["message"], image_url=image_url, alert=alert_data)
            if ok is True:
                log.info(f"[REINTENTO] ✓ Enviado a '{group}'")
                try:
                    _alert_data = json.loads(item.get("alert_json", "{}"))
                    dedup.mark_alert_sent(_alert_data)
                except Exception:
                    pass
            elif ok is False:
                queue.release(item["id"])
                log.warning(f"[REINTENTO] ✗ Aún sin bridge para '{group}'")
            else:
                log.warning(
                    f"[REINTENTO] ? Sin confirmar para '{group}' — "
                    f"se deja como enviada para no duplicar"
                )
            time.sleep(1)


# ─────────────────────────────────────────────────────────────
# ENVIO INMEDIATO — se llama despues de cada pagina
# ─────────────────────────────────────────────────────────────
def flush_all_pending(queued_ids: list[int], queue: AlertQueue,
                      wa_sender: WhatsAppSender, dedup: Deduplicator):
    """Envía las alertas encoladas en esta pagina (por ID)."""
    if not queued_ids:
        return

    groups = queue.get_pending_by_ids(queued_ids)
    if not groups:
        return

    hora_str = now_peru().strftime("%H:%M")
    log.info(f"[ENVIO] {hora_str} — {len(queued_ids)} alerta(s) → {len(groups)} grupo(s)")

    for group, pending in groups.items():
        for item in pending:
            image_url = item.get("image_url", "") or ""
            try:
                alert_data = json.loads(item.get("alert_json", "{}") or "{}")
            except Exception:
                alert_data = {}
            if (
                not image_url and
                getattr(wa_sender.config, "WHATSAPP_PROVIDER", "bridge") == "bridge" and
                getattr(wa_sender.config, "ENABLE_IMAGE_FALLBACK", False)
            ):
                image_url = generate_alert_image_data_uri(alert_data)
                if image_url:
                    log.info(f"[ENVIO] imagen fallback generada para bridge")

            if image_url:
                log.info(f"[ENVIO] ✓ CON IMAGEN: {image_url[:80]}")
            else:
                log.debug(f"[ENVIO] sin imagen")

            with _send_lock:
                if not queue.claim(item["id"]):
                    log.info(f"[ENVIO] — alerta {item['id']} ya reclamada, se omite")
                    continue

                ok = wa_sender.send(
                    group,
                    item["message"],
                    image_url=image_url,
                    alert=alert_data
                )

                if ok is True:
                    log.info(f"[ENVIO] ✓ Enviado a '{group}'")
                elif ok is False:
                    queue.release(item["id"])
                    log.error(f"[ENVIO] ✗ FALLO '{group}' — WhatsApp no conectado o grupo no encontrado")
                else:
                    log.warning(
                        f"[ENVIO] ? Sin confirmar '{group}' — "
                        f"se deja como enviada para no duplicar"
                    )
                time.sleep(1)


# ─────────────────────────────────────────────────────────────
# PROCESAR UNA PAGINA — clasifica y envia inmediatamente
# ─────────────────────────────────────────────────────────────
def process_page(page_name, config, classifier, dedup,
                 formatter, router, queue, sh_sender,
                 wa_sender: WhatsAppSender, fetcher: Fetcher) -> int:
    """Procesa un cliente RSS: obtención → clasificación → envío inmediato. Retorna alertas enviadas."""
    try:
        posts = fetcher.fetch_posts(page_name)
    except Exception as e:
        log.error(f"[{page_name}] Error obteniendo posts: {e}")
        return 0

    posts_nuevos = []
    for post in posts:
        with _dedup_lock:
            try:
                if dedup.already_processed(post):
                    log.info(f"[{page_name}] Duplicado descartado antes de IA: {post.get('url', '')[:120]}")
                    continue
                dedup.mark_processed(post)
            except DBUnavailable:
                log.warning(f"[{page_name}] BD de dedup caida — post pasa sin chequeo de duplicado")
        posts_nuevos.append(post)

    posts = posts_nuevos

    if not posts:
        log.info(f"[{page_name}] 0 posts desde RSS bundle")
        return 0

    log.info(f"[{page_name}] {len(posts)} posts (RSS)")
    queued_ids = []

    for post in posts:
        if post.get("is_video") and not post.get("text"):
            continue
        if not post.get("text", "").strip():
            continue

        if es_ruido_evidente(post.get("text", "")):
            log.info(f"[{page_name}] Pre-filtro: ruido evidente — omitido sin llamar a la IA")
            continue

        prefiltro_decision = None
        try:
            with _ai_lock:
                prefiltro_decision = classifier.pre_filtro_ia(post.get("text", ""))
        except Exception as e:
            log.warning(f"[{page_name}] Pre-filtro error: {e}")

        if prefiltro_decision == "RUIDO":
            preview_ruido = post.get("text", "")[:150].replace("\n", " ")
            log.info(f"[{page_name}] Pre-filtro IA: RUIDO — omitido: {preview_ruido}...")
            continue

        preview = post.get("text", "")[:100].replace("\n", " ")
        log.info(f"[{page_name}] Clasificando: {preview}...")

        with _ai_lock:
            alert = classifier.classify(post)

        if not alert:
            log.info(f"[{page_name}] Sin respuesta del clasificador — omitiendo")
            continue

        nivel = alert.get("nivel", "IGNORAR")
        if nivel == "IGNORAR":
            log.info(
                f"[{page_name}] IGNORAR — dept={alert.get('departamento','?')} "
                f"cliente={alert.get('cliente','?')} sub={alert.get('subcategoria','?')}"
            )
            continue

        with _dedup_lock:
            try:
                if dedup.is_duplicate_alert(alert):
                    log.info(
                        f"[{page_name}] DUPLICADO — ya enviado: "
                        f"dept={alert.get('departamento','?')} sub={alert.get('subcategoria','?')}"
                    )
                    continue
                # Se registra COMO enviado inmediatamente, en el mismo lock que el
                # chequeo — si esto se hiciera despues de formatear/encolar (como
                # antes), dos posts casi simultaneos del mismo hecho (uno por RSS
                # y otro por webhook, o dos webhooks seguidos) pueden pasar ambos
                # el chequeo de duplicado antes de que cualquiera se registre,
                # y se mandan los dos. Cerrar esta ventana evita el duplicado.
                # mark_alert_sent() puede AUN ASI rechazar (otro hilo gano la
                # insercion en el microsegundo entre el chequeo y este insert) —
                # por eso hay que revisar su resultado, no solo llamarlo.
                if not dedup.mark_alert_sent(alert):
                    log.info(
                        f"[{page_name}] DUPLICADO — perdio la carrera de registro: "
                        f"dept={alert.get('departamento','?')} sub={alert.get('subcategoria','?')}"
                    )
                    continue
            except DBUnavailable:
                log.warning(f"[{page_name}] BD de dedup caida — alerta se envia sin chequeo de duplicado")

        cliente = alert.get("cliente", "")
        groups  = router.get_whatsapp_groups(cliente)

        log.info(
            f"[{page_name}] {nivel} | {cliente} | "
            f"{alert.get('subcategoria')} | grupos: {groups or 'NINGUNO'}"
        )

        wa_msg    = formatter.format_whatsapp(alert, post, config)
        tabla_msg = formatter.format_tabla(alert, post, config)
        image_url = post.get("image_url", "")

        if image_url:
            log.debug(f"[{page_name}] post con imagen: {image_url[:80]}")
        else:
            log.debug(f"[{page_name}] post sin imagen")

        log.debug(f"TABLA: {tabla_msg}")
        log.debug(f"WHATSAPP: {wa_msg}")

        if "Coyuntura Nacional" in (groups or []):
            if not _should_send_to_nacional(alert, config):
                log.info(f"[{page_name}] NACIONAL RECHAZADA — no cumple filtros")
                continue

        if not groups:
            log.warning(f"[{page_name}] Sin grupo WhatsApp para cliente '{cliente}' — no se envia")
            continue

        for group in groups:
            new_id = queue.push(group, wa_msg, image_url, alert)
            queued_ids.append(new_id)

        if getattr(config, "SHEETS_ENABLED", False):
            sheets_row = formatter.format_sheets_row(alert, post, config)
            sh_sender.append_row(sheets_row)

    flush_all_pending(queued_ids, queue, wa_sender, dedup)
    return len(queued_ids)


# ─────────────────────────────────────────────────────────────
# CLIENTES RSS
# ─────────────────────────────────────────────────────────────
def get_clients_for_rss() -> list[str]:
    """Obtiene lista de clientes configurados en RSS_BUNDLES."""
    return list(Config.RSS_BUNDLES.keys())


# ─────────────────────────────────────────────────────────────
# PROCESAR UN CLIENTE RSS
# ─────────────────────────────────────────────────────────────
def process_region(region: str, config, classifier, dedup,
                   formatter, router, queue, sh_sender, wa_sender, fetcher) -> int:
    """Procesa un cliente RSS."""
    log.info(f"\n{'─'*50}")
    log.info(f"CLIENTE RSS: {region}")
    log.info(f"{'─'*50}")

    return process_page(
        region, config, classifier, dedup,
        formatter, router, queue, sh_sender, wa_sender, fetcher
    )


# ─────────────────────────────────────────────────────────────
# LOOP PRINCIPAL
# ─────────────────────────────────────────────────────────────
def run_forever():
    config     = Config()
    classifier = AlertClassifier(config)
    dedup      = Deduplicator()
    queue      = AlertQueue()
    formatter  = AlertFormatter()
    router     = RegionRouter(config)
    sh_sender  = SheetsSender(config)
    wa_sender  = WhatsAppSender(config)

    fetcher = Fetcher(config)

    webhook_thread = None
    if WEBHOOKS_AVAILABLE and config.WEBHOOKS_ENABLED:
        if config.WEBHOOK_RELAY_URL:
            try:
                log.info("[WEBHOOKS] Modo RELAY — iniciando polling contra servicio externo...")
                webhook_thread = start_relay_poller_thread(
                    config.WEBHOOK_RELAY_URL,
                    config.WEBHOOK_RELAY_TOKEN,
                    config.WEBHOOK_RELAY_POLL_SECONDS,
                )
                log.info(f"[WEBHOOKS] ✓ Polling activo contra {config.WEBHOOK_RELAY_URL}")
            except Exception as e:
                log.error(f"[WEBHOOKS] Error iniciando poller de relay: {e}")
        else:
            try:
                log.info("[WEBHOOKS] Modo DIRECTO — iniciando servidor webhook local...")
                webhook_server = WebhookServer(
                    host=config.WEBHOOK_HOST,
                    port=config.WEBHOOK_PORT,
                    secret=config.WEBHOOK_SECRET
                )
                webhook_thread = webhook_server.run_in_thread()
                time.sleep(1)
                log.info(f"[WEBHOOKS] ✓ Servidor escuchando en {config.WEBHOOK_HOST}:{config.WEBHOOK_PORT}")
            except Exception as e:
                log.error(f"[WEBHOOKS] Error iniciando servidor: {e}")

    def process_webhook_post(post):
        """Procesa un post del webhook igual que uno normal."""
        if post.get("is_video") and not post.get("text"):
            return
        if not post.get("text", "").strip():
            return

        if es_ruido_evidente(post.get("text", "")):
            log.info(f"[WEBHOOK] Pre-filtro: ruido evidente — omitido sin llamar a la IA")
            return

        prefiltro_decision = None
        try:
            with _ai_lock:
                prefiltro_decision = classifier.pre_filtro_ia(post.get("text", ""))
        except Exception as e:
            log.warning(f"[WEBHOOK] Pre-filtro error: {e}")

        if prefiltro_decision == "RUIDO":
            preview_ruido = post.get("text", "")[:150].replace("\n", " ")
            log.info(f"[WEBHOOK] Pre-filtro IA: RUIDO — omitido: {preview_ruido}...")
            return

        preview = post.get("text", "")[:100].replace("\n", " ")
        log.info(f"[WEBHOOK] Clasificando: {preview}...")

        with _ai_lock:
            alert = classifier.classify(post)

        if not alert:
            log.info(f"[WEBHOOK] Sin respuesta del clasificador")
            return

        nivel = alert.get("nivel", "IGNORAR")
        if nivel == "IGNORAR":
            log.info(f"[WEBHOOK] Ignorado")
            return

        with _dedup_lock:
            try:
                if dedup.is_duplicate_alert(alert):
                    log.info(f"[WEBHOOK] Duplicado detectado")
                    return
                # Registrado como enviado en el mismo lock que el chequeo — ver
                # comentario en process_page() sobre la ventana de carrera que
                # esto cierra (dos posts casi simultaneos del mismo hecho).
                # Revisar el resultado: puede rechazar igual si otro hilo gano
                # la insercion en el microsegundo entre el chequeo y este insert.
                if not dedup.mark_alert_sent(alert):
                    log.info(f"[WEBHOOK] Duplicado — perdio la carrera de registro")
                    return
            except DBUnavailable:
                log.warning("[WEBHOOK] BD de dedup caida — alerta se envia sin chequeo de duplicado")

        cliente = alert.get("cliente", "")
        groups = router.get_whatsapp_groups(cliente)

        if "Coyuntura Nacional" in (groups or []):
            if not _should_send_to_nacional(alert, config):
                log.info(f"[WEBHOOK] NACIONAL RECHAZADA — no cumple filtros")
                return

        if not groups:
            log.warning(f"[WEBHOOK] No hay grupos para cliente: {cliente}")
            return

        wa_msg = formatter.format_whatsapp(alert, post, config)
        image_url = post.get("image_url", "")
        queued_ids = []
        for group in groups:
            new_id = queue.push(group, wa_msg, image_url, alert)
            queued_ids.append(new_id)

        if getattr(config, "SHEETS_ENABLED", False):
            sheets_row = formatter.format_sheets_row(alert, post, config)
            sh_sender.append_row(sheets_row)

        if queued_ids:
            flush_all_pending(queued_ids, queue, wa_sender, dedup)

    if WEBHOOKS_AVAILABLE and config.WEBHOOKS_ENABLED:
        # Drenado continuo en su propio thread — NO atado al ciclo de 5 min de
        # RSS (antes se procesaban max 10 eventos por ciclo y con trafico alto
        # la cola se llenaba hasta el maxsize=500, causando 503 en rss.app).
        start_webhook_drain_thread(process_webhook_post)

    items_to_process = get_clients_for_rss()

    log.info("=" * 60)
    log.info("Sistema de Alertas Protecta Peru — LOOP CONTINUO")
    log.info(f"Hora Peru: {now_peru().strftime('%d-%m-%Y %H:%M')}")
    log.info("Modo: RSS Feed")
    log.info(f"Items a procesar: {' → '.join(items_to_process)}")
    log.info(f"Intervalo de ciclo: {config.INTERVAL_MINUTES} minutos")
    if WEBHOOKS_AVAILABLE and config.WEBHOOKS_ENABLED:
        log.info(f"Webhooks: ✓ HABILITADOS ({config.WEBHOOK_HOST}:{config.WEBHOOK_PORT})")
    log.info("=" * 60)

    ciclo = 0

    while True:
        ciclo += 1
        log.info(
            f"\n{'='*60}\n"
            f"CICLO {ciclo} — {now_peru().strftime('%d-%m-%Y %H:%M')} PE\n"
            f"{'='*60}"
        )

        if hasattr(fetcher, "clear_cache"):
            fetcher.clear_cache()

        if webhook_thread is not None and not webhook_thread.is_alive():
            log.error(
                "[WEBHOOKS] ⚠ El hilo del webhook server MURIÓ — "
                "los webhooks entrantes no se procesarán hasta reiniciar el proceso. "
                "Revisa logs anteriores para la causa raíz."
            )
            webhook_thread = None

        try:
            retry_unsent(queue, wa_sender, dedup)
        except Exception as e:
            log.error(f"[MAIN] Error en retry_unsent: {e}", exc_info=True)

        ciclo_alertas = 0
        for item in items_to_process:
            try:
                enviadas = process_region(
                    item, config, classifier, dedup,
                    formatter, router, queue, sh_sender, wa_sender, fetcher
                )
            except Exception as e:
                log.error(f"[MAIN] Error procesando '{item}': {e}", exc_info=True)
                enviadas = 0
            ciclo_alertas += enviadas

        webhooks_status = ""
        if WEBHOOKS_AVAILABLE and config.WEBHOOKS_ENABLED:
            webhooks_status = f" | Webhooks: {webhook_queue.qsize()} encolados"

        try:
            queue.cleanup_old(days=2)
        except Exception as e:
            log.warning(f"[COLA] cleanup_old salteado (BD no disponible): {e}")

        dedup.log_dedup_stats()
        log_prefiltro_stats()

        log.info(
            f"\nCiclo {ciclo} completo — "
            f"Alertas enviadas: {ciclo_alertas}{webhooks_status}\n"
            f"Esperando {config.INTERVAL_MINUTES} minutos antes del siguiente ciclo...\n"
        )
        heartbeat()
        time.sleep(config.INTERVAL_MINUTES * 60)


def main():
    run_forever()


if __name__ == "__main__":
    main()
