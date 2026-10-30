
"""Fetch Tank01 data and normalize it into Game objects."""
from __future__ import annotations

import logging
import re
import time
from datetime import datetime, tzinfo
from typing import Any

from .models import FINAL, LIVE, OTHER, SCHEDULED, Game
from .odds import GameOdds, fetch_odds
from .state import StateCache, Venue

log = logging.getLogger(__name__)

TEAM_TTL = 6 * 3600
VENUE_RETRY = 30 * 60
NO_ARENA = "Available at game time"


# ----------------------------------------------------------------
# Parsing helpers
# ----------------------------------------------------------------

def first_present(d: dict, *keys: str) -> Any:
    """Return the first value that is not None or an empty string."""
    for key in keys:
        value = d.get(key)
        if value is not None and value != "":
            return value
    return None


def to_int(val: Any) -> int | None:
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


def to_epoch(val: Any) -> int | None:
    """Convert Tank01 epoch values to integers."""
    try:
        return int(float(val))
    except (TypeError, ValueError, OverflowError):
        return None


def format_period(period: Any) -> str:
    s = str(period or "").strip()

    if not s:
        return ""

    low = s.lower()

    if "half" in low:
        return "Half"

    num = re.search(r"\d+", low)

    if re.search(r"\bot\b|overtime|\d+ot\b", low):
        return f"OT{num.group()}" if num and int(num.group()) > 1 else "OT"

    if num:
        n = int(num.group())

        if n == 0:
            return ""

        if n <= 4:
            return f"Q{n}"

        return "OT" if n == 5 else f"OT{n - 4}"

    return s


def parse_status(
    raw_status: str,
    period: Any,
    clock: Any,
) -> tuple[str, str]:
    """Return the normalized game state and display text."""

    status = (raw_status or "").strip().lower()

    if any(word in status for word in ("final", "complete", "finished")):
        return FINAL, "Final"

    if any(word in status for word in ("postpon", "cancel", "suspend")):
        return OTHER, raw_status.strip().title()

    period_text = format_period(period)
    clock_text = str(clock or "").strip()

    if any(word in status for word in ("live", "progress")) or period_text or clock_text:
        display = " ".join(
            part for part in (period_text, clock_text) if part
        )
        return LIVE, display or "Live"

    return SCHEDULED, "Scheduled"


def format_tipoff(epoch: Any, tz: tzinfo) -> str:
    try:
        dt = datetime.fromtimestamp(int(float(epoch)), tz=tz)
    except (TypeError, ValueError, OverflowError, OSError):
        return ""

    return (
        dt.strftime("%I:%M%p")
        .lstrip("0")
        .lower()
        .replace("pm", "p")
        .replace("am", "a")
    )


def team_record(abbr: str, teams: list) -> str:
    for team in teams:
        if team.get("teamAbv") == abbr:
            wins = team.get("wins", 0)
            losses = team.get("loss", 0)
            ties = team.get("tie", 0)

            return (
                f"{wins}-{losses}-{ties}"
                if to_int(ties)
                else f"{wins}-{losses}"
            )

    return "N/A"


def nba_season(now: datetime) -> int:
    return now.year if now.month >= 10 else now.year - 1


# ----------------------------------------------------------------
# Scoreboard
# ----------------------------------------------------------------

