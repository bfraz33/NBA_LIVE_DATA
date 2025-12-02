import time
from datetime import datetime
from zoneinfo import ZoneInfo
from livescores import process_scores
from logger import get_logger
from odds import get_betting_odds

logger = get_logger(__name__)
POLL_INTERVAL = 180  # seconds (3 minutes)


def should_poll(now=None) -> bool:
    # Return True if current time is within polling hours (8 AM to midnight Chicago).
    if now is None:
        now = datetime.now(ZoneInfo("America/Chicago"))
    return 8 <= now.hour < 24


def run_once():
    """
    Run the livescores + odds logic ONCE
    This is what publisher.py will call.
    """
    now = datetime.now(ZoneInfo("America/Chicago"))
    polling = should_poll(now)

    # Always compute odds; you can gate this by polling if you want
    odds = get_betting_odds()
    scores = None

    if polling:
        logger.info("Polling API (single run)...")
        scores = process_scores(return_games=True)
    else:
        logger.info("Outside polling hours. Skipping API call.")

    data = {
        "timestamp": now.isoformat(),
        "within_polling_hours": polling,
        "scores": scores,   # list[dict] or None
        "odds": odds,       # whatever get_betting_odds() returns
    }
    return data


def main_loop():
    # Main polling loop to run livescores process periodically.
    while True:
        run_once()
        logger.info(f"Waiting {POLL_INTERVAL // 60} minutes before next poll...\n")
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main_loop()