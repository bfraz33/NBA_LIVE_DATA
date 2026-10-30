-- Matches the columns the original database.py wrote, so an existing table keeps working.
CREATE TABLE IF NOT EXISTS nba (
    game_id         TEXT PRIMARY KEY,
    game_date       DATE,
    arena           TEXT,
    away            TEXT,
    home            TEXT,
    away_score      INTEGER,
    home_score      INTEGER,
    display_status  TEXT,
    ou_string       TEXT,
    ml_string       TEXT,
    scheduled_time  TEXT,
    away_record     TEXT,
    home_record     TEXT,
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS nba_game_date_idx ON nba (game_date);
