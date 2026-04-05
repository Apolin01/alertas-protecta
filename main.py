"""
Sistema de Alertas Protecta Peru
- Rota entre regiones: procesa N paginas de cada region antes de pasar a la siguiente
- Si una region no tiene noticias utiles en X paginas, rota automaticamente
- Envia al instante sin restriccion horaria
"""

import sys
import io
import time
import json
import logging
import threading
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from scraper import FacebookScraper
from classifier import AlertClassifier
from deduplicator import Deduplicator
from formatter import AlertFormatter
from router import RegionRouter
from sender_whatsapp import WhatsAppSender
from sender_sheets import SheetsSender
from alert_queue import AlertQueue
from config import Config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("alertas.log", encoding="utf-8"), 
        logging.StreamHandler(sys.stdout),
    ]
)
log = logging.getLogger(__name__)

_dedup_lock   = threading.Lock()
_send_lock    = threading.Lock()
_ai_semaphore = threading.Semaphore(1)


def now_peru() -> datetime:
    return datetime.now(timezone(timedelta(hours=-5)))


# ─────────────────────────────────────────────────────────────
# ENVIO INMEDIATO
# ─────────────────────────────────────────────────────────────
def send_now(group: str, wa_msg: str, image_url: str,
             alert: dict, queue: AlertQueue,
             wa_sender: WhatsAppSender, dedup: Deduplicator):
    """Encola y envía una alerta al instante."""
    queue.push(group, wa_msg, image_url, alert)

    pending = queue.get_pending(group)
    hora_str = now_peru().strftime("%H:%M")
    log.info(f"[ENVIO] {hora_str} PE → '{group}'")

    for item in pending:
        with _send_lock:
            ok = wa_sender.send(
                group,
                item["message"],
                image_url=item.get("image_url", "")
            )
        if ok:
            queue.mark_sent(item["id"])
            try:
                _alert_data = json.loads(item.get("alert_json", "{}"))
                dedup.mark_alert_sent(_alert_data)
            except Exception:
                pass
        time.sleep(1)

    queue.cleanup_old(days=2)


# ─────────────────────────────────────────────────────────────
# PROCESAR UNA PAGINA
# ─────────────────────────────────────────────────────────────
def process_page(page_name, config, classifier, dedup,
                 formatter, router, queue, sh_sender, wa_sender) -> int:
    """
    Procesa una pagina completa.
    Retorna el numero de alertas enviadas (0 = sin noticias utiles).
    """
    scraper = FacebookScraper(config)
    try:
        posts = scraper._fetch_posts(page_name)
    except Exception as e:
        log.error(f"[{page_name}] Error scraping: {e}")
        return 0

    if not posts:
        return 0

    log.info(f"[{page_name}] {len(posts)} posts")
    alertas_enviadas = 0

    for post in posts:
        with _dedup_lock:
            if dedup.already_processed(post):
                continue
            dedup.mark_processed(post)

        if post.get("is_video") and not post.get("text"):
            continue
        if not post.get("text", "").strip():
            continue

        preview = post.get("text", "")[:80].replace("\n", " ")
        log.info(f"[{page_name}] Clasificando: {preview}...")

        with _ai_semaphore:
            time.sleep(4)
            alert = classifier.classify(post)

        if not alert or alert.get("nivel") == "IGNORAR":
            continue

        # Dedup de contenido — misma noticia de otra pagina
        if dedup.is_duplicate_alert(alert):
            log.info(
                f"[{page_name}] Duplicado: {alert.get('subcategoria')} "
                f"en {alert.get('departamento')} — omitiendo."
            )
            continue

        log.info(
            f"[{page_name}] -> {alert.get('nivel')} | "
            f"{alert.get('cliente')} | {alert.get('subcategoria')}"
        )

        wa_msg    = formatter.format_whatsapp(alert, post, config)
        tabla_msg = formatter.format_tabla(alert, post, config)
        image_url = post.get("image_url", "")
        groups    = router.get_whatsapp_groups(alert.get("cliente", ""))

        # ── Imprimir ambos formatos en consola ──────────────────
        sep = "─" * 60
        print(f"\n{sep}")
        print("▶ FORMATO TABLA:")
        print(tabla_msg)
        print(f"{sep}")
        print("▶ FORMATO WHATSAPP:")
        print(wa_msg)
        print(f"{sep}\n")

        if not groups:
            log.warning(f"[{page_name}] Sin grupo para '{alert.get('cliente')}'")
            continue

        for group in groups:
            send_now(group, wa_msg, image_url, alert, queue, wa_sender, dedup)
            alertas_enviadas += 1
            log.info(f"[{page_name}] Enviado → '{group}'")

        if getattr(config, "SHEETS_ENABLED", False):
            sheets_row = formatter.format_sheets_row(alert, post, config)
            sh_sender.append_row(sheets_row)

    return alertas_enviadas


