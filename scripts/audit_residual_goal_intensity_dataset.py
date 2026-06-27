"""Audit the residual goal-intensity dataset (Phase 1) against its leakage + integrity contract.

research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible.

Re-verifies, on the PRODUCED files (no rebuild required), every invariant the schemas promise:
  * international-only population (no club rows leaked in)
  * 1:1 join across the three residual tables on (source_match_id, snapshot_minute)
  * W2 reconstruction: w2_remaining_home == w2_remaining_away == R2_BASE*remaining/90 (recomputed)
  * W2 probs reconstruct from (goals_diff, remaining) via r2_remaining_time_poisson (recomputed)
  * residual = observed - W2 (recomputed, both families)
  * remaining_* goals == reg_final - goals_at_cutoff, all >= 0
  * competing-risk classes exhaustive + mutually exclusive; right-censoring monotone (h_eff<=h, <=90-t)
  * regulation-only minutes (snapshot_minute <= 90); no negative remaining
  * source_sha256 / engine_version preserved (non-empty) on every row
  * regime labels are from the documented closed set
Exits non-zero / prints status=fail with the first offending rows when any invariant breaks.
"""
from __future__ import annotations

import csv
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from wcdrawlab.research import dynamic_models as DM  # noqa: E402

OUT_DIR = ROOT / "data/processed/residual_goal_intensity"
HORIZONS = (5, 10, 15)
W2_BASE = DM.R2_BASE
TOL = 1e-4

VALID_REGIME = {
    "regime_time": {"early", "mid", "late"},
    "regime_score": {"level", "one_goal", "two_plus"},
    "regime_lead_side": {"home", "away", "none"},
    "regime_player_count": {"even", "home_up", "away_up"},
    "regime_advantage": {"home", "away", "none"},
    "regime_recent_pressure": {"high", "normal"},
    "regime_recent_transition": {"high", "normal"},
    "regime_set_piece": {"recent", "none"},
    "regime_high_xg_chance": {"recent", "none"},
    "regime_completeness": {"full", "partial", "sparse"},
}


def _read(path):
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _f(r, k, d=None):
    v = r.get(k, "")
    if v in (None, ""):
        return d
    try:
        return float(v)
    except ValueError:
        return d


