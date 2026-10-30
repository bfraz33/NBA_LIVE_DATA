"""Tank01 (RapidAPI) client: throttling, retries, timeouts, and health monitoring."""
from __future__ import annotations

import logging
import time
from enum import Enum
from typing import Any

import requests

from .config import Settings

log = logging.getLogger(__name__)


class APIHealth(Enum):
    HEALTHY = "HEALTHY"
    WARNING = "WARNING"
    RECOVERED = "RECOVERED"


class Tank01Client:
    def __init__(self, settings: Settings, session: requests.Session | None = None):
        self._s = settings
        self._session = session or requests.Session()
        self._session.headers.update(
            {"X-RapidAPI-Key": settings.api_key, "X-RapidAPI-Host": settings.api_host}
        )
        self._last_call = 0.0
        self._health_state = APIHealth.HEALTHY
        self._consecutive_failures = 0
        self._last_warning_time = 0.0
        self._warning_cooldown = 30.0  # seconds between repeated warnings

    def _throttle(self) -> None:
        wait = self._s.api_min_interval - (time.monotonic() - self._last_call)
        if wait > 0:
            time.sleep(wait)
        self._last_call = time.monotonic()

    def _log_health(self, state: APIHealth, message: str) -> None:
        """Log API health state changes with structured format."""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        log.info("[API %s] %s", state.value, message)

    def _check_health_transition(self, success: bool, error_type: str | None = None) -> None:
        """Track and log API health state transitions."""
        now = time.monotonic()

        if success:
            self._consecutive_failures = 0
            if self._health_state != APIHealth.HEALTHY:
                if self._health_state == APIHealth.WARNING:
                    self._log_health(APIHealth.RECOVERED, "Tank01 connection restored")
                self._health_state = APIHealth.HEALTHY
                self._log_health(APIHealth.HEALTHY, "Tank01 connection healthy")
        else:
            self._consecutive_failures += 1
            if self._health_state == APIHealth.HEALTHY:
                self._health_state = APIHealth.WARNING

            # Log warning with cooldown to avoid spam
            if now - self._last_warning_time >= self._warning_cooldown:
                if error_type == "timeout":
                    self._log_health(APIHealth.WARNING, "Request timed out")
                elif error_type == "rate_limit":
                    self._log_health(APIHealth.WARNING, "Rate limit reached. Retrying in 10 seconds")
                else:
                    self._log_health(APIHealth.WARNING, f"Request failed: {error_type}")
                self._last_warning_time = now

    def _get(self, endpoint: str, params: dict | None) -> Any:
        url = f"https://{self._s.api_host}/{endpoint}"
        last_err: Exception | None = None

        for attempt in range(1, self._s.api_retries + 1):
            self._throttle()
            try:
                resp = self._session.get(url, params=params, timeout=self._s.api_timeout)
            except requests.Timeout as exc:
                last_err = exc
                self._check_health_transition(False, "timeout")
                log.warning("%s: timeout (attempt %d): %s", endpoint, attempt, exc)
                time.sleep(2 * attempt)
                continue
            except requests.RequestException as exc:
                last_err = exc
                self._check_health_transition(False, type(exc).__name__)
                log.warning("%s: network error (attempt %d): %s", endpoint, attempt, exc)
                time.sleep(2 * attempt)
                continue

            if resp.status_code == 429 or resp.status_code >= 500:
                last_err = RuntimeError(f"HTTP {resp.status_code}")

                retry_after = resp.headers.get("Retry-After")

                if resp.status_code == 429 and retry_after:
                    try:
                        wait = float(retry_after)
                    except ValueError:
                        wait = 2 * attempt
                else:
                    wait = 2 * attempt

                log.warning(
                    "%s: HTTP %d (attempt %d). Retrying in %.1f seconds",
                    endpoint,
                    resp.status_code,
                    attempt,
                    wait,
                )

                time.sleep(wait)
                continue
            if resp.status_code >= 400:
                last_err = RuntimeError(f"HTTP {resp.status_code}")
                self._check_health_transition(False, f"HTTP {resp.status_code}")
                log.warning("%s: HTTP %d (attempt %d), backing off", endpoint, resp.status_code, attempt)
                time.sleep(2 * attempt)
                continue

            resp.raise_for_status()
            self._check_health_transition(True)
            return resp.json()

        self._check_health_transition(False, "max_retries")
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