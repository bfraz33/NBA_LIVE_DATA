import time
from datetime import datetime, timedelta
import requests
import os
import csv
from dotenv import load_dotenv

load_dotenv()


LAST_CALL = 0
MIN_INTERVAL = 3   # min between  API calls

LOG_DIR = r"C:/ProjectX/NBA/weekly api call logs"
os.makedirs(LOG_DIR, exist_ok=True)

def throttle():
    global LAST_CALL
    now = time.time()
    elapsed = now - LAST_CALL
    if elapsed < MIN_INTERVAL:
        time.sleep(MIN_INTERVAL - elapsed)
    LAST_CALL = time.time()

def get_log_filename():
    today = datetime.now().date()
    start_of_week = today - timedelta(days=today.weekday() + 1 if today.weekday() != 6 else 0)
    end_of_week = start_of_week + timedelta(days=6)
    filename = f"api_usage_{start_of_week}_to_{end_of_week}.csv"
    return os.path.join(LOG_DIR, filename)

def log_api_call(endpoint, params, response_time, status_code):
    filename = get_log_filename()
    file_exists = os.path.exists(filename)

    with open(filename, mode="a", newline="") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["timestamp", "endpoint", "params", "response_time_sec", "status_code"])
        writer.writerow([
            datetime.now().isoformat(),
            endpoint,
            str(params),
            round(response_time, 2),
            status_code
        ])


def get(endpoint, params, retries=3, backoff=2):
    throttle()  # call throttle before each API request

    url = f"https://tank01-fantasy-stats.p.rapidapi.com/{endpoint}"
    headers = {
        "X-RapidAPI-Key": os.environ.get("NBA_API_KEY"),
        "X-RapidAPI-Host": "tank01-fantasy-stats.p.rapidapi.com"
    }

    

    for attempt in range(retries):
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 429:
            print("⚠️ Rate limited: waiting...")
            time.sleep(backoff * (attempt + 1))  # Exponential backoff: 2s, 4s, 6s
        else:
            response.raise_for_status()
            return response.json()

    raise Exception("Too many retries for API call")