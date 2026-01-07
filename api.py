#Importing
import time
from datetime import datetime, timedelta
import requests
import os
from dotenv import load_dotenv

load_dotenv()

LAST_CALL = 0
MIN_INTERVAL = 3 #min inbetween Api calls

#Throttling API calls
def throttle():
    global LAST_CALL
    now = time.time()
    elapsed = now - LAST_CALL
    if elapsed < MIN_INTERVAL:
        time.sleep(MIN_INTERVAL - elapsed)
    LAST_CALL = time.time()

def get(endpoint, params, retries=3, backoff=2):
    throttle() # Throttling before each request

    url = f"https://tank01-fantasy-stats.p.rapidapi.com/{endpoint}"
    headers = {
        "X-RapidAPI-Key": os.environ.get("NBA_API_KEY"),
        "X-RapidAPI-Host": "tank01-fantasy-stats.p.rapidapi.com"
    }
   #Data pull with error handling
    for attempt in range(retries):
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 429:
            print("⚠️ Rate limited: waiting...")
            time.sleep(backoff * (attempt + 1)) 
        else:
            response.raise_for_status()
            return response.json()

    raise Exception("Too many retries for API call")