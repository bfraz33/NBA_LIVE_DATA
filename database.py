import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

Table_NAME = "nba"

#Connecting to DB
def get_conn():
 return psycopg2.connect(
    dbname=os.getenv("DB_NAME"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    host=os.getenv("DB_HOST"),
    port=os.getenv("DB_PORT")
)

#Printing for personal satisfaction
print("Connected to PostgreSQL")
 
#Loading game data
def upsert_game_state(game_data: dict):
    sql = f"""
    INSERT INTO {Table_NAME}
       (game_id, game_date, arena, away, home, away_score, home_score,
       display_status, ou_string, ml_string, scheduled_time,
       away_record, home_record, updated_at)
    
        VALUES
      (%s, to_date(%s,'YYYYMMDD'), %s, %s, %s, %s, %s,
       %s, %s, %s, %s,
       %s, %s, NOW())
    ON CONFLICT (game_id) DO UPDATE SET
      game_date      = EXCLUDED.game_date,
      arena          = EXCLUDED.arena,
      away           = EXCLUDED.away,
      home           = EXCLUDED.home,
      away_score     = EXCLUDED.away_score,
      home_score     = EXCLUDED.home_score,
      display_status = EXCLUDED.display_status,
      ou_string      = EXCLUDED.ou_string,
      ml_string      = EXCLUDED.ml_string,
      scheduled_time = EXCLUDED.scheduled_time,
      away_record    = EXCLUDED.away_record,
      home_record    = EXCLUDED.home_record,
      updated_at     = NOW();
    """

    vals = (
        game_data["game_id"],
        game_data["date"],
        game_data["arena"],
        game_data["away"],
        game_data["home"],
        game_data["away_score"],
        game_data["home_score"],
        game_data["display_status"],
        game_data["ou_string"],
        game_data["ml_string"],
        game_data["scheduled_time"],
        game_data["away_record"],
        game_data["home_record"]
    )
    
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, vals)   
        conn.commit()    
    finally:
        conn.close()


def fetch_game_cache(date_str: str):
    sql =  """
    SELECT game_id, away_score, home_score, display_status, ou_string, ml_string, arena
    FROM nba
    WHERE game_date = to_date(%s, 'YYYYMMDD');
    """
    conn = get_conn()
    try:
        # optional debug
        print("CONNECTED TO PORT:", os.getenv("DB_PORT"))

        with conn.cursor() as cur:
            cur.execute(sql, (date_str,))
            rows = cur.fetchall()

        return [
            {
                "game_id": r[0],
                "away_score": r[1],
                "home_score": r[2],
                "display_status": r[3],
            }
            for r in rows
        ]
    finally:
        conn.close()