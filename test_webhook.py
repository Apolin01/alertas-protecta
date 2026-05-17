"""
test_webhook.py — Script de testing para webhooks
Ejecutar: python test_webhook.py
"""

import requests
import json
from datetime import datetime, timedelta

# Configuración
WEBHOOK_URL = "http://localhost:5000/webhook"
HEALTH_URL = "http://localhost:5000/health"


def test_health_check():
    """Prueba si el servidor webhook está activo."""
    print("\n" + "="*60)
    print("TEST 1: Health Check")
    print("="*60)
    
    try:
        response = requests.get(HEALTH_URL, timeout=5)
        print(f"✓ Status: {response.status_code}")
        data = response.json()
        print(f"✓ Server: {data.get('status')}")
        print(f"✓ Queue size: {data['queue_size']}")
        print(f"✓ Stats: {json.dumps(data['stats'], indent=2)}")
        return True
    except requests.exceptions.ConnectionError:
        print("✗ ERROR: No se puede conectar a http://localhost:5000")
        print("  Asegúrate de que main.py está corriendo con WEBHOOKS_ENABLED=true")
        return False
    except Exception as e:
        print(f"✗ ERROR: {e}")
        return False


def create_test_webhook(bundle_id: str, num_items: int = 1) -> dict:
    """Crea un webhook de prueba."""
    
    # Mapeo bundle_id a cliente
    bundle_map = {
        "_vv3HkItEzKqytLHk": "Antamina",
        "_dtKCh5CjRws0ai8H": "Bechtel / Newmont",
        "_vuHd6hNkLlFj0nPK": "Clientes Sur",
        "_i5tst4lPDJ5oTSW4": "Clientes Norte",
        "_XgBrvIyMIWm5YzLP": "Pisco",
        "_pM02KT2QspbdR8os": "Ninguno (Coyuntura Nacional)",
    }
    
    cliente = bundle_map.get(bundle_id, "Unknown")
    
    # Generar items de prueba
    items_new = []
    for i in range(1, num_items + 1):
        items_new.append({
            "url": f"https://example.com/test-news-{i}",
            "title": f"Noticia de Prueba #{i} - {cliente}",
            "description_text": f"Esta es una noticia de prueba para {cliente}. Contiene información relevante sobre seguridad y eventos. Generada a las {datetime.now().strftime('%H:%M:%S')}.",
            "description_html": f"<p>Esta es una noticia de prueba para {cliente}</p>",
            "thumbnail": "https://via.placeholder.com/400x300?text=Test+News",
            "date_published": (datetime.utcnow() - timedelta(minutes=i)).isoformat() + "Z",
            "authors": [
                {"name": f"Test Author {i}"}
            ]
        })
    
    webhook = {
        "id": f"evt_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{bundle_id[-4:]}",
        "type": "feed_update",
        "feed": {
            "id": bundle_id,
            "title": f"Test Feed - {cliente}",
            "source_url": "https://example-news.com",
            "rss_feed_url": f"https://rss.app/feeds/{bundle_id}.xml",
            "description": "Feed de prueba para webhook testing",
            "icon": "https://example.com/icon.png",
            "is_active": True
        },
        "data": {
            "items_new": items_new,
            "items_changed": []
        }
    }
    
    return webhook


def send_webhook(webhook: dict) -> bool:
    """Envía un webhook de prueba."""
    print(f"\nEnviando webhook: {webhook['id']}")
    print(f"Feed: {webhook['feed']['title']}")
    print(f"Items: {len(webhook['data']['items_new'])}")
    
    try:
        response = requests.post(
            WEBHOOK_URL,
            json=webhook,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        print(f"Status: {response.status_code}")
        result = response.json()
        
        if response.status_code in [200, 202]:
            print(f"✓ SUCCESS")
            print(f"  Event ID: {result.get('event_id')}")
            print(f"  Items queued: {result.get('items_queued')}")
            return True
        else:
            print(f"✗ ERROR")
            print(f"  {result.get('error', result)}")
            return False
            
    except Exception as e:
        print(f"✗ ERROR: {e}")
        return False


def test_all_bundles():
    """Prueba webhooks para todos los bundles configurados."""
    print("\n" + "="*60)
    print("TEST 2: Webhooks de Todos los Bundles")
    print("="*60)
    
    bundles = {
        "_vv3HkItEzKqytLHk": "Antamina",
        "_dtKCh5CjRws0ai8H": "Bechtel / Newmont",
        "_vuHd6hNkLlFj0nPK": "Clientes Sur",
        "_i5tst4lPDJ5oTSW4": "Clientes Norte",
        "_XgBrvIyMIWm5YzLP": "Pisco",
        "_pM02KT2QspbdR8os": "Ninguno (Coyuntura Nacional)",
    }
    
    success = 0
    failed = 0
    
    for bundle_id, cliente in bundles.items():
        webhook = create_test_webhook(bundle_id, num_items=1)
        if send_webhook(webhook):
            success += 1
        else:
            failed += 1
    
    print(f"\nResultados: {success} OK, {failed} FAILED")
    return failed == 0


def test_high_volume():
    """Prueba con múltiples items."""
    print("\n" + "="*60)
    print("TEST 3: High Volume (10 items en 1 webhook)")
    print("="*60)
    
    webhook = create_test_webhook("_vv3HkItEzKqytLHk", num_items=10)
    return send_webhook(webhook)


def check_queue_status():
    """Verifica el estado de la cola de webhooks."""
    print("\n" + "="*60)
    print("TEST 4: Queue Status")
    print("="*60)
    
    try:
        response = requests.get(f"{HEALTH_URL}?check_queue=1", timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            queue_size = data.get('queue_size', 0)
            print(f"✓ Queue size: {queue_size} items")
            
            if queue_size > 0:
                print("  Items encolados esperando procesamiento en el siguiente ciclo")
            else:
                print("  Queue vacía (todos los items procesados)")
            
            return True
    except Exception as e:
        print(f"✗ ERROR: {e}")
        return False


def main():
    print("\n" + "="*60)
    print("WEBHOOK TESTING SUITE")
    print("="*60)
    
    # Test 1: Health check
    if not test_health_check():
        print("\n✗ Server no está disponible. Inicia main.py primero.")
        return
    
    # Test 2: Enviar webhooks
    input("\nPresiona ENTER para enviar webhook de prueba...")
    test_all_bundles()
    
    # Test 3: High volume
    input("\nPresiona ENTER para enviar webhook de alto volumen...")
    test_high_volume()
    
    # Test 4: Queue status
    input("\nPresiona ENTER para verificar estado de la cola...")
    check_queue_status()
    
    print("\n" + "="*60)
    print("✓ Tests completados")
    print("="*60)
    print("\nPróximos pasos:")
    print("1. Revisa alertas.log para ver el procesamiento")
    print("   tail -f alertas.log | grep WEBHOOK")
    print("2. Verifica que los mensajes se envíen a WhatsApp")
    print("3. En producción, configura webhooks en rss.app")


if __name__ == "__main__":
    main()
