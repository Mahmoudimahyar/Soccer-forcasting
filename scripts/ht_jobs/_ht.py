"""Shared harness for the 14-job HIERARCHICAL CROSS-DOMAIN TRANSFER controller (HT_JOB01..HT_JOB14).

research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible.

Every HT job resolves the supervisor run-dir + the canonical ``hierarchical_transfer`` artifact sub-dir
here, imports the canonical transfer plane
(``wcdrawlab.research.transfer.{w2_reference_t0, domain_normalized_dataset}``) and the fail-closed
data-root resolver (``wcdrawlab.research.data_roots``), reuses the shared metric/bootstrap harness
(``scripts/research_jobs/_common.py``: rps / logloss3 / match_bootstrap_ci), and either:

  * performs REAL transfer work (load the materialised domain-normalized dataset, fit the T0..T7 ladder
    in-train, evaluate forward-chain / LOCO, calibrate, bootstrap), OR
  * invokes an EXISTING REAL builder/audit script as a read-only subprocess and parses its LAST JSON
    stdout line (dataset build / dataset audit).

Hard guarantees enforced here (defence in depth; also covered by the test suite):
  * ISOLATION -- this worktree must NEVER be the active collector checkout, and no resolved data root may
    live under worldcup_draw_model_lab_FINAL (data_roots fails closed on it).
  * NO FORBIDDEN SOURCE -- no HT job may import a network/provider/scrape/odds/credential token at module
    scope. The whole transfer plane is OFFLINE: it reads ONLY verified local products (the international
    event lake objects, the club auxiliary manifest, and the already-materialised transfer dataset CSV).
  * NO FABRICATION -- a count/metric that is not derivable from a present local product is emitted as an
    honest ``data_insufficient`` / ``skipped`` with a concrete reason. A false ``complete`` is NEVER
    emitted.
  * LEAKAGE -- the international-only population is the PRIMARY test population; club rows are auxiliary
    training only (never an international test row); every fit happens on TRAIN rows of a fold only; no
    completed-2026-World-Cup match enters any fold.

Supervisor contract (scripts/deep_research_supervisor.py): each job is invoked as
``python <script> --run-dir <dir>`` and the supervisor reads the LAST stdout JSON line emitted via
``emit(status, reason, state_updates, api_requests=...)``. Status in
{complete, skipped, failed, blocked, data_insufficient}.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]               # the worktree (scripts/ht_jobs/_ht.py -> parents[1])
SRC = ROOT / "src"
RJ = ROOT / "scripts/research_jobs"   # shared metric/bootstrap harness
for p in (str(SRC), str(RJ), str(HERE)):
    if p not in sys.path:
        sys.path.insert(0, p)

REF = ROOT / "data/reference"
PROC = ROOT / "data/processed"
NOTES = ROOT / "notes/research"
SCRIPTS = ROOT / "scripts"
ART_SUBDIR = "hierarchical_transfer"
LABELS = "research_only/experimental/not_runtime_approved/not_trade_eligible/not_live_eligible"
COLLECTOR_FORBIDDEN = "worldcup_draw_model_lab_FINAL"
EXPECTED_COLLECTOR_COMMIT = "dc73318"

DATASET_CSV = PROC / "domain_normalized_transfer/transfer_dataset_v1.csv"
BUILD_MANIFEST = PROC / "domain_normalized_transfer/build_manifest.json"

# Tokens that, if imported at module scope by any HT job, indicate a FORBIDDEN live/network/scrape path.
# The ENTIRE transfer plane is offline; NO HT job is permitted any of these.
FORBIDDEN_IMPORT_TOKENS = (
    "httpx", "aiohttp", "requests", "urllib.request", "websocket", "selenium", "playwright",
    "wcdrawlab.providers", "odds_api", "api_football_adapter", "fetch_odds", "live_2026",
    "api_football", "oddsapi", "the_odds_api", "statsbombpy", "kalshi", "dotenv",
)

# Hard backstop: an HT job must never run inside the active collector checkout.
if COLLECTOR_FORBIDDEN in str(ROOT).replace("\\", "/"):
    raise PermissionError("hierarchical-transfer jobs must not run inside the active collector checkout")


# --------------------------------------------------------------------------------------------------
# time / run-dir / artifacts
# --------------------------------------------------------------------------------------------------
def utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _argv_run_dir() -> Optional[str]:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=False, default=None)
    a, _ = ap.parse_known_args()
    return a.run_dir


def run_dir() -> Path:
    rd = _argv_run_dir() or os.environ.get("DEEP_RESEARCH_RUN_DIR")
    if not rd:
        rd = str(ROOT / "outputs/research_runs" / "ht_adhoc")
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
    """Write a derived artifact to the run-dir hierarchical_transfer/ sub-dir (atomic)."""
    p = art_dir() / name
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, default=str), encoding="utf-8")
    os.replace(tmp, p)
    return p


def write_text(name: str, text: str) -> Path:
    p = art_dir() / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
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
        return hashlib.sha256(Path(p).read_bytes()).hexdigest()
    except Exception:
        return None


def envelope(job_id: str, status: str, **kw) -> dict:
    """Standard per-job integrity envelope embedded in every artifact (versions, roots, labels)."""
    env = {
        "job_id": job_id,
        "run_id": run_dir().name,
        "status": status,
        "ts": utc(),
        "package_version": "hierarchical_transfer_v1",
        "reference_model": "research.transfer.w2_reference_t0",
        "source_roots": source_roots(),
        "no_external_api": True,
        "labels": LABELS,
    }
    env.update(kw)
    return env


# --------------------------------------------------------------------------------------------------
# canonical engines (proves wiring + isolation when imported)
# --------------------------------------------------------------------------------------------------
def data_roots():
    from wcdrawlab.research import data_roots as DR
    return DR


def t0_reference():
    from wcdrawlab.research.transfer import w2_reference_t0 as T0
    return T0


def dnd():
    from wcdrawlab.research.transfer import domain_normalized_dataset as DND
    return DND


def transfer_ids():
    from wcdrawlab.research import transfer as T
    return T


def common():
    """The shared metric/bootstrap harness (rps / logloss3 / match_bootstrap_ci / calibration)."""
    import _common as C  # scripts/research_jobs/_common.py (on sys.path)
    return C


def source_roots() -> Dict[str, str]:
    """Resolved (read-only) data roots, proving nothing points into the collector checkout."""
    out: Dict[str, str] = {}
    try:
        DR = data_roots()
        for name in DR._load()["roots"]:
            try:
                out[name] = str(DR.get_root(name))
            except Exception as e:  # surface, do not hide
                out[name] = f"<unresolved: {e}>"
    except Exception as e:
        out["<error>"] = str(e)
    return out


# --------------------------------------------------------------------------------------------------
# isolation primitives (reused by JOB01 preflight + JOB09 audit + JOB14 final audit + the watchdog)
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


def scan_forbidden_imports() -> list:
    """Scan every ht_job*.py for a forbidden network/provider/scrape import token at module scope."""
    hits = []
    for f in sorted(HERE.glob("ht_job*.py")):
        for ln in f.read_text(encoding="utf-8").splitlines():
            s = ln.strip()
            if not (s.startswith("import ") or s.startswith("from ")):
                continue
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
                if COLLECTOR_FORBIDDEN in rp and "worktree" not in rp:
                    bad.append(name)
            except PermissionError:
                bad.append(name)  # the fail-closed resolver tripped -> would be in collector
            except Exception:
                pass
    except Exception:
        pass
    return bad


def isolation_report() -> dict:
    """One-shot isolation snapshot used by preflight / audit / report jobs."""
    cc = collector_commit()
    return {
        "worktree": str(ROOT),
        "in_collector_checkout": COLLECTOR_FORBIDDEN in str(ROOT).replace("\\", "/"),
        "collector_commit": cc,
        "collector_commit_unchanged": (cc == EXPECTED_COLLECTOR_COMMIT) if cc else None,
        "raw_git_tracked": raw_git_tracked() or "(none)",
        "forbidden_imports": scan_forbidden_imports(),
        "roots_in_collector": roots_resolving_into_collector(),
    }


# --------------------------------------------------------------------------------------------------
# run an existing REAL builder/audit script (read-only) and parse its LAST JSON stdout line
# --------------------------------------------------------------------------------------------------
def run_builder(rel_script: str, args: "list[str] | None" = None, timeout: int = 36000) -> dict:
    """Invoke an existing REAL builder/audit script as a subprocess and parse its LAST JSON stdout line.

    Never fabricates a result: if the builder cannot run, the real returncode + stderr tail are surfaced.
    The offline/no-network policy is owned by the engine inside each builder.
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
            "stdout_tail": (p.stdout or "")[-800:], "stderr_tail": (p.stderr or "")[-800:]}


