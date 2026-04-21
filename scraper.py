"""
scraper.py — Scraping de Facebook con Playwright (navegador real).
Primera vez: ejecutar `python login_fb.py` para guardar la sesión.
Después: corre solo sin pedir login.
"""

import os
import re
import logging
from datetime import datetime, timedelta, timezone
from playwright.sync_api import sync_playwright
from config import Config

log = logging.getLogger(__name__)

SESSION_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fb_session")

# Browser singleton — se lanza una vez y se reutiliza entre páginas
_pw  = None
_ctx = None


def _load_cookies_txt(path: str) -> list[dict]:
    """Convierte cookies.txt (formato Netscape) al formato de Playwright."""
    cookies = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split("\t")
                if len(parts) < 7:
                    continue
                domain, _, path_c, secure, expires, name, value = parts[:7]
                cookies.append({
                    "name":     name,
                    "value":    value,
                    "domain":   domain,
                    "path":     path_c,
                    "expires":  int(expires) if expires.isdigit() else -1,
                    "httpOnly": False,
                    "secure":   secure.upper() == "TRUE",
                    "sameSite": "None",
                })
        log.info(f"[Scraper] {len(cookies)} cookies cargadas desde {path}")
    except Exception as e:
        log.warning(f"[Scraper] No se pudo leer cookies.txt: {e}")
    return cookies


def _get_context():
    global _pw, _ctx
    if _ctx is None:
        log.info("[Scraper] Iniciando browser...")
        _pw  = sync_playwright().start()
        _ctx = _pw.chromium.launch_persistent_context(
            SESSION_DIR,
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
            ],
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
            locale="es-PE",
        )

        # Cargar cookies de Facebook si existen
        cookies_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cookies.txt")
        if os.path.isfile(cookies_file):
            cookies = _load_cookies_txt(cookies_file)
            if cookies:
                _ctx.add_cookies(cookies)
                log.info("[Scraper] Cookies de Facebook cargadas en el browser.")
        else:
            log.warning("[Scraper] No se encontró cookies.txt — puede fallar el login.")

        log.info("[Scraper] Browser listo.")
    return _ctx


def close_browser():
    global _pw, _ctx
    if _ctx:
        try:
            _ctx.close()
        except Exception:
            pass
        _ctx = None
    if _pw:
        try:
            _pw.stop()
        except Exception:
            pass
        _pw = None



def _relative_to_iso(time_text: str) -> str:
    """Convierte '4 h', '2 d', '30 min' a ISO timestamp aproximado."""
    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone.utc)
    t   = time_text.strip().lower()
    try:
        num = int("".join(filter(str.isdigit, t)))
        if "d" in t:
            return (now - timedelta(days=num)).isoformat()
        elif "h" in t:
            return (now - timedelta(hours=num)).isoformat()
        elif "min" in t or "m" in t:
            return (now - timedelta(minutes=num)).isoformat()
        elif "w" in t:
            return (now - timedelta(weeks=num)).isoformat()
    except Exception:
        pass
    return now.isoformat()


