"""Render a Game to a 256x48 LED-panel frame (and a preview sheet of many frames)."""
from __future__ import annotations

import hashlib
import logging
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .models import FINAL, LIVE, Game

log = logging.getLogger(__name__)

WIDTH, HEIGHT = 256, 48
LOGO = 24

WHITE = (255, 255, 255)
DIM = (140, 140, 140)
AMBER = (255, 176, 0)
GREEN = (80, 220, 100)
BG = (0, 0, 0)

# Tank01 abbreviations that differ from the common ones - try both when looking for a logo file
LOGO_ALIASES = {
    "GS": "GSW", "NY": "NYK", "SA": "SAS", "NO": "NOP", "PHO": "PHX",
    "UTAH": "UTA", "WAS": "WSH", "BKN": "BRK", "CHA": "CHO",
}
LOGO_ALIASES.update({v: k for k, v in list(LOGO_ALIASES.items())})


@lru_cache(maxsize=None)
def _font(size: int) -> ImageFont.ImageFont:
    try:
        return ImageFont.load_default(size=size)      # Pillow >= 10.1
    except TypeError:
        return ImageFont.load_default()


def _find_logo(abbr: str, logos_dir: Path) -> Path | None:
    for name in (abbr, LOGO_ALIASES.get(abbr)):
        if name:
            p = logos_dir / f"{name.upper()}.png"
            if p.exists():
                return p
    return None


@lru_cache(maxsize=64)
def _load_logo(abbr: str, logos_dir: Path) -> Image.Image:
    path = _find_logo(abbr, logos_dir)
    if path:
        try:
            return Image.open(path).convert("RGBA").resize((LOGO, LOGO), Image.LANCZOS)
        except Exception as exc:  # noqa: BLE001
            log.warning("Could not load logo %s: %s", path, exc)
    else:
        log.debug("No logo for %s in %s - using badge", abbr, logos_dir)
    return _badge(abbr)


def _badge(abbr: str) -> Image.Image:
    """Placeholder: colored tile with the team abbreviation."""
    h = hashlib.md5(abbr.encode()).digest()
    color = (60 + h[0] % 140, 60 + h[1] % 140, 60 + h[2] % 140, 255)
    img = Image.new("RGBA", (LOGO, LOGO), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, LOGO - 1, LOGO - 1), radius=5, fill=color)
    f = _font(10)
    d.text((LOGO / 2, LOGO / 2), abbr[:3], font=f, fill=WHITE, anchor="mm")
    return img


def _fit(draw: ImageDraw.ImageDraw, text: str, font, max_w: int) -> str:
    if draw.textlength(text, font=font) <= max_w:
        return text
    while text and draw.textlength(text + "...", font=font) > max_w:
        text = text[:-1]
    return text + "..."


def render_game(game: Game, logos_dir: Path) -> Image.Image:
    img = Image.new("RGBA", (WIDTH, HEIGHT), BG + (255,))
    d = ImageDraw.Draw(img)
    d.fontmode = "1"                                   # no anti-aliasing: crisp like real LEDs

    big, small, tiny = _font(18), _font(11), _font(9)

    # logos + records
    img.paste(_load_logo(game.away, logos_dir), (3, 3), _load_logo(game.away, logos_dir))
    img.paste(_load_logo(game.home, logos_dir), (WIDTH - LOGO - 3, 3), _load_logo(game.home, logos_dir))
    d.text((3, 34), game.away_record, font=tiny, fill=DIM)
    d.text((WIDTH - 3, 34), game.home_record, font=tiny, fill=DIM, anchor="ra")

    # scores (live/final only); dim the loser once it's final
    if game.show_score:
        a_col = h_col = WHITE
        if game.state == FINAL and game.away_score != game.home_score:
            a_col, h_col = (WHITE, DIM) if game.away_score > game.home_score else (DIM, WHITE)
        d.text((32, 4), str(game.away_score), font=big, fill=a_col)
        d.text((WIDTH - 32, 4), str(game.home_score), font=big, fill=h_col, anchor="ra")

    # center column
    status = f"Tipoff {game.scheduled_time}" if game.state == "scheduled" else game.display_status
    status_color = AMBER if game.state == LIVE else (GREEN if game.state == FINAL else WHITE)
    lines: list[tuple[str, tuple[int, int, int]]] = [(status, status_color)]
    if game.total:
        lines.append((f"O/U {game.total}", WHITE))
    if game.home_ml:
        lines.append((f"{game.home} ML {game.home_ml}", WHITE))
    if game.arena:
        lines.append((game.arena, DIM))

    max_w, line_h = 112, 11
    top = (HEIGHT - len(lines) * line_h) // 2
    for i, (text, color) in enumerate(lines):
        d.text((WIDTH // 2, top + i * line_h), _fit(d, text, small, max_w), font=small, fill=color, anchor="ma")
    return img


def render_message(text: str) -> Image.Image:
    img = Image.new("RGBA", (WIDTH, HEIGHT), BG + (255,))
    d = ImageDraw.Draw(img)
    d.fontmode = "1"
    d.text((WIDTH // 2, HEIGHT // 2), text, font=_font(12), fill=AMBER, anchor="mm")
    return img


def render_sheet(frames: list[Image.Image], scale: int = 3, gap: int = 6) -> Image.Image:
    """Tile frames into one preview image (scaled up so pixels are easy to see)."""
    cols = 1 if len(frames) <= 4 else 2
    rows = -(-len(frames) // cols)
    w, h = WIDTH * scale, HEIGHT * scale
    sheet = Image.new("RGB", (cols * w + (cols + 1) * gap, rows * h + (rows + 1) * gap), (28, 28, 32))
    for i, fr in enumerate(frames):
        r, c = divmod(i, cols)
        big = fr.convert("RGB").resize((w, h), Image.NEAREST)
        sheet.paste(big, (gap + c * (w + gap), gap + r * (h + gap)))
    return sheet
