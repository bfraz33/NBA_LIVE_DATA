from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class GameOdds:
    total: str | None = None
    home_ml: str | None = None


def _pick(books: list, key: str, preferred_book: str | None) -> str | None:
    for book in books:
        if not isinstance(book, dict):
            continue
        if preferred_book and book.get("sportsBook") != preferred_book:
            continue
        block = book.get("odds")
        if isinstance(block, dict) and block.get(key) not in (None, ""):
            return str(block[key])
    return None


def parse_odds(items: list, preferred_book: str | None = None) -> dict[str, GameOdds]:
    """Tank01 getNBABettingOdds (list format) -> {gameID: GameOdds}."""
    out: dict[str, GameOdds] = {}
    for item in items:
        if not isinstance(item, dict) or "gameID" not in item:
            continue
        books = item.get("sportsBooks")
        if not isinstance(books, list):
            continue
        out[item["gameID"]] = GameOdds(
            total=_pick(books, "totalOver", preferred_book),
            home_ml=_pick(books, "homeTeamMLOdds", preferred_book),
        )
    return out


def fetch_odds(client: Any, date_str: str, preferred_book: str | None = None) -> dict[str, GameOdds]:
    items = client.body(

        "getNBABettingOdds",
        {"gameDate": date_str, "playerProps": "false", "itemFormat": "list"},
        list,
        [],
    )
    
    return parse_odds(items, preferred_book)
