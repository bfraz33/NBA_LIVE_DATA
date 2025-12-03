import time
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import Optional, Dict, Any, List

from api import get
from dotenv import load_dotenv
from paneldisplay import render_game_to_image
from odds import odds_by_game

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# -----------------------------------------------------------
# CACHES FOR LAST KNOWN GOOD STATUS + SCORE
# -----------------------------------------------------------
LAST_STATUS_CACHE: Dict[str, str] = {}
LAST_SCORE_CACHE: Dict[str, tuple[int, int]] = {}


# -----------------------------------------------------------
# API WRAPPERS
# -----------------------------------------------------------

def get_api_data(endpoint: str, params: dict, expected_type: type, default):
    """Generic API fetch helper."""
    try:
        resp = get(endpoint, params)
        body = resp.get("body", default)
        return body if isinstance(body, expected_type) else default
    except Exception as e:
        logger.error(f"Error fetching {endpoint}: {e}")
        return default


def get_live_scores(date: Optional[str] = None) -> Dict[str, Any]:
    """Main live scoreboard (Tank01: getNBAScoresOnly)."""
    if not date:
        date = datetime.now(ZoneInfo("America/Chicago")).strftime("%Y%m%d")
    return get_api_data(
        "getNBAScoresOnly",
        {"gameDate": date, "topPerformers": "true"},
        dict,
        {},
    )


def get_team_data() -> list:
    """Source of correct team records (Tank01: getNBATeams)."""
    return get_api_data(
        "getNBATeams",
        {
            "sortBy": "standings",
            "rosters": "false",
            "schedules": "false",
            "topPerformers": "false",
            "teamStats": "false",
            "teamStatsSeason": "2024",
        },
        list,
        [],
    )


def get_game_venue(game_id: str) -> dict:
    """
    Used for arena + scheduled tipoff (Tank01: getNBABoxScore).

    getNBABoxScore body (you showed):
        {
          "arena": "Rocket Mortgage FieldHouse",
          "gameTime": "7:00p",
          "gameTime_epoch": "...",
          ...
        }
    We normalize that into a dict that has a 'arena' key so the rest
    of the code can stay identical to the NFL version.
    """
    fallback = {
        "arena": "N/A",
        "arena": "N/A",
        "gameTime": "",
        "gameTime_epoch": None,
    }

    try:
        resp = get("getNBABoxScore", {"gameID": game_id})
    except Exception as e:
        logger.error(f"Error fetching getNBABoxScore for {game_id}: {e}")
        return fallback

    body = resp.get("body")
    if not isinstance(body, dict):
        logger.warning(f"Unexpected getNBABoxScore body type for {game_id}: {type(body).__name__}")
        return fallback

    # Map arena -> arena for downstream compatibility
    arena = body.get("arena", "N/A")
    arena = body.get("arena", arena)  # if Tank01 ever adds 'arena', prefer it
    game_time = body.get("gameTime", "")
    game_time_epoch = body.get("gameTime_epoch")

    return {
        "arena": arena,
        "arena": arena,
        "gameTime": game_time,
        "gameTime_epoch": game_time_epoch,
    }


# SAFE SCORE

def safe_score(game_id: str, game_info: Dict[str, Any]) -> tuple[int, int]:
    """
    Returns a stable score using:
      1) new API values if valid
      2) last cached values if API dropped them
      3) 0–0 only if nothing else is known
    """
    prev = LAST_SCORE_CACHE.get(game_id)

    def parse(val):
        try:
            return int(val)
        except (TypeError, ValueError):
            return None

    # Pulling raw score
    raw_away = (
        game_info.get("awayScore")
        or game_info.get("awayPts")
        or game_info.get("away_score")
    )
    raw_home = (
        game_info.get("homeScore")
        or game_info.get("homePts")
        or game_info.get("home_score")
    )

    new_away = parse(raw_away)
    new_home = parse(raw_home)

    # Scores returned
    if new_away is not None and new_home is not None:
        LAST_SCORE_CACHE[game_id] = (new_away, new_home)
        return new_away, new_home

    # Scores drop but we keep the previous score
    if prev:
        return prev

    # No previous score 0 - 0
    LAST_SCORE_CACHE[game_id] = (0, 0)
    return 0, 0


# SAFE LIVE STATUS HANDLING

def safe_live_status(game_id: str, raw_status: str, period: str, clock: str) -> str:
    """
    Stabilizes live game status texts so they don't flip back to "Scheduled"
    when Tank01 temporarily drops fields.
    """
    prev = LAST_STATUS_CACHE.get(game_id)
    s = (raw_status or "").lower().strip()

    # API drops status fields often during transitions
    if s in ("", None, "scheduled", "gametime", "game time"):
        if prev:
            return prev

    # Final
    if "final" in s or "completed" in s:
        status = "Final"

    # Live indicators (NBA: periods/quarters/OT, same logic as NFL)
    elif "live" in s or period or clock:
        parts = []
        if period:
            parts.append(f"Q{period}")
        if clock:
            parts.append(clock)
        status = "Live " + " ".join(parts)

    else:
        status = raw_status or "In Progress"

    LAST_STATUS_CACHE[game_id] = status
    return status


# UTILITIES

def validate_game_data(data: Any) -> bool:
    return isinstance(data, dict) and "away" in data and "home" in data


