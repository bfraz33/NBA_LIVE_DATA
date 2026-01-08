#Importing
import time
from datetime import datetime
from zoneinfo import ZoneInfo
from livescores import process_scores
from logger import get_logger
from odds import get_betting_odds

#Logging
logger = get_logger(__name__)
POLL_INTERVAL = 180  # seconds (3 minutes)

#Polling hours
"""
This is only polling between 8am to 11:59pm
"""
def should_poll(now=None):
    if now is None:
        now = datetime.now(ZoneInfo("America/Chicago"))
    return 8 <= now.hour < 24


def run_once():

    now = datetime.now(ZoneInfo("America/Chicago"))
    polling = should_poll(now)
    scores = None
    odds = None

    if polling:
        logger.info("Polling API (single run)...")
        scores = process_scores(return_games=True)
        odds = get_betting_odds()

    else:
        logger.info("Outside polling hours. Skipping API call.")
    
    data = {              # This is for MQTT   
        "timestamp": now.isoformat(),
        "within_polling_hours": polling,
        "scores": scores,
        "odds": odds,       
    }
    return data

#Looping every three min 
def main_loop():

    while True:
        run_once()
        logger.info(f"Waiting {POLL_INTERVAL // 60} minutes before next poll...\n")
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main_loop()