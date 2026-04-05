"""
page_rotator.py — Divide las 239 paginas en grupos y rota entre ellos.

En vez de leer TODAS las paginas cada ciclo (consume mucho credito Apify),
las divide en N grupos y cada ciclo lee solo un grupo.

Con 239 paginas y grupos de ~25:
  - 10 grupos en rotacion
  - Cada pagina se lee cada ~5 ciclos (cada 2.5h con intervalo de 30min)
  - Credito Apify: ~$0.50-1/mes en vez de $30+

Uso en main.py:
  from page_rotator import PageRotator
  rotator = PageRotator(config)
  pages_this_cycle = rotator.next_group()
"""

import os
import logging
import math
import psycopg2
from config import Config

log = logging.getLogger(__name__)


def _get_conn():
    url = os.environ["DATABASE_URL"]
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return psycopg2.connect(url)


class PageRotator:
    def __init__(self, config: Config, pages_per_cycle: int = None):
        self.config = config
        self.all_pages = config.FACEBOOK_PAGES

        if pages_per_cycle is None:
            interval = getattr(config, "INTERVAL_MINUTES", 30)
            cycles_per_hour = 60 / interval
            target_pages_per_hour = len(self.all_pages) / 2
            pages_per_cycle = max(20, int(target_pages_per_hour / cycles_per_hour))

        self.pages_per_cycle = min(pages_per_cycle, len(self.all_pages))
        self.num_groups = math.ceil(len(self.all_pages) / self.pages_per_cycle)

        self.conn = _get_conn()
        self._init_db()

        log.info(
            f"PageRotator: {len(self.all_pages)} paginas / "
            f"{self.pages_per_cycle} por ciclo / "
            f"{self.num_groups} grupos"
        )

    def _init_db(self):
        cur = self.conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS state (
                key   TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        cur.execute(
            "INSERT INTO state (key, value) VALUES ('current_group', '0') ON CONFLICT DO NOTHING"
        )
        self.conn.commit()

    def _get_current_group(self) -> int:
        cur = self.conn.cursor()
        cur.execute("SELECT value FROM state WHERE key='current_group'")
        return int(cur.fetchone()[0])

    def _advance_group(self):
        current = self._get_current_group()
        next_group = (current + 1) % self.num_groups
        cur = self.conn.cursor()
        cur.execute(
            "UPDATE state SET value=%s WHERE key='current_group'",
            (str(next_group),)
        )
        self.conn.commit()

    def next_group(self) -> list[str]:
        """
        Retorna el siguiente grupo de paginas a leer.
        Avanza el puntero para el proximo ciclo.
        """
        current = self._get_current_group()
        start   = current * self.pages_per_cycle
        end     = start + self.pages_per_cycle
        group   = self.all_pages[start:end]

        log.info(
            f"[ROTACION] Grupo {current+1}/{self.num_groups} — "
            f"paginas {start+1}-{min(end, len(self.all_pages))} "
            f"de {len(self.all_pages)}"
        )

        self._advance_group()
        return group

    def status(self) -> dict:
        current = self._get_current_group()
        return {
            "total_pages":      len(self.all_pages),
            "pages_per_cycle":  self.pages_per_cycle,
            "num_groups":       self.num_groups,
            "current_group":    current + 1,
            "next_pages":       self.all_pages[current * self.pages_per_cycle:
                                               (current + 1) * self.pages_per_cycle],
        }
