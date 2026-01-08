# venue_debug_today.py

from datetime import datetime
from zoneinfo import ZoneInfo

from api import get
from dotenv import load_dotenv

load_dotenv()

CENTRAL_TZ = ZoneInfo("America/Chicago")


def get_today_str() -> str:
    """Return today's date as YYYYMMDD in Central time."""
    return datetime.now(CENTRAL_TZ).strftime("%Y%m%d")


def get_today_game_ids(date_str: str):
    """Use getNBAScoresOnly to get all gameIDs for a date."""
    resp = get("getNBAScoresOnly", {"gameDate": date_str, "topPerformers": "false"})
    body = resp.get("body", {})

    game_ids = []

    if isinstance(body, dict):
        # Tank01 usually returns a dict keyed by gameID
        game_ids = list(body.keys())
    elif isinstance(body, list):
        # Fallback if they ever return a list
        for g in body:
            if isinstance(g, dict) and "gameID" in g:
                game_ids.append(g["gameID"])

    return game_ids


def dump_boxscore(game_id: str):
    """Fetch getNBABoxScore for one game and print arena info."""
    resp = get("getNBABoxScore", {"gameID": game_id})
    body = resp.get("body")

    print("gameID:", game_id)
    print("type:", type(body).__name__)

    if isinstance(body, dict):
        print("arena:", body.get("arena"))
    else:
        print("body:", body)

    print("-" * 60)


if __name__ == "__main__":
    date_str = get_today_str()
    print(f"Testing arenas for games on {date_str}\n")

    game_ids = get_today_game_ids(date_str)

    if not game_ids:
        print("No games found for today.")
    else:
        for gid in game_ids:
            dump_boxscore(gid)