# ==================================================================================================
# TRANSFER DATASET LOADER -- read the already-materialised, leakage-safe domain-normalized dataset.
# Returns per-fold row dicts grouped by row_role. Never fabricates rows: if the CSV/manifest is absent
# it raises DataInsufficient so the caller can emit an honest skip.
# ==================================================================================================
class DataInsufficient(Exception):
    pass


# numeric snapshot-state columns the T1..T6 residual models may use (domain-comparable + leakage-safe).
# These are EXACTLY the derived causal state columns + the kept stable-feature subset (feat_*). Targets,
# residuals, baselines, provenance and the T0 reference probs are NEVER features.
STATE_DESIGN_COLS: List[str] = [
    "state_score_diff_signed", "state_remaining_fraction", "state_minute_fraction",
    "state_players_diff", "state_is_second_half",
]
# the feat_* columns are discovered per dataset (the kept stable-feature subset) at load time.

# columns that must NEVER enter a model design matrix (leakage / provenance / targets)
NEVER_FEATURE_COLS = {
    "transfer_residual_home", "transfer_residual_away", "transfer_residual_total",
    "rem_goals_home", "rem_goals_away", "target_wdl",
    "domain_baseline_home", "domain_baseline_away", "domain_baseline_total",
    "t0_prob_H", "t0_prob_D", "t0_prob_A",
    "source_sha256", "engine_version", "n_events_observed",
}


