"""Residual goal-intensity DATASET + horizon targets builder (Phase 1).

research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible.

Builds, by REUSING the already-materialised international event-process snapshots
(data/processed/event_process_snapshots/), the residual goal-intensity plane:

  (1) residual_goal_intensity_snapshots.csv  -- per-snapshot INPUT plane:
        leakage-safe event-process state at cutoff t
        + W2 REFERENCE remaining home/away/total goal INTENSITIES
        + W2 final H/D/A probs (r2_remaining_time_poisson)
        + W2-implied near-term scoring/competing-risk probs (5/10/15m, right-censored)
        + source completeness / xG-complete flags + pre-match anchor + source hash
  (2) near_term_competing_risk_targets.csv   -- LABELS:
        (A) remaining home/away/total goals after cutoff (regulation only)
        (B) competing-risk next 5/10/15m: home_goal / away_goal / no_goal (right-censored)
  (3) selective_dynamic_correction.csv       -- RESIDUALS (observed - W2) + causal REGIME labels

The W2 reference is the remaining-time Poisson reference reimplemented in
wcdrawlab.research.dynamic_models (r2_remaining_time_poisson, R2_BASE = 1.35 goals/team/90').
It is a REFERENCE INTENSITY (home & away remaining-goal rates), NOT a competing classifier.

LEAKAGE / ISOLATION RULES (enforced + tested):
  * Every snapshot feature is taken VERBATIM from the leakage-safe event-process snapshot (events <= t).
  * The W2 reference is a parameter-free closed form of (score_diff, remaining) ONLY.
  * Targets/residuals live in SEPARATE tables and are never an input feature.
  * remaining_* goals = regulation-final MINUS goals-at-cutoff; finals are labels only.
  * Competing-risk windows are right-censored at the regulation boundary (h_eff = min(h, 90 - t)).
  * Extra-time and shootout goals never count; regulation only (already enforced upstream).
  * Club rows are NEVER emitted (only comp_type == 'international').
  * Missing source fields are FLAGGED (xg_complete / source_quality_*), never imputed as 0.
  * No completed-2026-World-Cup match participates (corpus is 2018/2020/2022/2024 only).
  * The active collector checkout is NEVER read (data_roots fails closed on it).
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from wcdrawlab.research import dynamic_models as DM  # noqa: E402  (W2 reference lives here)

RESIDUAL_BUILDER_VERSION = "residual_goal_intensity_builder_v1"
SCHEMA_VERSION = "residual_goal_intensity_snapshot_v1"
HORIZONS = (5, 10, 15)
REGULATION_MINUTE = 90.0
W2_BASE = DM.R2_BASE  # 1.35 goals/team/90' (parameter-free remaining-time Poisson reference)

SNAP_DIR = ROOT / "data/processed/event_process_snapshots"
OUT_DIR = ROOT / "data/processed/residual_goal_intensity"

# fixed-form, corpus-free regime thresholds (documented in the data card; never tuned to any test set)
RECENT_PRESSURE_XG10 = 0.30      # xG accumulated in last 10m (both sides) above this => 'high' pressure regime
RECENT_TRANSITION_BURST = 4      # recoveries+turnovers (both sides) in last window above this => 'high' transition
SPARSE_EVENTS = 200              # n_events_observed below this at/after 60' => 'sparse' completeness bucket


# =================================================================================================
# small numeric helpers (no leakage; pure functions of cutoff state)
# =================================================================================================
def _f(row: dict, key: str, default=None):
    v = row.get(key, "")
    if v is None or v == "":
        return default
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _i(row: dict, key: str, default=None):
    v = _f(row, key, None)
    return int(round(v)) if v is not None else default


def w2_remaining_intensity(remaining_min: float) -> float:
    """W2 reference expected remaining goals for ONE side over `remaining_min` regulation minutes.
    Parameter-free: R2_BASE * remaining/90. Symmetric across home/away (the reference has no team prior)."""
    return W2_BASE * max(0.0, remaining_min) / 90.0


def w2_window_score_prob(horizon_eff: float) -> float:
    """W2-implied P(a given side scores >=1 goal) within an effective window of `horizon_eff` minutes."""
    lam = W2_BASE * max(0.0, horizon_eff) / 90.0
    return 1.0 - math.exp(-lam)


def w2_window_any_goal_prob(horizon_eff: float) -> float:
    """W2-implied P(any goal by either side) within `horizon_eff` minutes (two independent Poisson sides)."""
    lam = W2_BASE * max(0.0, horizon_eff) / 90.0
    return 1.0 - math.exp(-2.0 * lam)


def w2_window_first_side_prob(horizon_eff: float) -> float:
    """W2-implied P(home scores first | someone scores) == 0.5 by symmetry; the unconditional
    P(home is the first scorer in the window) = 0.5 * P(any goal)."""
    return 0.5 * w2_window_any_goal_prob(horizon_eff)


# =================================================================================================
# load the upstream materialised tables (reuse — do not recompute snapshots)
# =================================================================================================
def _read_csv(path: Path):
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_upstream():
    snaps = _read_csv(SNAP_DIR / "intl_event_process_snapshots.csv")
    if snaps is None:
        return None, "missing intl_event_process_snapshots.csv (run build_event_process_snapshots.py first)"
    ng = _read_csv(SNAP_DIR / "intl_targets_next_goal.csv") or []
    sc = _read_csv(SNAP_DIR / "intl_targets_scoring_horizon.csv") or []
    wdl = _read_csv(SNAP_DIR / "intl_targets_wdl.csv") or []
    cq = _read_csv(SNAP_DIR / "competition_source_quality.csv") or []
    intl = [r for r in snaps if (r.get("comp_type") or "").strip() == "international"]
    if not intl:
        return None, "no international snapshot rows present"
    ng_idx = {(r["source_match_id"], r["snapshot_minute"]): r for r in ng}
    sc_idx = {(r["source_match_id"], r["snapshot_minute"]): r for r in sc}
    wdl_idx = {r["source_match_id"]: r for r in wdl}
    # per-competition dominant source-quality flags (for completeness regime + per-row flag fallback)
    cq_idx: dict[tuple, str] = {}
    for r in cq:
        cq_idx[(r.get("competition_label"), r.get("capability"))] = r.get("dominant_quality")
    return {
        "snaps": intl, "ng": ng_idx, "sc": sc_idx, "wdl": wdl_idx, "cq": cq_idx,
    }, None


# =================================================================================================
# competing-risk near-term labels (from the upstream scoring-horizon + next-goal targets)
# =================================================================================================
def competing_risk_for_horizon(snap, sc_row, ng_row, h: int):
    """Build the right-censored competing-risk block for one horizon h from the upstream targets.

    The upstream scoring_in_window already caps the window at minute 90, so home_scores_next{h}m /
    away_scores_next{h}m are right-censored marginals. We add the FIRST-side decision using the next-goal
    minute when that next goal falls inside the (censored) window."""
    t = _f(snap, "snapshot_minute", 0.0) or 0.0
    h_eff = min(float(h), max(0.0, REGULATION_MINUTE - t))
    censored = 1 if (t + h) > REGULATION_MINUTE + 1e-9 else 0
    home_sc = _i(sc_row, f"home_scores_next{h}m", 0) or 0
    away_sc = _i(sc_row, f"away_scores_next{h}m", 0) or 0
    any_g = _i(sc_row, f"any_goal_next{h}m", 0) or 0

    # first side in the window: use the next-goal side/minute (next goal after t), gated to the window.
    first_side = "none"
    first_min = None
    ng_side = (ng_row or {}).get("next_goal_side", "none")
    ng_min = _f(ng_row or {}, "next_goal_minute", None)
    if ng_side in ("home", "away") and ng_min is not None and (t + 1e-9) < ng_min <= (t + h_eff + 1e-9):
        first_side = ng_side
        first_min = round(ng_min, 3)

    if first_side == "home":
        cls = "home_goal"
    elif first_side == "away":
        cls = "away_goal"
    else:
        # no goal STRICTLY decided as first inside window. If a side scored but next-goal fell outside
        # window edge rounding, fall back to the marginal (still no leakage; same window).
        if any_g and (home_sc or away_sc):
            if home_sc and not away_sc:
                cls, first_side = "home_goal", "home"
            elif away_sc and not home_sc:
                cls, first_side = "away_goal", "away"
            else:
                # both scored in window but first-side ambiguous from available labels -> use next-goal side
                cls = "home_goal" if ng_side == "home" else ("away_goal" if ng_side == "away" else "no_goal")
                first_side = ng_side if ng_side in ("home", "away") else "none"
        else:
            cls = "no_goal"
    return {
        f"next{h}_class": cls,
        f"next{h}_home_goal": home_sc,
        f"next{h}_away_goal": away_sc,
        f"next{h}_any_goal": any_g,
        f"next{h}_first_side": first_side,
        f"next{h}_first_goal_minute": first_min,
        f"next{h}_effective_horizon": round(h_eff, 3),
        f"next{h}_censored": censored,
    }


# =================================================================================================
# regime labels (causal; cutoff-state only)
# =================================================================================================
def regime_labels(snap):
    t = _f(snap, "snapshot_minute", 0.0) or 0.0
    gd = _i(snap, "goals_diff", 0) or 0
    pdiff = _i(snap, "players_diff", 0) or 0
    n_ev = _i(snap, "n_events_observed", 0) or 0
    xg10_h = _f(snap, "xg_last10m_home", 0.0) or 0.0
    xg10_a = _f(snap, "xg_last10m_away", 0.0) or 0.0
    rec_h = _i(snap, "recoveries_home", 0) or 0
    rec_a = _i(snap, "recoveries_away", 0) or 0
    to_h = _i(snap, "turnovers_home", 0) or 0
    to_a = _i(snap, "turnovers_away", 0) or 0
    shots10_h = _i(snap, "shots_last10m_home", 0) or 0
    shots10_a = _i(snap, "shots_last10m_away", 0) or 0
    corners = (_i(snap, "corners_home", 0) or 0) + (_i(snap, "corners_away", 0) or 0)
    fks = (_i(snap, "att_free_kicks_home", 0) or 0) + (_i(snap, "att_free_kicks_away", 0) or 0)
    min_since_chance = _f(snap, "min_since_major_chance", None)
    xg_present = (snap.get("xg_present") or "").strip().lower() in ("true", "1")

    regime_time = "early" if t < 30 else ("mid" if t < 60 else "late")
    absd = abs(gd)
    regime_score = "level" if absd == 0 else ("one_goal" if absd == 1 else "two_plus")
    regime_lead_side = "home" if gd > 0 else ("away" if gd < 0 else "none")
    regime_player_count = "even" if pdiff == 0 else ("home_up" if pdiff > 0 else "away_up")
    adv_sign = (1 if gd > 0 else (-1 if gd < 0 else 0)) + (1 if pdiff > 0 else (-1 if pdiff < 0 else 0))
    regime_advantage = "home" if adv_sign > 0 else ("away" if adv_sign < 0 else "none")
    regime_recent_pressure = "high" if (xg10_h + xg10_a) >= RECENT_PRESSURE_XG10 or (shots10_h + shots10_a) >= 3 else "normal"
    regime_recent_transition = "high" if (rec_h + rec_a + to_h + to_a) - 0 >= RECENT_TRANSITION_BURST * 4 else "normal"
    # set-piece "recent": any corner / attacking FK accumulated AND a recent shot window proxy
    regime_set_piece = "recent" if (corners + fks) > 0 and (shots10_h + shots10_a) > 0 else "none"
    regime_high_xg_chance = "recent" if (min_since_chance is not None and min_since_chance <= 5.0) else "none"
    # completeness bucket: xG-complete & enough events => full; some xG => partial; sparse late => sparse
    if n_ev < SPARSE_EVENTS and t >= 60:
        regime_completeness = "sparse"
    elif xg_present:
        regime_completeness = "full"
    else:
        regime_completeness = "partial"
    return {
        "regime_time": regime_time,
        "regime_score": regime_score,
        "regime_lead_side": regime_lead_side,
        "regime_player_count": regime_player_count,
        "regime_advantage": regime_advantage,
        "regime_recent_pressure": regime_recent_pressure,
        "regime_recent_transition": regime_recent_transition,
        "regime_set_piece": regime_set_piece,
        "regime_high_xg_chance": regime_high_xg_chance,
        "regime_completeness": regime_completeness,
        "regime_xg_complete": bool(xg_present),
        "regime_cell": f"{regime_time}|{regime_score}|{regime_player_count}",
    }


# =================================================================================================
# per-snapshot builder
# =================================================================================================
# the verbatim event-process columns we preserve on the residual input plane
PASSTHROUGH = [
    "goals_home", "goals_away", "goals_diff", "score_state",
    "yellow_home", "yellow_away", "yellow_diff",
    "sendoff_home", "sendoff_away", "sendoff_diff",
    "players_home", "players_away", "players_diff",
    "subs_used_home", "subs_used_away", "subs_used_diff",
    "poss_actions_home", "poss_actions_away", "poss_share_home", "poss_share_diff",
    "final_third_actions_home", "final_third_actions_away", "final_third_actions_diff", "field_tilt_home",
    "box_entries_home", "box_entries_away", "box_entries_diff",
    "recoveries_home", "recoveries_away", "recoveries_diff",
    "turnovers_home", "turnovers_away", "turnovers_diff",
    "corners_home", "corners_away", "corners_diff",
    "att_free_kicks_home", "att_free_kicks_away", "att_free_kicks_diff",
    "shots_home", "shots_away", "shots_diff",
    "shots_on_target_home", "shots_on_target_away", "shots_on_target_diff",
    "cum_xg_home", "cum_xg_away", "cum_xg_diff", "cum_xg_total", "xg_present",
    "min_since_last_shot_any", "min_since_last_shot_home", "min_since_last_shot_away", "min_since_major_chance",
    "xg_last1m_home", "xg_last1m_away", "xg_last1m_diff", "shots_last1m_home", "shots_last1m_away",
    "xg_last2m_home", "xg_last2m_away", "xg_last2m_diff", "shots_last2m_home", "shots_last2m_away",
    "xg_last5m_home", "xg_last5m_away", "xg_last5m_diff", "shots_last5m_home", "shots_last5m_away",
    "xg_last10m_home", "xg_last10m_away", "xg_last10m_diff", "shots_last10m_home", "shots_last10m_away",
    "xg_last15m_home", "xg_last15m_away", "xg_last15m_diff", "shots_last15m_home", "shots_last15m_away",
    "xg_current_half_home", "xg_current_half_away", "xg_current_half_diff",
    "xg_momentum_diff_10m", "xg_acceleration_diff",
]
IDENT = [
    "source_match_id", "bridge_id", "api_fixture_id", "competition_label", "comp_type",
    "kickoff_date", "home_team_id", "away_team_id", "snapshot_minute", "snapshot_reason",
    "snapshot_kind", "remaining_regulation_min", "n_events_observed", "source_root",
    "source_sha256", "engine_version",
]


def build(upstream):
    snaps = upstream["snaps"]
    ng_idx, sc_idx, wdl_idx, cq_idx = upstream["ng"], upstream["sc"], upstream["wdl"], upstream["cq"]

    snap_rows, target_rows, corr_rows = [], [], []
    n_no_wdl = 0

    for s in snaps:
        mid = s["source_match_id"]
        smin = s["snapshot_minute"]
        wdl = wdl_idx.get(mid)
        if wdl is None:
            n_no_wdl += 1
            continue
        sc_row = sc_idx.get((mid, smin), {})
        ng_row = ng_idx.get((mid, smin), {})

        t = _f(s, "snapshot_minute", 0.0) or 0.0
        remaining = _f(s, "remaining_regulation_min", max(0.0, REGULATION_MINUTE - t))
        gh = _i(s, "goals_home", 0) or 0
        ga = _i(s, "goals_away", 0) or 0
        gd = gh - ga

        # ---- W2 reference (parameter-free; score_diff + remaining only) ----
        w2_int = w2_remaining_intensity(remaining)
        w2_probs = DM.r2_remaining_time_poisson({"score_diff": gd, "remaining": remaining})

        # ---- residual INPUT row ----
        out = {k: s.get(k) for k in IDENT}
        out["residual_builder_version"] = RESIDUAL_BUILDER_VERSION
        for k in PASSTHROUGH:
            out[k] = s.get(k)
        out["w2_base_rate_per90"] = W2_BASE
        out["w2_remaining_home_intensity"] = round(w2_int, 6)
        out["w2_remaining_away_intensity"] = round(w2_int, 6)
        out["w2_remaining_total_intensity"] = round(2.0 * w2_int, 6)
        out["w2_prob_H"] = round(w2_probs["H"], 6)
        out["w2_prob_D"] = round(w2_probs["D"], 6)
        out["w2_prob_A"] = round(w2_probs["A"], 6)

        # ---- targets row (A: remaining goals; B: competing risk) ----
        reg_h = _i(wdl, "reg_home_goals", gh) or 0
        reg_a = _i(wdl, "reg_away_goals", ga) or 0
        rem_h = max(0, reg_h - gh)
        rem_a = max(0, reg_a - ga)
        trow = {
            "source_match_id": mid, "snapshot_minute": smin, "snapshot_reason": s.get("snapshot_reason"),
            "competition_label": s.get("competition_label"), "comp_type": "international",
            "remaining_home_goals": rem_h, "remaining_away_goals": rem_a,
            "remaining_total_goals": rem_h + rem_a,
            "remaining_window_open": int(remaining > 1e-9),
            "reg_home_goals": reg_h, "reg_away_goals": reg_a,
            "goals_home_cutoff": gh, "goals_away_cutoff": ga,
        }
        # ---- residual + regime row ----
        crow = {
            "source_match_id": mid, "snapshot_minute": smin,
            "competition_label": s.get("competition_label"), "comp_type": "international",
            "resid_remaining_home": round(rem_h - w2_int, 6),
            "resid_remaining_away": round(rem_a - w2_int, 6),
            "resid_remaining_total": round((rem_h + rem_a) - 2.0 * w2_int, 6),
            "alpha_fallback_allowed": True,
        }

        for h in HORIZONS:
            h_eff = min(float(h), max(0.0, REGULATION_MINUTE - t))
            # W2-implied near-term (right-censored effective horizon)
            out[f"w2_implied_home_score_next{h}m"] = round(w2_window_score_prob(h_eff), 6)
            out[f"w2_implied_away_score_next{h}m"] = round(w2_window_score_prob(h_eff), 6)
            out[f"w2_implied_any_goal_next{h}m"] = round(w2_window_any_goal_prob(h_eff), 6)
            out[f"w2_implied_home_first_next{h}m"] = round(w2_window_first_side_prob(h_eff), 6)
            out[f"w2_implied_no_goal_next{h}m"] = round(math.exp(-2.0 * W2_BASE * h_eff / 90.0), 6)

            cr = competing_risk_for_horizon(s, sc_row, ng_row, h)
            trow.update(cr)

            obs_home = cr[f"next{h}_home_goal"]
            obs_away = cr[f"next{h}_away_goal"]
            obs_any = cr[f"next{h}_any_goal"]
            crow[f"resid_home_score_next{h}m"] = round(obs_home - w2_window_score_prob(h_eff), 6)
            crow[f"resid_away_score_next{h}m"] = round(obs_away - w2_window_score_prob(h_eff), 6)
            crow[f"resid_any_goal_next{h}m"] = round(obs_any - w2_window_any_goal_prob(h_eff), 6)

        # ---- completeness / pre-match anchor flags ----
        comp = s.get("competition_label")
        xg_dom = cq_idx.get((comp, "shot_xg"), "unknown")
        out["xg_complete"] = bool(xg_dom == "available_verified")
        out["source_quality_shot_xg"] = xg_dom
        out["source_quality_pressure"] = cq_idx.get((comp, "pressure"), "unknown")
        out["source_quality_possession"] = cq_idx.get((comp, "possession_structure"), "unknown")
        out["prematch_anchor_available"] = bool(wdl.get("bridge_reg_home") not in (None, ""))
        out["bridge_reg_home"] = wdl.get("bridge_reg_home")
        out["bridge_reg_away"] = wdl.get("bridge_reg_away")

        crow.update(regime_labels(s))

        snap_rows.append(out)
        target_rows.append(trow)
        corr_rows.append(crow)

    return snap_rows, target_rows, corr_rows, {"n_no_wdl": n_no_wdl}


# =================================================================================================
# write-out
# =================================================================================================
def _write_rows(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return 0
    fieldnames, seen = [], set()
    for r in rows:
        for k in r.keys():
            if k not in seen:
                seen.add(k)
                fieldnames.append(k)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)
    return len(rows)


def _horizon_positive_rates(target_rows):
    out = {}
    n = len(target_rows) or 1
    for h in HORIZONS:
        c = {"home_goal": 0, "away_goal": 0, "no_goal": 0, "censored": 0}
        for r in target_rows:
            c[r[f"next{h}_class"]] += 1
            c["censored"] += int(r[f"next{h}_censored"])
        out[f"next{h}m"] = {
            "home_goal_rate": round(c["home_goal"] / n, 5),
            "away_goal_rate": round(c["away_goal"] / n, 5),
            "no_goal_rate": round(c["no_goal"] / n, 5),
            "censored_rate": round(c["censored"] / n, 5),
        }
    rem_open = [r for r in target_rows if r["remaining_window_open"] == 1]
    out["remaining_goals"] = {
        "n_window_open": len(rem_open),
        "mean_remaining_total": round(sum(r["remaining_total_goals"] for r in rem_open) / (len(rem_open) or 1), 5),
        "mean_remaining_home": round(sum(r["remaining_home_goals"] for r in rem_open) / (len(rem_open) or 1), 5),
        "mean_remaining_away": round(sum(r["remaining_away_goals"] for r in rem_open) / (len(rem_open) or 1), 5),
    }
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", default=None)
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        _self_test()
        return

    upstream, err = load_upstream()
    if upstream is None:
        print(json.dumps({"status": "data_insufficient", "reason": err}))
        return

    snap_rows, target_rows, corr_rows, info = build(upstream)
    if not snap_rows:
        print(json.dumps({"status": "data_insufficient",
                          "reason": "no international residual rows produced", **info}))
        return

    run_id = args.run_id
    if run_id is None:
        rid = ROOT / "outputs/research_runs/active_run_id.txt"
        run_id = rid.read_text(encoding="utf-8").strip() if rid.exists() else \
            datetime.now(timezone.utc).strftime("residual_%Y%m%d_%H%M%S")
    run_out = ROOT / "outputs/research_runs" / run_id / "residual_goal_intensity"

    n_snap = _write_rows(OUT_DIR / "residual_goal_intensity_snapshots.csv", snap_rows)
    n_tgt = _write_rows(OUT_DIR / "near_term_competing_risk_targets.csv", target_rows)
    n_cor = _write_rows(OUT_DIR / "selective_dynamic_correction.csv", corr_rows)

    n_matches = len({r["source_match_id"] for r in snap_rows})
    comps = sorted({r["competition_label"] for r in snap_rows})
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "residual_builder_version": RESIDUAL_BUILDER_VERSION,
        "w2_reference": {"name": "research.intensity.w2_home_away_i0",
                         "impl": "dynamic_models.r2_remaining_time_poisson", "base_rate_per90": W2_BASE},
        "built_utc": datetime.now(timezone.utc).isoformat(),
        "run_id": run_id,
        "labels": "research_only/experimental/not_runtime_approved/not_trade_eligible/not_live_eligible",
        "n_intl_residual_rows": n_snap,
        "n_target_rows": n_tgt,
        "n_correction_rows": n_cor,
        "n_intl_matches": n_matches,
        "competitions": comps,
        "n_competitions": len(comps),
        "horizon_positive_rates": _horizon_positive_rates(target_rows),
        "regime_cell_coverage": _regime_coverage(corr_rows),
        "residual_summary": _residual_summary(corr_rows),
        "rows_skipped_no_wdl": info["n_no_wdl"],
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "build_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    run_out.mkdir(parents=True, exist_ok=True)
    (run_out / "build_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    for name in ("near_term_competing_risk_targets.csv", "selective_dynamic_correction.csv"):
        (run_out / name).write_bytes((OUT_DIR / name).read_bytes())

    print(json.dumps({"status": "ok", "n_intl_residual_rows": n_snap, "n_intl_matches": n_matches,
                      "n_competitions": len(comps), "horizon_positive_rates": manifest["horizon_positive_rates"],
                      "out": str(OUT_DIR)}, indent=2))


def _regime_coverage(corr_rows):
    from collections import Counter
    c = Counter(r["regime_cell"] for r in corr_rows)
    return {"n_distinct_cells": len(c), "top_cells": dict(c.most_common(10))}


def _residual_summary(corr_rows):
    import statistics as st
    keys = ["resid_remaining_total", "resid_remaining_home", "resid_remaining_away",
            "resid_any_goal_next5m", "resid_any_goal_next10m", "resid_any_goal_next15m"]
    out = {}
    for k in keys:
        vals = [r[k] for r in corr_rows if r.get(k) is not None]
        if vals:
            out[k] = {"mean": round(st.mean(vals), 5),
                      "stdev": round(st.pstdev(vals), 5) if len(vals) > 1 else 0.0,
                      "n": len(vals)}
    return out


# =================================================================================================
# deterministic in-memory self-test (no files)
# =================================================================================================
def _self_test():
    # remaining intensity is parameter-free and symmetric
    assert abs(w2_remaining_intensity(90.0) - W2_BASE) < 1e-9
    assert abs(w2_remaining_intensity(45.0) - W2_BASE / 2.0) < 1e-9
    assert abs(w2_remaining_intensity(0.0)) < 1e-12
    # window probs monotone in horizon and bounded
    assert 0.0 < w2_window_score_prob(5) < w2_window_score_prob(15) < 1.0
    assert w2_window_any_goal_prob(10) > w2_window_score_prob(10)
    # a synthetic snapshot at t=30, home 1-0, away scores @70 (outside 15m, inside remaining)
    snap = {"snapshot_minute": "30", "remaining_regulation_min": "60", "goals_home": "1",
            "goals_away": "0", "goals_diff": "1", "players_diff": "0", "n_events_observed": "300",
            "xg_last10m_home": "0.0", "xg_last10m_away": "0.0", "xg_present": "True"}
    sc_row = {"home_scores_next5m": "0", "away_scores_next5m": "0", "any_goal_next5m": "0",
              "home_scores_next10m": "0", "away_scores_next10m": "0", "any_goal_next10m": "0",
              "home_scores_next15m": "0", "away_scores_next15m": "0", "any_goal_next15m": "0"}
    ng_row = {"next_goal_side": "away", "next_goal_minute": "70"}
    cr5 = competing_risk_for_horizon(snap, sc_row, ng_row, 5)
    assert cr5["next5_class"] == "no_goal" and cr5["next5_censored"] == 0, cr5
    cr15 = competing_risk_for_horizon(snap, sc_row, ng_row, 15)
    assert cr15["next15_class"] == "no_goal", cr15  # away goal @70 is outside (30,45]
    reg = regime_labels(snap)
    assert reg["regime_time"] == "mid" and reg["regime_score"] == "one_goal" and reg["regime_lead_side"] == "home", reg
    # right-censoring at the boundary: t=85, h=15 -> h_eff=5, censored
    snap2 = dict(snap); snap2["snapshot_minute"] = "85"; snap2["remaining_regulation_min"] = "5"
    cr = competing_risk_for_horizon(snap2, sc_row, {"next_goal_side": "none", "next_goal_minute": ""}, 15)
    assert abs(cr["next15_effective_horizon"] - 5.0) < 1e-9 and cr["next15_censored"] == 1, cr
    print(json.dumps({"self_test": "pass", "cr5": cr5["next5_class"], "cr15": cr15["next15_class"],
                      "regime": reg["regime_cell"]}))


if __name__ == "__main__":
    main()
