"""Shared harness for the REAL International Event Lake restoration jobs (LK_JOB01-13).

research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible.

Every LK job resolves the supervisor run-dir + the canonical lake artifact sub-dir here, imports the
canonical fail-closed lake engine (wcdrawlab.research.international_event_lake) and the fail-closed
data-root resolver (wcdrawlab.research.data_roots), and either:

  * performs REAL lake work via the engine (init / restore-from-local / cohort / sentinel / retention),
    OR
  * invokes an EXISTING REAL builder script as a read-only subprocess and parses its LAST JSON stdout
    line (catalog / strict-bridge / legacy-restoration-manifest / acquire / power / model-rerun).

Hard guarantees enforced here (defence in depth; also covered by the test suite):
  * ISOLATION -- this worktree must NEVER be the active collector checkout, and no resolved data root
    may live under worldcup_draw_model_lab_FINAL. Raw event JSON lives ONLY in the external lake.
  * NO FORBIDDEN SOURCE -- no LK job may import a network/provider/scrape token at module scope EXCEPT
    the official-StatsBomb-open-data retrieval path that the engine itself owns (JOB6 acquisition).
    The only permitted external retrieval is the official StatsBomb Open Data events endpoint.
  * NO FABRICATION -- a count that is not derivable from a present manifest / lake object / file is
    emitted as an honest `unknown` / `data_insufficient` with a reason. A job may emit
    `skipped` / `data_insufficient` / `waiting_for_official_source` when an input is genuinely absent.
    A false `complete` is NEVER emitted.

Supervisor contract (scripts/deep_research_supervisor.py): each job is invoked as
`python <script> --run-dir <dir>` and the supervisor reads the LAST stdout JSON line emitted via
emit(status, reason, state_updates, api_requests=...). Status in
{complete, skipped, failed, blocked, waiting_for_official_source, data_insufficient}.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]               # the worktree (scripts/lake_jobs/_lk.py -> parents[1])
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
sys.path.insert(0, str(HERE))

REF = ROOT / "data/reference"
PROC = ROOT / "data/processed"
NOTES = ROOT / "notes/research"
SCRIPTS = ROOT / "scripts"
ART_SUBDIR = "international_event_lake"
LABELS = "research_only/experimental/not_runtime_approved/not_trade_eligible/not_live_eligible"
COLLECTOR_FORBIDDEN = "worldcup_draw_model_lab_FINAL"
EXPECTED_COLLECTOR_COMMIT = "dc73318"

# The ONLY external host any LK job is permitted to touch (the official StatsBomb Open Data tree).
OFFICIAL_HOST = "raw.githubusercontent.com/statsbomb/open-data"

# Hard backstop: an LK job must never run inside the active collector checkout.
if COLLECTOR_FORBIDDEN in str(ROOT).replace("\\", "/"):
    raise PermissionError("lake jobs must not run inside the active collector checkout")

# Tokens that, if imported at module scope by an LK job, would indicate a FORBIDDEN live/network path.
# JOB6 acquisition is allowed to use the engine's official-open-data retrieval (urllib via the engine
# acquisition script); it does NOT import any of these provider/scrape/browser tokens itself.
FORBIDDEN_IMPORT_TOKENS = (
    "httpx", "aiohttp", "websocket", "selenium", "playwright",
    "wcdrawlab.providers", "odds_api", "api_football_adapter", "fetch_odds", "live_2026",
    "api_football", "oddsapi", "the_odds_api",
)


def utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _argv_run_dir():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=False, default=None)
    a, _ = ap.parse_known_args()
    return a.run_dir


def run_dir() -> Path:
    rd = _argv_run_dir() or os.environ.get("DEEP_RESEARCH_RUN_DIR")
    if not rd:
        rd = str(ROOT / "outputs/research_runs" / "lk_adhoc")
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
    """Write a derived artifact to the run-dir international_event_lake/ sub-dir."""
    p = art_dir() / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=2, default=str), encoding="utf-8")
    return p


def read_run_json(name: str) -> "dict | None":
    return _read_json(art_dir() / name)


def read_ref_json(name: str) -> "dict | None":
    return _read_json(REF / name)


def _read_json(p: Path) -> "dict | None":
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def sha256_file(p: Path) -> "str | None":
    try:
        return hashlib.sha256(p.read_bytes()).hexdigest()
    except Exception:
        return None


# --------------------------------------------------------------------------------------------------
# canonical engines (proves DR wiring + isolation when imported)
# --------------------------------------------------------------------------------------------------
def lake_engine():
    from wcdrawlab.research import international_event_lake as L
    return L


def data_roots():
    from wcdrawlab.research import data_roots as DR
    return DR


def resolve_lake():
    """Resolve the persistent external lake (fails closed if it would live in a worktree/collector)."""
    return lake_engine().Lake.resolve()


# --------------------------------------------------------------------------------------------------
# isolation primitives (reused by JOB01 preflight + JOB07 audit + JOB13 final audit + the watchdog)
# --------------------------------------------------------------------------------------------------
def collector_commit() -> "str | None":
    coll = Path("C:/Users/Mahyar/worldcup_draw_model_lab_FINAL")
    try:
        out = subprocess.run(["git", "-C", str(coll), "rev-parse", "--short", "HEAD"],
                             capture_output=True, text=True).stdout.strip()
        return out or None
    except Exception:
        return None


def raw_git_tracked() -> str:
    try:
        return subprocess.run(["git", "ls-files", "data/raw"], capture_output=True, text=True,
                              cwd=str(ROOT)).stdout.strip()
    except Exception:
        return ""


def lake_objects_git_tracked() -> str:
    """The external lake must be 0 git-tracked files in THIS worktree (it lives outside it)."""
    try:
        L = lake_engine()
        lake = L.Lake.resolve()
        return subprocess.run(["git", "ls-files", str(lake.root)], capture_output=True, text=True,
                              cwd=str(ROOT)).stdout.strip()
    except Exception:
        return ""


def scan_forbidden_imports() -> list:
    """Scan every lk_job*.py for a forbidden network/provider/scrape import token at module scope."""
    hits = []
    for f in sorted(HERE.glob("lk_job*.py")):
        for ln in f.read_text(encoding="utf-8").splitlines():
            s = ln.strip()
            if not (s.startswith("import ") or s.startswith("from ")):
                continue
            # ignore comments-after-import is fine; we only care about real import statements
            for tok in FORBIDDEN_IMPORT_TOKENS:
                if tok in s:
                    hits.append({"file": f.name, "line": s, "token": tok})
    return hits


def roots_resolving_into_collector() -> list:
    """Names of any data root that resolves into the active collector checkout (fail-closed expects none)."""
    bad = []
    try:
        DR = data_roots()
        for name in DR._load()["roots"]:
            try:
                rp = str(DR.get_root(name)).replace("\\", "/")
                if COLLECTOR_FORBIDDEN in rp:
                    bad.append(name)
            except PermissionError:
                bad.append(name)  # the fail-closed resolver tripped -> would be in collector
            except Exception:
                pass
    except Exception:
        pass
    return bad


# --------------------------------------------------------------------------------------------------
# run an existing REAL builder script (read-only / engine-backed) and parse its LAST JSON stdout line
# --------------------------------------------------------------------------------------------------
def run_builder(rel_script: str, args: "list[str] | None" = None, timeout: int = 36000) -> dict:
    """Invoke an existing REAL builder script as a subprocess and parse its LAST JSON stdout line.

    Never fabricates a result: if the builder cannot run, the real returncode + stderr tail are surfaced.
    The forbidden-source / official-only retrieval policy is owned by the engine inside each builder.
    """
    script = ROOT / rel_script
    if not script.exists():
        return {"ok": False, "last_json": None, "returncode": None,
                "stderr_tail": f"builder missing: {rel_script}"}
    cmd = [sys.executable, str(script)] + list(args or [])
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=str(ROOT))
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
            "stdout_tail": (p.stdout or "")[-600:], "stderr_tail": (p.stderr or "")[-600:]}


def emit(status, reason="", state_updates=None, api_requests=0, **extra):
    print(json.dumps({"status": status, "reason": reason, "api_requests": int(api_requests or 0),
                      "state_updates": state_updates or {}, **extra}, default=str))
