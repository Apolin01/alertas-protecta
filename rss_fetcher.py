"""
rss_fetcher.py — Obtención de noticias desde RSS Feed API (rss.app)
Reemplaza scraper.py (Apify/Facebook) por una fuente centralizada de RSS.

El sistema usa bundles (paquetes) que contienen grupos de Facebook centralizados.
Cada bundle corresponde a una región/cliente.

Interfaz compatible con FacebookScraper para integración en main.py.

FILTROS APLICADOS:
- Solo noticias con antigüedad <= 2 horas (recent news only)
- No envía noticias antiguas/archivadas
"""

import os
import logging
import requests
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional
from config import Config

log = logging.getLogger(__name__)

# ── Configuración de API ────────────────────────
RSS_API_BASE = "https://api.rss.app/v1"
RSS_API_KEY = os.environ.get("RSS_API_KEY", Config.RSS_API_KEY)
RSS_API_SECRET = os.environ.get("RSS_API_SECRET", Config.RSS_API_SECRET)

# Cache local para evitar re-consultar en el mismo ciclo
_bundle_items_cache = {}


def _get_auth_header() -> Dict[str, str]:
    """Construye el header de autenticación para la API de rss.app."""
    token = f"{RSS_API_KEY}:{RSS_API_SECRET}"
    return {"Authorization": f"Bearer {token}"}


def get_bundle_items(bundle_id: str, limit: int = 50, max_age_hours: int = 2) -> Optional[List[Dict]]:
    """
    Obtiene los items (noticias) de un bundle específico.
    
    Args:
        bundle_id: ID del bundle en rss.app
        limit: Máximo de items a retornar
        max_age_hours: Máxima antigüedad de noticias en horas (default 2h)
        
    Returns:
        Lista de items filtrados por antigüedad o None si hay error
    """
    url = f"{RSS_API_BASE}/bundles/{bundle_id}"
    headers = _get_auth_header()
    
    try:
        log.info(f"[RSS] Obteniendo items del bundle: {bundle_id}")
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        data = response.json()
        items = data.get("items", [])
        
        log.info(f"[RSS] Bundle {bundle_id} devolvió {len(items)} items (sin filtrar)")
        
        # Filtrar por antigüedad (solo últimas 2 horas)
        now = datetime.now(timezone.utc)
        cutoff_time = now - timedelta(hours=max_age_hours)
        
        normalized_items = []
        filtered_out = 0
        rejected_no_date = 0
        
        for item in items[:limit]:
            title_preview = item.get('title', 'Sin título')[:70]
            
            # Obtener fecha de publicación
            date_str = item.get("date_published", "").strip() if item.get("date_published") else ""
            
            # ⚠️ CRÍTICO: Si NO tiene fecha, RECHAZAR (no asumir reciente)
            if not date_str:
                log.warning(f"[RSS] ❌ RECHAZADA (sin fecha): {title_preview}")
                rejected_no_date += 1
                continue
            
            try:
                # Parsear ISO format: "2026-05-19T14:30:00Z"
                if date_str.endswith("Z"):
                    item_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                else:
                    item_date = datetime.fromisoformat(date_str)
                
                # Si no tiene timezone, asumir UTC
                if item_date.tzinfo is None:
                    item_date = item_date.replace(tzinfo=timezone.utc)
                
                # Filtrar por antigüedad
                if item_date < cutoff_time:
                    age_hours = (now - item_date).total_seconds() / 3600
                    log.warning(f"[RSS] ❌ RECHAZADA (antigüedad {age_hours:.1f}h > {max_age_hours}h): {title_preview}")
                    filtered_out += 1
                    continue
                
                # ✅ ACEPTADA: Tiene fecha reciente (< 2h)
                age_hours = (now - item_date).total_seconds() / 3600
                log.debug(f"[RSS] ✅ ACEPTADA ({age_hours:.1f}h): {title_preview}")
                
            except Exception as e:
                log.warning(f"[RSS] ❌ ERROR parseando fecha '{date_str}': {e} — rechazando: {title_preview}")
                filtered_out += 1
                continue
            
            normalized_items.append({
                "id": item.get("url"),  # URL sirve como ID único
                "url": item.get("url"),
                "title": item.get("title", ""),
                "description": item.get("description_text", ""),
                "description_html": item.get("description_html", ""),
                "image_url": item.get("thumbnail", ""),
                "date_published": item.get("date_published", ""),
                "authors": item.get("authors", []),
                "source": data.get("name", "Unknown"),  # Nombre del bundle como fuente
                "bundle_id": bundle_id,
            })
        
        log.info(
            f"[RSS] Bundle {bundle_id}: "
            f"✅ {len(normalized_items)} aceptadas | "
            f"❌ {filtered_out} antiguas | "
            f"❌ {rejected_no_date} sin fecha"
        )
        
        return normalized_items
        
    except requests.exceptions.RequestException as e:
        log.error(f"[RSS] Error obteniendo bundle {bundle_id}: {e}")
        return None
    except Exception as e:
        log.error(f"[RSS] Error procesando respuesta del bundle {bundle_id}: {e}")
        return None


