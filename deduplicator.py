"""
deduplicator.py — Evita enviar la misma noticia dos veces.

Dos niveles de deduplicacion:
  1. Por URL exacta del post (como antes)
  2. Por similitud de contenido — si dos posts hablan del mismo hecho
     (mismo departamento + misma subcategoria + texto similar en las ultimas 6h)
     se considera duplicado aunque vengan de paginas distintas.
"""

import os
import hashlib
import logging
import psycopg2
from datetime import datetime, timedelta

log = logging.getLogger(__name__)


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
                sent_at       TEXT
            )
        """)
        self.conn.commit()
        self._cleanup_old()

    def _url_hash(self, post: dict) -> str:
        key = post.get("url") or post.get("text", "")
        return hashlib.md5(key.encode("utf-8")).hexdigest()

    def _content_hash(self, alert: dict) -> str:
        """
        Hash basado en departamento + subcategoria + primeras 60 letras del resumen.
        Detecta la misma noticia publicada por distintas paginas.
        """
        departamento = (alert.get("departamento") or "").upper().strip()
        subcategoria = (alert.get("subcategoria") or "").upper().strip()
        resumen_raw  = (alert.get("resumen_whatsapp") or "").lower()
        resumen_norm = "".join(c for c in resumen_raw if c.isalnum())[:60]
        key = f"{departamento}|{subcategoria}|{resumen_norm}"
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
    def is_duplicate_alert(self, alert: dict, window_hours: int = 6) -> bool:
        """
        Retorna True si ya se envio una alerta similar en las ultimas N horas.
        'Similar' = mismo departamento + misma subcategoria + resumen parecido.
        """
        ch = self._content_hash(alert)
        cutoff = (datetime.now() - timedelta(hours=window_hours)).isoformat()
        cur = self._cursor()
        cur.execute(
            "SELECT 1 FROM sent_alerts WHERE content_hash = %s AND sent_at > %s",
            (ch, cutoff)
        )
        return cur.fetchone() is not None

    def mark_alert_sent(self, alert: dict):
        """Registra una alerta como enviada para dedup de contenido."""
        ch = self._content_hash(alert)
        try:
            cur = self._cursor()
            cur.execute(
                """INSERT INTO sent_alerts
                   (content_hash, departamento, subcategoria, cliente, resumen, sent_at)
                   VALUES (%s, %s, %s, %s, %s, %s)
                   ON CONFLICT DO NOTHING""",
                (
                    ch,
                    alert.get("departamento", ""),
                    alert.get("subcategoria", ""),
                    alert.get("cliente", ""),
                    alert.get("resumen_whatsapp", "")[:120],
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
        cutoff_alerts = (datetime.now() - timedelta(hours=12)).isoformat()
        cur = self._cursor()
        cur.execute("DELETE FROM processed WHERE seen_at < %s", (cutoff,))
        cur.execute("DELETE FROM sent_alerts WHERE sent_at < %s", (cutoff_alerts,))
        self.conn.commit()
