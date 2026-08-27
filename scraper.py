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
import time as _time_mod
import logging
import threading
import queue as _queue
from datetime import datetime, timedelta, timezone
from playwright.sync_api import sync_playwright
from config import Config

log = logging.getLogger(__name__)

SESSION_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fb_session")

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
    """Convierte contenido de cookies.txt (formato Netscape) al formato de Playwright.

    Tolera tabs (formato original) y multi-espacios (cuando Railway u otros
    servicios convierten tabs al setear la variable de entorno).
    """
    cookies = []
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # Tabs primero (formato Netscape canonico).
        parts = line.split("\t")
        if len(parts) < 7:
            # Fallback: cualquier secuencia de whitespace, max 7 campos
            parts = re.split(r"\s+", line, maxsplit=6)
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


_session_expired    = False  # bandera: sesión con cookies expiró, modo anónimo
_last_login_attempt = 0.0    # epoch del ultimo intento de re-login (cooldown)
_LOGIN_COOLDOWN_S   = 600    # 10 min entre re-intentos para no martillar a FB


def _mark_session_expired():
    """
    Cookies caducaron: intenta re-login con FB_EMAIL/FB_PASSWORD.
    Solo cae a modo anónimo si el re-login falla o se intentó hace < 10 min.
    """
    global _session_expired, _last_login_attempt

    now = _time_mod.time()
    if now - _last_login_attempt < _LOGIN_COOLDOWN_S:
        if not _session_expired:
            _session_expired = True
            log.warning("[Scraper] Sesión expirada — modo anónimo (cooldown de re-login activo)")
        return

    _last_login_attempt = now
    log.warning("[Scraper] Sesión FB expirada → intentando re-login automático...")

    if _ctx:
        try:
            _ctx.clear_cookies()
        except Exception as e:
            log.debug(f"[Scraper] Error limpiando cookies: {e}")

        if _do_login(_ctx):
            log.info("[Scraper] ✓ Re-login exitoso — sesión renovada")
            _session_expired = False
            return

    _session_expired = True
    log.warning("[Scraper] Re-login falló — operando en modo anónimo hasta el próximo cooldown")


def is_session_expired() -> bool:
    return _session_expired


def _do_login(ctx) -> bool:
    """Intenta login con FB_EMAIL/FB_PASSWORD desde dentro del worker thread."""
    email    = os.environ.get("FB_EMAIL", "")
    password = os.environ.get("FB_PASSWORD", "")
    if not email or not password:
        log.warning("[Scraper] Sin FB_EMAIL/FB_PASSWORD — no se puede hacer login automático.")
        return False

    log.info("[Scraper] Intentando login automático (cuenta dedicada)...")
    page = ctx.new_page()
    try:
        page.goto("https://m.facebook.com/login", wait_until="domcontentloaded", timeout=25000)
        page.wait_for_load_state("networkidle", timeout=10000)

        # Intentar varios selectores para el email
        filled = False
        for sel in ['input[name="email"]', '#email', 'input[type="email"]']:
            try:
                page.fill(sel, email, timeout=8000)
                filled = True
                break
            except Exception:
                continue

        if not filled:
            log.error("[Scraper] No se encontró el campo email en la página de login.")
            return False

        for sel in ['input[name="pass"]', '#pass', 'input[type="password"]']:
            try:
                page.fill(sel, password, timeout=8000)
                break
            except Exception:
                continue

        for sel in ['button[name="login"]', 'button[type="submit"]', 'input[type="submit"]']:
            try:
                page.click(sel, timeout=8000)
                break
            except Exception:
                continue

        page.wait_for_timeout(6000)

        if "login" in page.url or "checkpoint" in page.url:
            log.error("[Scraper] Login fallido — Facebook bloqueó o requiere verificación.")
            return False

        log.info("[Scraper] ✓ Login automático exitoso — sesión guardada en volumen.")
        return True
    except Exception as e:
        log.error(f"[Scraper] Error en login: {e}")
        return False
    finally:
        page.close()


def _get_context():
    """Debe llamarse SOLO desde el hilo _worker."""
    global _pw, _ctx, _session_expired
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

        # Cargar cookies si hay (para sesiones previas o desde env)
        cookies_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cookies.txt")
        if os.path.isfile(cookies_file):
            cookies = _load_cookies_txt(cookies_file)
            if cookies:
                _ctx.add_cookies(cookies)
        elif os.environ.get("FB_COOKIES"):
            cookies = _load_cookies_txt("")
            if cookies:
                _ctx.add_cookies(cookies)

        # Verificar sesión; si no hay, intentar login o continuar anónimo
        test = _ctx.new_page()
        try:
            test.goto("https://www.facebook.com", wait_until="domcontentloaded", timeout=20000)
            test.wait_for_timeout(2000)
            if "login" in test.url or "checkpoint" in test.url:
                test.close()
                if _do_login(_ctx):
                    log.info("[Scraper] ✓ Login automático exitoso.")
                    _session_expired = False
                else:
                    log.warning("[Scraper] Sin login — modo anónimo (páginas públicas disponibles).")
                    _session_expired = True
            else:
                log.info("[Scraper] ✓ Sesión de Facebook válida.")
                test.close()
                _session_expired = False
        except Exception as ex:
            log.warning(f"[Scraper] Error verificando sesión: {ex}")
            test.close()
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


def _normalize_fb_url(href: str) -> str:
    """
    Convierte un href de Facebook en una URL absoluta navegable.
      - Paths relativos (/posts/...) → https://www.facebook.com/posts/...
      - story.php / permalink.php → conserva query (story_fbid es el ID del post)
      - /posts/, /videos/, /reel/ → quita query (fbclid y tracking)
    """
    if not href:
        return ""
    if href.startswith("/"):
        href = "https://www.facebook.com" + href
    if "story.php" in href or "permalink.php" in href:
        return href  # query params identifican el post
    return href.split("?")[0]