def main():
    checks = []

    def record(name, ok, detail=""):
        checks.append({"check": name, "ok": bool(ok), "detail": detail})

    snap_p = OUT_DIR / "residual_goal_intensity_snapshots.csv"
    tgt_p = OUT_DIR / "near_term_competing_risk_targets.csv"
    cor_p = OUT_DIR / "selective_dynamic_correction.csv"
    if not (snap_p.exists() and tgt_p.exists() and cor_p.exists()):
        print(json.dumps({"status": "data_insufficient",
                          "reason": "residual dataset not built; run build_residual_goal_intensity_dataset.py"}))
        return 2

    snaps = _read(snap_p)
    tgts = _read(tgt_p)
    cors = _read(cor_p)
    record("nonempty_intl_rows", len(snaps) > 0, f"n={len(snaps)}")

    # international-only
    record("international_only",
           all(r.get("comp_type") == "international" for r in snaps),
           "club row leaked" if any(r.get("comp_type") != "international" for r in snaps) else "")

    # 1:1 join
    sk = {(r["source_match_id"], r["snapshot_minute"]) for r in snaps}
    tk = {(r["source_match_id"], r["snapshot_minute"]) for r in tgts}
    ck = {(r["source_match_id"], r["snapshot_minute"]) for r in cors}
    record("join_1to1", sk == tk == ck and len(sk) == len(snaps),
           f"snap={len(sk)} tgt={len(tk)} corr={len(ck)}")

    tgt_idx = {(r["source_match_id"], r["snapshot_minute"]): r for r in tgts}
    cor_idx = {(r["source_match_id"], r["snapshot_minute"]): r for r in cors}

    bad_w2_int = bad_w2_prob = bad_resid_rem = bad_rem_goal = bad_neg = bad_reg = 0
    bad_cr_excl = bad_censor = bad_resid_near = bad_hash = bad_regime = 0
    first_fail = {}

    for r in snaps:
        key = (r["source_match_id"], r["snapshot_minute"])
        t = _f(r, "snapshot_minute", 0.0)
        rem = _f(r, "remaining_regulation_min", max(0.0, 90.0 - t))
        gd = int(round(_f(r, "goals_diff", 0.0)))

        # regulation-only + non-negative remaining
        if t > 90.0 + 1e-9:
            bad_reg += 1; first_fail.setdefault("regulation_minute", key)
        if rem < -1e-9:
            bad_neg += 1; first_fail.setdefault("negative_remaining", key)

        # W2 intensity reconstruction
        exp_int = W2_BASE * max(0.0, rem) / 90.0
        if abs(_f(r, "w2_remaining_home_intensity", -9) - exp_int) > TOL or \
           abs(_f(r, "w2_remaining_away_intensity", -9) - exp_int) > TOL or \
           abs(_f(r, "w2_remaining_total_intensity", -9) - 2 * exp_int) > TOL:
            bad_w2_int += 1; first_fail.setdefault("w2_intensity", key)

        # W2 prob reconstruction
        p = DM.r2_remaining_time_poisson({"score_diff": gd, "remaining": rem})
        if abs(_f(r, "w2_prob_H", -9) - p["H"]) > TOL or abs(_f(r, "w2_prob_D", -9) - p["D"]) > TOL \
           or abs(_f(r, "w2_prob_A", -9) - p["A"]) > TOL:
            bad_w2_prob += 1; first_fail.setdefault("w2_prob", key)

        # source provenance preserved
        if not (r.get("source_sha256") or "").strip() or not (r.get("engine_version") or "").strip():
            bad_hash += 1; first_fail.setdefault("source_hash", key)

        # remaining goals == reg_final - goals_at_cutoff, all >= 0
        tr = tgt_idx.get(key, {})
        gh = int(round(_f(r, "goals_home", 0.0))); ga = int(round(_f(r, "goals_away", 0.0)))
        reg_h = int(round(_f(tr, "reg_home_goals", gh))); reg_a = int(round(_f(tr, "reg_away_goals", ga)))
        rem_h = int(round(_f(tr, "remaining_home_goals", -9))); rem_a = int(round(_f(tr, "remaining_away_goals", -9)))
        if rem_h != max(0, reg_h - gh) or rem_a != max(0, reg_a - ga):
            bad_rem_goal += 1; first_fail.setdefault("remaining_goal_recon", key)
        if rem_h < 0 or rem_a < 0:
            bad_neg += 1; first_fail.setdefault("negative_remaining_goals", key)

        # residual remaining reconstruction
        cr = cor_idx.get(key, {})
        if abs(_f(cr, "resid_remaining_home", -99) - (rem_h - exp_int)) > TOL or \
           abs(_f(cr, "resid_remaining_away", -99) - (rem_a - exp_int)) > TOL or \
           abs(_f(cr, "resid_remaining_total", -99) - ((rem_h + rem_a) - 2 * exp_int)) > TOL:
            bad_resid_rem += 1; first_fail.setdefault("resid_remaining", key)

        # competing-risk + censoring + near-term residual
        for h in HORIZONS:
            cls = tr.get(f"next{h}_class")
            if cls not in ("home_goal", "away_goal", "no_goal"):
                bad_cr_excl += 1; first_fail.setdefault("cr_class", key)
            h_eff = _f(tr, f"next{h}_effective_horizon", -9)
            censored = int(round(_f(tr, f"next{h}_censored", 0)))
            want_eff = min(float(h), max(0.0, 90.0 - t))
            want_cens = 1 if (t + h) > 90.0 + 1e-9 else 0
            if abs(h_eff - want_eff) > TOL or censored != want_cens:
                bad_censor += 1; first_fail.setdefault("censoring", key)
            # near-term residual reconstruction
            obs_any = _f(tr, f"next{h}_any_goal", 0.0)
            w2_any = 1.0 - math.exp(-2.0 * W2_BASE * h_eff / 90.0)
            if abs(_f(cr, f"resid_any_goal_next{h}m", -99) - (obs_any - w2_any)) > TOL:
                bad_resid_near += 1; first_fail.setdefault("resid_near", key)

        # regime label membership
        for col, allowed in VALID_REGIME.items():
            if cr.get(col) not in allowed:
                bad_regime += 1; first_fail.setdefault(f"regime:{col}", (key, cr.get(col)))
                break

    record("w2_intensity_reconstruct", bad_w2_int == 0, f"bad={bad_w2_int}")
    record("w2_prob_reconstruct", bad_w2_prob == 0, f"bad={bad_w2_prob}")
    record("remaining_goal_reconstruct", bad_rem_goal == 0, f"bad={bad_rem_goal}")
    record("resid_remaining_reconstruct", bad_resid_rem == 0, f"bad={bad_resid_rem}")
    record("resid_near_reconstruct", bad_resid_near == 0, f"bad={bad_resid_near}")
    record("regulation_only", bad_reg == 0, f"bad={bad_reg}")
    record("non_negative", bad_neg == 0, f"bad={bad_neg}")
    record("cr_class_exhaustive", bad_cr_excl == 0, f"bad={bad_cr_excl}")
    record("right_censoring", bad_censor == 0, f"bad={bad_censor}")
    record("source_provenance_preserved", bad_hash == 0, f"bad={bad_hash}")
    record("regime_membership", bad_regime == 0, f"bad={bad_regime}")

    all_ok = all(c["ok"] for c in checks)
    out = {
        "status": "ok" if all_ok else "fail",
        "n_intl_rows": len(snaps),
        "n_matches": len({r["source_match_id"] for r in snaps}),
        "n_competitions": len({r["competition_label"] for r in snaps}),
        "checks": checks,
        "first_failures": {k: (list(v) if isinstance(v, tuple) else v) for k, v in first_fail.items()},
        "labels": "research_only/experimental/not_runtime_approved/not_trade_eligible/not_live_eligible",
    }
    print(json.dumps(out, indent=2))
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
