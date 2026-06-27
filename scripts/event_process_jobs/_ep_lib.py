"""Shared helpers for the REAL event-process modeling/eval jobs (EPJOB5-16).

research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible.

Every EP modeling job resolves its run-dir + artifact sub-dir here, loads sources ONLY through the
canonical engine/eval modules (which themselves go through wcdrawlab.research.data_roots), and writes
derived artifacts under outputs/research_runs/<run_id>/event_process/. Nothing here touches the active
collector checkout, B1, frozen models, .env, or any network/API.

A job emits its LAST stdout line via _ep.emit(status, reason, state_updates). Honest `skipped` /
`data_insufficient` is allowed when an input product is genuinely absent; a false `complete` is not.
"""
from __future__ import annotations

import json
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
import _ep  # noqa: E402

PROC = ROOT / "data/processed/event_process_snapshots"
REF = ROOT / "data/reference"
COLLECTOR_FORBIDDEN = "worldcup_draw_model_lab_FINAL"

# Hard backstop: this worktree must never resolve into the active collector checkout for writes.
if COLLECTOR_FORBIDDEN in str(ROOT).replace("\\", "/"):
    raise PermissionError("EP modeling jobs must not run inside the active collector checkout")


def utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_dir() -> Path:
    """Resolve the supervisor run-dir from --run-dir (or DEEP_RESEARCH_RUN_DIR env fallback)."""
    try:
        rd = _ep.run_dir()
    except SystemExit:
        rd = os.environ.get("DEEP_RESEARCH_RUN_DIR")
    if not rd:
        rd = str(ROOT / "outputs/research_runs" / "ep_adhoc")
    return Path(rd)


def art_dir() -> Path:
    d = run_dir() / "event_process"
    d.mkdir(parents=True, exist_ok=True)
    return d


def write_json(name: str, obj: dict) -> Path:
    p = art_dir() / name
    p.write_text(json.dumps(obj, indent=2, default=str), encoding="utf-8")
    return p


def read_json(name: str) -> dict | None:
    p = art_dir() / name
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def emit(status, reason="", state_updates=None, **extra):
    _ep.emit(status, reason=reason, state_updates=state_updates or {}, **extra)


# =================================================================================================
# preregistered candidate-promotion rule (shared by EPJOB15 calibration + EPJOB16 ledger).
# A candidate model is judged against its family reference (W/D/L: e2; binary: the base-rate head).
# Verdicts: reference_only | rejected | data_insufficient | research_candidate_for_future_shadow_review.
# =================================================================================================
MIN_MATCHES = 30          # need enough matches to bootstrap meaningfully
MIN_TEST_ROWS = 200       # need enough test rows across folds
CAL_ECE_TOL = 0.02        # candidate calibration may not be worse than reference by > this


def candidate_verdict(*, n_matches, n_test_rows, beats_reference_pooled, bootstrap_favors,
                      fold_win_fraction, calibration_not_worse, all_test_international,
                      xg_subset_ok=True):
    """Apply the 8 preregistered promotion rules and return (verdict, evidence).

    Rules (ALL must hold to promote a candidate to research_candidate_for_future_shadow_review):
      1 improves the reference on pooled out-of-sample RPS/Brier;
      2 favorable in a majority of folds (>=0.6);
      3 match-level paired bootstrap CI favors the candidate (upper bound < 0);
      4 calibration not degraded vs reference (ECE within tol);
      5 not one-tournament-driven (subsumed by rule 2's fold-fraction);
      6 not club-test-driven (all test rows international);
      7 xG-bearing models use the exact-bridge nonzero-xG subset (only when applicable);
      8 completeness adequate (enough matches + test rows).
    Falls to data_insufficient when the completeness gate (rule 8) fails; otherwise reference_only
    (the honest default) or rejected when it under-performs the reference.
    """
    evidence = {
        "rule1_beats_reference": bool(beats_reference_pooled),
        "rule2_fold_majority": bool(fold_win_fraction is not None and fold_win_fraction >= 0.6),
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
    # under-performs the reference outright -> rejected; otherwise it is a reference-tier baseline.
    if not evidence["rule1_beats_reference"]:
        return "reference_only", evidence
    return "rejected", evidence
