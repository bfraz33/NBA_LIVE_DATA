
"""Render individual NBA game frames and display a live rotating preview."""
from __future__ import annotations

import logging
import re
import threading
from pathlib import Path

from PIL import Image

from ..render import HEIGHT, WIDTH, render_game, render_message, render_sheet

log = logging.getLogger(__name__)

FRAME_SIZE = (WIDTH, HEIGHT)


class PreviewSink:
    name = "preview"

    def __init__(
        self,
        logos_dir: Path,
        out_dir: Path,
        popup: str = "first",
        scale: int = 3,
        scroll_interval: float = 5.0,
    ):
        self.logos_dir = logos_dir
        self.out_dir = out_dir
        self.frames_dir = out_dir / "frames"

        self.preview_path = out_dir / "preview.png"
        self.sheet_path = out_dir / "preview-sheet.png"

        self.popup = popup
        self.scale = max(1, scale)
        self.scroll_interval = max(0.0, scroll_interval)

        self._shown = False
        self._popup_requested = False

        # Game rotation
        self._scroll_thread = None
        self._stop_scroll = threading.Event()

        # Shared state
        self._lock = threading.Lock()
        self._current_games = []
        self._current_index = 0
        self._preview_version = 0

        self.frames_dir.mkdir(parents=True, exist_ok=True)

    def _save_single_frame(self, frame: Image.Image) -> None:
        """Save one scaled game frame as preview.png."""
        scaled = frame.convert("RGB").resize(
            (WIDTH * self.scale, HEIGHT * self.scale),
            Image.Resampling.NEAREST,
        )

        temporary_path = self.preview_path.with_name("preview.tmp.png")
        scaled.save(temporary_path)
        temporary_path.replace(self.preview_path)

    def _save_game_frames(self, games: list) -> list:
        """Render and save an individual image for every game."""
        frames = []

        for game in games:
            frame = render_game(game, self.logos_dir)

            safe_id = re.sub(r"[^A-Za-z0-9_.-]", "_", game.game_id)
            frame.save(self.frames_dir / f"{safe_id}.png")

            frames.append((game, frame))

        return frames

    # ---------------------------------------------------------
    # GAME ROTATION
    # ---------------------------------------------------------

    def _stop_existing_scroll(self) -> None:
        self._stop_scroll.set()

        if self._scroll_thread and self._scroll_thread.is_alive():
            self._scroll_thread.join()

        self._scroll_thread = None
        self._stop_scroll.clear()

    def publish(self, snapshot) -> None:
        """Update available games and start or restart rotation."""
        self._stop_existing_scroll()

        if snapshot.games:
            game_frames = self._save_game_frames(snapshot.games)
        else:
            game_frames = [(None, render_message("No NBA games"))]

        frames = [frame for _, frame in game_frames]

        sheet = render_sheet(frames, scale=self.scale)
        sheet.save(self.sheet_path)

        with self._lock:
            previous_game_id = None

            if self._current_games:
                previous_game = self._current_games[self._current_index][0]
                previous_game_id = getattr(previous_game, "game_id", None)

            self._current_games = game_frames
            self._current_index = 0

            if previous_game_id:
                for index, (game, _) in enumerate(self._current_games):
                    if getattr(game, "game_id", None) == previous_game_id:
                        self._current_index = index
                        break

            current_frame = self._current_games[self._current_index][1]
            self._preview_version += 1

        self._save_single_frame(current_frame)

        log.info(
            "Preview updated: %s (%d games available)",
            self.preview_path,
            len(game_frames),
        )

        if self.popup != "never":
            self._popup_requested = True

        if self.scroll_interval > 0 and len(game_frames) > 1:
            self._scroll_thread = threading.Thread(
                target=self._scroll_loop,
                name="nba-preview-scroll",
                daemon=True,
            )
            self._scroll_thread.start()

    def _scroll_loop(self) -> None:
        """Rotate preview.png through one game at a time."""
        while not self._stop_scroll.wait(self.scroll_interval):
            with self._lock:
                if not self._current_games:
                    return

                self._current_index = (
                    self._current_index + 1
                ) % len(self._current_games)

                game, frame = self._current_games[self._current_index]
                index = self._current_index + 1
                count = len(self._current_games)
                self._preview_version += 1

            self._save_single_frame(frame)

            game_id = getattr(game, "game_id", "message")

            log.info(
                "Preview showing game %s (%d/%d)",
                game_id,
                index,
                count,
            )

    # ---------------------------------------------------------
    # LIVE TKINTER PREVIEW - MAIN THREAD ONLY
    # ---------------------------------------------------------

    def run_popup(self) -> None:
        """Run the Tkinter window on the application's main thread."""
        import tkinter as tk
        from PIL import ImageTk

        root = tk.Tk()
        root.title("NBA Live Scoreboard Preview")
        root.resizable(False, False)
        root.withdraw()

        label = tk.Label(root)
        label.pack()

        last_version = -1
        photo_image = None

        def refresh_preview():
            nonlocal last_version, photo_image

            if self._popup_requested and not self._shown:
                root.deiconify()
                self._shown = True

            with self._lock:
                version = self._preview_version

                if self._current_games:
                    frame = self._current_games[
                        self._current_index
                    ][1].copy()
                else:
                    frame = None

            if frame is not None and version != last_version:
                resized = frame.convert("RGB").resize(
                    (WIDTH * self.scale, HEIGHT * self.scale),
                    Image.Resampling.NEAREST,
                )

                photo_image = ImageTk.PhotoImage(resized)
                label.configure(image=photo_image)
                last_version = version

            root.after(150, refresh_preview)

        def on_close():
            root.destroy()

        root.protocol("WM_DELETE_WINDOW", on_close)

        refresh_preview()
        root.mainloop()

    # ---------------------------------------------------------
    # SHUTDOWN
    # ---------------------------------------------------------

    def close(self) -> None:
        """Stop game rotation."""
        self._stop_existing_scroll()
        log.info("Preview sink closed.")
