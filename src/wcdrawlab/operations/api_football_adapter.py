"""Read-only, rate-limited, quota-aware API-Football adapter (V1.5 operations plane).

Safety by construction:
  - GET only; endpoint must be on the read-only allowlist (fail-closed otherwise).
  - Minimum inter-request interval + daily request budget with a held reserve (quota-aware).
  - The API key is read from the environment and NEVER printed, logged, or returned. Logs carry only a
    sanitized "GET <endpoint> params=<keys>" template (no secret, no values that could embed a secret).
  - Raw payloads are persisted append-only with a provenance envelope (caller chooses a gitignored dir).
  - A `transport` callable is injectable so unit tests never touch the network.

This adapter never trades, never writes model state, and never mutates protected files.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

BASE = "https://v3.football.api-sports.io"
READONLY_ALLOWLIST = {"/status", "/fixtures", "/standings", "/fixtures/events",
                      "/fixtures/lineups", "/fixtures/statistics", "/fixtures/players"}


class QuotaExceeded(RuntimeError):
    pass


class EndpointNotAllowed(RuntimeError):
    pass


@dataclass
class AdapterStats:
    requests_made: int = 0
    last_request_monotonic: float = 0.0
    sanitized_log: list = field(default_factory=list)


class ApiFootballReadOnly:
    def __init__(self, key_env: str = "API_FOOTBALL_KEY", *, daily_budget: int = 200,
                 reserve: int = 20, min_interval_s: float = 2.0, raw_dir: str | Path | None = None,
                 transport: Callable | None = None, clock: Callable[[], float] = time.monotonic,
                 sleep: Callable[[float], None] = time.sleep):
        self._key_env = key_env
        self.daily_budget = daily_budget
        self.reserve = reserve
        self.min_interval_s = min_interval_s
        self.raw_dir = Path(raw_dir) if raw_dir else None
        if self.raw_dir:
            self.raw_dir.mkdir(parents=True, exist_ok=True)
        self._transport = transport  # callable(url, headers, params) -> (status_code, json_obj)
        self._clock = clock
        self._sleep = sleep
        self.stats = AdapterStats()

    def _key(self) -> str:
        k = os.getenv(self._key_env)
        if not k:
            raise RuntimeError(f"{self._key_env} not set")
        return k

    def remaining_budget(self) -> int:
        return max(0, self.daily_budget - self.reserve - self.stats.requests_made)

    def _default_transport(self, url, headers, params):
        import requests
        r = requests.get(url, headers=headers, params=params, timeout=30)
        try:
            return r.status_code, r.json()
        except Exception:
            return r.status_code, {}

    def get(self, endpoint: str, params: dict | None = None) -> dict:
        if endpoint not in READONLY_ALLOWLIST:
            raise EndpointNotAllowed(f"{endpoint!r} not in read-only allowlist")
        if self.remaining_budget() <= 0:
            raise QuotaExceeded(f"daily budget exhausted (budget={self.daily_budget}, reserve={self.reserve})")
        # rate limit: enforce minimum interval since last request
        elapsed = self._clock() - self.stats.last_request_monotonic
        if self.stats.requests_made and elapsed < self.min_interval_s:
            self._sleep(self.min_interval_s - elapsed)
        params = params or {}
        # sanitized log: endpoint + param KEYS only (never values/secret)
        self.stats.sanitized_log.append(f"GET {endpoint} params={sorted(params.keys())}")
        transport = self._transport or self._default_transport
        status, payload = transport(BASE + endpoint, {"x-apisports-key": self._key()}, params)
        self.stats.requests_made += 1
        self.stats.last_request_monotonic = self._clock()
        if self.raw_dir and payload:
            self._persist(endpoint, params, status, payload)
        return {"status_class": f"{status // 100}xx", "ok": status == 200 and not payload.get("errors"),
                "response": payload.get("response", []), "errors": payload.get("errors")}

    def _persist(self, endpoint, params, status, payload):
        raw = json.dumps(payload, sort_keys=True).encode("utf-8")
        h = hashlib.sha256(raw).hexdigest()
        env = {"source": "api_football", "endpoint": endpoint, "param_keys": sorted(params.keys()),
               "status_class": f"{status // 100}xx", "payload_sha256": h}
        # append-only: content-addressed file + index line
        (self.raw_dir / f"{endpoint.strip('/').replace('/', '_')}_{h[:16]}.json").write_bytes(raw)
        with (self.raw_dir / "index.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(env) + "\n")
