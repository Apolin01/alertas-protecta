"""
reset_dedup.py — Limpia la base de datos de deduplicacion.
Uso:
  python reset_dedup.py           # borra todo
  python reset_dedup.py --hoy     # solo borra los de hoy
"""

import os
import sys
import psycopg2
from datetime import date

sys.stdout.reconfigure(encoding='utf-8') if hasattr(sys.stdout, 'reconfigure') else None


def _get_conn():
    url = os.environ["DATABASE_URL"]
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return psycopg2.connect(url)


def reset_all():
    conn = _get_conn()
    cur  = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM processed")
    total = cur.fetchone()[0]
    cur.execute("DELETE FROM processed")
    conn.commit()
    conn.close()
    print(f"[OK] Eliminados {total} registros. La proxima corrida procesara todo de nuevo.")


def reset_hoy():
    hoy  = date.today().isoformat()
    conn = _get_conn()
    cur  = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM processed WHERE seen_at LIKE %s", (f"{hoy}%",))
    total = cur.fetchone()[0]
    cur.execute("DELETE FROM processed WHERE seen_at LIKE %s", (f"{hoy}%",))
    conn.commit()
    conn.close()
    print(f"[OK] Eliminados {total} registros de hoy ({hoy}).")


if __name__ == "__main__":
    if "--hoy" in sys.argv:
        reset_hoy()
    else:
        reset_all()