def get_team_record(team_abv: str, team_data: list) -> str:
    for team in team_data:
        if team.get("teamAbv") == team_abv:
            w = team.get("wins", 0)
            l = team.get("loss", 0)
            t = team.get("tie", 0)
            return f"{w}-{l}-{t}" if t else f"{w}-{l}"
    return "N/A"


def format_tipoff_ct(game_info: dict, venue_info: dict) -> str:
    """
    Format tipoff time into Central Time like '7:00p'.
    """
    epoch = venue_info.get("gameTime_epoch") or game_info.get("gameTime_epoch")
    try:
        if epoch:
            dt_utc = datetime.fromtimestamp(int(epoch), tz=ZoneInfo("UTC"))
            dt_ct = dt_utc.astimezone(ZoneInfo("America/Chicago"))
            return dt_ct.strftime("%-I:%M%p").lower().replace("pm", "p").replace("am", "a")
    except Exception:
        pass
    return venue_info.get("gameTime") or game_info.get("gameTime") or "TBD"


# CMD OUTPUT

def print_game_status(game: Dict[str, Any]) -> None:
    away, home = game["away"], game["home"]
    ascore, hscore = game["away_score"], game["home_score"]
    status = game["display_status"]
    arena = game["arena"]
    sched = game["scheduled_time"]
    ou = game["ou_string"]
    ml = game["ml_string"]
    ar = game["away_record"]
    hr = game["home_record"]

    if "live" in status.lower() or "q" in status.lower() or "win!" in status.lower():
        print(f"{away} {ascore} @ {home} {hscore}")
        print(f"arena: {arena}")
        print(f"Status: {status} | {ou} | {ml}")
    else:
        print(f"Upcoming: {away} ({ar}) @ {home} ({hr})")
        print(f"arena: {arena}")
        print(f"Tipoff: {sched} | {ou} | {ml}")


# MAIN ENGINE

def find_next_game_date(start_date: datetime, max_days: int = 7):
    for offset in range(1, max_days + 1):
        next_date = start_date + timedelta(days=offset)
        date_str = next_date.strftime("%Y%m%d")
        games = get_live_scores(date_str)
        if games:
            return date_str, games
    return None, None


def process_scores(return_games: bool = False) -> Optional[List[Dict[str, Any]]]:
    """
    Core engine:
      • When run as a script -> logs & renders panels.
      • When called with return_games=True -> returns a list of game dicts
        suitable for publishing over MQTT.
    """
    today = datetime.now(ZoneInfo("America/Chicago"))
    date_str = today.strftime("%Y%m%d")
    games = get_live_scores(date_str)

    if not games:
        logger.info("No games today. Searching next 7 days…")
        date_str, games = find_next_game_date(today) or (None, None)
        if not games:
            logger.info("No upcoming games at all.")
            return [] if return_games else None
        logger.info(f"Next games on {date_str}")

    odds_data = odds_by_game(date_str)
    team_data_cache = get_team_data()

    logger.info(f"\nNBA Games for {date_str}:\n")

    games_payload: List[Dict[str, Any]] = []

    for game_id, game_info in games.items():
        if not validate_game_data(game_info):
            logger.warning(f"Skipping invalid game {game_id}")
            continue

        try:
            time.sleep(0.5)

            away = game_info["away"]
            home = game_info["home"]

            # SAFE SCORES
            away_score, home_score = safe_score(game_id, game_info)

            # STATUS FIELDS
            raw_status = (
                game_info.get("gameStatus")
                or game_info.get("gameStatusText")
                or ""
            )

            # Try a bunch of possible quarter/period fields
            period = (
                game_info.get("currentPeriod")
                or game_info.get("quarter")
                or game_info.get("qtr")
                or game_info.get("currentQtr")
                or game_info.get("currentQuarter")
                or game_info.get("quarterNum")
                or game_info.get("qtrNum")
                or ""
            )

            clock = game_info.get("gameClock") or game_info.get("clock") or ""

            # SAFE STATUS
            display_status = safe_live_status(game_id, raw_status, period, clock)

            # arena & TIME
            venue_info = get_game_venue(game_id)
            arena = venue_info.get("arena", "N/A")
            scheduled_time = format_tipoff_ct(game_info, venue_info)

            # RECORDS
            away_record = get_team_record(away, team_data_cache)
            home_record = get_team_record(home, team_data_cache)

            # ODDS
            game_odds = odds_data.get(game_id, {"ML": "ML: N/A", "O/U": "O/U: N/A"})
            ou_string = game_odds["O/U"]
            ml_string = game_odds["ML"]

            # FINAL GAME DATA
            game_data = {
                "game_id": game_id,
                "date": date_str,
                "arena": arena,
                "away": away,
                "home": home,
                "away_score": away_score,
                "home_score": home_score,
                "display_status": display_status,
                "ou_string": ou_string,
                "ml_string": ml_string,
                "scheduled_time": scheduled_time,
                "away_record": away_record,
                "home_record": home_record,
            }

            games_payload.append(game_data)

            # Local display / debugging
            render_game_to_image(game_data)
            print_game_status(game_data)

        except Exception as e:
            logger.error(f"Error processing game {game_id}: {e}", exc_info=True)

    if return_games:
        return games_payload

    return None


if __name__ == "__main__":
    process_scores()
