"""Shared helpers for the 16-job DYNAMIC IN-PLAY MODELING PHASE controller queue (Component 5 / Phase 7).

research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible.

This module is the SINGLE place where the modeling jobs:
  * resolve the run directory + the ``model_phase`` artifact sub-directory (every job writes there);
  * resolve EVERY data source through the canonical data-root registry
    (``from wcdrawlab.research import data_roots as DR``) -- nothing here hard-codes a competing raw path,
    and the active collector checkout is never read;
  * assemble the LEAKAGE-SAFE evaluation rows for the dynamic model families by joining the already-built,
    already-validated derived products:
        - data/processed/model_phase/international_regulation_state.parquet   (W/D/L + team-state rows)
        - data/processed/model_phase/international_state_xg_enriched.parquet  (xG event-state subset)
        - data/processed/dynamic_player_priors/*.csv                         (player-impact diffs)
        - data/processed/dynamic_xg_state_v1.csv                             (richer dynamic xG state)
    The join keys are (api_fixture_id, snapshot_minute[, is_home]); the resulting row dicts use the EXACT
    schema the ``wcdrawlab.research.dynamic_models`` feature spaces expect (minute / remaining / score_diff /
    so_diff / subs_diff / player_count_diff / card_diff / prematch_impact_diff / onpitch_impact_diff /
    sub_impact_delta / lineup_continuity_diff / cum_xg_diff ... / target_wdl / next_goal_15 / match_id /
    competition / comp_type / kickoff_date).

NO model fitting, scaling, or calibration happens here -- that all lives inside ``dynamic_models`` /
``dynamic_eval`` and is performed INSIDE training rows only. This module only LOADS rows. If a required
product is missing it raises ``DataInsufficient`` with the concrete reason so the calling job can emit an
honest ``data_insufficient`` status (never a fake metric, never a silent stub).

Primary evaluation population = senior men's INTERNATIONAL fixtures (comp_type == "international"); club rows
are never returned as test rows here. The 2026 World Cup is never returned for fitting/selection -- the loader
filters to PRE-2026 completed competitions and ``dynamic_eval.assert_no_2026`` is the hard backstop.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
# research_jobs holds the shared metric/fold harness reused across phases.
RJ = ROOT / "scripts/research_jobs"
if str(RJ) not in sys.path:
    sys.path.insert(0, str(RJ))

from wcdrawlab.research import data_roots as DR  # noqa: E402

RUN_ID = "truth_20260626_134931"
DATASET_VERSION = "dynamic_state_v1"
MODEL_VERSION = "dynamic_models_v1"
EVAL_VERSION = "dynamic_eval_v1"
DECISION_MINUTES = [15, 30, 45, 60, 75]

# Canonical decision-minute derived products (all relative to the worktree ROOT).
PROC = ROOT / "data/processed"
MODEL_PHASE_PROC = PROC / "model_phase"
PRIORS_DIR = PROC / "dynamic_player_priors"
XG_STATE_CSV = PROC / "dynamic_xg_state_v1.csv"

IRS_PARQUET = MODEL_PHASE_PROC / "international_regulation_state.parquet"
XG_ENRICHED_PARQUET = MODEL_PHASE_PROC / "international_state_xg_enriched.parquet"
NEXTGOAL_PARQUET = MODEL_PHASE_PROC / "next_goal_target_state.parquet"
DISCIPLINE_PARQUET = MODEL_PHASE_PROC / "team_discipline_state.parquet"

# Forbidden root substring (active collector checkout). Re-asserted at import in every job.
COLLECTOR_FORBIDDEN = "worldcup_draw_model_lab_FINAL"


class DataInsufficient(Exception):
    """Raised when a required local product is absent / empty. Jobs convert this into an honest skip."""


# ----------------------------------------------------------------------------------------------------
# run-dir / model_phase artifact sub-dir
# ----------------------------------------------------------------------------------------------------
def utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def resolve_run_dir(run_dir: Optional[str]) -> Path:
    """The supervisor passes --run-dir; fall back to DEEP_RESEARCH_RUN_DIR, then the canonical run id."""
    rd = run_dir or os.environ.get("DEEP_RESEARCH_RUN_DIR")
    if rd:
        return Path(rd)
    return ROOT / "outputs/research_runs" / RUN_ID


def model_phase_dir(run_dir: Optional[str]) -> Path:
    d = resolve_run_dir(run_dir) / "model_phase"
    d.mkdir(parents=True, exist_ok=True)
    return d


def write_artifact(run_dir: Optional[str], name: str, obj) -> Path:
    """Write a JSON artifact under <run>/model_phase atomically and return its path."""
    out = model_phase_dir(run_dir) / name
    tmp = out.with_suffix(out.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, default=str), encoding="utf-8")
    os.replace(tmp, out)
    return out


def job_envelope(job_id: str, status: str, **kw) -> dict:
    """Standard per-job integrity envelope embedded in every artifact (start/end ts, versions, roots)."""
    env = {
        "job_id": job_id,
        "run_id": RUN_ID,
        "status": status,
        "dataset_version": DATASET_VERSION,
        "model_version": MODEL_VERSION,
        "eval_version": EVAL_VERSION,
        "source_roots": source_roots(),
        "no_external_api": True,
        "labels": "research_only/experimental/not_runtime_approved/not_trade_eligible/not_live_eligible",
    }
    env.update(kw)
    return env


def source_roots() -> Dict[str, str]:
    """Resolved (read-only) data roots, proving nothing points into the collector checkout."""
    out: Dict[str, str] = {}
    for name in ("api_football_corpus", "api_football_player_history",
                 "api_football_player_history_prior", "statsbomb_raw", "statsbomb_raw_prior"):
        try:
            p = DR.get_root(name)
            out[name] = str(p)
        except Exception as e:  # surface, do not hide
            out[name] = f"<unresolved: {e}>"
    return out


def assert_not_collector(*paths: Path) -> None:
    """Fail closed if any path resolves into the active collector checkout."""
    for p in paths:
        s = str(Path(p)).replace("\\", "/")
        if COLLECTOR_FORBIDDEN in s and "worktree" not in s:
            raise PermissionError(f"path resolves into the forbidden collector checkout: {p}")


# ----------------------------------------------------------------------------------------------------
# leakage-safe eval-row assembly (pandas)
# ----------------------------------------------------------------------------------------------------
_COMP_CANON = {
    "World Cup": "WC", "Euro Championship": "Euro", "Copa America": "Copa",
    "Africa Cup of Nations": "AFCON", "Asian Cup": "AsianCup",
}


def _need(p: Path, what: str):
    if not p.exists():
        raise DataInsufficient(f"{what} missing at {p} -- run the build jobs first (no stub allowed)")


def _player_impact_map() -> Dict[tuple, dict]:
    """Map (api_fixture_id:int, minute:int, is_home:bool) -> player-impact diffs from the priors products.

    Returns a per (fixture, minute) HOME-minus-AWAY diff dict with keys:
      prematch_impact_diff, prematch_impact_uncertainty, prematch_impact_coverage,
      onpitch_impact_diff, sub_impact_delta, lineup_continuity_diff.
    Built from team_composition_features.csv (per-team, per-minute) + substitution_delta_features.csv.
    Missing => the caller leaves the column absent and dynamic_models imputes on TRAIN mean + unknown flag.
    """
    import pandas as pd
    comp_path = PRIORS_DIR / "team_composition_features.csv"
    if not comp_path.exists():
        return {}
    comp = pd.read_csv(comp_path)
    # restrict to international rows (population) -- club rows never used as test rows
    if "comp_type" in comp.columns:
        comp = comp[comp["comp_type"] == "international"]
    # per (match, minute) split into home/away then diff
    by_side: Dict[tuple, dict] = {}
    for _, r in comp.iterrows():
        key = (int(r["match_id"]), int(r["minute"]), bool(r["is_home"]))
        by_side[key] = {
            "xi_weighted": float(r.get("xi_weighted_prior_gd90", 0.0) or 0.0),
            "onpitch_weighted": float(r.get("onpitch_weighted_prior_gd90", 0.0) or 0.0),
            "uncertainty": float(r.get("mean_uncertainty", 1.0) or 1.0),
            "coverage": float(r.get("coverage_aggregate", 0.0) or 0.0),
            "continuity": float(r.get("familiarity_continuity", 0.0) or 0.0),
        }
    # substitution delta: cumulative gd_delta per team up to minute t
    sub_path = PRIORS_DIR / "substitution_delta_features.csv"
    sub_cum: Dict[tuple, float] = {}
    if sub_path.exists():
        sub = pd.read_csv(sub_path)
        if "comp_type" in sub.columns:
            sub = sub[sub["comp_type"] == "international"]
        for _, r in sub.iterrows():
            try:
                fid = int(r["match_id"]); team = int(r["team_id"]); mnt = int(r["minute"])
                gd = float(r.get("gd_delta_per90", 0.0) or 0.0)
            except (TypeError, ValueError):
                continue
            for t in DECISION_MINUTES:
                if mnt <= t:
                    sub_cum[(fid, t, team)] = sub_cum.get((fid, t, team), 0.0) + gd

    out: Dict[tuple, dict] = {}
    # build a team_id lookup per (match, is_home) from the composition table
    team_of: Dict[tuple, int] = {}
    for _, r in comp.iterrows():
        team_of[(int(r["match_id"]), bool(r["is_home"]))] = int(r["team_id"])
    fixtures = sorted({k[0] for k in by_side})
    for fid in fixtures:
        for t in DECISION_MINUTES:
            h = by_side.get((fid, t, True)); a = by_side.get((fid, t, False))
            if h is None or a is None:
                continue
            th = team_of.get((fid, True)); ta = team_of.get((fid, False))
            sub_h = sub_cum.get((fid, t, th), 0.0) if th is not None else 0.0
            sub_a = sub_cum.get((fid, t, ta), 0.0) if ta is not None else 0.0
            out[(fid, t)] = {
                "prematch_impact_diff": h["xi_weighted"] - a["xi_weighted"],
                "prematch_impact_uncertainty": (h["uncertainty"] + a["uncertainty"]) / 2.0,
                "prematch_impact_coverage": (h["coverage"] + a["coverage"]) / 2.0,
                "onpitch_impact_diff": h["onpitch_weighted"] - a["onpitch_weighted"],
                "sub_impact_delta": sub_h - sub_a,
                "lineup_continuity_diff": h["continuity"] - a["continuity"],
            }
    return out


def _xg_state_map() -> Dict[tuple, dict]:
    """Map (api_fixture_id:int, minute:int) -> richer dynamic xG state columns (xG-eligible rows only)."""
    import pandas as pd
    if not XG_STATE_CSV.exists():
        return {}
    df = pd.read_csv(XG_STATE_CSV)
    if "xg_eligible" in df.columns:
        df = df[df["xg_eligible"] == 1]
    cols = ["cum_xg_diff", "roll5_xg_diff", "roll10_xg_diff", "xg_momentum", "shot_count_diff",
            "shot_on_target_diff", "time_since_last_shot", "time_since_last_major_chance"]
    out: Dict[tuple, dict] = {}
    for _, r in df.iterrows():
        try:
            key = (int(r["api_fixture_id"]), int(r["snapshot_minute"]))
        except (TypeError, ValueError):
            continue
        out[key] = {c: float(r[c]) for c in cols if c in df.columns and pd.notna(r[c])}
        out[key]["xg_eligible"] = 1
    return out


def _base_rows_from_parquet(parquet: Path, with_xg: bool) -> List[dict]:
    import pandas as pd
    _need(parquet, "international state parquet")
    df = pd.read_parquet(parquet)
    df = df[df["snapshot_minute"].isin(DECISION_MINUTES)]
    df = df[df["comp_type"] == "international"]
    if "reconciliation_status" in df.columns:
        df = df[df["reconciliation_status"] == "exact"]
    rows: List[dict] = []
    for _, r in df.iterrows():
        kd = str(r.get("kickoff_date", ""))
        comp_label = str(r.get("competition", ""))
        # PRE-2026 only for fit/selection; 2026 WC is never a fitting/selection row.
        is_2026_wc = kd.startswith("2026") and ("World Cup" in comp_label)
        if is_2026_wc:
            continue
        yh = int(r.get("yellow_home", 0) or 0); ya = int(r.get("yellow_away", 0) or 0)
        row = {
            "match_id": str(r["api_fixture_id"]),
            "api_fixture_id": int(r["api_fixture_id"]),
            "competition": _COMP_CANON.get(comp_label, comp_label),
            "competition_label": comp_label,
            "comp_type": "international",
            "kickoff_date": kd,
            "minute": int(r["snapshot_minute"]),
            "remaining": int(r.get("remaining_minutes", 90 - int(r["snapshot_minute"]))),
            "score_diff": int(r.get("score_diff", 0) or 0),
            "card_diff": yh - ya,
            "so_diff": int(r.get("red_diff", 0) or 0),
            "subs_diff": int(r.get("subs_diff", 0) or 0),
            "player_count_diff": int(r.get("player_count_diff", 0) or 0),
            "n_starters_home": int(r.get("n_starters_home", 0) or 0),
            "target_wdl": str(r["target_wdl"]),
            "next_goal_15": int(r.get("next_goal_15", 0) or 0),
        }
        if with_xg:
            for c in ("cum_xg_diff", "roll5_xg_diff", "roll10_xg_diff", "xg_momentum", "shot_count_diff",
                      "shot_on_target_diff", "time_since_last_shot", "time_since_last_major_chance"):
                v = r.get(c)
                if v is not None and pd.notna(v):
                    row[c] = float(v)
            xe = r.get("xg_eligible")
            row["xg_eligible"] = int(xe) if (xe is not None and pd.notna(xe)) else 0
        rows.append(row)
    return rows


def load_wdl_rows() -> List[dict]:
    """Primary W/D/L eval rows (international, pre-2026, decision minutes) with player-impact diffs joined."""
    rows = _base_rows_from_parquet(IRS_PARQUET, with_xg=False)
    if not rows:
        raise DataInsufficient("no pre-2026 international decision-minute rows in IRS parquet")
    impact = _player_impact_map()
    for r in rows:
        ev = impact.get((r["api_fixture_id"], r["minute"]))
        if ev:
            r.update(ev)
    return rows


def load_xg_rows() -> List[dict]:
    """xG-family eval rows = the exact-bridge xG-ELIGIBLE subset (nonzero xG snapshots) with player-impact."""
    rows = _base_rows_from_parquet(XG_ENRICHED_PARQUET, with_xg=True)
    rows = [r for r in rows if r.get("xg_eligible") == 1]
    if not rows:
        raise DataInsufficient("no xG-eligible international rows (exact StatsBomb bridge) available")
    impact = _player_impact_map()
    xg = _xg_state_map()
    for r in rows:
        ev = impact.get((r["api_fixture_id"], r["minute"]))
        if ev:
            r.update(ev)
        xs = xg.get((r["api_fixture_id"], r["minute"]))
        if xs:
            r.update(xs)
    return rows


def load_nextgoal_rows() -> List[dict]:
    """Next-goal rows reuse the W/D/L international rows (they carry next_goal_15 + on-pitch impact)."""
    return load_wdl_rows()


def load_discipline_rows() -> List[dict]:
    """Discipline rows: per (fixture, minute) sending-off occurrence within the next window as the target.

    Built from team_discipline_state.parquet (international decision minutes). The positive target is whether
    a NEW sending-off (red or second-yellow) appears for either side between t and t+15 -- derived causally
    from the cumulative red counts across consecutive decision minutes of the SAME match.
    """
    import pandas as pd
    _need(DISCIPLINE_PARQUET, "team_discipline_state parquet")
    irs_rows = load_wdl_rows()
    irs_idx = {(r["api_fixture_id"], r["minute"]): r for r in irs_rows}
    d = pd.read_parquet(DISCIPLINE_PARQUET)
    d = d[(d["snapshot_minute"].isin(DECISION_MINUTES)) & (d["comp_type"] == "international")]
    # cumulative total reds per (fixture, minute)
    red_tot: Dict[tuple, int] = {}
    for _, r in d.iterrows():
        fid = int(r["api_fixture_id"]); mnt = int(r["snapshot_minute"])
        red_tot[(fid, mnt)] = int(r.get("red_home", 0) or 0) + int(r.get("red_away", 0) or 0) \
            + int(r.get("second_yellow_home", 0) or 0) + int(r.get("second_yellow_away", 0) or 0)
    rows: List[dict] = []
    for (fid, t), base in irs_idx.items():
        nxt = t + 15
        cur = red_tot.get((fid, t))
        fut = red_tot.get((fid, nxt))
        if cur is None or fut is None:
            # no later decision minute (e.g. t=75 -> 90 not in grid) -> skip honestly (no fabricated target)
            continue
        ev = 1 if fut > cur else 0
        row = dict(base)
        row["discipline_event"] = ev
        # team-card-rate priors (causal, from cumulative yellow/red state at t; no future leak)
        row["team_card_rate_prior"] = float(base.get("card_diff", 0))
        row["opp_card_rate_prior"] = float(-base.get("card_diff", 0))
        rows.append(row)
    if not rows:
        raise DataInsufficient("no discipline rows with a valid t->t+15 transition on the decision grid")
    return rows


def coverage_counts(rows: Sequence[dict]) -> dict:
    comps: Dict[str, int] = {}
    matches = set()
    for r in rows:
        comps[r["competition"]] = comps.get(r["competition"], 0) + 1
        matches.add(r["match_id"])
    return {"n_rows": len(rows), "n_matches": len(matches), "by_competition": comps}
