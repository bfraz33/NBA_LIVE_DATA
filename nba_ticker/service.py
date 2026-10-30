
"""Poll loop: fetch -> detect change -> fan out to sinks."""
from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from .models import Game

log = logging.getLogger(__name__)


@dataclass
class Snapshot:
    timestamp: str
    games: list[Game]

    def payload(self) -> dict:
        return {"timestamp": self.timestamp, "games": [g.to_dict() for g in self.games]}

    def fingerprint(self) -> str:
        return json.dumps([g.to_dict() for g in self.games], sort_keys=True, default=str)


class Sink(Protocol):
    name: str

    def publish(self, snapshot: Snapshot) -> None: ...
    def close(self) -> None: ...


class TickerService:
    def __init__(self, settings: Any, scoreboard: Any, sinks: list[Sink], ignore_hours: bool = False):
        self.settings = settings
        self.scoreboard = scoreboard
        self.sinks = sinks
        self.ignore_hours = ignore_hours
        self._last_fingerprint: str | None = None
        self._stop_event = threading.Event()
        self._closed = False

    def within_hours(self, now: datetime) -> bool:
        return self.ignore_hours or self.settings.poll_start_hour <= now.hour < self.settings.poll_end_hour

    def run_once(self, now: datetime | None = None) -> bool:
        """One poll cycle. Returns True if sinks were notified (data changed)."""
        now = now or datetime.now(self.settings.tz)
        if not self.within_hours(now):
            log.info("Outside polling hours (%s:00-%s:00). Skipping.",
                     self.settings.poll_start_hour, self.settings.poll_end_hour)
            return False

        games = self.scoreboard.fetch(now)
        snap = Snapshot(timestamp=now.isoformat(), games=games)
        fp = snap.fingerprint()
        if fp == self._last_fingerprint:
            log.info("No change in data (%d games).", len(games))
            return False
        self._last_fingerprint = fp

        for sink in self.sinks:
            try:
                sink.publish(snap)
            except Exception:
                log.exception("Sink '%s' failed", sink.name)
        return True

    def run_forever(self) -> None:
        log.info("Polling every %ds. Ctrl+C to stop.", self.settings.poll_interval)
        try:
            while not self._stop_event.is_set():
                try:
                    self.run_once()
                except Exception:
                    log.exception("Poll cycle failed; will retry next interval")

                self._stop_event.wait(self.settings.poll_interval)
        finally:
            self.close()

    def stop(self) -> None:
        """Request the polling loop to stop."""
        self._stop_event.set()

    def close(self) -> None:
        """Stop the service and close its sinks once."""
        self._stop_event.set()

        if self._closed:
            return

        self._closed = True

        for sink in self.sinks:
            try:
                sink.close()
            except Exception:
                log.exception("Error closing sink '%s'", sink.name)
