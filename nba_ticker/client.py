"""Tank01 (RapidAPI) client: throttling, retries, timeouts."""
from __future__ import annotations

import logging
import time
from typing import Any

import requests

from .config import Settings

log = logging.getLogger(__name__)


class Tank01Client:
    def __init__(self, settings: Settings, session: requests.Session | None = None):
        self._s = settings
        self._session = session or requests.Session()
        self._session.headers.update(
            {"X-RapidAPI-Key": settings.api_key, "X-RapidAPI-Host": settings.api_host}
        )
        self._last_call = 0.0

    def _throttle(self) -> None:
        wait = self._s.api_min_interval - (time.monotonic() - self._last_call)
        if wait > 0:
            time.sleep(wait)
        self._last_call = time.monotonic()

    def _get(self, endpoint: str, params: dict | None) -> Any:
        url = f"https://{self._s.api_host}/{endpoint}"
        last_err: Exception | None = None
        for attempt in range(1, self._s.api_retries + 1):
            self._throttle()
            try:
                resp = self._session.get(url, params=params, timeout=self._s.api_timeout)
            except requests.RequestException as exc:
                last_err = exc
                log.warning("%s: network error (attempt %d): %s", endpoint, attempt, exc)
                time.sleep(2 * attempt)
                continue
            if resp.status_code == 429 or resp.status_code >= 500:
                last_err = RuntimeError(f"HTTP {resp.status_code}")
                log.warning("%s: HTTP %d (attempt %d), backing off", endpoint, resp.status_code, attempt)
                time.sleep(2 * attempt)
                continue
            resp.raise_for_status()
            return resp.json()
        raise RuntimeError(f"{endpoint}: gave up after {self._s.api_retries} attempts ({last_err})")

    def body(self, endpoint: str, params: dict | None, expected_type: type, default: Any) -> Any:
        """Return payload['body'] if it has the expected type, otherwise `default`.

        Never raises: API trouble is logged and the caller carries on with cached data.
        """
        try:
            payload = self._get(endpoint, params)
        except Exception as exc:  # noqa: BLE001 - we deliberately keep the loop alive
            log.error("Error fetching %s: %s", endpoint, exc)
            return default
        body = payload.get("body", default) if isinstance(payload, dict) else default
        if not isinstance(body, expected_type):
            log.warning("%s: unexpected body type %s", endpoint, type(body).__name__)
            return default
        return body
