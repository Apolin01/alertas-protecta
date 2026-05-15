"""
deduplicator.py — Evita enviar la misma noticia dos veces.

Dos niveles de deduplicacion:
  1. Por URL exacta del post (tabla 'processed')
  2. Por similitud de contenido — si dos posts hablan del mismo hecho
     (mismo departamento + misma subcategoria + palabras_clave) o si el
     titulo+resumen comparten >= 65% de palabras significativas (Jaccard)
     en las ultimas 12h, se considera duplicado aunque vengan de paginas
     distintas.
"""

import os
import re
import hashlib
import logging
import unicodedata
import psycopg2
from datetime import datetime, timedelta

log = logging.getLogger(__name__)

# Umbral de similitud para considerar dos alertas como el mismo evento
JACCARD_THRESHOLD = 0.65
# Ventana de busqueda hacia atras para nivel 2
DEDUP_WINDOW_HOURS = 12

# Stopwords español + palabras frecuentes en titulares de noticias
_STOPWORDS_ES = {
    "el","la","los","las","de","del","en","a","y","o","u","un","una","unos","unas",
    "que","se","por","con","para","su","sus","es","al","lo","como","mas","pero","le",
    "ya","este","esta","estos","estas","fue","ha","han","hay","ser","son","muy",
    "sin","sobre","tras","entre","donde","cuando","tambien","todo","todos","toda",
    "todas","esto","eso","hace","hizo","tuvo","dijo","ante","ese","esa","esos","esas",
    "sera","ser","fue","fui","tras","cada","otro","otra","otros","otras","desde",
    "hasta","aun","aun","tan","ahi","alli","aqui","yo","tu","el","ella","nos",
}


def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def _words_set(text: str) -> set:
    """Tokeniza: lowercase, sin tildes, solo letras, sin stopwords, longitud >= 3."""
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


def _get_conn():
    url = os.environ["DATABASE_URL"]
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return psycopg2.connect(url)


