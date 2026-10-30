# GameTimeProps – NBA LED Ticker

A Python-powered NBA scoreboard ticker designed for LED displays. GameTimeProps retrieves NBA game data, processes live scoreboard information, and displays games in a rotating scoreboard format.

## Features

- **Live NBA Scores:** Retrieves NBA scoreboard data through the Tank01 API.
- **Game Status:** Displays scheduled, live, and final game statuses.
- **Team Logos:** Displays NBA team logos with fallback graphics when a logo is unavailable.
- **Betting Odds:** Retrieves and displays game moneylines and over/under totals.
- **Automatic Rotation:** Cycles through available NBA games throughout the day.
- **Local Preview:** Generates image previews of the LED display.
- **Automated Polling:** Periodically refreshes scoreboard information.
- **Modular Architecture:** Separates API communication, data processing, rendering, and display output.

## Display

The ticker currently renders for a **256 × 48 pixel LED display**.

The rendering system is designed to keep the display compact and readable while presenting relevant game information.

## Tech

- Python
- Tank01 NBA API (RapidAPI)
- Pillow (PIL)
- Tkinter
- Logging
- Git / GitHub

## Structure

The application is organized into separate modules for:

- API communication and request handling
- NBA scoreboard retrieval
- Game data normalization
- Betting odds processing
- Team and venue information
- LED display rendering
- Preview and output management

## Installation

Clone the repository:

```bash
git clone YOUR_REPOSITORY_URL
cd NBA_LIVE_DATA
```

Create a virtual environment:

```bash
python -m venv .venv
```

Activate it on Windows:

```bash
.venv\Scripts\activate
```

Install project dependencies:

```bash
pip install -r requirements.txt
```

## Configuration

Create a local `.env` file containing your RapidAPI credentials and configure the application settings.

**Important:** Never commit `.env` or API keys to GitHub. The repository includes a `.gitignore` to protect sensitive configuration files.

## Running the Application

Start the ticker:

```bash
python -m nba_ticker --ignore-hours --scroll-interval 3
```

The application will retrieve available NBA games, process the scoreboard information, and rotate through the games in the preview/display output.

## Future Development

Planned development includes:

- Automated testing
- Centralized cloud-based NBA data collection
- Remote device communication
- Wi-Fi configuration for individual LED boards
- Multi-device support
- Remote software updates
- Physical enclosure and hardware integration

The long-term goal is to create a plug-and-play NBA LED scoreboard that connects to Wi-Fi and receives updates without requiring a separate computer.

---

## Releases & Version History

For release notes, version descriptions, screenshots, and feature updates, visit the project's GitHub Releases.

**Current stable release:** [v1.0.0 – Initial Stable Release](../../releases/tag/v1.0.0)
