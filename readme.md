# NBA LIVE DATA (v1)

Real-time NBA scores + game status pipeline built to power LED matrix tickers and other live displays.  
**v1** focuses on reliable polling, caching “last known good” values, and clean normalized outputs you can publish to MQTT / a DB / an API.

---

## What this does

- Polls an NBA data API on an interval (rate-limit friendly)
- Extracts and normalizes:
  - scores (home/away)
  - game status (scheduled / live / final)
  - game time / tip time (when available)
  - venue / arena (when available)
  - optional: betting odds / totals (if enabled)
- Caches last known good values to prevent flicker & handle API hiccups
- Produces downstream-friendly payloads (for LED renderers, microservices, or MQTT topics)

---

## Architecture (v1)

**Polling Script / Service**
1. Fetch scoreboard / games list for a date
2. For each game:
   - fetch details (boxscore/venue as needed)
   - fetch odds (optional)
3. Normalize + cache
4. Publish/store results

**Downstream consumers**
- LED renderer (image/frame output)
- MQTT subscribers (devices)
- Database (optional)
- API layer (optional)

---

## Repo layout (example)

> Your repo may differ — this is the intended v1 structure.

NBA_LIVE_DATA/
├─ livescores.py              # main poller/orchestrator
├─ api.py                     # API wrapper + throttling
├─ odds.py                    # odds fetching + mapping
├─ paneldisplay.py            # render helpers for LED output
├─ database.py                # optional DB persistence
├─ logger.py                  # logging config (if separated)
├─ requirements.txt
├─ .env.example
└─ README.md


---

## Requirements

- Python 3.10+ (3.11+ recommended)
- `pip` / virtualenv
- An NBA data API key (Tank01 / RapidAPI or your provider)
- (Optional) MQTT broker (Mosquitto / AWS IoT Core)
- (Optional) PostgreSQL if you persist results

---

## Setup

### 1) Create a virtual environment

```bash
python -m venv env

# Windows
env\Scripts\activate

# macOS/Linux
source env/bin/activate
```

### 2) Install dependencies
```
pip install -r requirements.txt
```

### 3) Configure environment variables
```
Create a .env file (start from .env.example):

cp .env.example .env
```
## Example .env.example
```
# --- API ---
RAPIDAPI_KEY=YOUR_KEY_HERE
RAPIDAPI_HOST=YOUR_HOST_HERE

# --- POLLING ---
POLL_INTERVAL_SECONDS=180

# --- TIMEZONE ---
TZ=America/Chicago

# --- MQTT (optional) ---
MQTT_ENABLED=false
MQTT_BROKER=localhost
MQTT_PORT=1883
MQTT_TOPIC=nba/scores

# --- DB (optional) ---
DB_ENABLED=false
DB_HOST=localhost
DB_PORT=5432
DB_NAME=FrontOffice
DB_USER=postgres
DB_PASSWORD=postgres
```

### Run (v1)

## Poll live scores
```
python livescores.py
```
#### Typical behavior

- Sleeps between calls to respect rate limits

- Logs game status updates

- Only updates downstream when values change

### Example output payload
 ```
{
  "game_id": "20251203_LAC@ATL",
  "home_team": "ATL",
  "away_team": "LAC",
  "home_score": 102,
  "away_score": 97,
  "display_status": "Q4 02:11",
  "is_live": true,
  "last_updated_epoch": 1733299200
}
```
### Expected DB output

![Screenshot 2026-01-11 200514](https://github.com/user-attachments/assets/feb016af-64f2-4af2-b61e-16541184314d)


### Expected Virtual Display Output


<img width="256" height="48" alt="tmpdsmpc_9m" src="https://github.com/user-attachments/assets/9ec43ba0-d76a-4d50-8f68-01c47ca3dbcd" />


<img width="256" height="48" alt="tmp_dht93c1" src="https://github.com/user-attachments/assets/22e7b51b-fe4c-4165-b35e-8d1ac1359a89" />


<img width="256" height="48" alt="tmpkncii_mv" src="https://github.com/user-attachments/assets/21e654ad-343e-4d4c-985c-c9e3c01de3db" />





