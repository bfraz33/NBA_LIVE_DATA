import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from nba_ticker.config import Settings
from nba_ticker.models import FINAL, LIVE, SCHEDULED
from nba_ticker.odds import parse_odds
from nba_ticker.render import HEIGHT, WIDTH, render_game
from nba_ticker.scoreboard import (Scoreboard, format_period, format_tipoff,
                                   parse_status, team_record)
from nba_ticker.service import TickerService
from nba_ticker.state import StateCache

CT = ZoneInfo("America/Chicago")
NOW = datetime(2026, 10, 29, 19, 0, tzinfo=CT)


class FakeClient:
    """Stands in for Tank01Client. `scores` can be swapped between polls."""

    def __init__(self):
        self.calls = []
        self.scores = {}
        self.boxscore = {"arena": "TD Garden", "gameTime": "7:30p", "gameTime_epoch": "1793320200.0"}
        self.teams = [{"teamAbv": "BOS", "wins": 15, "loss": 5}, {"teamAbv": "LAL", "wins": 12, "loss": 8}]
        self.odds = [{"gameID": "G1", "sportsBooks": [
            {"sportsBook": "fanduel", "odds": {"totalOver": "224.5", "homeTeamMLOdds": "-185"}}]}]

    def body(self, endpoint, params, expected_type, default):
        self.calls.append(endpoint)
        data = {
            "getNBAScoresOnly": self.scores, "getNBATeams": self.teams,
            "getNBABoxScore": self.boxscore, "getNBABettingOdds": self.odds,
        }[endpoint]
        return data if isinstance(data, expected_type) else default


def make_board(client=None):
    c = client or FakeClient()
    return c, Scoreboard(c, Settings(timezone="America/Chicago"))


class ParsingTests(unittest.TestCase):
    def test_period(self):
        self.assertEqual(format_period("3"), "Q3")
        self.assertEqual(format_period("3rd Qtr"), "Q3")
        self.assertEqual(format_period("Q2"), "Q2")
        self.assertEqual(format_period("5"), "OT")
        self.assertEqual(format_period("6"), "OT2")
        self.assertEqual(format_period("OT"), "OT")
        self.assertEqual(format_period("Halftime"), "Half")
        self.assertEqual(format_period("0"), "")
        self.assertEqual(format_period(None), "")

    def test_status(self):
        self.assertEqual(parse_status("Completed", "4", "0:00"), (FINAL, "Final"))
        self.assertEqual(parse_status("Live - In Progress", "3", "4:21"), (LIVE, "Q3 4:21"))
        self.assertEqual(parse_status("Live - In Progress", "", ""), (LIVE, "Live"))
        self.assertEqual(parse_status("Scheduled", "", ""), (SCHEDULED, "Scheduled"))
        self.assertEqual(parse_status("Not Started Yet", "0", ""), (SCHEDULED, "Scheduled"))

    def test_tipoff_is_portable_and_local(self):
        # 1793320200 = 2026-10-29 19:30 CDT -> "7:30p"; no %-I so it works on Windows
        self.assertEqual(format_tipoff("1793320200.0", CT), "7:30p")
        self.assertEqual(format_tipoff(None, CT), "")
        self.assertEqual(format_tipoff("garbage", CT), "")

    def test_records(self):
        teams = [{"teamAbv": "BOS", "wins": 3, "loss": 1}]
        self.assertEqual(team_record("BOS", teams), "3-1")
        self.assertEqual(team_record("XXX", teams), "N/A")

    def test_odds(self):
        o = parse_odds(FakeClient().odds)["G1"]
        self.assertEqual((o.total, o.home_ml), ("224.5", "-185"))
        self.assertEqual(parse_odds([{"gameID": "X", "sportsBooks": "bad"}]), {})


class CacheTests(unittest.TestCase):
    def test_score_survives_dropped_fields(self):
        s = StateCache()
        self.assertEqual(s.resolve_score("g", 50, 48), (50, 48))
        self.assertEqual(s.resolve_score("g", None, None), (50, 48))
        self.assertEqual(s.resolve_score("new", None, None), (0, 0))

    def test_real_zero_is_not_dropped(self):
        self.assertEqual(StateCache().resolve_score("g", 0, 0), (0, 0))

    def test_live_never_slides_back_to_scheduled(self):
        s = StateCache()
        s.resolve_status("g", LIVE, "Q2 5:00")
        self.assertEqual(s.resolve_status("g", SCHEDULED, "Scheduled"), (LIVE, "Q2 5:00"))
        self.assertEqual(s.resolve_status("g", LIVE, "Live"), (LIVE, "Q2 5:00"))
        self.assertEqual(s.resolve_status("g", LIVE, "Q2 4:40"), (LIVE, "Q2 4:40"))

    def test_seed_from_db(self):
        s = StateCache()
        n = s.seed([{"game_id": "g", "away_score": 10, "home_score": 12, "display_status": "Q1 2:00"}])
        self.assertEqual(n, 1)
        self.assertEqual(s.statuses["g"][0], LIVE)
        self.assertEqual(s.scores["g"], (10, 12))


