"""Collector session integrity (V1.5): append-only manifest, heartbeat, quota tracking, staleness,
fail-closed source reconciliation, MISSED_UNRECOVERABLE markers, clean-shutdown summary, resume.
Pure/IO helpers; time is injectable so tests are deterministic and never sleep.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class CriticalSourceDisagreement(RuntimeError):
    pass


def reconcile_critical(field: str, values: list):
    """Fail closed: a critical field (score, status, goal, red card) must agree across sources."""
    distinct = {json.dumps(v, sort_keys=True) for v in values if v is not None}
    if len(distinct) > 1:
        raise CriticalSourceDisagreement(f"{field}: sources disagree -> {sorted(distinct)}")
    return values[0] if values else None


def is_stale(decision_ts: str, retrieval_ts: str, max_minutes: float = 10.0) -> bool:
    """A snapshot is stale if retrieval is far after the intended decision time."""
    try:
        d = datetime.fromisoformat(str(decision_ts).replace("Z", "+00:00"))
        r = datetime.fromisoformat(str(retrieval_ts).replace("Z", "+00:00"))
    except Exception:
        return False
    return (r - d).total_seconds() > max_minutes * 60.0


class SessionManifest:
    """Append-only session log + heartbeat. Idempotent event keys prevent duplicate logging."""
    def __init__(self, session_dir: str | Path, session_id: str, clock=now_iso):
        self.dir = Path(session_dir); self.dir.mkdir(parents=True, exist_ok=True)
        self.session_id = session_id
        self.manifest = self.dir / f"manifest_{session_id}.jsonl"
        self.heartbeat_path = self.dir / f"heartbeat_{session_id}.json"
        self._clock = clock
        self.counts = {"captured": 0, "skipped": 0, "missed": 0, "duplicate": 0, "requests": 0}

    def _seen(self) -> set:
        if not self.manifest.exists():
            return set()
        return {json.loads(l).get("event_key") for l in self.manifest.read_text(encoding="utf-8").splitlines() if l.strip()}

    def log(self, event: str, event_key: str, **fields) -> bool:
        if event_key in self._seen():
            self.counts["duplicate"] += 1
            return False
        rec = {"ts": self._clock(), "session_id": self.session_id, "event": event,
               "event_key": event_key, **fields}
        with self.manifest.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, sort_keys=True) + "\n")
        if event in self.counts:
            self.counts[event] += 1
        return True

    def mark_missed(self, match_id, window, reason="MISSED_UNRECOVERABLE"):
        return self.log("missed", f"missed:{match_id}:{window}", match_id=match_id, window=window, reason=reason)

    def heartbeat(self, status="alive", **fields):
        self.heartbeat_path.write_text(json.dumps(
            {"ts": self._clock(), "session_id": self.session_id, "status": status, **fields}), encoding="utf-8")

    def shutdown_summary(self) -> dict:
        s = {"ts": self._clock(), "session_id": self.session_id, "status": "clean_shutdown", **self.counts}
        self.log("shutdown", f"shutdown:{self.session_id}", **self.counts)
        self.heartbeat("stopped", **self.counts)
        return s