def list_bundles() -> Optional[List[Dict]]:
    """
    Lista todos los bundles disponibles en rss.app.
    
    Returns:
        Lista de bundles o None si hay error
    """
    url = f"{RSS_API_BASE}/bundles?limit=100"
    headers = _get_auth_header()
    
    try:
        log.info("[RSS] Listando bundles disponibles")
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        data = response.json()
        bundles = data.get("bundles", [])
        
        log.info(f"[RSS] Se encontraron {len(bundles)} bundles")
        return bundles
        
    except requests.exceptions.RequestException as e:
        log.error(f"[RSS] Error listando bundles: {e}")
        return None
    except Exception as e:
        log.error(f"[RSS] Error procesando lista de bundles: {e}")
        return None


def fetch_all_bundles() -> Dict[str, List[Dict]]:
    """
    Obtiene items de todos los bundles configurados en config.py.
    
    Returns:
        Dict con estructura: {client: [items], ...}
    """
    results = {}
    
    # Iterar sobre cada bundle configurado
    for client, bundle_id in Config.RSS_BUNDLES.items():
        items = get_bundle_items(bundle_id, max_age_hours=2)
        if items:
            results[client] = items
            log.info(f"[RSS] ✓ {client}: {len(items)} items")
        else:
            log.warning(f"[RSS] ✗ {client}: Error obteniendo items")
            results[client] = []
    
    return results


def test_connection() -> bool:
    """Prueba la conexión y autenticación con rss.app."""
    bundles = list_bundles()
    if bundles:
        log.info(f"[RSS] ✓ Conexión exitosa - {len(bundles)} bundles disponibles")
        return True
    else:
        log.error("[RSS] ✗ Error de conexión o autenticación")
        return False


