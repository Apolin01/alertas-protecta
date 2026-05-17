"""
Sistema de Alertas Protecta Peru
- Rota entre regiones: procesa N paginas de cada region antes de pasar a la siguiente
- Envia al instante despues de cada pagina, sin esperar a que termine la region
"""

import os
import sys
import io
import time
import json
import logging
import threading
from datetime import datetime, timezone, timedelta

import requests

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from config import Config

# Importar según configuración: RSS o Scraper tradicional
if Config.USE_RSS_FEED:
    from rss_fetcher import RSSFetcher as Fetcher
    log_source = "[RSS]"
else:
    from scraper import FacebookScraper as Fetcher
    from scraper import is_session_expired
    log_source = "[SCRAPER]"

from classifier import AlertClassifier
from deduplicator import Deduplicator
from formatter import AlertFormatter
from router import RegionRouter
from sender_whatsapp import WhatsAppSender
from sender_sheets import SheetsSender
from alert_queue import AlertQueue

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("alertas.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ]
)
log = logging.getLogger(__name__)

# Webhooks (opcional)
try:
    from webhook_server import WebhookServer, process_webhook_queue, webhook_queue
    WEBHOOKS_AVAILABLE = True
except ImportError as e:
    log.warning(f"[INIT] webhook_server no disponible: {e}")
    log.warning("[INIT] Instala Flask: pip install flask>=2.3.0")
    WEBHOOKS_AVAILABLE = False

_send_lock    = threading.Lock()
_ai_semaphore = threading.Semaphore(1)


def now_peru() -> datetime:
    return datetime.now(timezone(timedelta(hours=-5)))


def heartbeat(suffix: str = ""):
    """Pinga al watchdog externo (healthchecks.io / UptimeRobot Heartbeat).
    Si HEARTBEAT_URL no está configurado, no hace nada.
    suffix opcional: '/start' al iniciar ciclo, '/fail' si falló."""
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
            with _send_lock:
                ok = wa_sender.send(group, item["message"], image_url=item.get("image_url", ""))
            if ok:
                queue.mark_sent(item["id"])
                log.info(f"[REINTENTO] ✓ Enviado a '{group}'")
                try:
                    _alert_data = json.loads(item.get("alert_json", "{}"))
                    dedup.mark_alert_sent(_alert_data)
                except Exception:
                    pass
            else:
                log.warning(f"[REINTENTO] ✗ Aún sin bridge para '{group}'")
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
            image_url = item.get("image_url", "")
            
            if image_url:
                log.info(f"[ENVIO] ✓ CON IMAGEN: {image_url[:80]}")
            else:
                log.warning(f"[ENVIO] ✗ SIN IMAGEN")

            with _send_lock:
                ok = wa_sender.send(
                    group,
                    item["message"],
                    image_url=image_url
                )

                if ok:
                    queue.mark_sent(item["id"])
                    log.info(f"[ENVIO] ✓ Enviado a '{group}'")
                    try:
                        _alert_data = json.loads(item.get("alert_json", "{}"))
                        dedup.mark_alert_sent(_alert_data)
                    except Exception:
                        pass
                else:
                    log.error(f"[ENVIO] ✗ FALLO '{group}' — WhatsApp no conectado o grupo no encontrado")
                time.sleep(1)

    queue.cleanup_old(days=2)


