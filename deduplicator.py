"""deduplicator.py — Evita enviar la misma noticia dos veces."""

import os
import re
import hashlib
import logging
import unicodedata
import psycopg2
from collections import Counter
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from functools import wraps
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode

log = logging.getLogger(__name__)

_dedup_stats = Counter()


def log_dedup_stats():
    """Loguea (y resetea) el resumen de NIVELes de dedup del ciclo."""
    if not _dedup_stats or _dedup_stats.get("total_checks", 0) == 0:
        _dedup_stats.clear()
        return

    total = _dedup_stats.pop("total_checks", 0)
    llamadas_ia = _dedup_stats.pop("NIVEL 6 llamadas IA", 0)
    deterministas = sum(v for k, v in _dedup_stats.items() if k != "NIVEL 6")
    ia_duplicados = _dedup_stats.get("NIVEL 6", 0)

    resumen = ", ".join(f"{k}={v}" for k, v in sorted(_dedup_stats.items())) or "sin duplicados"
    log.info(
        f"[Dedup] Resumen del ciclo: {total} chequeos, {llamadas_ia} llamadas a IA "
        f"(NIVEL 6) — {resumen}"
    )

    if llamadas_ia > 0 and llamadas_ia >= max(deterministas, 1):
        log.warning(
            f"[Dedup] ⚠️ Consumo excesivo de IA en dedup: {llamadas_ia} llamadas a OpenAI "
            f"en NIVEL 6 (fallback) frente a solo {deterministas} duplicados atrapados por "
            f"los niveles gratis (0-5, {ia_duplicados} de ellos confirmados como duplicado "
            f"por la IA). Cada llamada de NIVEL 6 cuesta tokens — revisar "
            f"JACCARD_THRESHOLD_TITULO / OVERLAP_THRESHOLD_TITULO si esto persiste."
        )

    _dedup_stats.clear()

JACCARD_THRESHOLD_TITULO = 0.35
JACCARD_THRESHOLD_CONTENIDO = 0.40
LEVENSHTEIN_THRESHOLD = 0.60
SIMILITUD_EVENTO_MIN = 0.55
OVERLAP_THRESHOLD_TITULO = 0.65

DEDUP_WINDOW_HOURS = 24
DEDUP_SAME_BUNDLE_HOURS = 0.5
DEDUP_SAME_SOURCE_HOURS = 6
DEDUP_SAME_LOCATION_HOURS = 0.25
DEDUP_SAME_PROVINCIA_HOURS = 24

_STOPWORDS_ES = {
    "el","la","los","las","de","del","en","a","y","o","u","un","una","unos","unas",
    "que","se","por","con","para","su","sus","es","al","lo","como","mas","pero","le",
    "ya","este","esta","estos","estas","fue","ha","han","hay","ser","son","muy",
    "sin","sobre","tras","entre","donde","cuando","tambien","todo","todos","toda",
    "todas","esto","eso","hace","hizo","tuvo","dijo","ante","ese","esa","esos","esas",
    "sera","ser","fue","fui","tras","cada","otro","otra","otros","otras","desde",
    "hasta","aun","aun","tan","ahi","alli","aqui","yo","tu","el","ella","nos",
}

_EVENT_KEYWORDS = {
    "muerta", "muerto", "muerte", "homicidio", "asesinato", "crimen",
    "accidente", "choque", "colisión", "disparo", "tiroteo", "balazo",
    "incendio", "fuego", "explosión", "derrumbe", "desmoronamiento",
    "inundación", "flood", "deslizamiento", "caída", "derrumbe",
    "robo", "asalto", "hurto", "robobanc", "robocasa", "secuestro",
    "violencia", "agresión", "ataque", "combate", "enfrentamiento",
    "arrestado", "detenido", "capturado", "aprehendido", "encarcelado",
    "herido", "lesionado", "grave", "coma", "hospital", "urgencia",
    "desaparecido", "extraviado", "hallado", "búsqueda", "rescate",
    "canon", "minería", "explotacion", "protestas", "bloqueo", "huelga",
    "corte", "vía", "carretera", "emergencia", "estado de emergencia",
}

