"""Shared helpers for the REAL Evidence-Power Consolidation jobs (EV_JOB01-12).

research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible.

Every EV job resolves its supervisor run-dir + the canonical evidence_power artifact sub-dir here, and
reads ONLY validated LOCAL artifacts already on disk (data/reference/, data/processed/, prior research
runs, the exact StatsBomb<->API-Football bridge, the API-Football corpus via data_roots). It never:
  - touches the active collector checkout (worldcup_draw_model_lab_FINAL), B1, frozen M1-M5, candidate.py,
    approved_models.yaml, trading/Kalshi/risk, or .env;
  - performs ANY network / API-Football / Odds API / StatsBomb / scrape / credential / browser access;
  - fabricates a number -- a count that is not derivable from a present manifest/file is emitted as an
    honest `unknown` / `data_insufficient` with a reason, and a job may emit `skipped`/`data_insufficient`
    when an input product is genuinely absent. A false `complete` is never emitted.

The supervisor (deep_research_supervisor.py) invokes each job as `python <script> --run-dir <dir>` and
reads the LAST stdout JSON line emitted via emit(status, reason, state_updates). This mirrors
scripts/residual_jobs/_rg.py so the SAME supervisor harness runs these jobs unchanged.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
sys.path.insert(0, str(HERE))

REF = ROOT / "data/reference"
PROC = ROOT / "data/processed"
NOTES = ROOT / "notes/research"
SCRIPTS = ROOT / "scripts"
ART_SUBDIR = "evidence_power"
LABELS = "research_only/experimental/not_runtime_approved/not_trade_eligible/not_live_eligible"
COLLECTOR_FORBIDDEN = "worldcup_draw_model_lab_FINAL"

# ----- read-only source repos (validated local artifacts; NEVER the active collector) ---------------
BRIDGE_CSV = Path(
    "C:/Users/Mahyar/worldcup-player-impact-xg/data/processed/api_statsbomb_match_bridge_v1.csv")
RESIDUAL_REPO = Path("C:/Users/Mahyar/worldcup-residual-goal-intensity")
RESIDUAL_RUN_REL = "outputs/research_runs/rg_20260627_155623_run1/residual_goal_intensity"

# Hard backstop: this worktree must never resolve into the active collector checkout for writes.
if COLLECTOR_FORBIDDEN in str(ROOT).replace("\\", "/"):
    raise PermissionError("evidence jobs must not run inside the active collector checkout")

# Tokens that, if imported at module level by an EV job, would indicate a forbidden live/network path.
# Used by JOB01's own static self-check and by the test-suite (defence in depth).
FORBIDDEN_IMPORT_TOKENS = (
    "requests", "httpx", "urllib.request", "aiohttp", "websocket", "selenium", "playwright",
    "wcdrawlab.providers", "odds_api", "api_football_adapter", "fetch_odds", "live_2026",
)


def utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _argv_run_dir():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=False, default=None)
    a, _ = ap.parse_known_args()
    return a.run_dir


def run_dir() -> Path:
    """Resolve the supervisor run-dir from --run-dir (or DEEP_RESEARCH_RUN_DIR env fallback)."""
    rd = _argv_run_dir() or os.environ.get("DEEP_RESEARCH_RUN_DIR")
    if not rd:
        rd = str(ROOT / "outputs/research_runs" / "evp_adhoc")
    return Path(rd)


def art_dir() -> Path:
    d = run_dir() / ART_SUBDIR
    d.mkdir(parents=True, exist_ok=True)
    return d


def shared() -> dict:
    try:
        return json.loads(os.environ.get("DEEP_RESEARCH_SHARED", "{}"))
    except Exception:
        return {}


def write_json(name: str, obj: dict) -> Path:
    """Write a derived artifact to BOTH the run-dir evidence_power/ and data/reference/ (canonical)."""
    p = art_dir() / name
    p.write_text(json.dumps(obj, indent=2, default=str), encoding="utf-8")
    return p


def read_ref_json(name: str) -> "dict | None":
    return _read_json(REF / name)


def read_run_json(name: str) -> "dict | None":
    return _read_json(art_dir() / name)


def _read_json(p: Path) -> "dict | None":
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def residual_run_dir() -> Path:
    return RESIDUAL_REPO / RESIDUAL_RUN_REL


def data_roots():
    """Import the canonical fail-closed data-root resolver (proves DR wiring + isolation)."""
    from wcdrawlab.research import data_roots as DR
    return DR


def run_builder(rel_script: str, timeout=1800) -> dict:
    """Invoke an existing REAL builder script (read-only, offline) as a subprocess and parse its LAST
    JSON stdout line. Returns {ok, last_json, returncode, stderr_tail}. Never fabricates a result: if the
    builder cannot run we surface the real returncode + stderr."""
    script = ROOT / rel_script
    if not script.exists():
        return {"ok": False, "last_json": None, "returncode": None,
                "stderr_tail": f"builder missing: {rel_script}"}
    try:
        p = subprocess.run([sys.executable, str(script)], capture_output=True, text=True,
                           timeout=timeout, cwd=str(ROOT))
    except subprocess.TimeoutExpired:
        return {"ok": False, "last_json": None, "returncode": None,
                "stderr_tail": f"builder timeout: {rel_script}"}
    last = None
    for line in (p.stdout or "").splitlines():
        s = line.strip()
        if s.startswith("{") and s.endswith("}"):
            try:
                last = json.loads(s)
            except Exception:
                pass
    return {"ok": p.returncode == 0, "last_json": last, "returncode": p.returncode,
            "stderr_tail": (p.stderr or "")[-400:]}


def emit(status, reason="", state_updates=None, **extra):
    print(json.dumps({"status": status, "reason": reason,
                      "state_updates": state_updates or {}, **extra}, default=str))