class Scoreboard:

    def __init__(
        self,
        client: Any,
        settings: Any,
        state: StateCache | None = None,
    ):
        self.client = client
        self.settings = settings
        self.state = state or StateCache()

        self._teams: list = []
        self._teams_at = 0.0

    # ------------------------------------------------------------
    # Raw API fetchers
    # ------------------------------------------------------------

    def _scores_for(self, date_str: str) -> dict:
        """Retrieve the complete scoreboard for one calendar date."""

        log.info("Requesting NBA scoreboard for %s", date_str)

        response = self.client.body(
            "getNBAScoresOnly",
            {
                "gameDate": date_str,
                "topPerformers": "false",
            },
            dict,
            {},
        )

        if not isinstance(response, dict):
            log.warning(
                "Unexpected scoreboard response for %s: %s",
                date_str,
                type(response).__name__,
            )
            return {}

        log.info(
            "Tank01 returned %d raw games for %s",
            len(response),
            date_str,
        )

        return response

    def _records(self, now: datetime) -> list:
        """Retrieve and cache NBA team records."""

        if self._teams and time.monotonic() - self._teams_at < TEAM_TTL:
            return self._teams

        teams = self.client.body(
            "getNBATeams",
            {
                "sortBy": "standings",
                "rosters": "false",
                "schedules": "false",
                "topPerformers": "false",
                "teamStats": "false",
                "teamStatsSeason": str(nba_season(now)),
            },
            list,
            [],
        )

        if isinstance(teams, list) and teams:
            self._teams = teams
            self._teams_at = time.monotonic()
        else:
            log.warning("Unable to refresh NBA team records; using cached records")

        return self._teams

    def _venue(self, game_id: str) -> Venue:
        """Retrieve and cache arena and game-time information."""

        cached = self.state.venues.get(game_id)
        now = time.monotonic()

        if cached and (
            cached.ok or now - cached.fetched_at < VENUE_RETRY
        ):
            return cached

        body = self.client.body(
            "getNBABoxScore",
            {"gameID": game_id},
            dict,
            {},
        )

        if not isinstance(body, dict):
            body = {}

        arena = body.get("arena") or NO_ARENA
        epoch = to_epoch(body.get("gameTime_epoch"))

        venue = Venue(
            arena=arena,
            tip_epoch=epoch,
            tip_text=str(body.get("gameTime") or ""),
            ok=bool(body.get("arena")),
            fetched_at=now,
        )

        self.state.venues[game_id] = venue

        return venue

    # ------------------------------------------------------------
    # Date resolution
    # ------------------------------------------------------------

    def _resolve_games(self, now: datetime) -> tuple[str, dict]:
        """
        Always retrieve games for today's date.

        Do not replace today's scoreboard with tomorrow's games.
        Completed, live, and scheduled games should all be returned
        by the daily scoreboard endpoint.
        """

        today = now.strftime("%Y%m%d")

        games = self._scores_for(today)

        log.info(
            "Today's NBA scoreboard contains %d games (%s)",
            len(games),
            today,
        )

        return today, games

    # ------------------------------------------------------------
    # Main entry
    # ------------------------------------------------------------

    def fetch(self, now: datetime) -> list[Game]:
        """Fetch and normalize every game returned for today's date."""

        date_str, raw_games = self._resolve_games(now)

        if not raw_games:
            log.warning(
                "No NBA games returned for today's date: %s",
                date_str,
            )
            return []

        log.info(
            "Processing %d NBA games for %s",
            len(raw_games),
            date_str,
        )

        odds = fetch_odds(
            self.client,
            date_str,
            self.settings.preferred_book,
        )

        teams = self._records(now)

        games: list[Game] = []

        for game_id, info in raw_games.items():

            if not isinstance(info, dict):
                log.warning(
                    "Skipping game %s: response is not a dictionary",
                    game_id,
                )
                continue

            away = info.get("away")
            home = info.get("home")

            if not away or not home:
                log.warning(
                    "Skipping malformed game %s: away=%r home=%r",
                    game_id,
                    away,
                    home,
                )
                continue

            try:
                game = self._build(
                    game_id,
                    info,
                    date_str,
                    odds.get(game_id, GameOdds()),
                    teams,
                )

                games.append(game)

                log.info(
                    "Game added: %s @ %s | %s | %s",
                    game.away,
                    game.home,
                    game.display_status,
                    game.game_id,
                )

            except Exception:
                log.exception(
                    "Error processing game %s",
                    game_id,
                )

        games.sort(
            key=lambda game: (
                game.tip_epoch or 0,
                game.game_id,
            )
        )

        log.info(
            "Successfully processed %d of %d games returned by Tank01",
            len(games),
            len(raw_games),
        )

        return games

    # ------------------------------------------------------------
    # Build normalized Game object
    # ------------------------------------------------------------

    def _build(
        self,
        game_id: str,
        info: dict,
        date_str: str,
        odds: GameOdds,
        teams: list,
    ) -> Game:

        away = info["away"]
        home = info["home"]

        away_raw = to_int(
            first_present(
                info,
                "awayScore",
                "awayPts",
                "away_score",
            )
        )

        home_raw = to_int(
            first_present(
                info,
                "homeScore",
                "homePts",
                "home_score",
            )
        )

        away_score, home_score = self.state.resolve_score(
            game_id,
            away_raw,
            home_raw,
        )

        period = first_present(
            info,
            "currentPeriod",
            "quarter",
            "qtr",
            "currentQtr",
            "currentQuarter",
            "quarterNum",
            "qtrNum",
        )

        clock = first_present(
            info,
            "gameClock",
            "clock",
        )

        raw_status = str(
            first_present(
                info,
                "gameStatus",
                "gameStatusText",
            ) or ""
        )

        state, display = self.state.resolve_status(
            game_id,
            *parse_status(raw_status, period, clock),
        )

        venue = self._venue(game_id)

        epoch = (
            venue.tip_epoch
            or to_epoch(info.get("gameTime_epoch"))
        )

        tip = (
            format_tipoff(epoch, self.settings.tz)
            or venue.tip_text
            or str(info.get("gameTime") or "")
            or "TBD"
        )

        return Game(
            game_id=game_id,
            date=date_str,
            away=away,
            home=home,
            away_score=away_score,
            home_score=home_score,
            state=state,
            display_status=display,
            arena=venue.arena,
            scheduled_time=tip,
            tip_epoch=epoch,
            away_record=team_record(away, teams),
            home_record=team_record(home, teams),
            total=odds.total,
            home_ml=odds.home_ml,
        )