_LOCATION_NORMALIZE = {
    "nuevochimbote": "chimbote",
    "nuevo chimbote": "chimbote",
    "villa maria": "villa maría",
    "chanchamayo": "chanchamayo",
    "pucallpa": "pucallpa",
    "huancayo": "huancayo",
}


def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def _normalize_text(s: str) -> str:
    s = _strip_accents(s.lower())
    s = re.sub(r'[^a-z0-9\s]', ' ', s)
    return re.sub(r'\s+', ' ', s).strip()


def _words_set(text: str) -> set:
    if not text:
        return set()
    norm = _strip_accents(text.lower())
    words = re.findall(r"[a-z]+", norm)
    return {w for w in words if len(w) >= 3 and w not in _STOPWORDS_ES}


def _jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def _overlap_coef(a: set, b: set) -> float:
    """Intersección / tamaño del set más chico — a diferencia de Jaccard, no se diluye cuando un set es mucho más grande que el otro."""
    if not a or not b:
        return 0.0
    inter = len(a & b)
    smaller = min(len(a), len(b))
    return inter / smaller if smaller else 0.0


def _levenshtein_ratio(s1: str, s2: str) -> float:
    return SequenceMatcher(None, s1, s2).ratio()


def _normalize_url(url: str) -> str:
    if not url:
        return ""

    parsed = urlparse(url.strip())

    clean_query = []
    for k, v in parse_qsl(parsed.query):
        key = k.lower()
        if not key.startswith("utm_") and key not in {
            "fbclid", "mibextid", "ref", "locale"
        }:
            clean_query.append((k, v))

    return urlunparse((
        parsed.scheme.lower(),
        parsed.netloc.lower(),
        parsed.path.rstrip("/"),
        "",
        urlencode(clean_query),
        ""
    ))


def _ai_are_same_event(titulo1: str, titulo2: str, desc1: str, desc2: str) -> bool:
    """NIVEL 6: le pregunta a la IA si dos alertas hablan del mismo evento."""
    try:
        import requests
        from config import Config

        config = Config()
        ai_provider = getattr(config, "AI_PROVIDER", "openai").lower()

        prompt = f"""Analiza estos dos titulares/resumenes de noticias, publicados con pocos minutos de diferencia.
¿Son la MISMA noticia o pertenecen a una MISMA historia EN DESARROLLO?
Responde "SI" si:
- Reportan el mismo evento (aunque con palabras distintas), O
- Son actualizaciones consecutivas de una cobertura EN VIVO sobre el mismo tema
  (ej. resultados electorales en tiempo real donde cambian las cifras o el candidato que lidera,
  un incendio cuyo numero de victimas se va actualizando, una busqueda de desaparecidos con avances).
Responde "NO" solo si son temas/eventos CLARAMENTE DISTINTOS sin relacion entre si.
Responde con una palabra: "SI" o "NO"

TITULO 1: {titulo1[:100]}
{desc1[:80]}

TITULO 2: {titulo2[:100]}
{desc2[:80]}

Respuesta:"""

        if ai_provider == "openai":
            key = config.OPENAI_API_KEY
            if not key:
                return False

            _dedup_stats["NIVEL 6 llamadas IA"] += 1
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {key}"},
                json={
                    "model": "gpt-4o-mini",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 10,
                    "temperature": 0
                },
                timeout=5
            )

            if response.status_code == 200:
                content = response.json()["choices"][0]["message"]["content"].strip().upper()
                first_token = re.split(r'[\s.,;:!?]+', content, maxsplit=1)[0]
                if first_token == "SI":
                    log.info(f"[Dedup] ⚡ NIVEL 6 (IA Semántica) → DUPLICADO DETECTADO")
                    return True
            return False

        return False

    except Exception as e:
        log.warning(f"[Dedup] IA fallback no disponible: {e}")
        return False


