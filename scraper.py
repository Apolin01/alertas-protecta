"""
scraper.py — Scraping de Facebook con Playwright (navegador real).
Primera vez: ejecutar `python login_fb.py` para guardar la sesión.
Después: corre solo sin pedir login.

Playwright sync API no puede correr dentro de un asyncio loop (Railway).
Solución: todo el código de Playwright corre en un hilo dedicado (_Worker)
que nunca tiene un event loop de asyncio.
"""

import os
import re
import logging
import threading
import queue as _queue
from datetime import datetime, timedelta, timezone
from playwright.sync_api import sync_playwright
from config import Config

log = logging.getLogger(__name__)

SESSION_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fb_session")


# ── Worker thread dedicado para Playwright ────────────────────
# Playwright sync API lanza error si hay un asyncio loop activo.
# Este hilo no tiene loop, así que sync Playwright funciona bien.

class _Worker:
    def __init__(self):
        self._q = _queue.Queue()
        t = threading.Thread(target=self._loop, daemon=True, name="pw-worker")
        t.start()

    def _loop(self):
        while True:
            item = self._q.get()
            if item is None:
                break
            rq, fn = item
            try:
                rq.put(("ok", fn()))
            except Exception as e:
                rq.put(("err", e))

    def run(self, fn):
        """Ejecuta fn() en el hilo de Playwright y retorna el resultado."""
        rq = _queue.Queue()
        self._q.put((rq, fn))
        status, val = rq.get()
        if status == "err":
            raise val
        return val

    def stop(self):
        self._q.put(None)


_worker = _Worker()


# ── Browser singleton (vive en el hilo _worker) ───────────────
_pw  = None
_ctx = None


def _parse_cookies_txt(content: str) -> list[dict]:
    """Convierte contenido de cookies.txt (formato Netscape) al formato de Playwright."""
    cookies = []
    for line in content.splitlines():
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
    return cookies


def _load_cookies_txt(path: str) -> list[dict]:
    """Carga cookies desde archivo .txt o desde variable de entorno FB_COOKIES."""
    env_cookies = os.environ.get("FB_COOKIES", "")
    if env_cookies:
        cookies = _parse_cookies_txt(env_cookies)
        if cookies:
            log.info(f"[Scraper] {len(cookies)} cookies cargadas desde FB_COOKIES")
            return cookies

    try:
        with open(path, encoding="utf-8") as f:
            content = f.read()
        cookies = _parse_cookies_txt(content)
        log.info(f"[Scraper] {len(cookies)} cookies cargadas desde {path}")
        return cookies
    except Exception as e:
        log.warning(f"[Scraper] No se pudo leer cookies.txt: {e}")
    return []


def _auto_login(ctx):
    """Login automático con FB_EMAIL y FB_PASSWORD. Llama solo desde _worker."""
    email = os.environ.get("FB_EMAIL", "")
    password = os.environ.get("FB_PASSWORD", "")
    if not email or not password:
        log.error("[Scraper] Sin sesión y sin FB_EMAIL/FB_PASSWORD — no se puede re-login.")
        return False
    log.info("[Scraper] Intentando login automático con FB_EMAIL...")
    page = ctx.new_page()
    try:
        page.goto("https://www.facebook.com/login", wait_until="domcontentloaded", timeout=20000)
        page.fill('input[name="email"]', email)
        page.fill('input[name="pass"]', password)
        page.click('button[name="login"]')
        page.wait_for_timeout(5000)
        if "login" in page.url or "checkpoint" in page.url:
            log.error("[Scraper] Login fallido — Facebook bloqueó o requiere verificación.")
            return False
        log.info("[Scraper] Login automático exitoso.")
        return True
    except Exception as e:
        log.error(f"[Scraper] Error en login automático: {e}")
        return False
    finally:
        page.close()


def _get_context():
    """Debe llamarse SOLO desde el hilo _worker."""
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

        cookies_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cookies.txt")
        if os.path.isfile(cookies_file):
            cookies = _load_cookies_txt(cookies_file)
            if cookies:
                _ctx.add_cookies(cookies)
                log.info("[Scraper] Cookies de Facebook cargadas en el browser.")
        elif os.environ.get("FB_COOKIES"):
            cookies = _load_cookies_txt("")
            if cookies:
                _ctx.add_cookies(cookies)
                log.info("[Scraper] Cookies de Facebook cargadas desde env.")
        else:
            log.warning("[Scraper] No se encontró cookies.txt ni FB_COOKIES.")

        log.info("[Scraper] Browser listo.")
    return _ctx


def close_browser():
    def _close():
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

    _worker.run(_close)