def _relative_to_iso(time_text: str) -> str:
    """Convierte '4 h', '2 d', '30 min', '2 sem', '3 mes' a ISO timestamp aproximado."""
    now = datetime.now(timezone.utc)
    t   = time_text.strip().lower()
    try:
        num = int("".join(filter(str.isdigit, t)))
        if "min" in t:                                        # minutos — va antes de "m"
            return (now - timedelta(minutes=num)).isoformat()
        elif "h" in t:
            return (now - timedelta(hours=num)).isoformat()
        elif "sem" in t or "w" in t:                          # semanas (español) o weeks
            return (now - timedelta(weeks=num)).isoformat()
        elif "mes" in t or "ano" in t or "año" in t:          # meses / años → muy antiguo
            return (now - timedelta(days=num * 30)).isoformat()
        elif "d" in t:
            return (now - timedelta(days=num)).isoformat()
    except Exception:
        pass
    # No se pudo parsear → asumir muy antiguo para que sea filtrado
    return (now - timedelta(days=365)).isoformat()


class FacebookScraper:
    def __init__(self, config: Config):
        self.config = config

    def fetch_all_pages(self) -> list[dict]:
        all_posts = []
        for page_name in self.config.FACEBOOK_PAGES:
            try:
                posts = self.fetch_posts(page_name)
                all_posts.extend(posts)
                log.info(f"  {page_name}: {len(posts)} posts")
            except Exception as e:
                log.error(f"  Error scrapeando {page_name}: {e}")
        return all_posts

    def fetch_posts(self, page_name: str) -> list[dict]:
        """Despacha el scraping al hilo de Playwright y retorna los posts."""
        return _worker.run(lambda: self._fetch_posts_sync(page_name))

    def _fetch_posts_sync(self, page_name: str) -> list[dict]:
        """Corre DENTRO del hilo _worker — puede usar Playwright libremente."""
        max_age  = datetime.now(timezone.utc) - timedelta(hours=24)  # descartar posts > 24h
        max_posts = self.config.POSTS_PER_PAGE                        # hasta 8 por página
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
                _mark_session_expired()
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
            skipped_old   = 0
            skipped_empty = 0

            for article in articles[:max_posts * 2]:  # evalúa hasta 16 para encontrar 8 recientes
                try:
                    time_link = None
                    time_text = ""
                    post_url  = ""

                    for link in article.locator("a").all():
                        txt  = (link.inner_text() or "").strip()
                        href = (link.get_attribute("href") or "")
                        # Tiempo relativo (modo con sesión): "8 h", "30 min", "2 d", "1 sem"
                        if re.match(r"^\d+\s*(min|h|d|sem|w|s)$", txt, re.IGNORECASE):
                            time_link = link
                            time_text = txt
                            post_url  = _normalize_fb_url(href)
                            break
                        # Fecha absoluta FB: "14 de abr.", "5 mayo" → post >7 días → filtrar
                        if re.match(r"^\d{1,2}\s+(de\s+)?[a-z\xe1\xe9\xed\xf3\xfa\xfc]{3}", txt, re.IGNORECASE):
                            time_link = link
                            time_text = "30 d"  # forzar antiguo → descartado por max_age
                            post_url  = _normalize_fb_url(href)
                            break
                        # Fallback modo anónimo: enlace directo a publicación
                        if not time_link and re.search(
                            r"/(posts|permalink|videos)/|story\.php|\?story_fbid=|/reel/", href
                        ):
                            time_link = link
                            time_text = "1 h"   # asumir reciente
                            post_url  = _normalize_fb_url(href)

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
                        skipped_empty += 1
                        continue

                    # Filtro de fecha ANTES del scroll/imagen → posts viejos se descartan rápido
                    date = _relative_to_iso(time_text)
                    try:
                        pt = datetime.fromisoformat(date)
                        if pt.tzinfo is None:
                            pt = pt.replace(tzinfo=timezone.utc)
                        if pt < max_age:
                            skipped_old += 1
                            continue
                    except Exception:
                        pass

                    article.scroll_into_view_if_needed()
                    pw_page.wait_for_timeout(1500)

                    image_b64 = ""
                    for img in article.locator("img").all():
                        src = img.get_attribute("src") or ""
                        if "fbcdn.net" not in src or src.startswith("data:"):
                            continue
                        try:
                            natural_w = img.evaluate("el => el.naturalWidth")
                            if natural_w and natural_w < 200:
                                continue  # avatar / icono pequeño
                        except Exception:
                            pass
                        image_b64 = self._download_image_b64_sync(src)
                        if image_b64:
                            break

                    # Videos: extraer poster (thumbnail) si no hay imagen
                    is_video = False
                    try:
                        videos = article.locator("video").all()
                        if videos:
                            is_video = True
                            if not image_b64:
                                for vid in videos:
                                    poster = vid.get_attribute("poster") or ""
                                    if poster and poster.startswith("http"):
                                        image_b64 = self._download_image_b64_sync(poster)
                                        if image_b64:
                                            break
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
                        "is_video":    is_video,
                    })
                    if len(results) >= max_posts:
                        break

                except Exception as e:
                    log.debug(f"[{page_name}] Error en artículo: {e}")

            if skipped_old or skipped_empty:
                motivos = []
                if skipped_old:   motivos.append(f"{skipped_old} antigua(s)")
                if skipped_empty: motivos.append(f"{skipped_empty} sin texto")
                log.info(f"[{page_name}] {len(results)} útil(es) / {len(articles)} en feed — descartado(s): {', '.join(motivos)}")

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
