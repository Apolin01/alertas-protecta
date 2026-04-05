"""
scraper.py — Obtiene publicaciones de paginas de Facebook via Apify.
Actor: apify/facebook-posts-scraper
"""

import time
import logging
import requests
from datetime import datetime, timedelta
from config import Config

log = logging.getLogger(__name__)
APIFY_BASE = "https://api.apify.com/v2"


class FacebookScraper:
    def __init__(self, config: Config):
        self.config = config
        self.token  = config.APIFY_TOKEN

    def fetch_all_pages(self) -> list[dict]:
        if not self.token:
            log.warning("APIFY_TOKEN no configurado. Usando posts de prueba.")
            return self._mock_posts()

        all_posts = []
        for page in self.config.FACEBOOK_PAGES:
            try:
                posts = self._fetch_posts(page)
                all_posts.extend(posts)
                log.info(f"  {page}: {len(posts)} posts")
            except Exception as e:
                log.error(f"  Error scrapeando {page}: {e}")
        return all_posts

    def _fetch_posts(self, page_name: str) -> list[dict]:
        payload = {
            "startUrls": [{"url": f"https://www.facebook.com/{page_name}"}],
            "resultsLimit": self.config.POSTS_PER_PAGE,
            "onlyPostsNewerThan": (
                datetime.utcnow() - timedelta(hours=12)
            ).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        }

        run_resp = requests.post(
            f"{APIFY_BASE}/acts/apify~facebook-posts-scraper/runs",
            json=payload,
            params={"token": self.token},
            timeout=30
        )
        run_resp.raise_for_status()
        run_id = run_resp.json()["data"]["id"]

        for attempt in range(30):
            time.sleep(6)
            status_resp = requests.get(
                f"{APIFY_BASE}/actor-runs/{run_id}",
                params={"token": self.token},
                timeout=15
            ).json()
            status = status_resp["data"]["status"]
            if status == "SUCCEEDED":
                break
            if status in ("FAILED", "ABORTED", "TIMED-OUT"):
                log.error(f"Apify run {run_id} status: {status}")
                return []
        else:
            log.error(f"Apify run {run_id} timeout.")
            return []

        dataset_id = status_resp["data"]["defaultDatasetId"]
        items_resp = requests.get(
            f"{APIFY_BASE}/datasets/{dataset_id}/items",
            params={"token": self.token, "format": "json"},
            timeout=30
        )
        items_resp.raise_for_status()
        raw_items = items_resp.json()

        if not raw_items:
            return []

        valid  = [i for i in raw_items if "error" not in i]
        errors = [i for i in raw_items if "error" in i]
        for e in errors:
            log.warning(f"[{page_name}] Apify error: {e.get('error')} — {e.get('errorDescription','')}")
        if not valid:
            return []

        return [self._normalize(item, page_name) for item in valid]

    def _normalize(self, raw: dict, source_page: str) -> dict:
        text     = raw.get("text", "").strip()
        url      = raw.get("url") or raw.get("topLevelUrl", "")
        post_id  = str(raw.get("postId", ""))
        date     = raw.get("time") or str(raw.get("timestamp", ""))
        is_video = raw.get("isVideo", False)


        image_url = self._extract_best_image(raw.get("media", []))

        if not text and is_video:
            log.info(f"Video sin texto en '{source_page}' — omitiendo.")
        if not text and not is_video:
            log.warning(
                f"Post sin texto de '{source_page}' "
                f"(postId={post_id}). Campos: {list(raw.keys())}"
            )

        return {
            "id":          post_id,
            "url":         url,
            "text":        text,
            "date":        date,
            "source_page": source_page,
            "likes":       raw.get("likes", 0) or raw.get("topReactionsCount", 0),
            "shares":      raw.get("shares", 0),
            "image_url":   image_url,
            "is_video":    is_video,
        }

    def _extract_best_image(self, media: list) -> str:
        """
        Recorre todos los items de media[] y retorna la primera URL
        de imagen valida de fbcdn.net.

        Maneja los casos:
          - post con 1 foto
          - album con 2+ fotos (toma la primera)
          - video con thumbnail
          - media item con campo 'images' anidado (algunas versiones del actor)
        """
        if not isinstance(media, list):
            return ""

        for item in media:
            if not isinstance(item, dict):
                continue

            # Caso 1: thumbnail directo
            thumb = item.get("thumbnail", "")
            if thumb and "fbcdn.net" in str(thumb):
                return str(thumb)

            # Caso 2: campo 'url' que apunta a fbcdn (no a facebook.com)
            url = item.get("url", "")
            if url and "fbcdn.net" in str(url):
                return str(url)

            # Caso 3: campo 'images' anidado (array de resoluciones)
            images = item.get("images", [])
            if isinstance(images, list):
                for img in images:
                    if isinstance(img, dict):
                        src = img.get("src") or img.get("url", "")
                        if src and "fbcdn.net" in str(src):
                            return str(src)

            # Caso 4: campo 'photo' con 'image' anidado
            photo = item.get("photo", {})
            if isinstance(photo, dict):
                src = photo.get("image", {}).get("uri", "")
                if src and "fbcdn.net" in str(src):
                    return str(src)

        return ""

    def _mock_posts(self) -> list[dict]:
        return [
            {
                "id": "mock_001",
                "url": "https://facebook.com/ancashaldia/posts/001",
                "text": (
                    "URGENTE: Se reportan disparos durante una despedida funebre "
                    "en el sector El Porvenir, Lima Barranca. Heridos en la escena."
                ),
                "date": datetime.now().isoformat(),
                "source_page": "ancashaldia",
                "likes": 120, "shares": 45,
                "image_url": "",
            },
        ]