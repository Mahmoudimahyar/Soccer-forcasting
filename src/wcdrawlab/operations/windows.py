"""Capture-window scheduling for the prospective collector (V1.5).

Pre-match windows are T-90 and T-15 before kickoff. In-play checkpoints are fixed minutes
(0, 15, 30, HT=45, 60, 75, 85). A window is 'due' only inside [target, target+grace] and is otherwise
'pending' (too early) or 'missed' (grace elapsed). Pure datetime logic; no I/O, no network.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

PRE_MATCH = [("T-90", 90), ("T-15", 15)]
IN_PLAY = [("m0", 0), ("m15", 15), ("m30", 30), ("HT", 45), ("m60", 60), ("m75", 75), ("m85", 85)]


def _parse(ts):
    return datetime.fromisoformat(str(ts).replace("Z", "+00:00")).astimezone(timezone.utc)


def capture_plan(kickoff_iso: str, now_iso: str, *, grace_min: float = 10.0,
                 include_inplay: bool = True) -> list:
    """Return a status for every window: due / pending / missed (relative to `now`)."""
    ko = _parse(kickoff_iso); now = _parse(now_iso)
    plan = []

    def status(target):
        if now < target:
            return "pending"
        return "due" if now <= target + timedelta(minutes=grace_min) else "missed"

    for name, mins in PRE_MATCH:
        t = ko - timedelta(minutes=mins)
        plan.append({"window": name, "phase": "pre_match", "target_utc": t.isoformat(),
                     "decision_minute": 0, "status": status(t)})
    if include_inplay:
        for name, mins in IN_PLAY:
            t = ko + timedelta(minutes=mins)
            plan.append({"window": name, "phase": "in_play", "target_utc": t.isoformat(),
                         "decision_minute": mins, "status": status(t)})
    return plan


def due_windows(kickoff_iso, now_iso, **kw):
    return [w for w in capture_plan(kickoff_iso, now_iso, **kw) if w["status"] == "due"]
