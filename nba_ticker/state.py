"""'Last known good' cache so a flaky API response never makes the board flicker."""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Iterable

from .models import FINAL, LIVE, SCHEDULED


@dataclass
class Venue:
    arena: str
    tip_epoch: int | None
    tip_text: str
    ok: bool            # False => fallback values; retry later
    fetched_at: float


def _state_from_display(display: str) -> str:
    d = (display or "").strip().lower()
    if d.startswith("final"):
        return FINAL
    if d.startswith(("q", "ot", "half", "live")):
        return LIVE
    return SCHEDULED


class StateCache:
    def __init__(self) -> None:
        self.scores: dict[str, tuple[int, int]] = {}
        self.statuses: dict[str, tuple[str, str]] = {}   # game_id -> (state, display)
        self.venues: dict[str, Venue] = {}

    # ---- warm start (e.g. from Postgres after a restart) ----
    def seed(self, rows: Iterable[dict]) -> int:
        loaded = 0
        for r in rows:
            gid = r.get("game_id")
            if not gid:
                continue
            a, h = r.get("away_score"), r.get("home_score")
            if a is not None and h is not None:
                self.scores[gid] = (int(a), int(h))
            disp = r.get("display_status")
            if disp:
                self.statuses[gid] = (_state_from_display(disp), disp)
            loaded += 1
        return loaded

    # ---- scores ----
    def resolve_score(self, game_id: str, away: int | None, home: int | None) -> tuple[int, int]:
        if away is not None and home is not None:
            self.scores[game_id] = (away, home)
            return away, home
        return self.scores.get(game_id, (0, 0))

    # ---- status ----
    def resolve_status(self, game_id: str, state: str, display: str) -> tuple[str, str]:
        prev = self.statuses.get(game_id)
        if prev:
            prev_state, prev_display = prev
            # API dropped fields mid-game: don't slide back to "scheduled"
            if state == SCHEDULED and prev_state in (LIVE, FINAL):
                return prev
            # Lost the quarter/clock but we know them: keep the richer text
            if state == LIVE and display == "Live" and prev_state == LIVE:
                return prev
        self.statuses[game_id] = (state, display)
        return state, display