# ─────────────────────────────────────────────────────────────
# PROCESAR UNA PAGINA — clasifica y envia inmediatamente
# ─────────────────────────────────────────────────────────────
def process_page(page_name, config, classifier, dedup,
                 formatter, router, queue, sh_sender,
                 wa_sender: WhatsAppSender, fetcher: Fetcher) -> int:
    """
    Procesa una pagina/cliente: obtención → clasificacion → envio inmediato.
    Retorna cantidad de alertas enviadas.
    
    Args:
        page_name: Nombre de página (para RSS/Scraper)
        fetcher: Instancia de Fetcher (RSSFetcher o FacebookScraper)
    """
    try:
        posts = fetcher._fetch_posts(page_name)
    except Exception as e:
        log.error(f"[{page_name}] Error obteniendo posts: {e}")
        return 0

    if not posts:
        if Config.USE_RSS_FEED:
            log.info(f"[{page_name}] 0 posts desde RSS bundle")
        else:
            session_expired = is_session_expired() if not Config.USE_RSS_FEED else False
            if session_expired:
                log.info(f"[{page_name}] 0 posts (modo anónimo)")
            else:
                log.info(f"[{page_name}] 0 posts encontrados")
        return 0

    source_type = "RSS" if Config.USE_RSS_FEED else "Scraper"
    log.info(f"[{page_name}] {len(posts)} posts ({source_type})")
    queued_ids = []

    for post in posts:
        if post.get("is_video") and not post.get("text"):
            continue
        if not post.get("text", "").strip():
            continue

        preview = post.get("text", "")[:100].replace("\n", " ")
        log.info(f"[{page_name}] Clasificando: {preview}...")

        with _ai_semaphore:
            time.sleep(2)  # Reducir espera con RSS (es menos pesado que scraper)
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

        if dedup.is_duplicate_alert(alert):
            log.info(
                f"[{page_name}] DUPLICADO — ya enviado: "
                f"dept={alert.get('departamento','?')} sub={alert.get('subcategoria','?')}"
            )
            continue

        cliente = alert.get("cliente", "")
        groups  = router.get_whatsapp_groups(cliente)

        log.info(
            f"[{page_name}] {nivel} | {cliente} | "
            f"{alert.get('subcategoria')} | grupos: {groups or 'NINGUNO'}"
        )

        wa_msg    = formatter.format_whatsapp(alert, post, config)
        tabla_msg = formatter.format_tabla(alert, post, config)
        image_url = post.get("image_url", "")
        
        # DEBUG: Loguear estado de imagen
        if image_url:
            log.info(f"[{page_name}] ✓ POST CON IMAGEN: {image_url[:80]}")
        else:
            log.warning(f"[{page_name}] ✗ POST SIN IMAGEN - post keys: {list(post.keys())}")

        log.debug(f"TABLA: {tabla_msg}")
        log.debug(f"WHATSAPP: {wa_msg}")

        if not groups:
            log.warning(f"[{page_name}] Sin grupo WhatsApp para cliente '{cliente}' — no se envia")
            continue

        for group in groups:
            new_id = queue.push(group, wa_msg, image_url, alert)
            queued_ids.append(new_id)

        # Marcar inmediatamente para que la misma noticia de otra página no pase el dedup
        dedup.mark_alert_sent(alert)

        if getattr(config, "SHEETS_ENABLED", False):
            sheets_row = formatter.format_sheets_row(alert, post, config)
            sh_sender.append_row(sheets_row)

    # Envio inmediato al terminar esta pagina
    flush_all_pending(queued_ids, queue, wa_sender, dedup)
    return len(queued_ids)


# ─────────────────────────────────────────────────────────────
# OBTENER PAGINAS POR REGION (Scraper) / CLIENTES (RSS)
# ─────────────────────────────────────────────────────────────
def get_pages_for_region(region: str, config: Config) -> list[str]:
    """
    Para Scraper: obtiene páginas de una región
    Para RSS: retorna lista vacía (se maneja directamente con clientes)
    """
    if config.USE_RSS_FEED:
        # RSS maneja clientes, no regiones tradicionales
        return []
    
    page_to_client = getattr(config, "PAGE_TO_CLIENT", {})
    pages = [
        page for page, client in page_to_client.items()
        if client == region
    ]
    return pages if pages else config.FACEBOOK_PAGES


def get_clients_for_rss() -> list[str]:
    """Obtiene lista de clientes configurados en RSS_BUNDLES."""
    return list(Config.RSS_BUNDLES.keys())