def _relative_to_iso(time_text: str) -> str:
    """Convierte '4 h', '2 d', '30 min' a ISO timestamp aproximado."""
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
        """Despacha el scraping al hilo de Playwright y retorna los posts."""
        return _worker.run(lambda: self._fetch_posts_sync(page_name))

    def _fetch_posts_sync(self, page_name: str) -> list[dict]:
        """Corre DENTRO del hilo _worker — puede usar Playwright libremente."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=6)
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
                pw_page.close()
                log.warning("[Scraper] Sesión expirada — intentando re-login automático...")
                if _auto_login(_get_context()):
                    pw_page = _get_context().new_page()
                    pw_page.goto(
                        f"https://www.facebook.com/{page_name}",
                        wait_until="domcontentloaded",
                        timeout=25000
                    )
                    if "login" in pw_page.url or "checkpoint" in pw_page.url:
                        log.error("[Scraper] Re-login falló. Configura FB_EMAIL y FB_PASSWORD en Railway.")
                        return []
                else:
                    return []

            try:
                pw_page.wait_for_selector('[role="article"]', timeout=15000)
            except Exception:
                log.warning(f"[{page_name}] Sin posts visibles.")
                return []

            # Scroll progresivo para cargar más posts del feed
            for _ in range(3):
                pw_page.evaluate("window.scrollBy(0, 800)")
                pw_page.wait_for_timeout(1500)

            articles = pw_page.locator('[role="article"]').all()

            for article in articles[:self.config.POSTS_PER_PAGE + 2]:
                try:
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

                    # Leer innerText completo y cortar antes de la barra de acciones
                    # ("Me gusta / Comentar / Compartir"), que separa el cuerpo del post
                    # de los comentarios. Cada botón aparece solo en su propia línea.
                    # Detectar la línea de la hora ("3 h", "2 d", "30 min") y
                    # empezar a leer el cuerpo del post DESPUÉS de ella.
                    text = article.evaluate("""
                        node => {
                            const raw = (node.innerText || '');
                            const lines = raw.split('\\n').map(l => l.trim()).filter(l => l);
                            const ACTIONS = new Set([
                                'Me gusta','Like','Comentar','Comment',
                                'Compartir','Share','Reaccionar','React'
                            ]);
                            const CUTOFF_CONTAINS = [
                                'Todas las reacciones','All reactions',
                                'reacciones:','reactions:'
                            ];
                            const VIDEO_RE = /\\d+:\\d+\\s*\\/\\s*\\d+:\\d+/;
                            // Corte: antes de la barra de acciones o conteo de reacciones
                            let cutoff = lines.length;
                            for (let i = 0; i < lines.length; i++) {
                                if (ACTIONS.has(lines[i])) { cutoff = i; break; }
                                if (CUTOFF_CONTAINS.some(p => lines[i].includes(p))) { cutoff = i; break; }
                            }
                            // Inicio: línea DESPUÉS de la que contiene la hora relativa
                            // Buscar patrón tipo "3 h", "2 d", "30 min", "1 h · Público"
                            const timeRe = /^\\d+\\s*(min|h|d|w|s)\\b/i;
                            let startIdx = 1; // mínimo saltar nombre de página
                            for (let i = 0; i < Math.min(cutoff, 8); i++) {
                                if (timeRe.test(lines[i])) { startIdx = i + 1; break; }
                            }
                            // Filtrar líneas con duraciones de video (0:00 / 3:44)
                            const bodyLines = lines.slice(startIdx, cutoff)
                                .filter(l => !VIDEO_RE.test(l));
                            const body = bodyLines.join(' ').trim();
                            return body.replace(/Ver más$/, '').replace(/See more$/, '').trim();
                        }
                    """)

                    if not text:
                        continue

                    article.scroll_into_view_if_needed()
                    pw_page.wait_for_timeout(1500)

                    image_b64 = ""
                    for img in article.locator("img").all():
                        src = img.get_attribute("src") or ""
                        if "fbcdn.net" in src and not src.startswith("data:"):
                            image_b64 = self._download_image_b64_sync(src)
                            break

                    date = _relative_to_iso(time_text)
                    try:
                        pt = datetime.fromisoformat(date)
                        if pt.tzinfo is None:
                            pt = pt.replace(tzinfo=timezone.utc)
                        if pt < cutoff:
                            continue
                    except Exception:
                        pass

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
        """Descarga imagen desde el hilo principal (despacha al worker)."""
        return _worker.run(lambda: self._download_image_b64_sync(image_url))

    def _download_image_b64_sync(self, image_url: str) -> str:
        """Descarga imagen dentro del hilo _worker usando la sesión activa."""
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
        image_b64 = self._download_image_b64(image_url) if image_url else ""

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