class FacebookScraper:
    def __init__(self, config: Config):
        self.config = config

    def fetch_all_pages(self) -> list[dict]:
        all_posts = []
        for page_name in self.config.FACEBOOK_PAGES:
            try:
                posts = self._fetch_posts(page_name)
                all_posts.extend(posts)
                log.info(f"  {page_name}: {len(posts)} posts")
            except Exception as e:
                log.error(f"  Error scrapeando {page_name}: {e}")
        return all_posts

    def _fetch_posts(self, page_name: str) -> list[dict]:
        # Solo posts de hoy (desde medianoche hora Perú UTC-5)
        peru_tz    = timezone(timedelta(hours=-5))
        today_peru = datetime.now(peru_tz).replace(hour=0, minute=0, second=0, microsecond=0)
        cutoff     = today_peru.astimezone(timezone.utc)
        ctx        = _get_context()
        pw_page    = ctx.new_page()
        results    = []

        try:
            pw_page.goto(
                f"https://www.facebook.com/{page_name}",
                wait_until="domcontentloaded",
                timeout=25000
            )

            if "login" in pw_page.url or "checkpoint" in pw_page.url:
                log.error("[Scraper] Sin sesión. Ejecuta: python login_fb.py")
                return []

            try:
                pw_page.wait_for_selector('[role="article"]', timeout=15000)
            except Exception:
                log.warning(f"[{page_name}] Sin posts visibles.")
                return []

            # Scroll inicial para activar el feed
            pw_page.evaluate("window.scrollBy(0, 500)")
            pw_page.wait_for_timeout(2000)

            articles = pw_page.locator('[role="article"]').all()

            for article in articles[:self.config.POSTS_PER_PAGE + 2]:
                try:
                    # Buscar link de tiempo relativo ("4 h", "2 d", "30 min")
                    time_link = None
                    time_text = ""
                    post_url  = ""

                    for link in article.locator("a").all():
                        txt = (link.inner_text() or "").strip()
                        if re.match(r"^\d+\s*(min|h|d|w|s)$", txt):
                            time_link = link
                            time_text = txt
                            post_url  = (link.get_attribute("href") or "").split("?")[0]
                            break

                    if not time_link:
                        continue

                    # Texto del post
                    text = ""
                    for el in article.locator('[dir="auto"]').all():
                        t = (el.inner_text() or "").strip()
                        if len(t) > len(text) and len(t) < 5000:
                            text = t

                    if not text:
                        continue

                    # Scrollear el artículo para disparar lazy load de imagen
                    article.scroll_into_view_if_needed()
                    pw_page.wait_for_timeout(1500)

                    # Extraer imagen real (ignorar SVG placeholders)
                    image_b64 = ""
                    for img in article.locator("img").all():
                        src = img.get_attribute("src") or ""
                        if "fbcdn.net" in src and not src.startswith("data:"):
                            image_b64 = self._download_image_b64(src)
                            break

                    # Fecha aproximada desde tiempo relativo
                    date = _relative_to_iso(time_text)
                    try:
                        pt = datetime.fromisoformat(date)
                        if pt.tzinfo is None:
                            pt = pt.replace(tzinfo=timezone.utc)
                        if pt < cutoff:
                            continue
                    except Exception:
                        pass

                    # Post ID desde URL
                    post_id = ""
                    m = re.search(r"/(\d{10,})/", post_url)
                    if m:
                        post_id = m.group(1)

                    results.append({
                        "id":          post_id,
                        "url":         post_url,
                        "text":        text,
                        "date":        date,
                        "source_page": page_name,
                        "likes":       0,
                        "shares":      0,
                        "image_url":   image_b64,
                        "is_video":    False,
                    })

                except Exception as e:
                    log.debug(f"[{page_name}] Error en artículo: {e}")

        except Exception as e:
            log.warning(f"[{page_name}] Error: {e}")
        finally:
            pw_page.close()

        return results

    def _download_image_b64(self, image_url: str) -> str:
        """
        Descarga la imagen usando la sesión activa del browser (con cookies)
        y retorna base64. Así el bridge puede enviarla aunque sea privada.
        Formato: 'data:image/jpeg;base64,<datos>'
        """
        if not image_url or not image_url.startswith("http"):
            return ""
        try:
            ctx  = _get_context()
            resp = ctx.request.get(image_url, timeout=10000)
            if resp.ok:
                import base64
                b64  = base64.b64encode(resp.body()).decode()
                mime = resp.headers.get("content-type", "image/jpeg").split(";")[0]
                return f"data:{mime};base64,{b64}"
        except Exception as e:
            log.debug(f"No se pudo descargar imagen: {e}")
        return ""

    def _normalize(self, raw: dict, source_page: str) -> dict:
        date      = raw.get("timestamp") or _relative_to_iso(raw.get("timeText", ""))
        image_url = raw.get("imageUrl", "")

        # Descargar imagen como base64 para que el bridge pueda enviarla
        if image_url:
            image_b64 = self._download_image_b64(image_url)
        else:
            image_b64 = ""

        return {
            "id":          raw.get("postId", ""),
            "url":         raw.get("postUrl", ""),
            "text":        (raw.get("text") or "").strip(),
            "date":        date,
            "source_page": source_page,
            "likes":       0,
            "shares":      0,
            "image_url":   image_b64 or image_url,
            "is_video":    False,
        }
