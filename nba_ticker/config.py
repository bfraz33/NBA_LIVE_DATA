"""All configuration lives here. Everything comes from environment / .env."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent


def _bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    # --- Tank01 / RapidAPI ---
    api_key: str = ""
    api_host: str = "tank01-fantasy-stats.p.rapidapi.com"
    api_min_interval: float = 3.0   # seconds between API calls
    api_retries: int = 3
    api_timeout: float = 15.0

    # --- Polling ---
    poll_interval: int = 180        # seconds between cycles
    timezone: str = "America/Chicago"
    poll_start_hour: int = 8        # inclusive
    poll_end_hour: int = 24         # exclusive (24 == through 11:59pm)
    preferred_book: str | None = None

    # --- Paths ---
    logos_dir: Path = ROOT / "logos"
    output_dir: Path = ROOT / "output"
    log_file: Path = ROOT / "nba_ticker.log"

    # --- Postgres (optional) ---
    db_enabled: bool = False
    db_name: str = "FrontOffice"
    db_user: str = "postgres"
    db_password: str = ""
    db_host: str = "localhost"
    db_port: int = 5432

    # --- AWS IoT Core (optional) ---
    aws_enabled: bool = False
    aws_endpoint: str = ""
    aws_region: str = "us-east-2"
    aws_client_id: str = "nba-publisher-ec2"
    aws_topic: str = "nba/live/scores"

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()
        e = os.getenv
        return cls(
            api_key=e("NBA_API_KEY") or e("RAPIDAPI_KEY") or "",
            api_host=e("RAPIDAPI_HOST", cls.api_host),
            api_min_interval=float(e("API_MIN_INTERVAL", cls.api_min_interval)),
            poll_interval=int(e("POLL_INTERVAL_SECONDS", cls.poll_interval)),
            timezone=e("TIMEZONE", "America/Chicago"),
            poll_start_hour=int(e("POLL_START_HOUR", cls.poll_start_hour)),
            poll_end_hour=int(e("POLL_END_HOUR", cls.poll_end_hour)),
            preferred_book=e("PREFERRED_BOOK") or None,
            db_enabled=_bool("DB_ENABLED"),
            db_name=e("DB_NAME", cls.db_name),
            db_user=e("DB_USER", cls.db_user),
            db_password=e("DB_PASSWORD", ""),
            db_host=e("DB_HOST", cls.db_host),
            db_port=int(e("DB_PORT", cls.db_port)),
            aws_enabled=_bool("AWS_ENABLED"),
            aws_endpoint=e("ENDPOINT", ""),
            aws_region=e("REGION", cls.aws_region),
            aws_client_id=e("NBA_CLIENT_ID", cls.aws_client_id),
            aws_topic=e("NBA_TOPIC", cls.aws_topic),
        )
