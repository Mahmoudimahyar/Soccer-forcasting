"""Shared helpers for the REAL residual goal-intensity modeling/eval jobs (RG_JOB01-14).

research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible.

Every RG job resolves its run-dir + artifact sub-dir here, loads sources ONLY through the canonical
residual_intensity package (which itself goes through wcdrawlab.research.event_process.eval ->
wcdrawlab.research.data_roots), and writes derived artifacts under
outputs/research_runs/<run_id>/residual_goal_intensity/. Nothing here touches the active collector
checkout (worldcup_draw_model_lab_FINAL), B1, frozen M1-M5, candidate.py, approved_models.yaml, trading/
Kalshi/risk, or .env. NO network/API (no API-Football, no Odds, no download).

A job emits its LAST stdout line via emit(status, reason, state_updates). Honest `skipped` /
`data_insufficient` is allowed when an input product is genuinely absent; a false `complete` is not.
Mirrors scripts/event_process_jobs/_ep_lib.py so the same supervisor harness runs these unchanged.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
sys.path.insert(0, str(HERE))

PROC = ROOT / "data/processed/event_process_snapshots"
REF = ROOT / "data/reference"
RES_REF = REF / "residual_goal_intensity"
NOTES = ROOT / "notes/research"
ART_SUBDIR = "residual_goal_intensity"
LABELS = "research_only/experimental/not_runtime_approved/not_trade_eligible/not_live_eligible"
COLLECTOR_FORBIDDEN = "worldcup_draw_model_lab_FINAL"

# Hard backstop: this worktree must never resolve into the active collector checkout for writes.
if COLLECTOR_FORBIDDEN in str(ROOT).replace("\\", "/"):
    raise PermissionError("residual jobs must not run inside the active collector checkout")


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
        rd = str(ROOT / "outputs/research_runs" / "rg_adhoc")
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
    p = art_dir() / name
    p.write_text(json.dumps(obj, indent=2, default=str), encoding="utf-8")
    return p


def read_json(name: str) -> "dict | None":
    p = art_dir() / name
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def emit(status, reason="", state_updates=None, **extra):
    print(json.dumps({"status": status, "reason": reason,
                      "state_updates": state_updates or {}, **extra}, default=str))


# =================================================================================================
# data access (canonical loaders only) + metrics (reused from scripts/research_jobs/_common.py).
# =================================================================================================
def load_rows():
    """Load + annotate the REAL international residual-intensity panel via the canonical package.
    Raises residual_intensity.datasets.DataInsufficient (re-exported here) when the local product is
    absent so a job can emit an honest data_insufficient (never fabricates rows)."""
    from wcdrawlab.research.residual_intensity import datasets as DS
    return DS.load_residual_rows()


def load_club_rows(max_rows=4000):
    from wcdrawlab.research.residual_intensity import datasets as DS
    try:
        return DS.load_club_aux_rows(max_rows=max_rows)
    except Exception:
        return []


def metrics_mod():
    """Reused metrics + LOCO + match bootstrap (rps / logloss3 / brier_draw / calibration /
    match_bootstrap_ci) from the shared research harness. Avoids reinventing scoring."""
    sys.path.insert(0, str(ROOT / "scripts/research_jobs"))
    import _common as C  # noqa: E402
    return C


# =================================================================================================
# preregistered candidate-promotion rule (shared by RG_JOB11 calibration + RG_JOB13 ledger).
# A candidate is judged against its family W2 reference (residual: r0; horizon: h0; intensity: i0).
# Verdicts: reference_only | rejected | data_insufficient | research_candidate_for_future_shadow_review.
# Identical thresholds/semantics to the event-process bar (_ep_lib.candidate_verdict) for consistency.
# =================================================================================================
MIN_MATCHES = 30          # need enough matches to bootstrap meaningfully
MIN_TEST_ROWS = 200       # need enough test rows across folds
CAL_ECE_TOL = 0.02        # candidate calibration may not be worse than reference by > this
FOLD_MAJORITY = 0.6


def candidate_verdict(*, n_matches, n_test_rows, beats_reference_pooled, bootstrap_favors,
                      fold_win_fraction, calibration_not_worse, all_test_international,
                      xg_subset_ok=True):
    """Apply the preregistered promotion rules and return (verdict, evidence).

    ALL must hold to promote to research_candidate_for_future_shadow_review:
      1 improves the W2 reference on pooled out-of-sample RPS/Brier;
      2 favorable in a majority of folds (>= FOLD_MAJORITY);
      3 match-level paired bootstrap CI favors the candidate (upper bound < 0);
      4 calibration not degraded vs reference (ECE within tol);
      6 all test rows international (club rows never test rows);
      7 xG-bearing models use the nonzero-xG subset (only when applicable);
      8 completeness adequate (enough matches + test rows).
    Falls to data_insufficient when rule 8 fails; otherwise reference_only (honest default) or rejected.
    """
    evidence = {
        "rule1_beats_reference": bool(beats_reference_pooled),
        "rule2_fold_majority": bool(fold_win_fraction is not None and fold_win_fraction >= FOLD_MAJORITY),
        "rule3_bootstrap_favors": bool(bootstrap_favors),
        "rule4_calibration_ok": bool(calibration_not_worse),
        "rule6_all_test_intl": bool(all_test_international),
        "rule7_xg_subset_ok": bool(xg_subset_ok),
        "rule8_completeness": bool(n_matches >= MIN_MATCHES and n_test_rows >= MIN_TEST_ROWS),
        "n_matches": n_matches, "n_test_rows": n_test_rows, "fold_win_fraction": fold_win_fraction,
    }
    if not evidence["rule8_completeness"]:
        return "data_insufficient", evidence
    promote = all([evidence["rule1_beats_reference"], evidence["rule2_fold_majority"],
                   evidence["rule3_bootstrap_favors"], evidence["rule4_calibration_ok"],
                   evidence["rule6_all_test_intl"], evidence["rule7_xg_subset_ok"]])
    if promote:
        return "research_candidate_for_future_shadow_review", evidence
    if not evidence["rule1_beats_reference"]:
        return "reference_only", evidence
    return "rejected", evidence


# small scoring shims (so jobs need not re-import _common everywhere)
WDL = ["H", "D", "A"]


def logloss_wdl(p, y, eps=1e-12):
    return -math.log(max(eps, float(p.get(y, 0.0))))


def rps_wdl(p, y):
    cum_p = cum_o = s = 0.0
    for k in WDL:
        cum_p += float(p.get(k, 0.0))
        cum_o += 1.0 if k == y else 0.0
        s += (cum_p - cum_o) ** 2
    return s / (len(WDL) - 1)


def brier_draw(p, y):
    return (float(p.get("D", 0.0)) - (1.0 if y == "D" else 0.0)) ** 2