class Deduplicator:
    def __init__(self):
        self.conn = _get_conn()
        self._init_db()

    def _cursor(self):
        """Retorna cursor reconectando si la conexión cayó."""
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
                id            SERIAL PRIMARY KEY,
                content_hash  TEXT UNIQUE,
                departamento  TEXT,
                subcategoria  TEXT,
                cliente       TEXT,
                resumen       TEXT,
                titulo_norm   TEXT,
                sent_at       TEXT
            )
        """)
        # Migracion suave si la tabla ya existia sin titulo_norm
        cur.execute("ALTER TABLE sent_alerts ADD COLUMN IF NOT EXISTS titulo_norm TEXT")
        cur.execute(
            "CREATE INDEX IF NOT EXISTS sent_alerts_dept_idx ON sent_alerts (departamento, sent_at)"
        )
        self.conn.commit()
        self._cleanup_old()

    def _url_hash(self, post: dict) -> str:
        key = post.get("url") or post.get("text", "")
        return hashlib.md5(key.encode("utf-8")).hexdigest()

    def _content_hash(self, alert: dict) -> str:
        """
        Hash exacto basado en estructura clasificada:
        departamento + provincia + subcategoria + palabras_clave ordenadas.
        Identifica el mismo evento cuando la IA mantiene categorias estables.
        Para casos donde la IA varia, hay un segundo nivel (Jaccard).
        """
        dept = (alert.get("departamento") or "").upper().strip()
        prov = (alert.get("provincia")    or "").upper().strip()
        sub  = (alert.get("subcategoria") or "").upper().strip()
        kws  = sorted(str(k).upper().strip() for k in (alert.get("palabras_clave") or []))
        key  = f"{dept}|{prov}|{sub}|{'-'.join(kws)}"
        return hashlib.md5(key.encode("utf-8")).hexdigest()

    # ─────────────────────────────────────────────
    # DEDUP DE POSTS (nivel 1 — por URL)
    # ─────────────────────────────────────────────
    def already_processed(self, post: dict) -> bool:
        h = self._url_hash(post)
        cur = self._cursor()
        cur.execute("SELECT 1 FROM processed WHERE hash = %s", (h,))
        return cur.fetchone() is not None

    def mark_processed(self, post: dict):
        h = self._url_hash(post)
        try:
            cur = self._cursor()
            cur.execute(
                "INSERT INTO processed (hash, url, seen_at) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
                (h, post.get("url", ""), datetime.now().isoformat())
            )
            self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            log.error(f"Error en dedup BD: {e}")

    # ─────────────────────────────────────────────
    # DEDUP DE ALERTAS (nivel 2 — por contenido)
    # ─────────────────────────────────────────────
    def is_duplicate_alert(self, alert: dict, window_hours: int = DEDUP_WINDOW_HOURS) -> bool:
        """
        Retorna True si ya se envio una alerta similar en las ultimas N horas.

        Dos niveles:
          A) Hash exacto sobre (departamento, provincia, subcategoria, palabras_clave).
          B) Si A no matchea, comparar Jaccard del titulo+resumen contra alertas
             del mismo departamento en la ventana. >= 0.65 → duplicado.
        """
        ch = self._content_hash(alert)
        cutoff = (datetime.now() - timedelta(hours=window_hours)).isoformat()
        cur = self._cursor()

        # Nivel A: hash exacto
        cur.execute(
            "SELECT 1 FROM sent_alerts WHERE content_hash = %s AND sent_at > %s",
            (ch, cutoff)
        )
        if cur.fetchone():
            return True

        # Nivel B: similitud Jaccard sobre titulo+resumen del mismo departamento
        dept = (alert.get("departamento") or "").upper().strip()
        if not dept:
            return False

        texto_nuevo = f"{alert.get('titulo','')} {alert.get('resumen_whatsapp','')}"
        set_nuevo = _words_set(texto_nuevo)
        if len(set_nuevo) < 4:
            # Muy pocas palabras significativas → no es fiable comparar
            return False

        cur.execute(
            "SELECT titulo_norm FROM sent_alerts WHERE departamento = %s AND sent_at > %s",
            (dept, cutoff)
        )
        for (titulo_norm,) in cur.fetchall():
            if not titulo_norm:
                continue
            set_existente = set(titulo_norm.split())
            score = _jaccard(set_nuevo, set_existente)
            if score >= JACCARD_THRESHOLD:
                log.info(
                    f"[Dedup] Jaccard={score:.2f} ≥ {JACCARD_THRESHOLD} en {dept} → duplicado"
                )
                return True
        return False

    def mark_alert_sent(self, alert: dict):
        """Registra una alerta como enviada para dedup de contenido."""
        ch = self._content_hash(alert)
        texto = f"{alert.get('titulo','')} {alert.get('resumen_whatsapp','')}"
        titulo_norm = " ".join(sorted(_words_set(texto)))[:500]
        try:
            cur = self._cursor()
            cur.execute(
                """INSERT INTO sent_alerts
                   (content_hash, departamento, subcategoria, cliente, resumen, titulo_norm, sent_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT DO NOTHING""",
                (
                    ch,
                    alert.get("departamento", ""),
                    alert.get("subcategoria", ""),
                    alert.get("cliente", ""),
                    alert.get("resumen_whatsapp", "")[:120],
                    titulo_norm,
                    datetime.now().isoformat()
                )
            )
            self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            log.error(f"Error registrando alerta enviada: {e}")

    # ─────────────────────────────────────────────
    # LIMPIEZA
    # ─────────────────────────────────────────────
    def _cleanup_old(self):
        cutoff = (datetime.now() - timedelta(days=7)).isoformat()
        cutoff_alerts = (datetime.now() - timedelta(hours=24)).isoformat()
        cur = self._cursor()
        cur.execute("DELETE FROM processed WHERE seen_at < %s", (cutoff,))
        cur.execute("DELETE FROM sent_alerts WHERE sent_at < %s", (cutoff_alerts,))
        self.conn.commit()
