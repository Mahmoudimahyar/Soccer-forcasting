"""Persistent, fail-closed budget + rate guard for The Odds API (V1.5 shadow collection).

Enforces a HARD total-credit ceiling and a minimum inter-request interval across process restarts via a
small JSON state file. All checks fail CLOSED (deny on any doubt). Time is injectable for tests.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def _now():
    return datetime.now(timezone.utc)


class OddsBudget:
    def __init__(self, state_path: str | Path, *, max_credits: int = 500, min_interval_s: float = 600.0,
                 clock=_now):
        self.path = Path(state_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.max_credits = max_credits
        self.min_interval_s = min_interval_s
        self._clock = clock
        self._state = self._load()

    def _load(self) -> dict:
        if self.path.exists():
            try:
                return json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {"credits_used": 0, "last_request_utc": None, "requests": 0}

    def _save(self):
        self.path.write_text(json.dumps(self._state, indent=2), encoding="utf-8")

    @property
    def credits_used(self) -> int:
        return int(self._state.get("credits_used", 0))

    def remaining(self) -> int:
        return max(0, self.max_credits - self.credits_used)

    def can_request(self, projected_credits: int = 1) -> tuple[bool, str]:
        """Fail-closed pre-check before a request that will cost `projected_credits`."""
        if projected_credits < 1:
            return False, "projected_credits must be >= 1"
        if self.credits_used + projected_credits > self.max_credits:
            return False, (f"budget would be exceeded: used {self.credits_used} + {projected_credits} "
                           f"> max {self.max_credits}")
        last = self._state.get("last_request_utc")
        if last:
            try:
                elapsed = (self._clock() - datetime.fromisoformat(last)).total_seconds()
            except Exception:
                return False, "unparseable last_request_utc (fail-closed)"
            if elapsed < self.min_interval_s:
                return False, (f"rate limit: only {elapsed:.0f}s since last request "
                               f"(< {self.min_interval_s:.0f}s)")
        return True, "ok"

    def record_request(self, credits: int):
        self._state["credits_used"] = self.credits_used + int(credits)
        self._state["requests"] = int(self._state.get("requests", 0)) + 1
        self._state["last_request_utc"] = self._clock().isoformat()
        self._save()

    def summary(self) -> dict:
        return {"credits_used": self.credits_used, "max_credits": self.max_credits,
                "remaining": self.remaining(), "requests": int(self._state.get("requests", 0)),
                "last_request_utc": self._state.get("last_request_utc")}