def _fnum(v) -> Optional[float]:
    if v is None:
        return None
    if isinstance(v, str):
        s = v.strip()
        if s == "" or s.lower() in ("none", "nan", "null"):
            return None
        try:
            return float(s)
        except ValueError:
            return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def dataset_present() -> bool:
    return DATASET_CSV.exists() and DATASET_CSV.stat().st_size > 0


def load_dataset_rows(limit: Optional[int] = None) -> List[dict]:
    """Load the materialised transfer dataset CSV into row dicts. Raises DataInsufficient if absent."""
    if not dataset_present():
        raise DataInsufficient(
            f"materialised transfer dataset missing/empty at {DATASET_CSV} -- run "
            "scripts/build_domain_normalized_transfer_dataset.py first (no stub allowed)")
    rows: List[dict] = []
    with DATASET_CSV.open("r", encoding="utf-8", newline="") as f:
        rd = csv.DictReader(f)
        for i, r in enumerate(rd):
            rows.append(r)
            if limit is not None and (i + 1) >= limit:
                break
    if not rows:
        raise DataInsufficient("transfer dataset CSV present but contained no data rows")
    return rows


def discover_feat_cols(rows: Sequence[dict]) -> List[str]:
    """The kept stable-feature columns present in the dataset (feat_*), in header order."""
    if not rows:
        return []
    return [c for c in rows[0].keys()
            if c.startswith("feat_") and c not in NEVER_FEATURE_COLS]


def fold_names(rows: Sequence[dict]) -> List[str]:
    return sorted({r.get("fold_held_tournament") for r in rows if r.get("fold_held_tournament")})