# ── Adaptador compatible con FacebookScraper ────────────────────────
class RSSFetcher:
    """
    Adaptador que reemplaza FacebookScraper pero mantiene interfaz compatible.
    Obtiene posts desde RSS bundles en lugar de scraping directo de Facebook.
    """
    
    def __init__(self, config: Config = None):
        self.config = config or Config()
        self._current_bundle_index = 0
        self._bundles_list = list(self.config.RSS_BUNDLES.values())
    
    def _normalize_post(self, item: Dict, client: str) -> Dict:
        """
        Convierte item del RSS a formato compatible con FacebookScraper.
        
        Formato esperado por classifier.py:
        {
            "text": str,           # Título + descripción para clasificar
            "image_url": str,      # URL de imagen
            "url": str,            # Link original (Facebook)
            "date": str,           # Fecha de publicación
            "author": str,         # Autor/fuente
            "is_video": bool,
            "source": str,         # Nombre del bundle/fuente
            "bundle_id": str,      # ID del bundle para tracking
            "client": str,         # Cliente derivado (Antamina, etc.)
        }
        """
        # Combinar título y descripción para que el clasificador tenga contexto
        text_content = f"{item.get('title', '')}\n\n{item.get('description', '')}".strip()
        
        image_url = item.get("image_url", "")
        
        post = {
            "text": text_content,
            "image_url": image_url,
            "url": item.get("url", ""),
            "date": item.get("date_published", ""),
            "author": ", ".join([a.get("name", "") for a in item.get("authors", [])]) or "Desconocido",
            "is_video": False,  # RSS no indica si es video, asumir False
            "source": item.get("source", "RSS"),
            "source_page": item.get("source", "RSS Bundle"),
            "bundle_id": item.get("bundle_id", ""),
            "client": client,
            "_raw": item,  # Guardar original para debugging
        }
        
        # Logging para debugging
        if image_url:
            log.debug(f"[RSS] Post con imagen: {image_url[:80]}")
        else:
            log.debug(f"[RSS] POST SIN IMAGEN - item keys: {item.keys()}")
        
        return post
    
    def fetch_posts(self, client_or_bundle: str) -> List[Dict]:
        """
        Obtiene posts de un cliente (mapea a bundle ID) o directamente de un bundle ID.
        Compatible con la llamada en main.py: process_page(page_name, ...)

        Args:
            client_or_bundle: Nombre de cliente (ej: "Antamina") o bundleID directo

        Returns:
            Lista de posts normalizados al formato de FacebookScraper
        """
        # Intentar mapeo cliente → bundle ID
        bundle_id = self.config.RSS_BUNDLES.get(client_or_bundle)
        if bundle_id:
            client = client_or_bundle
        else:
            # Si no es un cliente conocido, asumir que es un bundle ID directo
            bundle_id = client_or_bundle
            # Mapeo inverso bundle_id → cliente
            bundle_to_client = {v: k for k, v in self.config.RSS_BUNDLES.items()}
            client = bundle_to_client.get(bundle_id, "Ninguno (Coyuntura Nacional)")
        
        # Verificar cache primera vez
        if bundle_id in _bundle_items_cache:
            log.debug(f"[RSS] Usando cache para bundle {bundle_id}")
            items = _bundle_items_cache[bundle_id]
        else:
            # Obtener desde API — 8h para capturar bundles con páginas de baja frecuencia
            # (ej. Coyuntura Nacional publica cada 3-8h).
            # URL dedup evita reenviar contenido que ya fue procesado en ciclos anteriores.
            items = get_bundle_items(bundle_id, max_age_hours=8)
            if items:
                _bundle_items_cache[bundle_id] = items
            else:
                log.warning(f"[RSS] No se pudo obtener items de {bundle_id}")
                return []
        
        # Normalizar posts
        normalized = []
        for item in items:
            normalized.append(self._normalize_post(item, client))
        
        return normalized
    
    def clear_cache(self):
        """Limpia el cache de bundles (útil entre ciclos)."""
        global _bundle_items_cache
        _bundle_items_cache.clear()
        log.info("[RSS] Cache limpiado")


if __name__ == "__main__":
    # Script de prueba
    logging.basicConfig(level=logging.INFO)
    
    print("=" * 60)
    print("TEST: RSSFetcher - Obtener posts de Antamina (Ancash)")
    print("=" * 60)
    
    fetcher = RSSFetcher()
    posts = fetcher.fetch_posts("Antamina")
    
    if posts:
        print(f"\n✓ Obtenidos {len(posts)} posts del bundle Ancash")
        print("\nPrimeros 3 posts normalizados:")
        for i, post in enumerate(posts[:3]):
            print(f"\n  Post {i+1}:")
            print(f"    Title: {post['text'][:80]}...")
            print(f"    URL: {post['url'][:60]}...")
            print(f"    Date: {post['date']}")
            print(f"    Client: {post['client']}")
            print(f"    Author: {post['author']}")
    else:
        print("\n✗ No se obtuvieron posts del bundle")
