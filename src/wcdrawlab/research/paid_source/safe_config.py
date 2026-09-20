"""Read-only loader for the already-paid keys. Loads API_FOOTBALL_KEY + ODDS_API_KEY from the MAIN project
root .env into os.environ for in-process use. NEVER prints/returns/logs values, lengths, prefixes, or hashes.
Does NOT modify .env. research_only.
"""
from __future__ import annotations

import os
from pathlib import Path

MAIN_ROOT = Path("C:/Users/Mahyar/worldcup_draw_model_lab_FINAL")
KEYS = ("API_FOOTBALL_KEY", "ODDS_API_KEY")


def load_paid_keys(root: Path = MAIN_ROOT) -> dict:
    """Set os.environ for the two keys from the main-root .env (read-only). Return ONLY SET/MISSING status."""
    env = root / ".env"
    status = {k: "MISSING" for k in KEYS}
    if env.exists():
        for line in env.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            if k in KEYS and v:
                os.environ.setdefault(k, v)  # set without printing
                status[k] = "SET"
            # tolerate API_FOOTBALL_KEY_1 alias -> map onto API_FOOTBALL_KEY if base missing
            if k == "API_FOOTBALL_KEY_1" and v and not os.environ.get("API_FOOTBALL_KEY"):
                os.environ["API_FOOTBALL_KEY"] = v
                status["API_FOOTBALL_KEY"] = "SET"
    return status  # values never included


def status_only() -> dict:
    return load_paid_keys()