class ScoreboardTests(unittest.TestCase):
    def test_builds_game_and_caches_static_calls(self):
        c, board = make_board()
        c.scores = {"G1": {"away": "LAL", "home": "BOS", "awayPts": "88", "homePts": "91",
                           "gameStatus": "Live - In Progress", "currentPeriod": "3rd Qtr", "gameClock": "4:21"}}
        g = board.fetch(NOW)[0]
        self.assertEqual((g.away_score, g.home_score, g.display_status), (88, 91, "Q3 4:21"))
        self.assertEqual((g.arena, g.scheduled_time), ("TD Garden", "7:30p"))
        self.assertEqual((g.away_record, g.home_record, g.total, g.home_ml), ("12-8", "15-5", "224.5", "-185"))

        c.calls.clear()
        board.fetch(NOW)
        # second poll: ONLY scores + odds. Venue and team records come from cache.
        self.assertEqual(sorted(c.calls), ["getNBABettingOdds", "getNBAScoresOnly"])

    def test_api_blip_does_not_blank_scores(self):
        c, board = make_board()
        c.scores = {"G1": {"away": "LAL", "home": "BOS", "awayPts": "50", "homePts": "48",
                           "gameStatus": "Live - In Progress", "currentPeriod": "2", "gameClock": "6:00"}}
        board.fetch(NOW)
        c.scores = {"G1": {"away": "LAL", "home": "BOS", "gameStatus": "Scheduled"}}   # fields dropped
        g = board.fetch(NOW)[0]
        self.assertEqual((g.away_score, g.home_score, g.state), (50, 48, LIVE))

    def test_missing_arena_is_retried_not_cached_forever(self):
        c, board = make_board()
        c.boxscore = {}
        c.scores = {"G1": {"away": "LAL", "home": "BOS", "gameStatus": "Scheduled"}}
        self.assertEqual(board.fetch(NOW)[0].arena, "Available at game time")
        self.assertFalse(board.state.venues["G1"].ok)

    def test_malformed_game_skipped(self):
        c, board = make_board()
        c.scores = {"BAD": "nope", "G1": {"away": "LAL", "home": "BOS", "gameStatus": "Scheduled"}}
        self.assertEqual([g.game_id for g in board.fetch(NOW)], ["G1"])

    def test_lookahead_searches_once_per_day(self):
        c, board = make_board()
        days = []
        orig = c.body

        def body(endpoint, params, expected_type, default):
            if endpoint == "getNBAScoresOnly":
                days.append(params["gameDate"])
                if params["gameDate"] == "20261101":
                    return {"G1": {"away": "LAL", "home": "BOS", "gameStatus": "Scheduled"}}
                return {}
            return orig(endpoint, params, expected_type, default)

        c.body = body
        self.assertEqual(len(board.fetch(NOW)), 1)
        first = len(days)
        board.fetch(NOW)
        self.assertEqual(len(days) - first, 2)     # today + remembered next date, not a fresh 7-day sweep


class ServiceTests(unittest.TestCase):
    class Rec:
        name = "rec"
        def __init__(self): self.n = 0
        def publish(self, snap): self.n += 1
        def close(self): pass

    class Boom(Rec):
        name = "boom"
        def publish(self, snap): raise RuntimeError("down")

    def test_publish_only_on_change_and_sinks_isolated(self):
        c, board = make_board()
        c.scores = {"G1": {"away": "LAL", "home": "BOS", "gameStatus": "Scheduled"}}
        rec = self.Rec()
        svc = TickerService(Settings(), board, [self.Boom(), rec])
        self.assertTrue(svc.run_once(NOW))
        self.assertFalse(svc.run_once(NOW))          # unchanged
        self.assertEqual(rec.n, 1)                   # good sink still ran despite the broken one
        c.scores = {"G1": {"away": "LAL", "home": "BOS", "awayPts": "2", "homePts": "0",
                           "gameStatus": "Live - In Progress", "currentPeriod": "1", "gameClock": "11:00"}}
        self.assertTrue(svc.run_once(NOW))
        self.assertEqual(rec.n, 2)

    def test_polling_window(self):
        c, board = make_board()
        svc = TickerService(Settings(), board, [])
        self.assertFalse(svc.within_hours(datetime(2026, 10, 29, 7, 59, tzinfo=CT)))
        self.assertTrue(svc.within_hours(datetime(2026, 10, 29, 8, 0, tzinfo=CT)))
        self.assertTrue(svc.within_hours(datetime(2026, 10, 29, 23, 59, tzinfo=CT)))


class RenderTests(unittest.TestCase):
    def test_frame_size_and_missing_logo_fallback(self):
        c, board = make_board()
        c.scores = {"G1": {"away": "LAL", "home": "BOS", "awayPts": "1", "homePts": "2",
                           "gameStatus": "Completed"}}
        img = render_game(board.fetch(NOW)[0], Path("/nonexistent"))
        self.assertEqual(img.size, (WIDTH, HEIGHT))


if __name__ == "__main__":
    unittest.main()
