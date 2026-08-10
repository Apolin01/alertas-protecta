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
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "DATABASE_URL no está configurado. "
            "Agrega la cadena de conexión PostgreSQL en el archivo .env"
        )
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return psycopg2.connect(url)


class AlertQueue:
    def __init__(self):
        self.conn = _get_conn()
        self._init_db()

    def _cursor(self):
        """Retorna cursor reconectando si la conexión cayó."""
        try:
            self.conn.cursor().execute("SELECT 1")
        except Exception:
            log.warning("[Cola] Reconectando a PostgreSQL...")
            try:
                self.conn.close()
            except Exception:
                pass
            self.conn = _get_conn()
        return self.conn.cursor()

    def _init_db(self):
        cur = self._cursor()
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
        # Contador de intentos — evita que una alerta se reintente sin límite
        # durante toda la ventana de 4h de get_recent_unsent (hasta 48 rondas).
        cur.execute("ALTER TABLE pending ADD COLUMN IF NOT EXISTS attempts INTEGER DEFAULT 0")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_pending_sent_created ON pending (sent, created_at)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_pending_group_sent ON pending (group_name, sent)")
        self.conn.commit()

    # ─────────────────────────────────────────────────────────────
    # CLAIM / RELEASE — exclusión mutua de envío
    # ─────────────────────────────────────────────────────────────
    # El envío es "at-least-once" por naturaleza: si el bridge entrega el
    # mensaje pero la confirmación HTTP se pierde (timeout), el emisor no
    # puede distinguirlo de un fallo real. Sin exclusión, la alerta se
    # reenvía y el grupo recibe el duplicado.
    #
    # claim() marca la fila ANTES de enviar, de forma atómica. Como el UPDATE
    # lleva `AND sent=0`, solo un proceso puede ganarla — esto vale también
    # entre instancias distintas de main.py que comparten el mismo Postgres.
    def claim(self, alert_id: int) -> bool:
        """Reserva la alerta para envío. True si la ganó este proceso."""
        cur = self._cursor()
        cur.execute(
            "UPDATE pending SET sent=1, sent_at=%s, attempts=attempts+1 "
            "WHERE id=%s AND sent=0 RETURNING id",
            (datetime.now().isoformat(), alert_id)
        )
        won = cur.fetchone() is not None
        self.conn.commit()
        return won

    def release(self, alert_id: int):
        """Devuelve la alerta a la cola. Solo tras un fallo CONFIRMADO
        (bridge inalcanzable / grupo inexistente), nunca tras un timeout."""
        cur = self._cursor()
        cur.execute("UPDATE pending SET sent=0, sent_at=NULL WHERE id=%s", (alert_id,))
        self.conn.commit()

    def clear_pending(self):
        """Elimina todas las alertas pendientes (se llama al arrancar)."""
        cur = self._cursor()
        cur.execute("DELETE FROM pending WHERE sent = 0")
        deleted = cur.rowcount
        self.conn.commit()
        if deleted:
            log.info(f"[COLA] {deleted} alerta(s) antigua(s) eliminadas al iniciar.")

    def push(self, group_name: str, message: str, image_url: str = "", alert: dict = None) -> int:
        """Agrega una alerta a la cola. Retorna el ID insertado."""
        cur = self._cursor()
        cur.execute(
            """INSERT INTO pending (group_name, message, image_url, alert_json, created_at)
               VALUES (%s, %s, %s, %s, %s) RETURNING id""",
            (
                group_name,
                message,
                image_url or "",
                json.dumps(alert or {}, ensure_ascii=False),
                datetime.now().isoformat()
            )
        )
        new_id = cur.fetchone()[0]
        self.conn.commit()
        log.info(f"[COLA] Alerta guardada para '{group_name}': {message[:60]}...")
        return new_id

    def get_pending(self, group_name: str) -> list[dict]:
        """Retorna todas las alertas pendientes para un grupo."""
        cur = self._cursor()
        cur.execute(
            "SELECT id, message, image_url, alert_json FROM pending WHERE group_name=%s AND sent=0 ORDER BY id",
            (group_name,)
        )
        return [
            {"id": r[0], "message": r[1], "image_url": r[2], "alert_json": r[3]}
            for r in cur.fetchall()
        ]

    def get_pending_by_ids(self, ids: list[int]) -> dict[str, list[dict]]:
        """Retorna alertas pendientes agrupadas por grupo, filtradas por IDs del ciclo actual."""
        if not ids:
            return {}
        cur = self._cursor()
        placeholders = ",".join(["%s"] * len(ids))
        cur.execute(
            f"SELECT id, group_name, message, image_url, alert_json FROM pending "
            f"WHERE id IN ({placeholders}) AND sent=0 ORDER BY id",
            ids
        )
        groups: dict[str, list[dict]] = {}
        for r in cur.fetchall():
            entry = {"id": r[0], "message": r[2], "image_url": r[3], "alert_json": r[4]}
            groups.setdefault(r[1], []).append(entry)
        return groups

    def mark_sent(self, alert_id: int):
        """Marca una alerta como enviada."""
        cur = self._cursor()
        cur.execute(
            "UPDATE pending SET sent=1, sent_at=%s WHERE id=%s",
            (datetime.now().isoformat(), alert_id)
        )
        self.conn.commit()

    def pending_count(self, group_name: str = None) -> int:
        cur = self._cursor()
        if group_name:
            cur.execute(
                "SELECT COUNT(*) FROM pending WHERE group_name=%s AND sent=0", (group_name,)
            )
        else:
            cur.execute("SELECT COUNT(*) FROM pending WHERE sent=0")
        return cur.fetchone()[0]

    def get_pending_groups(self) -> list[str]:
        """Retorna los grupos que tienen alertas pendientes de enviar."""
        cur = self._cursor()
        cur.execute(
            "SELECT DISTINCT group_name FROM pending WHERE sent=0 ORDER BY group_name"
        )
        return [r[0] for r in cur.fetchall()]

    def get_recent_unsent(self, max_age_hours: int = 4,
                          max_attempts: int = 5) -> dict[str, list[dict]]:
        """Retorna alertas no enviadas de las últimas N horas, agrupadas por grupo.

        Se excluyen las que ya agotaron max_attempts: si el bridge sigue caído
        tras 5 rondas, insistir cada 5 min durante 4h no cambia el resultado.
        """
        from datetime import timedelta
        cutoff = (datetime.now() - timedelta(hours=max_age_hours)).isoformat()
        cur = self._cursor()
        cur.execute(
            "SELECT id, group_name, message, image_url, alert_json FROM pending "
            "WHERE sent=0 AND created_at > %s AND attempts < %s ORDER BY id",
            (cutoff, max_attempts)
        )
        groups: dict[str, list[dict]] = {}
        for r in cur.fetchall():
            entry = {"id": r[0], "message": r[2], "image_url": r[3], "alert_json": r[4]}
            groups.setdefault(r[1], []).append(entry)
        return groups

    def cleanup_old(self, days: int = 2, days_unsent: int = 7):
        """Borra alertas enviadas de mas de N dias, y las nunca-enviadas de
        mas de `days_unsent` dias — estas ultimas agotaron sus reintentos en
        get_recent_unsent() (max 5, ventana de 4h) y quedan sent=0 para
        siempre; sin este DELETE se acumulan indefinidamente en la tabla."""
        from datetime import timedelta
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        cutoff_unsent = (datetime.now() - timedelta(days=days_unsent)).isoformat()
        cur = self._cursor()
        cur.execute(
            "DELETE FROM pending WHERE sent=1 AND sent_at < %s", (cutoff,)
        )
        cur.execute(
            "DELETE FROM pending WHERE sent=0 AND created_at < %s", (cutoff_unsent,)
        )
        self.conn.commit()
