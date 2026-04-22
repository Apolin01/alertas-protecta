"""
Sistema de Alertas Protecta Peru
- Rota entre regiones: procesa N paginas de cada region antes de pasar a la siguiente
- Envia al instante despues de cada pagina, sin esperar a que termine la region
"""

import sys
import io
import time
import json
import logging
import threading
from datetime import datetime, timezone, timedelta

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

_send_lock    = threading.Lock()
_ai_semaphore = threading.Semaphore(1)


def now_peru() -> datetime:
    return datetime.now(timezone(timedelta(hours=-5)))


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
            with _send_lock:
                ok = wa_sender.send(
                    group,
                    item["message"],
                    image_url=item.get("image_url", "")
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
                 wa_sender: WhatsAppSender) -> int:
    """
    Procesa una pagina: scraping → clasificacion → envio inmediato.
    Retorna cantidad de alertas enviadas.
    """
    scraper = FacebookScraper(config)
    try:
        posts = scraper._fetch_posts(page_name)
    except Exception as e:
        log.error(f"[{page_name}] Error scraping: {e}")
        return 0

    if not posts:
        return 0

    log.info(f"[{page_name}] {len(posts)} posts scrapeados")
    queued_ids = []

    for post in posts:
        if post.get("is_video") and not post.get("text"):
            continue
        if not post.get("text", "").strip():
            continue

        preview = post.get("text", "")[:100].replace("\n", " ")
        log.info(f"[{page_name}] Clasificando: {preview}...")

        with _ai_semaphore:
            time.sleep(4)
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

        # Dedup de contenido — misma noticia de otra pagina
        if dedup.is_duplicate_alert(alert):
            log.info(
                f"[{page_name}] Duplicado: {alert.get('subcategoria')} "
                f"en {alert.get('departamento')} — omitiendo"
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

        sep = "─" * 60
        print(f"\n{sep}")
        print("▶ FORMATO TABLA:")
        print(tabla_msg)
        print(f"{sep}")
        print("▶ FORMATO WHATSAPP:")
        print(wa_msg)
        print(f"{sep}\n")

        if not groups:
            log.warning(f"[{page_name}] Sin grupo WhatsApp para cliente '{cliente}' — no se envia")
            continue

        for group in groups:
            new_id = queue.push(group, wa_msg, image_url, alert)
            queued_ids.append(new_id)

        if getattr(config, "SHEETS_ENABLED", False):
            sheets_row = formatter.format_sheets_row(alert, post, config)
            sh_sender.append_row(sheets_row)

    # Envio inmediato al terminar esta pagina
    flush_all_pending(queued_ids, queue, wa_sender, dedup)
    return len(queued_ids)


# ─────────────────────────────────────────────────────────────
# OBTENER PAGINAS POR REGION
# ─────────────────────────────────────────────────────────────
def get_pages_for_region(region: str, config: Config) -> list[str]:
    page_to_client = getattr(config, "PAGE_TO_CLIENT", {})
    pages = [
        page for page, client in page_to_client.items()
        if client == region
    ]
    return pages if pages else config.FACEBOOK_PAGES


# ─────────────────────────────────────────────────────────────
# PROCESAR UNA REGION
# ─────────────────────────────────────────────────────────────
def process_region(region: str, config, classifier, dedup,
                   formatter, router, queue, sh_sender, wa_sender,
                   pages_limit: int = None) -> int:
    pages       = get_pages_for_region(region, config)
    limit       = pages_limit or getattr(config, "PAGES_PER_REGION_TURN", 8)
    pages_slice = pages[:limit]

    if not pages_slice:
        log.debug(f"[{region}] Sin paginas configuradas.")
        return 0

    log.info(f"\n{'─'*50}")
    log.info(f"REGION: {region} — {len(pages_slice)}/{len(pages)} paginas")
    log.info(f"{'─'*50}")

    total_enviadas = 0

    for i, page in enumerate(pages_slice, 1):
        log.info(f"  [{i}/{len(pages_slice)}] {page}")
        enviadas = process_page(
            page, config, classifier, dedup,
            formatter, router, queue, sh_sender, wa_sender
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

    regions    = config.REGION_ROTATION
    total_pags = len(config.FACEBOOK_PAGES)

    log.info("=" * 60)
    log.info("Sistema de Alertas Protecta Peru — LOOP CONTINUO")
    log.info(f"Hora Peru: {now_peru().strftime('%d-%m-%Y %H:%M')}")
    log.info(f"Paginas totales: {total_pags}")
    log.info(f"Regiones en rotacion: {' → '.join(regions)}")
    log.info(f"Paginas por region por turno: {config.PAGES_PER_REGION_TURN}")
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
