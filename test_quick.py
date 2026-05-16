#!/usr/bin/env python3
"""
test_quick.py — Prueba RÁPIDA sin cargar todos los bundles.
¡Solo 3 items por bundle! Perfecto para testing.

USO:
    python test_quick.py          # Procesa solo 3 items, sin enviar a WhatsApp
    python test_quick.py --send   # Procesa 3 items Y envía a WhatsApp si el bridge está corriendo
"""

import sys
import os
import logging
import time
from pathlib import Path

# Añadir el directorio actual al path
sys.path.insert(0, str(Path(__file__).parent))

from config import Config
from rss_fetcher import RSSFetcher, get_bundle_items
from classifier import AlertClassifier
from formatter import AlertFormatter
from router import RegionRouter
from sender_whatsapp import WhatsAppSender

# Deduplicador simple para testing (sin base de datos)
class SimpleDuplicateDetector:
    def __init__(self):
        self.seen = set()
    
    def is_duplicated(self, alert):
        key = f"{alert.get('departamento')}_{alert.get('subcategoria')}"
        if key in self.seen:
            return True
        self.seen.add(key)
        return False
    
    def mark_alert_sent(self, alert):
        pass

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
log = logging.getLogger(__name__)

SEND_MODE = "--send" in sys.argv

def test_quick():
    """Prueba rápida con solo 3 items."""
    log.info("=" * 70)
    log.info(f"TEST RÁPIDO - Modo: {'ENVÍO REAL' if SEND_MODE else 'SIMULACIÓN'}")
    log.info("=" * 70)
    log.info(f"Bundles a procesar: {len(Config.RSS_BUNDLES)}")
    log.info(f"Items por bundle: 3 (para pruebas rápidas)")
    log.info("")

    config = Config()
    fetcher = RSSFetcher(config)
    classifier = AlertClassifier(config)
    dedup = SimpleDuplicateDetector()
    formatter = AlertFormatter()
    router = RegionRouter(config)
    wa_sender = WhatsAppSender(config)

    # Forzar modo simulación a menos que especifique --send
    if not SEND_MODE:
        wa_sender.provider = "simulate"
        log.info("✓ Modo SIMULACIÓN: los mensajes se mostrarán en log, no se enviarán a WhatsApp")
    else:
        log.info(f"✓ Modo ENVÍO REAL: intentaremos enviar a través de {wa_sender.provider}")
    
    log.info("")

    total_processed = 0
    total_alerts = 0

    # Procesar solo los 3 primeros bundles para ir más rápido
    bundles_to_test = list(Config.RSS_BUNDLES.items())[:3]

    for client, bundle_id in bundles_to_test:
        log.info(f"{'─'*70}")
        log.info(f"PROCESANDO: {client} (Bundle ID: {bundle_id})")
        log.info(f"{'─'*70}")

        # Obtener solo 3 items
        items = get_bundle_items(bundle_id, limit=3)
        
        if not items:
            log.warning(f"No se obtuvieron items del bundle {bundle_id}")
            continue

        log.info(f"✓ Obtenidos {len(items)} items")

        # Procesar cada item
        for idx, post in enumerate(items, 1):
            log.info(f"  [{idx}/3] Procesando: {post.get('title', 'Sin título')[:60]}...")
            
            try:
                # Clasificar
                alert = classifier.classify(post)
                if not alert:
                    log.debug(f"    ✗ No clasificado o filtrado")
                    continue

                # Deduplicar
                if dedup.is_duplicated(alert):
                    log.debug(f"    ✗ Duplicado")
                    continue

                # Formatear y enviar
                wa_msg = formatter.format_whatsapp(alert, post, config)
                image_url = post.get("image_url", "")
                groups = router.get_whatsapp_groups(client)

                if groups:
                    for group in groups:
                        result = wa_sender.send(group, wa_msg, image_url=image_url)
                        if result:
                            total_alerts += 1
                            dedup.mark_alert_sent(alert)
                            log.info(f"    ✓ Enviado a '{group}'")
                        else:
                            log.info(f"    ✗ Error enviando a '{group}'")
                else:
                    log.debug(f"    ✗ Sin grupos WhatsApp configurados para {client}")

            except Exception as e:
                log.error(f"    ✗ Error procesando item: {e}")
                continue

            total_processed += 1

        log.info("")

    # Resumen
    log.info("=" * 70)
    log.info(f"RESUMEN TEST RÁPIDO")
    log.info(f"  Bundles procesados: {len(bundles_to_test)}")
    log.info(f"  Items procesados: {total_processed}")
    log.info(f"  Alertas enviadas: {total_alerts}")
    log.info(f"  Modo: {'SIMULACIÓN ✓' if not SEND_MODE else 'ENVÍO REAL ✓'}")
    log.info(f"  Bridge: {wa_sender.provider}")
    log.info("=" * 70)

    if SEND_MODE and wa_sender.provider == "bridge":
        log.info("\n💡 Asegurate que el bridge esté corriendo:")
        log.info("    cd whatsapp_bridge")
        log.info("    node server.js")

if __name__ == "__main__":
    test_quick()