# ─────────────────────────────────────────────────────────────
# PROCESAR UNA REGION (con offset rotativo) — SCRAPER / RSS
# ─────────────────────────────────────────────────────────────
def process_region(region: str, config, classifier, dedup,
                   formatter, router, queue, sh_sender, wa_sender, fetcher,
                   offset: int = 0) -> int:
    """
    Procesa una región (Scraper) o cliente (RSS).
    """
    if config.USE_RSS_FEED:
        # En modo RSS, procesamos el cliente directamente
        log.info(f"\n{'─'*50}")
        log.info(f"CLIENTE RSS: {region}")
        log.info(f"{'─'*50}")
        
        enviadas = process_page(
            region, config, classifier, dedup,
            formatter, router, queue, sh_sender, wa_sender, fetcher
        )
        return enviadas
    else:
        # Modo Scraper: procesar páginas de la región
        pages  = get_pages_for_region(region, config)
        limit  = getattr(config, "PAGES_PER_REGION_TURN", 8)
        total  = len(pages)

        if not total:
            log.debug(f"[{region}] Sin paginas configuradas.")
            return 0

        start       = offset % total
        pages_slice = (pages + pages)[start : start + limit]   # wrap-around

        log.info(f"\n{'─'*50}")
        log.info(f"REGION: {region} — págs {start+1}-{start+len(pages_slice)}/{total}")
        log.info(f"{'─'*50}")

        total_enviadas = 0
        for i, page in enumerate(pages_slice, 1):
            log.info(f"  [{i}/{len(pages_slice)}] {page}")
            enviadas = process_page(
                page, config, classifier, dedup,
                formatter, router, queue, sh_sender, wa_sender, fetcher
            )
            total_enviadas += enviadas
            time.sleep(config.DELAY_BETWEEN_PAGES)

        return total_enviadas


