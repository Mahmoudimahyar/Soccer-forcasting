"""Component 2 (Phase 2) AUDIT + self-tests for the full temporal player priors.

research_only. Proves the two load-bearing guarantees with DETERMINISTIC SYNTHETIC fixtures, then audits the
REAL built outputs (data/processed/dynamic_player_priors/*.csv) for the same invariants:

  SELF-TEST 1  NO FUTURE-APPEARANCE LEAKAGE
     A prior at time T must ignore an appearance dated exactly T (same match) and any appearance dated > T.
     We construct a player with a benign early appearance and an extreme later appearance and assert the
     prior at T reflects ONLY the early one; advancing T past the extreme appearance makes the prior move.

  SELF-TEST 2  CORRECT SHRINKAGE
     (a) An unknown player (no strictly-earlier appearance) returns EXACTLY the shrinkage mean, never an
         extreme/own value, and is flagged unknown with 0 prior appearances.
     (b) A thin-history player's contribution is strictly BETWEEN its raw value and the shrinkage target
         (monotone), and grows toward the raw value as exposure (minutes/appearances) increases.
     (c) Nested-tier monotonicity: more player exposure => closer to the player's own raw value.

  REAL-OUTPUT AUDIT
     Over the actual built tables: every unknown row has prior_appearances == 0; every known row has
     prior_appearances >= 1; exposure in [0,1]; uncertainty in [0,1]; all contributions finite; coverage
     rate matches the manifest. Reports the real coverage so status=complete is grounded in data.

Exit code 0 == all checks pass; nonzero == a guarantee failed. Run:
    python scripts/audit_dynamic_player_priors.py [--run-dir <dir>]
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
from wcdrawlab.research.player_history import Appearance  # noqa: E402
from wcdrawlab.research import dynamic_player_prior_models as DPP  # noqa: E402

PROC = ROOT / "data/processed/dynamic_player_priors"
MANIFEST = ROOT / "notes/research/dynamic_player_priors_manifest.json"


def _dt(s: str) -> datetime:
    return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)


def _ap(pid, team, mid, date, comp, pos, started, mins, gf, ga, res, h="h"):
    return Appearance(pid, team, mid, _dt(date), comp, pos, started, float(mins),
                      gf, ga, gf - ga, res, h)


# --------------------------------------------------------------------------------------------------
# SELF-TEST 1 — no future-appearance leakage
# --------------------------------------------------------------------------------------------------
def test_no_future_leakage(results):
    # player 1: benign early (gd +1), extreme later (gd +9). A prior AT the extreme's date must exclude it.
    aps = [
        _ap(1, 100, "m_early", "2024-01-01", "international", "F", True, 90, 1, 0, "W", "he"),
        _ap(1, 100, "m_T", "2024-03-01", "international", "F", True, 90, 9, 0, "W", "hT"),   # AT T
        _ap(1, 100, "m_future", "2024-06-01", "international", "F", True, 90, 9, 0, "W", "hf"),  # > T
        # filler players so the shrinkage means are not degenerate
        _ap(2, 100, "m_early", "2024-01-01", "international", "D", True, 90, 1, 0, "W", "h2"),
        _ap(3, 200, "m_early", "2024-01-01", "international", "M", True, 90, 0, 1, "L", "h3"),
    ]
    dp = DPP.DynamicPlayerPriors(aps, comp_label_by_match={
        "m_early": "WC", "m_T": "WC", "m_future": "WC"})
    T = _dt("2024-03-01")

    ex = dp.exposure_features(1, T, "international", team_id=100)
    cp = dp.contribution_prior(1, T, "international", team_id=100)
    # only the early appearance is visible at T
    _check(results, "leak.exposure_only_early", ex["prior_appearances"] == 1,
           f"expected 1 prior appearance at T, got {ex['prior_appearances']}")
    # the raw gd from the single early appearance is +1/90min => +1.0; shrinkage pulls it DOWN, never up
    _check(results, "leak.contribution_excludes_extreme", cp["gd_contribution_per90"] <= 1.0 + 1e-9,
           f"gd {cp['gd_contribution_per90']} > 1.0 => the +9 future appearance leaked in")

    # advancing T past the extreme appearance MUST change the prior (proves it was genuinely excluded before)
    T2 = _dt("2024-04-01")
    cp2 = dp.contribution_prior(1, T2, "international", team_id=100)
    ex2 = dp.exposure_features(1, T2, "international", team_id=100)
    _check(results, "leak.future_becomes_visible", ex2["prior_appearances"] == 2,
           f"expected 2 appearances after the extreme date, got {ex2['prior_appearances']}")
    _check(results, "leak.prior_moves_when_future_arrives",
           cp2["gd_contribution_per90"] > cp["gd_contribution_per90"] + 1e-6,
           "prior did not increase after the +9 appearance entered the strictly-before window")

    # substitution-delta uses the same strictly-before priors -> same guarantee
    sd = dp.substitution_delta_features(1, 2, T, "international", minute=70, score_diff=-1, team_id=100)
    sd2 = dp.substitution_delta_features(1, 2, T2, "international", minute=70, score_diff=-1, team_id=100)
    _check(results, "leak.subdelta_respects_strict_before",
           sd2["gd_delta_per90"] != sd["gd_delta_per90"],
           "substitution delta ignored the temporal change in the incoming player's prior")


# --------------------------------------------------------------------------------------------------
# SELF-TEST 2 — correct shrinkage
# --------------------------------------------------------------------------------------------------
def test_shrinkage(results):
    # population: many appearances so global/comp/pos means are stable and NONZERO
    aps = []
    for i in range(20):
        # alternating teams, positive global gd ~ +0.5
        aps.append(_ap(10 + i, 100, f"pm{i}", "2024-01-01", "international", "M", True, 90, 1, 0, "W", f"hp{i}"))
        aps.append(_ap(50 + i, 200, f"pm{i}", "2024-01-01", "international", "M", True, 90, 0, 1, "L", f"hq{i}"))
    dp = DPP.DynamicPlayerPriors(aps, comp_label_by_match={f"pm{i}": "WC" for i in range(20)})
    T = _dt("2024-02-01")

    # (a) UNKNOWN player -> exactly the shrinkage mean, flagged unknown, 0 prior appearances, finite
    unk = dp.contribution_prior(99999, T, "international", team_id=100)
    _check(results, "shrink.unknown_flagged", unk["unknown_player"] is True and unk["prior_appearances"] == 0,
           "unknown player not flagged / had nonzero prior appearances")
    _check(results, "shrink.unknown_finite", math.isfinite(unk["gd_contribution_per90"]),
           "unknown shrinkage value not finite")
    # the unknown value must equal a convex blend of the slice means (lie within their min/max range)
    glob = dp._means(T, "international").glob["gd90"]
    _check(results, "shrink.unknown_is_mean", abs(unk["gd_contribution_per90"] - round(_expected_unknown(dp, T), 6)) < 1e-6,
           f"unknown gd {unk['gd_contribution_per90']} != nested shrinkage target {_expected_unknown(dp, T)}")

    # (b) thin-history player: raw extreme +6 gd, ONE appearance -> shrunk strictly between raw and target
    aps_thin = aps + [_ap(7, 100, "thin1", "2024-01-05", "international", "M", True, 90, 6, 0, "W", "ht1")]
    dp2 = DPP.DynamicPlayerPriors(aps_thin, comp_label_by_match={**{f"pm{i}": "WC" for i in range(20)}, "thin1": "WC"})
    cp_thin = dp2.contribution_prior(7, _dt("2024-02-01"), "international", team_id=100)
    raw = 6.0
    target = _expected_unknown(dp2, _dt("2024-02-01"))  # the same nested target an unknown would get
    lo, hi = sorted((raw, target))
    _check(results, "shrink.thin_between_raw_and_target",
           lo - 1e-6 <= cp_thin["gd_contribution_per90"] <= hi + 1e-6,
           f"thin gd {cp_thin['gd_contribution_per90']} not between raw {raw} and target {target}")
    _check(results, "shrink.thin_strictly_shrunk", cp_thin["gd_contribution_per90"] < raw - 1e-6,
           "thin-history extreme value was NOT shrunk toward the mean")

    # (c) monotonicity: more exposure of the SAME-signed signal -> closer to raw (+6) than the thin case
    aps_thick = aps + [_ap(7, 100, f"thick{j}", f"2024-01-0{j+1}", "international", "M", True, 90, 6, 0, "W", f"hk{j}")
                       for j in range(5)]
    dp3 = DPP.DynamicPlayerPriors(aps_thick, comp_label_by_match={**{f"pm{i}": "WC" for i in range(20)},
                                                                  **{f"thick{j}": "WC" for j in range(5)}})
    cp_thick = dp3.contribution_prior(7, _dt("2024-02-01"), "international", team_id=100)
    _check(results, "shrink.more_exposure_closer_to_raw",
           cp_thick["gd_contribution_per90"] > cp_thin["gd_contribution_per90"] + 1e-6,
           "more same-signed exposure did not move the prior closer to the raw value")
    _check(results, "shrink.exposure_increases",
           cp_thick["exposure"] > cp_thin["exposure"] + 1e-6,
           "exposure did not increase with more minutes")
    _check(results, "shrink.uncertainty_decreases",
           cp_thick["uncertainty"] < cp_thin["uncertainty"] - 1e-6,
           "uncertainty did not decrease with more appearances")


def _expected_unknown(dp, T):
    """Recompute the nested shrinkage target an unknown M-position WC player would receive (gd90)."""
    m = dp._means(T, "international")
    metric = "gd90"
    g = m.glob.get(metric, 0.0)
    comp_m = m.by_comp.get(("WC", metric))
    comp_t = DPP._shrink_toward(comp_m, g, DPP._comp_weight(m, "WC", metric), DPP.SHRINK_COMPETITION) \
        if comp_m is not None else g
    pos_m = m.by_pos.get(("M", metric))
    pos_t = DPP._shrink_toward(pos_m, comp_t, DPP._pos_weight(m, "M", metric), DPP.SHRINK_POSITION) \
        if pos_m is not None else comp_t
    return pos_t


# --------------------------------------------------------------------------------------------------
# REAL-OUTPUT AUDIT
# --------------------------------------------------------------------------------------------------
def audit_real_outputs(results):
    contrib = PROC / "player_contribution_priors.csv"
    expo = PROC / "player_exposure_priors.csv"
    comp = PROC / "team_composition_features.csv"
    sub = PROC / "substitution_delta_features.csv"
    if not contrib.exists():
        _check(results, "real.outputs_exist", False, "built outputs missing -> run build script first")
        return {}
    rows = list(csv.DictReader(open(contrib, encoding="utf-8")))
    n = len(rows)
    unknown_zero = all(int(r["prior_appearances"]) == 0 for r in rows if r["unknown_player"] == "True")
    known_pos = all(int(r["prior_appearances"]) >= 1 for r in rows if r["unknown_player"] == "False")
    exp_ok = all(0.0 <= float(r["exposure"]) <= 1.0 and 0.0 <= float(r["uncertainty"]) <= 1.0 for r in rows)
    finite = all(math.isfinite(float(r["gd_contribution_per90"])) and
                 math.isfinite(float(r["off_contribution_per90"])) and
                 math.isfinite(float(r["def_contribution_per90"])) and
                 math.isfinite(float(r["wdl_contribution"])) for r in rows)
    n_known = sum(1 for r in rows if r["unknown_player"] == "False")
    _check(results, "real.unknown_zero_appearances", unknown_zero, "an unknown row had nonzero prior_appearances")
    _check(results, "real.known_ge1_appearance", known_pos, "a known row had <1 prior_appearance")
    _check(results, "real.exposure_uncertainty_in_unit", exp_ok, "exposure/uncertainty out of [0,1]")
    _check(results, "real.contributions_finite", finite, "a contribution value was non-finite")
    _check(results, "real.has_known_intl_priors", n_known > 0,
           "no known international player priors were computed")

    # coverage from composition table + manifest cross-check
    comp_rows = list(csv.DictReader(open(comp, encoding="utf-8"))) if comp.exists() else []
    cov_snaps = sum(1 for r in comp_rows if float(r["coverage_aggregate"]) > 0.0)
    man = json.loads(MANIFEST.read_text(encoding="utf-8")) if MANIFEST.exists() else {}
    _check(results, "real.manifest_coverage_matches",
           man.get("intl_decision_snapshots_with_player_prior_coverage") == cov_snaps,
           f"manifest coverage {man.get('intl_decision_snapshots_with_player_prior_coverage')} != recount {cov_snaps}")
    return {
        "contribution_rows": n,
        "known_intl_player_priors": n_known,
        "exposure_rows": sum(1 for _ in open(expo, encoding="utf-8")) - 1 if expo.exists() else 0,
        "composition_rows": len(comp_rows),
        "substitution_delta_rows": (sum(1 for _ in open(sub, encoding="utf-8")) - 1) if sub.exists() else 0,
        "intl_decision_snapshots_with_coverage": cov_snaps,
        "coverage_rate": man.get("coverage_rate"),
        "n_intl_matches": man.get("n_intl_matches_with_lineups"),
    }


# --------------------------------------------------------------------------------------------------
def _check(results, name, ok, msg=""):
    results.append({"check": name, "pass": bool(ok), "detail": "" if ok else msg})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", default=str(ROOT / "outputs/research_runs/truth_20260626_134931/model_phase"))
    args = ap.parse_args()

    results = []
    test_no_future_leakage(results)
    test_shrinkage(results)
    real = audit_real_outputs(results)

    n_pass = sum(1 for r in results if r["pass"])
    n_fail = len(results) - n_pass
    out = {
        "dynamic_prior_model_version": DPP.DYNAMIC_PRIOR_MODEL_VERSION,
        "self_test": "pass" if n_fail == 0 else "fail",
        "n_checks": len(results), "n_pass": n_pass, "n_fail": n_fail,
        "failed": [r for r in results if not r["pass"]],
        "checks": results,
        "real_outputs": real,
    }
    audit_path = PROC / "dynamic_player_priors_audit.json"
    PROC.mkdir(parents=True, exist_ok=True)
    audit_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    try:
        rd = Path(args.run_dir)
        rd.mkdir(parents=True, exist_ok=True)
        (rd / "dynamic_player_priors_audit.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    except Exception:
        pass
    print(json.dumps(out, indent=2))
    sys.exit(0 if n_fail == 0 else 1)


if __name__ == "__main__":
    main()