def _extract_event_signature(text: str) -> str:
    """Firma de evento: ubicación + palabra clave de evento + número, para detectar el mismo hecho narrado distinto."""
    if not text:
        return ""

    text_norm = _strip_accents(text.lower())

    location_words = []
    for word in text_norm.split():
        word_clean = re.sub(r'[^a-z]', '', word)
        if len(word_clean) >= 4 and word_clean not in _STOPWORDS_ES:
            normalized = _LOCATION_NORMALIZE.get(word_clean, word_clean)
            if normalized not in location_words:
                location_words.append(normalized)
            if len(location_words) >= 2:
                break

    location_sig = "_".join(location_words[:2]) if location_words else ""

    event_keyword = ""
    for keyword in _EVENT_KEYWORDS:
        if keyword in text_norm:
            event_keyword = keyword
            break

    numbers = re.findall(r'\d+[.,]?\d*', text)
    number_sig = numbers[0] if numbers else ""

    sig_parts = []
    if location_sig:
        sig_parts.append(location_sig)
    if event_keyword:
        sig_parts.append(event_keyword[:8])
    if number_sig:
        sig_parts.append(number_sig.replace('.', '').replace(',', '')[:6])

    sig = "_".join(sig_parts)
    return sig[:120] if sig else ""


def _get_conn():
    url = os.environ.get("DATABASE_URL")

    if not url:
        raise RuntimeError(
            "DATABASE_URL no está configurado. "
            "Agrega la cadena de conexión PostgreSQL en el archivo .env"
        )

    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)

    return psycopg2.connect(url)


def _reconnect_and_retry(method):
    """Reintenta el método una vez si la conexión a Postgres se cae a mitad de ejecución."""
    @wraps(method)
    def wrapper(self, *args, **kwargs):
        try:
            return method(self, *args, **kwargs)
        except (psycopg2.OperationalError, psycopg2.InterfaceError) as e:
            log.warning(f"[Dedup] Conexión perdida en {method.__name__} ({e}) — reconectando y reintentando...")
            try:
                self.conn.close()
            except Exception:
                pass
            self.conn = _get_conn()
            return method(self, *args, **kwargs)
    return wrapper


