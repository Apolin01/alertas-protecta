"""
alert_queue.py — Cola persistente de alertas pendientes de envio.

Las alertas se acumulan durante el dia y se envian cuando
llega la ventana horaria del grupo correspondiente.
Usa PostgreSQL para persistir entre reinicios del programa.
"""

import os
import json
import logging
import psycopg2
from datetime import datetime

log = logging.getLogger(__name__)


def _get_conn():
    url = os.environ["DATABASE_URL"]
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return psycopg2.connect(url)


class AlertQueue:
    def __init__(self):
        self.conn = _get_conn()
        self._init_db()

    def _init_db(self):
        cur = self.conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS pending (
                id          SERIAL PRIMARY KEY,
                group_name  TEXT NOT NULL,
                message     TEXT NOT NULL,
                image_url   TEXT DEFAULT '',
                alert_json  TEXT DEFAULT '',
                created_at  TEXT NOT NULL,
                sent        INTEGER DEFAULT 0,
                sent_at     TEXT
            )
        """)
        self.conn.commit()

    def push(self, group_name: str, message: str, image_url: str = "", alert: dict = None):
        """Agrega una alerta a la cola para el grupo indicado."""
        cur = self.conn.cursor()
        cur.execute(
            """INSERT INTO pending (group_name, message, image_url, alert_json, created_at)
               VALUES (%s, %s, %s, %s, %s)""",
            (
                group_name,
                message,
                image_url or "",
                json.dumps(alert or {}, ensure_ascii=False),
                datetime.now().isoformat()
            )
        )
        self.conn.commit()
        log.info(f"[COLA] Alerta guardada para '{group_name}': {message[:60]}...")

    def get_pending(self, group_name: str) -> list[dict]:
        """Retorna todas las alertas pendientes para un grupo."""
        cur = self.conn.cursor()
        cur.execute(
            "SELECT id, message, image_url, alert_json FROM pending WHERE group_name=%s AND sent=0 ORDER BY id",
            (group_name,)
        )
        return [
            {"id": r[0], "message": r[1], "image_url": r[2], "alert_json": r[3]}
            for r in cur.fetchall()
        ]

    def mark_sent(self, alert_id: int):
        """Marca una alerta como enviada."""
        cur = self.conn.cursor()
        cur.execute(
            "UPDATE pending SET sent=1, sent_at=%s WHERE id=%s",
            (datetime.now().isoformat(), alert_id)
        )
        self.conn.commit()

    def pending_count(self, group_name: str = None) -> int:
        cur = self.conn.cursor()
        if group_name:
            cur.execute(
                "SELECT COUNT(*) FROM pending WHERE group_name=%s AND sent=0", (group_name,)
            )
        else:
            cur.execute("SELECT COUNT(*) FROM pending WHERE sent=0")
        return cur.fetchone()[0]

    def cleanup_old(self, days: int = 2):
        """Borra alertas enviadas de mas de N dias."""
        from datetime import timedelta
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        cur = self.conn.cursor()
        cur.execute(
            "DELETE FROM pending WHERE sent=1 AND sent_at < %s", (cutoff,)
        )
        self.conn.commit()
