
from __future__ import annotations

import argparse
import logging
import sys
import threading
from dataclasses import replace
from datetime import datetime

from .config import Settings
from .logging_setup import setup_logging
from .service import TickerService

log = logging.getLogger("nba_ticker")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="nba_ticker", description="NBA live scores for LED tickers")
    p.add_argument("--demo", action="store_true", help="use built-in sample games (no API key needed)")
    p.add_argument("--once", action="store_true", help="run a single poll cycle and exit")
    p.add_argument("--ignore-hours", action="store_true", help="poll even outside the polling window")
    p.add_argument("--interval", type=int, help="seconds between polls (overrides POLL_INTERVAL_SECONDS)")
    p.add_argument("--preview", action=argparse.BooleanOptionalAction, default=True,
                   help="render the LED panel image (default: on)")
    p.add_argument("--popup", choices=["first", "always", "never"], default="first",
                   help="when to open the preview window (default: first)")
    p.add_argument("--scroll-interval", type=float, default=0,
                   help="seconds per game for scrolling preview (0=disabled, e.g. 3 for 3s per game)")
    p.add_argument("--db", action=argparse.BooleanOptionalAction, default=None, help="enable/disable Postgres")
    p.add_argument("--aws", action=argparse.BooleanOptionalAction, default=None, help="enable/disable AWS IoT publish")
    p.add_argument("-v", "--verbose", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = Settings.from_env()

    overrides = {}
    if args.interval:
        overrides["poll_interval"] = args.interval
    if args.db is not None:
        overrides["db_enabled"] = args.db
    if args.aws is not None:
        overrides["aws_enabled"] = args.aws

    settings = replace(settings, **overrides)
    setup_logging(settings.log_file, args.verbose)

    from .sinks import ConsoleSink

    sinks = [ConsoleSink(scroll_interval=args.scroll_interval)]
    preview_sink = None

    if args.preview:
        from .sinks.preview import PreviewSink

        preview_sink = PreviewSink(
            settings.logos_dir,
            settings.output_dir,
            popup=args.popup,
            scroll_interval=args.scroll_interval,
        )
        sinks.append(preview_sink)

    db_sink = None
    if settings.db_enabled and not args.demo:
        from .sinks.postgres import PostgresSink
        db_sink = PostgresSink(settings)
        sinks.append(db_sink)

    if settings.aws_enabled and not args.demo:
        from .sinks.aws_iot import AwsIotSink
        sinks.append(AwsIotSink(settings))

    if args.demo:
        from .demo import DemoScoreboard
        scoreboard = DemoScoreboard()
    else:
        if not settings.api_key:
            log.error("NBA_API_KEY is not set. Add it to .env (or run with --demo).")
            return 2

        from .client import Tank01Client
        from .scoreboard import Scoreboard

        scoreboard = Scoreboard(Tank01Client(settings), settings)

        if db_sink:
            try:
                today = datetime.now(settings.tz).strftime("%Y%m%d")
                n = scoreboard.state.seed(db_sink.load_day(today))
                log.info("Cache warm-started from DB: %d games", n)
            except Exception as exc:
                log.warning("DB warm start skipped: %s", exc)

    service = TickerService(
        settings,
        scoreboard,
        sinks,
        ignore_hours=args.demo or args.ignore_hours,
    )

    if args.once:
        try:
            service.run_once()
        finally:
            service.close()
        return 0

    # Without a popup, keep the original polling behavior.
    if preview_sink is None or args.popup == "never":
        service.run_forever()
        return 0

    # Run polling in the background so Tkinter owns the main thread.
    service_thread = threading.Thread(
        target=service.run_forever,
        name="nba-ticker-service",
        daemon=False,
    )

    service_thread.start()

    try:
        preview_sink.run_popup()
    except KeyboardInterrupt:
        log.info("Stopping...")
    except Exception:
        log.exception("Preview window failed")
    finally:
        service.stop()
        service_thread.join()

    return 0


if __name__ == "__main__":
    sys.exit(main())
