"""Offline demo data so you can see the display without an API key or live games."""
from __future__ import annotations

from datetime import datetime

from .models import FINAL, LIVE, SCHEDULED, Game


class DemoScoreboard:
    """Drop-in replacement for Scoreboard. Scores/clock advance on every call."""

    def __init__(self) -> None:
        self._tick = 0

    def fetch(self, now: datetime) -> list[Game]:
        t = self._tick
        self._tick += 1
        d = now.strftime("%Y%m%d")
        mk = lambda **kw: Game(date=d, tip_epoch=None, **kw)  # noqa: E731
        return [
            mk(game_id=f"{d}_LAL@BOS", away="LAL", home="BOS",
               away_score=88 + 3 * t, home_score=91 + 2 * t,
               state=LIVE, display_status=f"Q3 {max(0, 9 - 2 * t)}:{(41 + 7 * t) % 60:02d}",
               arena="TD Garden", scheduled_time="6:30p", away_record="12-8", home_record="15-5",
               total="224.5", home_ml="-185"),
            mk(game_id=f"{d}_NY@MIL", away="NY", home="MIL",
               away_score=0, home_score=0, state=SCHEDULED, display_status="Scheduled",
               arena="Fiserv Forum", scheduled_time="7:30p", away_record="14-6", home_record="10-10",
               total="231", home_ml="+112"),
            mk(game_id=f"{d}_GS@DEN", away="GS", home="DEN",
               away_score=109, home_score=118, state=FINAL, display_status="Final",
               arena="Ball Arena", scheduled_time="8:00p", away_record="11-9", home_record="13-7",
               total="228.5", home_ml="-140"),
        ]