# ─────────────────────────────────────────────────────────────
# OBTENER PAGINAS POR REGION
# ─────────────────────────────────────────────────────────────
def get_pages_for_region(region: str, config: Config) -> list[str]:
    """Retorna las paginas del config que pertenecen a esta region."""
    page_to_client = getattr(config, "PAGE_TO_CLIENT", {})
    pages = [
        page for page, client in page_to_client.items()
        if client == region
    ]
    # Fallback: si no hay mapeo, devolver todas
    return pages if pages else config.FACEBOOK_PAGES


# ─────────────────────────────────────────────────────────────
# PROCESAR UNA REGION (N paginas antes de rotar)
# ─────────────────────────────────────────────────────────────
def process_region(region: str, config, classifier, dedup,
                   formatter, router, queue, sh_sender, wa_sender,
                   pages_limit: int = None) -> int:
    """
    Procesa las paginas de una region.
    Si lleva MAX_EMPTY_PAGES_BEFORE_ROTATE paginas sin alertas, rota.
    Retorna total de alertas enviadas.
    """
    pages       = get_pages_for_region(region, config)
    limit       = pages_limit or getattr(config, "PAGES_PER_REGION_TURN", 8)
    max_empty   = getattr(config, "MAX_EMPTY_PAGES_BEFORE_ROTATE", 5)
    pages_slice = pages[:limit]

    if not pages_slice:
        log.debug(f"[{region}] Sin paginas configuradas.")
        return 0

    log.info(f"\n{'─'*50}")
    log.info(f"REGION: {region} — {len(pages_slice)}/{len(pages)} paginas")
    log.info(f"{'─'*50}")

    total_alertas = 0
    empty_streak  = 0   # paginas seguidas sin alertas

    for i, page in enumerate(pages_slice, 1):
        log.info(f"  [{i}/{len(pages_slice)}] {page}")

        sent = process_page(
            page, config, classifier, dedup,
            formatter, router, queue, sh_sender, wa_sender
        )
        total_alertas += sent

        if sent == 0:
            empty_streak += 1
        else:
            empty_streak = 0   # resetear si hubo alertas

        # Rotar si lleva demasiadas paginas sin noticias
        if empty_streak >= max_empty and i < len(pages_slice):
            log.info(
                f"  [{region}] {empty_streak} paginas sin noticias — "
                f"rotando a siguiente region."
            )
            break

        time.sleep(config.DELAY_BETWEEN_PAGES)

    log.info(f"[{region}] Total alertas: {total_alertas}")
    return total_alertas


# ─────────────────────────────────────────────────────────────
# LOOP PRINCIPAL — ROTA ENTRE REGIONES
# ─────────────────────────────────────────────────────────────
def run_forever():
    config     = Config()
    classifier = AlertClassifier(config)
    dedup      = Deduplicator()
    formatter  = AlertFormatter()
    router     = RegionRouter(config)
    sh_sender  = SheetsSender(config)
    queue      = AlertQueue()
    wa_sender  = WhatsAppSender(config)

    regions    = config.REGION_ROTATION
    total_pags = len(config.FACEBOOK_PAGES)

    log.info("=" * 60)
    log.info("Sistema de Alertas Protecta Peru — LOOP CONTINUO")
    log.info(f"Hora Peru: {now_peru().strftime('%d-%m-%Y %H:%M')}")
    log.info(f"Paginas totales: {total_pags}")
    log.info(f"Regiones en rotacion: {' → '.join(regions)}")
    log.info(f"Paginas por region por turno: {config.PAGES_PER_REGION_TURN}")
    log.info(f"Rota si hay {config.MAX_EMPTY_PAGES_BEFORE_ROTATE} paginas seguidas sin noticias")
    log.info("=" * 60)

    ciclo = 0
    while True:
        ciclo += 1
        log.info(
            f"\n{'='*60}\n"
            f"CICLO {ciclo} — {now_peru().strftime('%d-%m-%Y %H:%M')} PE\n"
            f"{'='*60}"
        )

        ciclo_alertas = 0
        for region in regions:
            enviadas = process_region(
                region, config, classifier, dedup,
                formatter, router, queue, sh_sender, wa_sender
            )
            ciclo_alertas += enviadas

        log.info(
            f"\nCiclo {ciclo} completo — "
            f"Total alertas enviadas: {ciclo_alertas}\n"
            f"Esperando {config.DELAY_BETWEEN_CYCLES}s antes del siguiente ciclo...\n"
        )
        time.sleep(config.DELAY_BETWEEN_CYCLES)


def main():
    run_forever()


if __name__ == "__main__":
    main()