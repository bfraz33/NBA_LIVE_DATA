"""Optional Postgres persistence. Needs: pip install psycopg2-binary"""
from __future__ import annotations

import logging

log = logging.getLogger(__name__)

TABLE = "nba"

UPSERT = f"""
INSERT INTO {TABLE}
  (game_id, game_date, arena, away, home, away_score, home_score,
   display_status, ou_string, ml_string, scheduled_time,
   away_record, home_record, updated_at)
VALUES
  (%(game_id)s, to_date(%(date)s,'YYYYMMDD'), %(arena)s, %(away)s, %(home)s,
   %(away_score)s, %(home_score)s, %(display_status)s, %(ou_string)s, %(ml_string)s,
   %(scheduled_time)s, %(away_record)s, %(home_record)s, NOW())
ON CONFLICT (game_id) DO UPDATE SET
  game_date = EXCLUDED.game_date, arena = EXCLUDED.arena,
  away = EXCLUDED.away, home = EXCLUDED.home,
  away_score = EXCLUDED.away_score, home_score = EXCLUDED.home_score,
  display_status = EXCLUDED.display_status, ou_string = EXCLUDED.ou_string,
  ml_string = EXCLUDED.ml_string, scheduled_time = EXCLUDED.scheduled_time,
  away_record = EXCLUDED.away_record, home_record = EXCLUDED.home_record,
  updated_at = NOW();
"""

SELECT_DAY = f"""
SELECT game_id, away_score, home_score, display_status
FROM {TABLE} WHERE game_date = to_date(%s, 'YYYYMMDD');
"""


class PostgresSink:
    name = "postgres"

    def __init__(self, settings):
        import psycopg2  # lazy: only needed when DB is enabled
        self._psycopg2 = psycopg2
        self._s = settings

    def _connect(self):
        s = self._s
        return self._psycopg2.connect(
            dbname=s.db_name, user=s.db_user, password=s.db_password, host=s.db_host, port=s.db_port
        )

    def publish(self, snapshot) -> None:
        rows = [g.to_dict() for g in snapshot.games]
        if not rows:
            return
        conn = self._connect()
        try:
            with conn, conn.cursor() as cur:       # one transaction for the whole slate
                cur.executemany(UPSERT, rows)
        finally:
            conn.close()
        log.info("Postgres: upserted %d games", len(rows))

    def load_day(self, date_str: str) -> list[dict]:
        """Used to warm the cache after a restart."""
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(SELECT_DAY, (date_str,))
                return [
                    {"game_id": r[0], "away_score": r[1], "home_score": r[2], "display_status": r[3]}
                    for r in cur.fetchall()
                ]
        finally:
            conn.close()

    def close(self) -> None:
        pass