class Deduplicator:
    def __init__(self):
        self.conn = _get_conn()
        self._init_db()

    def log_dedup_stats(self):
        log_dedup_stats()

    def _cursor(self):
        try:
            self.conn.cursor().execute("SELECT 1")
        except Exception:
            log.warning("[Dedup] Reconectando a PostgreSQL...")
            try:
                self.conn.close()
            except Exception:
                pass
            self.conn = _get_conn()
        return self.conn.cursor()

    def _init_db(self):
        cur = self._cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS processed (
                hash      TEXT PRIMARY KEY,
                url       TEXT,
                seen_at   TEXT
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS sent_alerts (
                id               SERIAL PRIMARY KEY,
                content_hash     TEXT,
                titulo_hash      TEXT,
                titulo_norm      TEXT,
                descripcion_norm TEXT,
                departamento     TEXT,
                provincia        TEXT,
                subcategoria     TEXT,
                cliente          TEXT,
                resumen          TEXT,
                url              TEXT,
                sent_at          TEXT,
                UNIQUE(titulo_hash, departamento)
            )
        """)
        cur.execute("ALTER TABLE sent_alerts ADD COLUMN IF NOT EXISTS titulo_hash TEXT")
        cur.execute("ALTER TABLE sent_alerts ADD COLUMN IF NOT EXISTS descripcion_norm TEXT")
        cur.execute("ALTER TABLE sent_alerts ADD COLUMN IF NOT EXISTS provincia TEXT")
        cur.execute("ALTER TABLE sent_alerts ADD COLUMN IF NOT EXISTS url TEXT")

        cur.execute("""
            DELETE FROM sent_alerts
            WHERE titulo_hash IS NOT NULL
              AND departamento IS NOT NULL
              AND id NOT IN (
                SELECT MAX(id) FROM sent_alerts
                WHERE titulo_hash IS NOT NULL AND departamento IS NOT NULL
                GROUP BY titulo_hash, departamento
              )
        """)
        cur.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint c
                    JOIN pg_class t ON c.conrelid = t.oid
                    WHERE t.relname = 'sent_alerts'
                      AND c.conname = 'sent_alerts_titulo_hash_departamento_key'
                ) THEN
                    ALTER TABLE sent_alerts
                    ADD CONSTRAINT sent_alerts_titulo_hash_departamento_key
                    UNIQUE (titulo_hash, departamento);
                END IF;
            END $$;
        """)

        cur.execute("CREATE INDEX IF NOT EXISTS idx_dept_sent ON sent_alerts (departamento, sent_at)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_titulo_hash ON sent_alerts (titulo_hash)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_cliente_sent ON sent_alerts (cliente, sent_at)")

        self.conn.commit()
        self._cleanup_old()

    def _url_hash(self, post: dict) -> str:
        key = _normalize_url(post.get("url") or "") or _normalize_text(post.get("text", ""))[:300]
        return hashlib.md5(key.encode("utf-8")).hexdigest()

    def _content_hash(self, alert: dict) -> str:
        dept = (alert.get("departamento") or "").upper().strip()
        prov = (alert.get("provincia")    or "").upper().strip()
        sub  = (alert.get("subcategoria") or "").upper().strip()
        kws  = sorted(str(k).upper().strip() for k in (alert.get("palabras_clave") or []))
        key  = f"{dept}|{prov}|{sub}|{'-'.join(kws)}"
        return hashlib.md5(key.encode("utf-8")).hexdigest()

    def _titulo_hash(self, titulo: str) -> str:
        norm = _normalize_text(titulo)[:100]
        return hashlib.md5(norm.encode("utf-8")).hexdigest()

    # ─────────────────────────────────────────────
    # DEDUP DE POSTS
    # ─────────────────────────────────────────────
    @_reconnect_and_retry
    def already_processed(self, post: dict) -> bool:
        h = self._url_hash(post)
        cur = self._cursor()
        cur.execute("SELECT 1 FROM processed WHERE hash = %s", (h,))
        return cur.fetchone() is not None

    @_reconnect_and_retry
    def mark_processed(self, post: dict):
        h = self._url_hash(post)
        try:
            cur = self._cursor()
            cur.execute(
                "INSERT INTO processed (hash, url, seen_at) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
                (h, post.get("url", ""), datetime.now().isoformat())
            )
            self.conn.commit()
        except (psycopg2.OperationalError, psycopg2.InterfaceError):
            raise
        except Exception as e:
            self.conn.rollback()
            log.error(f"Error en dedup BD: {e}")

    # ─────────────────────────────────────────────
    # DEDUP DE ALERTAS
    # ─────────────────────────────────────────────
    @_reconnect_and_retry
    def is_duplicate_alert(self, alert: dict, window_hours: int = DEDUP_WINDOW_HOURS) -> bool:
        """Recorre NIVEL 0 → 6 en orden de costo; corta en el primero que confirme duplicado."""
        _dedup_stats["total_checks"] += 1

        # NIVEL 0: URL exacta
        url = alert.get("url", "").strip()
        if url:
            cur = self._cursor()
            cutoff = (datetime.now() - timedelta(hours=window_hours)).isoformat()
            cur.execute(
                "SELECT 1 FROM sent_alerts WHERE url = %s AND sent_at > %s LIMIT 1",
                (url, cutoff)
            )
            if cur.fetchone():
                log.info(f"[Dedup] ✓ NIVEL 0 (URL exacta) → DUPLICADO")
                _dedup_stats["NIVEL 0"] += 1
                return True

        # NIVEL 0.5: content hash exacto
        ch = self._content_hash(alert)
        cutoff = (datetime.now() - timedelta(hours=window_hours)).isoformat()
        cur = self._cursor()

        cur.execute(
            "SELECT 1 FROM sent_alerts WHERE content_hash = %s AND sent_at > %s LIMIT 1",
            (ch, cutoff)
        )
        if cur.fetchone():
            log.info(f"[Dedup] ✓ NIVEL 0.5 (Content Hash exacto) → DUPLICADO")
            _dedup_stats["NIVEL 0.5"] += 1
            return True

        # NIVEL 1: firma de evento (números + ubicaciones)
        titulo = alert.get("titulo", "").strip()
        desc = alert.get("resumen_whatsapp", "").strip()
        combined_text = f"{titulo} {desc}"

        if len(combined_text) > 20:
            sig = _extract_event_signature(combined_text)
            if sig:
                dept = (alert.get("departamento") or "").upper().strip()
                if dept:
                    cur = self._cursor()
                    cutoff = (datetime.now() - timedelta(hours=1)).isoformat()
                    cur.execute(
                        "SELECT resumen FROM sent_alerts WHERE departamento = %s AND sent_at > %s AND resumen IS NOT NULL",
                        (dept, cutoff)
                    )
                    for (rec_resumen,) in cur.fetchall():
                        if rec_resumen:
                            sig_existente = _extract_event_signature(f"{rec_resumen}")
                            if sig == sig_existente and sig:
                                log.info(f"[Dedup] ✓ NIVEL 1 (Firma evento '{sig}') → DUPLICADO")
                                _dedup_stats["NIVEL 1"] += 1
                                return True

        # NIVEL 2.5: mismo departamento + provincia + subcategoria en 15 min
        dept = (alert.get("departamento") or "").upper().strip()
        prov = (alert.get("provincia") or "").upper().strip()
        sub  = (alert.get("subcategoria") or "").upper().strip()

        if dept and prov and sub:
            cutoff_agressive = (datetime.now() - timedelta(hours=DEDUP_SAME_LOCATION_HOURS)).isoformat()

            cur.execute(
                """SELECT 1 FROM sent_alerts
                   WHERE departamento = %s AND provincia = %s
                   AND UPPER(COALESCE(subcategoria, '')) = %s
                   AND sent_at > %s LIMIT 1""",
                (dept, prov, sub, cutoff_agressive)
            )
            if cur.fetchone():
                log.info(f"[Dedup] ✓ NIVEL 2.5 (Mismo Lugar+Subcat {dept}/{prov}/{sub} en 15min) → DUPLICADO")
                _dedup_stats["NIVEL 2.5"] += 1
                return True

        # NIVEL 3: hash de título
        if titulo and len(titulo) > 10:
            th = self._titulo_hash(titulo)

            if dept:
                cur.execute(
                    "SELECT 1 FROM sent_alerts WHERE titulo_hash = %s AND departamento = %s AND sent_at > %s LIMIT 1",
                    (th, dept, cutoff)
                )
                if cur.fetchone():
                    log.info(f"[Dedup] ✓ NIVEL 3 (Hash título) → DUPLICADO")
                    _dedup_stats["NIVEL 3"] += 1
                    return True

        # NIVEL 4: Jaccard / Overlap / Levenshtein de títulos
        if titulo and len(titulo) > 10 and dept:
            set_titulo_nuevo = _words_set(titulo)
            if len(set_titulo_nuevo) >= 2:
                cur.execute(
                    "SELECT DISTINCT titulo_norm FROM sent_alerts "
                    "WHERE departamento = %s AND sent_at > %s AND titulo_norm IS NOT NULL",
                    (dept, cutoff)
                )

                for (titulo_norm,) in cur.fetchall():
                    if not titulo_norm:
                        continue
                    set_existente = set(titulo_norm.split())
                    score_jaccard = _jaccard(set_titulo_nuevo, set_existente)
                    score_overlap = _overlap_coef(set_titulo_nuevo, set_existente)

                    titulo_norm_completo = " ".join(titulo_norm.split())[:100]
                    titulo_nuevo_norm = _normalize_text(titulo)[:100]
                    score_leven = _levenshtein_ratio(titulo_nuevo_norm, titulo_norm_completo)

                    if score_jaccard >= JACCARD_THRESHOLD_TITULO:
                        log.info(
                            f"[Dedup] ✓ NIVEL 4 (Jaccard Título={score_jaccard:.2f}) → DUPLICADO"
                        )
                        _dedup_stats["NIVEL 4"] += 1
                        return True

                    if score_overlap >= OVERLAP_THRESHOLD_TITULO:
                        log.info(
                            f"[Dedup] ✓ NIVEL 4 (Overlap Título={score_overlap:.2f}) → DUPLICADO"
                        )
                        _dedup_stats["NIVEL 4"] += 1
                        return True

                    if score_leven >= LEVENSHTEIN_THRESHOLD:
                        log.info(
                            f"[Dedup] ✓ NIVEL 4 (Levenshtein={score_leven:.2f}) → DUPLICADO"
                        )
                        _dedup_stats["NIVEL 4"] += 1
                        return True

        # NIVEL 5: Jaccard de descripciones
        if desc and len(desc) > 15 and dept:
            set_desc_nuevo = _words_set(desc)
            if len(set_desc_nuevo) >= 3:
                cur.execute(
                    "SELECT descripcion_norm FROM sent_alerts "
                    "WHERE departamento = %s AND sent_at > %s AND descripcion_norm IS NOT NULL",
                    (dept, (datetime.now() - timedelta(hours=6)).isoformat())
                )

                for (desc_norm,) in cur.fetchall():
                    if not desc_norm:
                        continue
                    set_desc_existente = set(desc_norm.split())
                    score = _jaccard(set_desc_nuevo, set_desc_existente)

                    if score >= JACCARD_THRESHOLD_CONTENIDO:
                        log.info(
                            f"[Dedup] ✓ NIVEL 5 (Jaccard DESC={score:.2f}) → DUPLICADO"
                        )
                        _dedup_stats["NIVEL 5"] += 1
                        return True

        # NIVEL 6: fallback de IA (último recurso, único nivel que cuesta tokens)
        if titulo and desc and dept:
            set_t_new = _words_set(titulo)

            cutoff_ia = (datetime.now() - timedelta(hours=DEDUP_WINDOW_HOURS)).isoformat()
            cur.execute(
                "SELECT titulo_norm, descripcion_norm FROM sent_alerts "
                "WHERE departamento = %s AND sent_at > %s AND titulo_norm IS NOT NULL "
                "ORDER BY sent_at DESC LIMIT 40",
                (dept, cutoff_ia)
            )
            for (titulo_existente, desc_existente) in cur.fetchall():
                if not titulo_existente:
                    continue
                set_t_exist = set(titulo_existente.split())
                score_medio = _jaccard(set_t_new, set_t_exist)
                if 0.15 <= score_medio < JACCARD_THRESHOLD_TITULO:
                    log.debug(f"[Dedup] Comparando semánticamente (Jaccard={score_medio:.2f}): podría ser duplicado")
                    if _ai_are_same_event(
                        titulo, titulo_existente,
                        desc[:150], desc_existente[:150] if desc_existente else ""
                    ):
                        log.info(f"[Dedup] ⚡ NIVEL 6 (IA Semántica, Jaccard={score_medio:.2f}) → DUPLICADO")
                        _dedup_stats["NIVEL 6"] += 1
                        return True

            if prov:
                cutoff_prov = (datetime.now() - timedelta(hours=DEDUP_SAME_PROVINCIA_HOURS)).isoformat()
                cur.execute(
                    "SELECT titulo_norm, descripcion_norm FROM sent_alerts "
                    "WHERE departamento = %s AND provincia = %s AND sent_at > %s "
                    "AND titulo_norm IS NOT NULL ORDER BY sent_at DESC LIMIT 8",
                    (dept, prov, cutoff_prov)
                )
                for (titulo_existente, desc_existente) in cur.fetchall():
                    if not titulo_existente:
                        continue
                    set_t_exist = set(titulo_existente.split())
                    score = _jaccard(set_t_new, set_t_exist)
                    if score >= JACCARD_THRESHOLD_TITULO:
                        continue
                    log.debug(f"[Dedup] Misma provincia {dept}/{prov} (Jaccard={score:.2f}): consultando IA")
                    if _ai_are_same_event(
                        titulo, titulo_existente,
                        desc[:150], desc_existente[:150] if desc_existente else ""
                    ):
                        log.info(f"[Dedup] ⚡ NIVEL 6 (IA Semántica, misma provincia {dept}/{prov}) → DUPLICADO")
                        _dedup_stats["NIVEL 6"] += 1
                        return True

        return False

    @_reconnect_and_retry
    def mark_alert_sent(self, alert: dict):
        """Registra una alerta enviada, con doble-check de duplicado antes de guardar."""
        if alert.get("nivel") == "IGNORAR":
            return

        if self.is_duplicate_alert(alert):
            log.info(f"[Dedup] Rechazado: duplicado detectado en mark_alert_sent, NO se guarda")
            return

        ch = self._content_hash(alert)
        titulo = alert.get("titulo", "").strip()
        desc = alert.get("resumen_whatsapp", "").strip()
        url = alert.get("url", "").strip()

        titulo_words = " ".join(sorted(_words_set(titulo)))[:500] if titulo else ""
        desc_words = " ".join(sorted(_words_set(desc)))[:500] if desc else ""
        titulo_hash = self._titulo_hash(titulo) if titulo else None

        try:
            cur = self._cursor()

            if titulo_hash and alert.get("departamento"):
                cur.execute(
                    "SELECT 1 FROM sent_alerts WHERE titulo_hash = %s AND departamento = %s LIMIT 1",
                    (titulo_hash, alert.get("departamento"))
                )
                if cur.fetchone():
                    log.info(f"[Dedup] Rechazo en transacción: ya existe titulo_hash + dept")
                    self.conn.rollback()
                    return

            cur.execute(
                """INSERT INTO sent_alerts
                   (content_hash, titulo_hash, titulo_norm, descripcion_norm,
                    departamento, provincia, subcategoria, cliente, resumen, url, sent_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (titulo_hash, departamento) DO NOTHING""",
                (
                    ch,
                    titulo_hash,
                    titulo_words,
                    desc_words,
                    alert.get("departamento", ""),
                    alert.get("provincia", ""),
                    alert.get("subcategoria", ""),
                    alert.get("cliente", ""),
                    desc[:250],
                    url,
                    datetime.now().isoformat()
                )
            )

            rows_affected = cur.rowcount
            self.conn.commit()

            if rows_affected > 0:
                log.info(f"[Dedup] ✓ Alerta registrada para futuras dedups")
            else:
                log.info(f"[Dedup] ℹ️ Alerta ya existe (ON CONFLICT), no se insertó")

        except Exception as e:
            try:
                self.conn.rollback()
            except Exception:
                pass
            log.error(f"[Dedup] Error registrando alerta: {e}")

    # ─────────────────────────────────────────────
    # LIMPIEZA
    # ─────────────────────────────────────────────
    @_reconnect_and_retry
    def _cleanup_old(self):
        cutoff = (datetime.now() - timedelta(days=7)).isoformat()
        cutoff_alerts = (datetime.now() - timedelta(hours=DEDUP_WINDOW_HOURS * 2)).isoformat()
        cur = self._cursor()

        cur.execute("DELETE FROM processed WHERE seen_at < %s", (cutoff,))
        count_processed = cur.rowcount

        cur.execute("DELETE FROM sent_alerts WHERE sent_at < %s", (cutoff_alerts,))
        count_alerts = cur.rowcount

        self.conn.commit()

        if count_processed > 0 or count_alerts > 0:
            log.info(f"[Dedup] Limpieza: {count_processed} URLs, {count_alerts} alertas antiguas")
