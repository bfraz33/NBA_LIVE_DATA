import unittest
from unittest import mock

import requests

from nba_ticker.client import Tank01Client
from nba_ticker.config import Settings


class Resp:
    def __init__(self, status, payload=None):
        self.status_code, self._p = status, payload or {}
    def json(self): return self._p
    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code}")


class FakeSession:
    def __init__(self, responses):
        self.headers, self.responses, self.calls = {}, list(responses), []
    def get(self, url, params=None, timeout=None):
        self.calls.append((url, params, timeout))
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


@mock.patch("nba_ticker.client.time.sleep", lambda *_: None)
class ClientTests(unittest.TestCase):
    S = Settings(api_key="k", api_min_interval=0, api_retries=3)

    def test_retries_429_then_succeeds_and_sets_timeout(self):
        s = FakeSession([Resp(429), Resp(200, {"body": {"a": 1}})])
        out = Tank01Client(self.S, session=s).body("ep", {}, dict, {})
        self.assertEqual(out, {"a": 1})
        self.assertEqual(len(s.calls), 2)
        self.assertEqual(s.calls[0][2], self.S.api_timeout)      # original had no timeout -> could hang forever

    def test_network_errors_return_default(self):
        s = FakeSession([requests.ConnectionError("x")] * 3)
        self.assertEqual(Tank01Client(self.S, session=s).body("ep", {}, list, []), [])

    def test_wrong_body_type_returns_default(self):
        s = FakeSession([Resp(200, {"body": "oops"})])
        self.assertEqual(Tank01Client(self.S, session=s).body("ep", {}, dict, {}), {})

    def test_auth_error_is_not_retried_forever(self):
        s = FakeSession([Resp(403)])
        self.assertEqual(Tank01Client(self.S, session=s).body("ep", {}, dict, {}), {})
        self.assertEqual(len(s.calls), 1)


if __name__ == "__main__":
    unittest.main()
