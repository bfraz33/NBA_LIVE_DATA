from __future__ import annotations

import logging
import os
import threading
import time
from typing import Optional

from ..models import Game

log = logging.getLogger(__name__)


def clear_screen() -> None:
    """Cross-platform screen clear."""
    os.system('cls' if os.name == 'nt' else 'clear')


def format_game_line(g: Game) -> str:
    if g.show_score:
        head = f"{g.away} {g.away_score} @ {g.home} {g.home_score}   {g.display_status}"
    elif g.state == "scheduled":
        head = f"{g.away} ({g.away_record}) @ {g.home} ({g.home_record})   Tipoff {g.scheduled_time}"
    else:
        head = f"{g.away} @ {g.home}   {g.display_status}"
    extras = []
    if g.total:
        extras.append(f"O/U {g.total}")
    if g.home_ml:
        extras.append(f"{g.home} ML {g.home_ml}")
    return head + ("   " + "  ".join(extras) if extras else "") + f"   [{g.arena}]"


class ConsoleSink:
    name = "console"

    def __init__(self, scroll_interval: float = 0):
        self.scroll_interval = scroll_interval  # 0 = disabled, >0 = seconds per game
        self._scroll_thread: Optional[threading.Thread] = None
        self._stop_scroll = threading.Event()
        self._current_games: list[Game] = []

    def publish(self, snapshot) -> None:
        # Stop any existing scroll
        self._stop_scroll.set()
        if self._scroll_thread and self._scroll_thread.is_alive():
            self._scroll_thread.join(timeout=1.0)
        self._stop_scroll.clear()

        self._current_games = list(snapshot.games)

        if not self._current_games:
            print()
            print("No NBA games found.")
            return

        # Start scrolling if enabled and multiple games
        if self.scroll_interval > 0 and len(self._current_games) > 1:
            self._scroll_thread = threading.Thread(target=self._scroll_loop, daemon=True)
            self._scroll_thread.start()
        else:
            # Print all games at once (original behavior)
            self._print_all()

    def _print_all(self) -> None:
        print()
        for g in self._current_games:
            print(format_game_line(g))

    def _scroll_loop(self) -> None:
        """Cycle through games, printing one at a time every scroll_interval seconds."""
        idx = 0
        while not self._stop_scroll.is_set():
            # Clear screen and print single game
            clear_screen()
            print(format_game_line(self._current_games[idx]))
            log.debug("Scrolling: showing %s (%d/%d)", self._current_games[idx].game_id, idx + 1, len(self._current_games))

            # Wait for scroll_interval or until stopped
            if self._stop_scroll.wait(timeout=self.scroll_interval):
                break
            idx = (idx + 1) % len(self._current_games)

    def close(self) -> None:
        self._stop_scroll.set()
        if self._scroll_thread and self._scroll_thread.is_alive():
            self._scroll_thread.join(timeout=1.0)