# ─────────────────────────────────────────────────────────────
# LOOP PRINCIPAL
# ─────────────────────────────────────────────────────────────
def run_forever():
    config     = Config()
    classifier = AlertClassifier(config)
    dedup      = Deduplicator()
    queue      = AlertQueue()
    queue.clear_pending()
    formatter  = AlertFormatter()
    router     = RegionRouter(config)
    sh_sender  = SheetsSender(config)
    wa_sender  = WhatsAppSender(config)
    
    # Inicializar fetcher (RSS o Scraper)
    fetcher = Fetcher(config)
    if isinstance(fetcher, str):  # fallback
        fetcher = Fetcher(config)
    
    # ─────────────────────────────────────────────────────────────
    # INICIAR WEBHOOK SERVER (si está habilitado)
    # ─────────────────────────────────────────────────────────────
    webhook_thread = None
    if WEBHOOKS_AVAILABLE and config.WEBHOOKS_ENABLED:
        try:
            log.info("[WEBHOOKS] Iniciando servidor webhook...")
            webhook_server = WebhookServer(
                host=config.WEBHOOK_HOST,
                port=config.WEBHOOK_PORT,
                secret=config.WEBHOOK_SECRET
            )
            webhook_thread = webhook_server.run_in_thread()
            time.sleep(1)  # Esperar a que suba el servidor
            log.info(f"[WEBHOOKS] ✓ Servidor escuchando en {config.WEBHOOK_HOST}:{config.WEBHOOK_PORT}")
        except Exception as e:
            log.error(f"[WEBHOOKS] Error iniciando servidor: {e}")
    
    # Determinar qué iterar según modo
    if config.USE_RSS_FEED:
        items_to_process = get_clients_for_rss()
        item_type = "clientes RSS"
        total_items = len(items_to_process)
    else:
        items_to_process = config.REGION_ROTATION
        item_type = "regiones"
        total_items = len(config.FACEBOOK_PAGES)

    log.info("=" * 60)
    log.info("Sistema de Alertas Protecta Peru — LOOP CONTINUO")
    log.info(f"Hora Peru: {now_peru().strftime('%d-%m-%Y %H:%M')}")
    log.info(f"Modo: {'RSS Feed' if config.USE_RSS_FEED else 'Facebook Scraper'}")
    if not config.USE_RSS_FEED:
        log.info(f"Paginas totales: {total_items}")
    log.info(f"Items a procesar: {' → '.join(items_to_process)}")
    if not config.USE_RSS_FEED:
        log.info(f"Paginas por region por turno: {config.PAGES_PER_REGION_TURN}")
    log.info(f"Intervalo de ciclo: {config.INTERVAL_MINUTES} minutos")
    if WEBHOOKS_AVAILABLE and config.WEBHOOKS_ENABLED:
        log.info(f"Webhooks: ✓ HABILITADOS ({config.WEBHOOK_HOST}:{config.WEBHOOK_PORT})")
    log.info("=" * 60)

    ciclo   = 0
    offsets = {r: 0 for r in items_to_process}   # offset rotativo
    limit   = getattr(config, "PAGES_PER_REGION_TURN", 8)

    while True:
        ciclo += 1
        log.info(
            f"\n{'='*60}\n"
            f"CICLO {ciclo} — {now_peru().strftime('%d-%m-%Y %H:%M')} PE\n"
            f"{'='*60}"
        )

        # ─────────────────────────────────────────────────────────────
        # PROCESAR WEBHOOKS (si hay)
        # ─────────────────────────────────────────────────────────────
        if WEBHOOKS_AVAILABLE and config.WEBHOOKS_ENABLED:
            webhook_count = webhook_queue.qsize()
            if webhook_count > 0:
                log.info(f"[WEBHOOKS] {webhook_count} evento(s) pendiente(s)")
                
                def process_webhook_post(post):
                    """Procesa un post del webhook igual que uno normal."""
                    if post.get("is_video") and not post.get("text"):
                        return
                    if not post.get("text", "").strip():
                        return
                    
                    preview = post.get("text", "")[:100].replace("\n", " ")
                    log.info(f"[WEBHOOK] Clasificando: {preview}...")
                    
                    with _ai_semaphore:
                        time.sleep(1)
                        alert = classifier.classify(post)
                    
                    if not alert:
                        log.info(f"[WEBHOOK] Sin respuesta del clasificador")
                        return
                    
                    nivel = alert.get("nivel", "IGNORAR")
                    if nivel == "IGNORAR":
                        log.info(f"[WEBHOOK] Ignorado")
                        return
                    
                    if dedup.is_duplicate_alert(alert):
                        log.info(f"[WEBHOOK] Duplicado detectado")
                        return
                    
                    msg = formatter.format_whatsapp(alert)
                    groups = router.get_whatsapp_groups(alert.get("cliente"))
                    
                    if not groups:
                        log.warning(f"[WEBHOOK] No hay grupos para cliente: {alert.get('cliente')}")
                        return
                    
                    queued = queue.push(groups, msg, alert, post.get("image_url", ""))
                    if queued:
                        flush_all_pending([queued], queue, wa_sender, dedup)
                
                try:
                    process_webhook_queue(process_webhook_post)
                except Exception as e:
                    log.error(f"[WEBHOOKS] Error procesando: {e}")

        # Reintentar alertas que fallaron por bridge caído en ciclos anteriores
        retry_unsent(queue, wa_sender, dedup)

        ciclo_alertas = 0
        for item in items_to_process:
            enviadas = process_region(
                item, config, classifier, dedup,
                formatter, router, queue, sh_sender, wa_sender, fetcher,
                offset=offsets[item]
            )
            ciclo_alertas += enviadas
            offsets[item] += limit   # avanzar al siguiente bloque

        session_status = ""
        if not config.USE_RSS_FEED:
            session_status = " | Sesión FB: ⚠ EXPIRADA" if is_session_expired() else " | Sesión FB: OK"
        
        webhooks_status = ""
        if WEBHOOKS_AVAILABLE and config.WEBHOOKS_ENABLED:
            webhooks_status = f" | Webhooks: {webhook_queue.qsize()} encolados"
        
        log.info(
            f"\nCiclo {ciclo} completo — "
            f"Alertas enviadas: {ciclo_alertas}{session_status}{webhooks_status}\n"
            f"Esperando {config.INTERVAL_MINUTES} minutos antes del siguiente ciclo...\n"
        )
        heartbeat()  # avisa al watchdog que el ciclo terminó OK
        time.sleep(config.INTERVAL_MINUTES * 60)


def main():
    run_forever()


if __name__ == "__main__":
    main()
