"""Read-only loader for API_FOOTBALL_KEY from the MAIN project-root .env. NEVER prints/returns values,
lengths, prefixes, or hashes. Does NOT modify .env. research_only."""
from __future__ import annotations
import os
from pathlib import Path
MAIN_ROOT = Path("C:/Users/Mahyar/worldcup_draw_model_lab_FINAL")
KEYS = ("API_FOOTBALL_KEY",)
def load_paid_keys(root: Path = MAIN_ROOT) -> dict:
    env = root / ".env"; status = {k: "MISSING" for k in KEYS}
    if env.exists():
        for line in env.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line: continue
            k, _, v = line.partition("="); k = k.strip(); v = v.strip().strip('"').strip("'")
            if k in KEYS and v: os.environ.setdefault(k, v); status[k] = "SET"
            if k == "API_FOOTBALL_KEY_1" and v and not os.environ.get("API_FOOTBALL_KEY"):
                os.environ["API_FOOTBALL_KEY"] = v; status["API_FOOTBALL_KEY"] = "SET"
    return status
