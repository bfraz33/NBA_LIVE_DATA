from __future__ import annotations

from dataclasses import dataclass, asdict

SCHEDULED, LIVE, FINAL, OTHER = "scheduled", "live", "final", "other"


@dataclass
class Game:
    game_id: str
    date: str                      # YYYYMMDD
    away: str
    home: str
    away_score: int
    home_score: int
    state: str                     # scheduled | live | final | other
    display_status: str            # "Q3 4:21", "Final", "Scheduled", ...
    arena: str
    scheduled_time: str            # "7:00p" (local tz)
    tip_epoch: int | None
    away_record: str
    home_record: str
    total: str | None              # over/under line, e.g. "228.5"
    home_ml: str | None            # home moneyline, e.g. "-140"

    @property
    def show_score(self) -> bool:
        return self.state in (LIVE, FINAL)

    def to_dict(self) -> dict:
        d = asdict(self)
        # Backwards-compatible strings (DB columns / older consumers)
        d["ou_string"] = f"O/U: {self.total}" if self.total else "O/U: N/A"
        d["ml_string"] = f"ML: {self.home_ml}" if self.home_ml else "ML: N/A"
        return d