def split_fold(rows: Sequence[dict], fold: str) -> Dict[str, List[dict]]:
    """Partition a fold's rows by row_role: intl_train / club_train / intl_test."""
    sub = [r for r in rows if r.get("fold_held_tournament") == fold]
    out = {"intl_train": [], "club_train": [], "intl_test": []}
    for r in sub:
        role = r.get("row_role")
        if role in out:
            out[role].append(r)
    return out


def design_matrix(rows: Sequence[dict], feat_cols: Sequence[str],
                  train_means: Optional[Dict[str, float]] = None
                  ) -> Tuple[List[List[float]], List[str], Dict[str, float]]:
    """Build a numeric design matrix over STATE_DESIGN_COLS + feat_cols, imputing missing cells with the
    TRAIN mean (computed here if ``train_means`` is None -> use this only on the TRAIN rows). Returns
    (X, col_names, train_means). Missingness is preserved as an explicit *_isna indicator column."""
    cols = list(STATE_DESIGN_COLS) + list(feat_cols)
    if train_means is None:
        train_means = {}
        for c in cols:
            vals = [_fnum(r.get(c)) for r in rows]
            vals = [v for v in vals if v is not None]
            train_means[c] = (sum(vals) / len(vals)) if vals else 0.0
    X: List[List[float]] = []
    col_names = []
    for c in cols:
        col_names.append(c)
        col_names.append(c + "_isna")
    for r in rows:
        row_vec: List[float] = []
        for c in cols:
            v = _fnum(r.get(c))
            if v is None:
                row_vec.append(train_means.get(c, 0.0))
                row_vec.append(1.0)
            else:
                row_vec.append(v)
                row_vec.append(0.0)
        X.append(row_vec)
    return X, col_names, train_means


def residual_target(rows: Sequence[dict], side: str = "total") -> List[Optional[float]]:
    key = {"total": "transfer_residual_total", "home": "transfer_residual_home",
           "away": "transfer_residual_away"}[side]
    return [_fnum(r.get(key)) for r in rows]


def wdl_target(rows: Sequence[dict]) -> List[str]:
    return [str(r.get("target_wdl") or "") for r in rows]


def t0_wdl_probs(rows: Sequence[dict]) -> List[Dict[str, float]]:
    out = []
    for r in rows:
        out.append({"H": _fnum(r.get("t0_prob_H")) or 0.0,
                    "D": _fnum(r.get("t0_prob_D")) or 0.0,
                    "A": _fnum(r.get("t0_prob_A")) or 0.0})
    return out


def match_ids(rows: Sequence[dict]) -> List[str]:
    return [str(r.get("match_id") or r.get("source_match_id") or "") for r in rows]


def assert_no_2026_rows(rows: Sequence[dict]) -> int:
    """Re-assert (defence in depth) that no completed-2026-World-Cup row is present. Returns violation count."""
    bad = 0
    for r in rows:
        lab = (r.get("competition_label") or "").lower()
        ko = (r.get("kickoff_date") or "")
        if "2026" in lab and ("world cup" in lab or "fifa" in lab):
            bad += 1
        elif ko.startswith("2026") and "world cup" in lab:
            bad += 1
    return bad


# ==================================================================================================
# FITTED-LADDER reload + scoring (shared by JOB07 forward-chain / JOB08 LOCO / JOB10 ablations /
# JOB11 calibration). Reconstructs FittedTransferModel objects from the JOB06 store and scores held-out
# international test rows on the W/D/L angle, expressed RELATIVE to T0.
# ==================================================================================================
def load_fitted_store() -> "dict | None":
    p = art_dir() / "fitted_ladder.json"
    return _read_json(p)


