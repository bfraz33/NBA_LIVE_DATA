# odds.py
import logging
from typing import Optional, Dict, Any
from api import get 

logger = logging.getLogger(__name__)

def extract_odds_line(
    game_odds: Optional[Dict[str, Any]], 
    key: str, 
    label: str, 
    preferred_book: Optional[str] = None
) -> str:
    # Extracting a specific line from a game's odds dictionary.
    if not game_odds or not isinstance(game_odds, dict):
        return f"{label}: N/A"
    for book in game_odds.get("sportsBooks", []):
        if not isinstance(book, dict):
            continue
        if preferred_book and book.get("sportsBook") != preferred_book:
            continue
        val = book.get("odds", {}).get(key)
        if val is not None:
            return f"{label}: {val}"
    return f"{label}: N/A"

extract_ou_line = lambda odds, pb=None: extract_odds_line(odds, "totalOver", "O/U", pb)
extract_ml_line = lambda odds, pb=None: extract_odds_line(odds, "homeTeamMLOdds", "ML", pb)

def get_betting_odds(date: Optional[str] = None) -> list:
    """Fetch betting odds from the API."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    if not date:
        date = datetime.now(ZoneInfo("America/Chicago")).strftime("%Y%m%d")

    try:
        resp = get("getNFLBettingOdds", {"gameDate": date, "playerProps": "true", "itemFormat": "list"})
        body = resp.get("body", [])
        if not isinstance(body, list):
            logger.warning("Unexpected response format for betting odds")
            return []
        return body
    except Exception as e:
        logger.error(f"Error fetching betting odds: {e}")
        return []

def odds_by_game(date: Optional[str] = None) -> Dict[str, Dict[str, str]]:
    """
    Returns a dictionary of odds per gameID:
    {
        "gameID1": {"ML": "ML: -110", "O/U": "O/U: 48.5"},
        "gameID2": {...}
    }
    """
    odds_list = get_betting_odds(date)
    result = {}
    for item in odds_list:
        if not isinstance(item, dict) or "gameID" not in item:
            continue
        game_id = item["gameID"]
        result[game_id] = {
            "ML": extract_ml_line(item),
            "O/U": extract_ou_line(item)
        }
    return result

if __name__ == "__main__":
    import os
    import dotenv
    dotenv.load_dotenv()
    logging.basicConfig(level=logging.INFO)

    odds_data = odds_by_game()
    for game_id, odds in odds_data.items():
        print(game_id, odds)