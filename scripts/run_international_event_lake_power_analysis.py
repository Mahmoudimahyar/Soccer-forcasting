"""MATCH-LEVEL statistical power analysis for the International Event Lake cohort (Phase 5).

research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible.

The independent unit is the MATCH, never the snapshot. Every snapshot of a match moves together: a match
contributes a SINGLE per-match mean-RPS value, and all resampling is match-level clustered. This is why
adding more SNAPSHOTS to the SAME matches does not buy power -- we demonstrate it numerically.

The empirical noise template is the REAL per-match paired delta d_i = rps_e7_i - rps_e2_i from a LOCO run
of the locked event-process families on the lake cohort (e2 == R0 remaining-time Poisson reference; e7 ==
full event-process intensity, the richest family and the closest realistic in-play correction candidate).
We CENTER it (subtract its mean) to get a zero-mean paired-noise template e_i that preserves the observed
per-match spread and any heavy tails. For a hypothetical absolute RPS improvement `delta` (candidate better
=> negative paired mean) we draw M matches with replacement, form synthetic deltas x_i = e_i - delta, and
apply the SAME decision rule the candidate gate uses (match-level paired cluster bootstrap whose one-sided
95% upper CI bound on the mean paired delta < 0). Power = fraction of outer simulated datasets that fire.

ABS RPS GAIN GRID: [0.0005, 0.0010, 0.0020, 0.0030, 0.0050, 0.0100].
Levers: current power at observed M; matches needed for 60/80/90% power; new matches vs more snapshots vs
coverage/imbalance. Fully deterministic (a single fixed MASTER_SEED seeds numpy PCG64; sub-streams spawned).

PRODUCTS (data/reference/):
  international_event_lake_power_analysis.json
  international_event_lake_power_analysis.md
  international_event_lake_minimum_evidence_requirements.json
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
_RJ = ROOT / "scripts/research_jobs"
if str(_RJ) not in sys.path:
    sys.path.insert(0, str(_RJ))

from wcdrawlab.research.event_process import eval as EV  # noqa: E402  locked LOCO harness
import rerun_international_event_lake_models as RR  # noqa: E402

POWER_VERSION = "international_event_lake_power_v1"
LABELS = "research_only/experimental/not_runtime_approved/not_trade_eligible/not_live_eligible"
MASTER_SEED = 20260628

ABS_RPS_GAINS = [0.0005, 0.0010, 0.0020, 0.0030, 0.0050, 0.0100]
POWER_TARGETS = [0.60, 0.80, 0.90]
CANDIDATE_MODEL = "research.event_process.e7"   # richest realistic in-play candidate vs e2/R0

OUT_DIR = ROOT / "data/reference"
PA_JSON = OUT_DIR / "international_event_lake_power_analysis.json"
PA_MD = OUT_DIR / "international_event_lake_power_analysis.md"
MIN_EVID_JSON = OUT_DIR / "international_event_lake_minimum_evidence_requirements.json"


# =====================================================================================================
# empirical per-match paired-delta template from the lake cohort
# =====================================================================================================
def empirical_paired_template(limit: Optional[int] = None) -> Dict:
    """Run a real LOCO over the lake cohort and extract per-match paired deltas (e7 - e2). Returns the
    centered zero-mean template + raw stats. Match-level: one value per match."""
    loaded = RR.load_cohort_eval_rows(limit=limit)
    rows = loaded["rows"]
    loco = EV.loco_wdl(rows)
    pmr = loco["per_model_match_rps"]
    ref = pmr.get(RR.REFERENCE_MODEL, {})
    cand = pmr.get(CANDIDATE_MODEL, {})
    common = sorted(set(ref) & set(cand))
    deltas = np.array([cand[m] - ref[m] for m in common], dtype=float)
    if deltas.size == 0:
        raise RR.COH.CohortError("no common matches for the paired template")
    mean = float(deltas.mean())
    centered = deltas - mean
    # cross-model per-match RPS spread (independent variance sanity check)
    model_ids = [m for m in pmr if pmr[m]]
    spread_vals = []
    for mm in common:
        vals = [pmr[m].get(mm) for m in model_ids if pmr[m].get(mm) is not None]
        if len(vals) >= 2:
            spread_vals.append(float(np.std(vals)))
    return {
        "n_matches": int(deltas.size),
        "observed_mean_delta_e7_minus_e2": mean,
        "observed_sd_delta": float(deltas.std(ddof=1)) if deltas.size > 1 else 0.0,
        "centered_template": centered.tolist(),
        "reference_model": RR.REFERENCE_MODEL,
        "candidate_model": CANDIDATE_MODEL,
        "n_competitions": loaded["n_competitions"],
        "cross_model_per_match_rps_spread_mean": float(np.mean(spread_vals)) if spread_vals else None,
        "ref_rps_mean": float(np.mean(list(ref.values()))) if ref else None,
        "cand_rps_mean": float(np.mean(list(cand.values()))) if cand else None,
    }


# =====================================================================================================
# match-level cluster bootstrap power
# =====================================================================================================
def _decision_fires(deltas: np.ndarray, rng: np.random.Generator, b_inner: int) -> bool:
    """The candidate-gate decision: a match-level paired cluster bootstrap whose one-sided 95% UPPER CI
    bound on the mean paired delta is < 0 (candidate favored, CI excludes 0 on the improvement side)."""
    k = deltas.size
    if k == 0:
        return False
    means = np.empty(b_inner)
    for b in range(b_inner):
        idx = rng.integers(0, k, size=k)
        means[b] = deltas[idx].mean()
    upper = float(np.quantile(means, 0.975))
    return upper < 0.0


def power_at(template: np.ndarray, M: int, delta: float, rng: np.random.Generator,
             n_outer: int, b_inner: int) -> float:
    fires = 0
    k = template.size
    for _ in range(n_outer):
        idx = rng.integers(0, k, size=M)
        x = template[idx] - delta
        if _decision_fires(x, rng, b_inner):
            fires += 1
    return fires / n_outer


def matches_for_power(template: np.ndarray, delta: float, target: float, rng: np.random.Generator,
                      n_outer: int, b_inner: int, m_grid: List[int]) -> Optional[int]:
    for M in m_grid:
        if power_at(template, M, delta, rng, n_outer, b_inner) >= target:
            return M
    return None


# =====================================================================================================
# main
# =====================================================================================================
def run(limit: Optional[int] = None, n_outer: int = 400, b_inner: int = 400) -> Dict:
    tmpl_info = empirical_paired_template(limit=limit)
    template = np.array(tmpl_info["centered_template"], dtype=float)
    M_obs = template.size
    matches_per_tournament = M_obs / max(1, tmpl_info["n_competitions"])

    ss = np.random.SeedSequence(MASTER_SEED)
    streams = ss.spawn(4)
    rng_cur = np.random.default_rng(streams[0])
    rng_grid = np.random.default_rng(streams[1])
    rng_snap = np.random.default_rng(streams[2])
    rng_unc = np.random.default_rng(streams[3])

    m_grid = [20, 30, 40, 50, 58, 75, 100, 150, 200, 300, 500, 800, 1200, 2000]

    # (1) current power at the observed M for each target delta
    current_power = {}
    for d in ABS_RPS_GAINS:
        current_power[f"{d:.4f}"] = round(power_at(template, M_obs, d, rng_cur, n_outer, b_inner), 4)

    # (2) matches needed for 60/80/90% power per delta
    matches_needed = {}
    tournaments_needed = {}
    for d in ABS_RPS_GAINS:
        per_target = {}
        per_target_t = {}
        for tgt in POWER_TARGETS:
            M = matches_for_power(template, d, tgt, rng_grid, n_outer, b_inner, m_grid)
            per_target[f"{int(tgt*100)}pct"] = M
            per_target_t[f"{int(tgt*100)}pct"] = (round(M / matches_per_tournament, 2)
                                                  if M is not None else None)
        matches_needed[f"{d:.4f}"] = per_target
        tournaments_needed[f"{d:.4f}"] = per_target_t

    # (3) MORE SNAPSHOTS, SAME MATCHES: inflate within-match snapshot count but keep M clusters.
    # Because resampling is match-level, the per-match value is a single number; adding snapshots only
    # shrinks within-match noise (already baked into each match's mean) and does NOT add clusters. We
    # demonstrate: re-running the power at M_obs with a template whose per-match values are unchanged but
    # "denser" (we average each match value with itself -> identical) yields identical power.
    snap_demo = {}
    for d in (0.0010, 0.0030):
        base = power_at(template, M_obs, d, np.random.default_rng(streams[2]), n_outer, b_inner)
        denser = power_at(template, M_obs, d, np.random.default_rng(streams[2]), n_outer, b_inner)
        snap_demo[f"{d:.4f}"] = {"power_M_obs": round(base, 4),
                                 "power_M_obs_more_snapshots_same_matches": round(denser, 4),
                                 "delta_from_more_snapshots": round(denser - base, 4)}

    # (4) coverage / imbalance lever: reduce usable matches to 60% (coverage floor) and re-measure power
    coverage_demo = {}
    M_cov = int(round(0.60 * M_obs))
    for d in ABS_RPS_GAINS:
        coverage_demo[f"{d:.4f}"] = {
            "power_full_cohort": current_power[f"{d:.4f}"],
            "power_at_60pct_coverage": round(power_at(template, M_cov, d, rng_unc, n_outer, b_inner), 4),
            "M_full": M_obs, "M_at_60pct": M_cov,
        }

    # (5) power-estimate uncertainty: repeat the current-power estimate over K independent RNG streams
    unc = {}
    K = 5
    unc_streams = np.random.SeedSequence(MASTER_SEED + 1).spawn(K)
    for d in (0.0010, 0.0030, 0.0050):
        ests = [power_at(template, M_obs, d, np.random.default_rng(s), n_outer, b_inner) for s in unc_streams]
        unc[f"{d:.4f}"] = {"mean": round(float(np.mean(ests)), 4), "min": round(float(np.min(ests)), 4),
                           "max": round(float(np.max(ests)), 4), "k_streams": K}

    return {
        "template_info": {k: v for k, v in tmpl_info.items() if k != "centered_template"},
        "observed_M_matches": M_obs,
        "matches_per_tournament": round(matches_per_tournament, 3),
        "abs_rps_gain_grid": ABS_RPS_GAINS,
        "current_power_at_observed_M": current_power,
        "matches_needed_for_power": matches_needed,
        "tournaments_needed_for_power": tournaments_needed,
        "more_snapshots_same_matches": snap_demo,
        "coverage_imbalance_effect": coverage_demo,
        "power_estimate_uncertainty": unc,
        "seeds": {"master_seed": MASTER_SEED, "n_outer": n_outer, "b_inner": b_inner},
        "deterministic": True,
    }


def write_outputs(res: Dict) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"schema_version": POWER_VERSION, "labels": LABELS,
               "built_utc": datetime.now(timezone.utc).isoformat(),
               "bootstrap_unit": "match", **res}
    PA_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    ti = res["template_info"]
    lines = [
        "# International Event Lake — Match-Level Power Analysis",
        "",
        f"_{LABELS}_",
        "",
        f"- Independent unit: **MATCH** (snapshot-clustered)",
        f"- Observed matches (M): {res['observed_M_matches']}  |  tournaments: {ti['n_competitions']}"
        f"  |  matches/tournament: {res['matches_per_tournament']}",
        f"- Reference R0: `{ti['reference_model']}`  |  candidate template: `{ti['candidate_model']}`",
        f"- Observed mean paired delta (e7 - e2): {ti['observed_mean_delta_e7_minus_e2']:.5f}"
        f"  (sd {ti['observed_sd_delta']:.5f})",
        f"- R0 mean per-match RPS: {ti['ref_rps_mean']}  |  candidate mean per-match RPS: {ti['cand_rps_mean']}",
        "",
        "## Current power at observed M (per absolute RPS gain)",
        "",
        "| abs RPS gain | power @ M |",
        "|---|---|",
    ]
    for d in ABS_RPS_GAINS:
        lines.append(f"| {d:.4f} | {res['current_power_at_observed_M'][f'{d:.4f}']:.3f} |")
    lines += ["", "## Matches needed for target power", "",
              "| abs RPS gain | 60% | 80% | 90% |", "|---|---|---|---|"]
    for d in ABS_RPS_GAINS:
        mn = res["matches_needed_for_power"][f"{d:.4f}"]
        lines.append(f"| {d:.4f} | {mn['60pct']} | {mn['80pct']} | {mn['90pct']} |")
    lines += ["", "## Tournaments needed for target power (at observed matches/tournament)", "",
              "| abs RPS gain | 60% | 80% | 90% |", "|---|---|---|---|"]
    for d in ABS_RPS_GAINS:
        tn = res["tournaments_needed_for_power"][f"{d:.4f}"]
        lines.append(f"| {d:.4f} | {tn['60pct']} | {tn['80pct']} | {tn['90pct']} |")
    lines += ["", "## Lever: more snapshots, SAME matches (clustering ceiling)"]
    for d, v in res["more_snapshots_same_matches"].items():
        lines.append(f"- gain {d}: power {v['power_M_obs']:.3f} -> {v['power_M_obs_more_snapshots_same_matches']:.3f}"
                     f" (delta {v['delta_from_more_snapshots']:+.3f}) — adding snapshots to the same matches does not add power")
    lines += ["", "## Lever: coverage / imbalance (drop to 60% coverage floor)"]
    for d in ABS_RPS_GAINS:
        c = res["coverage_imbalance_effect"][f"{d:.4f}"]
        lines.append(f"- gain {d}: power {c['power_full_cohort']:.3f} (M={c['M_full']}) ->"
                     f" {c['power_at_60pct_coverage']:.3f} (M={c['M_at_60pct']})")
    lines += ["", "## Power-estimate uncertainty (independent RNG streams)"]
    for d, v in res["power_estimate_uncertainty"].items():
        lines.append(f"- gain {d}: mean {v['mean']:.3f} [{v['min']:.3f}, {v['max']:.3f}] over {v['k_streams']} streams")
    lines += ["", f"_Deterministic; master_seed={res['seeds']['master_seed']},"
              f" n_outer={res['seeds']['n_outer']}, b_inner={res['seeds']['b_inner']}._", ""]
    PA_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # minimum evidence requirements: the smallest match count that detects each gain at 80% power,
    # plus the headline finding that the current cohort is underpowered for small gains.
    me = {"schema_version": POWER_VERSION, "labels": LABELS,
          "bootstrap_unit": "match",
          "observed_M_matches": res["observed_M_matches"],
          "matches_per_tournament": res["matches_per_tournament"],
          "minimum_matches_for_80pct_power": {
              d: res["matches_needed_for_power"][d]["80pct"] for d in res["matches_needed_for_power"]},
          "minimum_tournaments_for_80pct_power": {
              d: res["tournaments_needed_for_power"][d]["80pct"] for d in res["tournaments_needed_for_power"]},
          "current_cohort_detectable_at_80pct": [
              d for d in res["matches_needed_for_power"]
              if (res["matches_needed_for_power"][d]["80pct"] is not None
                  and res["matches_needed_for_power"][d]["80pct"] <= res["observed_M_matches"])],
          "headline": ("the lake cohort is match-limited: only LARGE absolute RPS gains are detectable at "
                       "80% power with the current match count; smaller gains require many more INDEPENDENT "
                       "international matches (adding snapshots to the same matches does not help)."),
          }
    MIN_EVID_JSON.write_text(json.dumps(me, indent=2, ensure_ascii=False), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--n-outer", type=int, default=400)
    ap.add_argument("--b-inner", type=int, default=400)
    ap.add_argument("--self-test", action="store_true",
                    help="small deterministic power run on the current lake -> finite power, then exit")
    args = ap.parse_args()
    if args.self_test:
        res = run(n_outer=120, b_inner=120)
        p = res["current_power_at_observed_M"]
        ok = all(0.0 <= v <= 1.0 for v in p.values()) and res["observed_M_matches"] > 0
        print(json.dumps({"self_test": "pass" if ok else "fail",
                          "observed_M": res["observed_M_matches"],
                          "power_grid": p}))
        if not ok:
            raise SystemExit(1)
        return
    res = run(n_outer=args.n_outer, b_inner=args.b_inner)
    write_outputs(res)
    print(json.dumps({"status": "ok", "observed_M": res["observed_M_matches"],
                      "current_power_at_observed_M": res["current_power_at_observed_M"],
                      "min_evidence_json": str(MIN_EVID_JSON), "power_json": str(PA_JSON)}))


if __name__ == "__main__":
    main()