def _model_from_dict(d: dict):
    from wcdrawlab.research.transfer.hierarchical_models import FittedTransferModel
    cal = d.get("calibration")
    cal = tuple(cal) if cal else None
    notes = dict(d.get("notes") or {})
    if d.get("train_means") is not None:
        notes["train_means"] = d["train_means"]
    return FittedTransferModel(
        model_id=d["model_id"], coef=list(d.get("coef") or []),
        intercept=float(d.get("intercept") or 0.0),
        feature_names=list(d.get("feature_names") or []),
        domain_intercepts=dict(d.get("domain_intercepts") or {}),
        alpha=float(d.get("alpha") or 1.0), n_train=int(d.get("n_train") or 0),
        notes=notes, calibration=cal)


def score_model_on_rows(model_dict: dict, test_rows: Sequence[dict], feat_cols: Sequence[str],
                        model_id: str) -> dict:
    """Score a fitted model's W/D/L predictions on held-out test rows vs T0. Returns mean RPS / logloss3 /
    draw-Brier + per-match RPS lists (for the match-level bootstrap) for both the model and T0."""
    from wcdrawlab.research.transfer import hierarchical_models as HM
    C = common()
    m = _model_from_dict(model_dict)
    tm = (model_dict.get("train_means") or None)
    X, _names, _tm = HM.build_design(test_rows, feat_cols, train_means=tm)
    domains = [str(r.get("domain") or "international") for r in test_rows]
    if model_id == "research.transfer.calibrated_transfer_simulation_t7":
        res = m.predict_residual(X, domains)
        probs = HM.mc_simulate_wdl(test_rows, res)
    elif not m.coef:
        probs = HM.reference_wdl_rows(test_rows)
        res = [0.0] * len(test_rows)
    else:
        res = m.predict_residual(X, domains)
        probs = HM.predict_wdl_rows(test_rows, res)
    t0_probs = HM.reference_wdl_rows(test_rows)
    tgt = wdl_target(test_rows)
    mids = match_ids(test_rows)
    # per-row metrics
    per_match_rps: Dict[str, List[float]] = {}
    per_match_rps_t0: Dict[str, List[float]] = {}
    rps_sum = ll_sum = brier_sum = 0.0
    rps_sum_t0 = ll_sum_t0 = brier_sum_t0 = 0.0
    n = 0
    for p, p0, t, mid in zip(probs, t0_probs, tgt, mids):
        if t not in ("H", "D", "A"):
            continue
        n += 1
        rps_sum += C.rps(p, t); ll_sum += C.logloss3(p, t); brier_sum += C.brier_draw(p, t)
        rps_sum_t0 += C.rps(p0, t); ll_sum_t0 += C.logloss3(p0, t); brier_sum_t0 += C.brier_draw(p0, t)
        per_match_rps.setdefault(mid, []).append(C.rps(p, t))
        per_match_rps_t0.setdefault(mid, []).append(C.rps(p0, t))
    if n == 0:
        return {"model_id": model_id, "n": 0, "status": "no_labeled_rows"}
    pm = [sum(v) / len(v) for v in per_match_rps.values()]
    pm0 = [sum(v) / len(v) for v in per_match_rps_t0.values()]
    return {
        "model_id": model_id, "n": n, "n_matches": len(per_match_rps),
        "rps": round(rps_sum / n, 6), "logloss3": round(ll_sum / n, 6),
        "draw_brier": round(brier_sum / n, 6),
        "rps_t0": round(rps_sum_t0 / n, 6), "logloss3_t0": round(ll_sum_t0 / n, 6),
        "draw_brier_t0": round(brier_sum_t0 / n, 6),
        "rps_delta_vs_t0": round((rps_sum - rps_sum_t0) / n, 6),
        "logloss3_delta_vs_t0": round((ll_sum - ll_sum_t0) / n, 6),
        "per_match_rps": pm, "per_match_rps_t0": pm0,
    }


# --------------------------------------------------------------------------------------------------
# emit (supervisor contract)
# --------------------------------------------------------------------------------------------------
def emit(status, reason="", state_updates=None, api_requests=0, **extra):
    print(json.dumps({"status": status, "reason": reason, "api_requests": int(api_requests or 0),
                      "state_updates": state_updates or {}, **extra}, default=str))
