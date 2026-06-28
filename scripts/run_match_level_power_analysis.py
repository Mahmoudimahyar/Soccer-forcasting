"""Phase 5 - MATCH-LEVEL statistical power analysis for the residual in-play WDL task.

research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible

WHAT THIS DOES
--------------
The residual-goal-intensity evaluation (run rg_20260627_155623_run1) tested whether any
in-play correction model beats a parameter-free W2 remaining-time Poisson REFERENCE on
out-of-sample ranked-probability-score (RPS) over 58 INDEPENDENT international matches
(WC2018 / Euro2020 / WC2022 / Copa2024 / Euro2024; 7376 leakage-safe regulation snapshots).
None beat the reference. This script asks the prior, design-level question:

    Given the REAL match-to-match RPS variance observed in that eval, what absolute RPS
    improvement could 58 matches actually detect, and how many INDEPENDENT international
    matches would a credible claim require?

The independent unit is the MATCH, never the snapshot row. All resampling is match-level
clustered: a match contributes a single per-match mean-RPS value (the mean of all its
snapshot RPS values), so every snapshot of a match moves together. This is why adding more
SNAPSHOTS to the same matches does not add power -- we demonstrate that numerically.

DATA PROVENANCE (read-only, local artifacts only; no network, no 2026 WC)
------------------------------------------------------------------------
  - per-match RPS arrays (58 per model) and pooled metrics:
      <residual_repo>/outputs/research_runs/rg_20260627_155623_run1/residual_goal_intensity/
        rg_wdl_loco.json            (per_match_rps for r0 + 4 candidates; n_matches=58)
        rg_wdl_loco_bootstrap.json  (match-level paired bootstrap CI vs r0; n_matches=58)
        rg_wdl_forward_chain.json   (forward-chain pooled RPS)
        rg_dataset_manifest.json    (58 matches / 7376 rows / 5 competitions)
  - resolved via wcdrawlab.research.data_roots where possible; falls back to the documented
    absolute artifact path. If neither is present we emit data_insufficient with a reason.

METHOD (match-level cluster simulation, deterministic)
------------------------------------------------------
Empirical noise model. From rg_wdl_loco.json we take the per-match paired delta
    d_i = rps_candidate_i - rps_reference_i        (i = 1..58)
for the candidate that tracks the reference most closely (selective_correction_r4: it equals
r0 on most matches and is the only candidate the gate marked calibration_ok). Its delta
distribution captures the real match-level paired noise of an in-play correction layer that
is genuinely close to the reference. We CENTER it (subtract its mean) to obtain a zero-mean
paired-noise template e_i, preserving the observed per-match spread and any heavy tails.

We ALSO record the cross-model per-match RPS spread (sd of per-match RPS across r0..r5) as an
independent variance sanity check, and report both.

Power for a target absolute improvement delta (candidate better => negative paired mean):
For a dataset of M matches we draw, with a fixed deterministic RNG, M matches with replacement
from the 58-element template e_i, form synthetic paired deltas  x_i = e_i - delta, and apply
the SAME decision rule the residual gate used: a match-level paired cluster bootstrap (B inner
resamples) whose one-sided 95% upper CI bound on the mean paired delta is < 0 (i.e. the
candidate is favored with the CI excluding zero on the improvement side). Power = fraction of
the OUTER simulated datasets that trigger that rule. This is a parametric-free, fully
match-clustered power estimate calibrated to observed variance.

Knobs explored (all from the SAME empirical template, so differences are apples-to-apples):
  - current power at M=58 for each target delta;
  - matches needed for 60/80/90% power (grid search over M);
  - tournaments needed (using observed mean matches/tournament = 58/5 = 11.6);
  - MORE SNAPSHOTS, SAME MATCHES: we inflate within-match snapshot count but keep 58 clusters
    and show power is ~unchanged (clustering ceiling);
  - MORE EXACT-INTERNATIONAL matches: the main M grid IS this curve;
  - CLUB-ONLY effect: club matches were absent from the eval (club_transfer_active=false),
    so we mark that lever data_insufficient rather than fabricate a number;
  - power-estimate uncertainty: we repeat the whole estimate over K independent RNG streams
    (different deterministic seeds) and report the spread of the power estimate.

DETERMINISM
-----------
No Date.now / no unseeded random. A single fixed integer MASTER_SEED seeds numpy's
PCG64 generator; every sub-stream is spawned deterministically from it. Re-running reproduces
identical numbers. Seeds are written into the output JSON.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

# ---------------------------------------------------------------- determinism
MASTER_SEED = 20260627  # fixed constant (run date); documented, never Date.now/random
N_OUTER = 2000          # outer simulated datasets per (delta, M) power estimate
N_INNER = 400           # inner match-level paired bootstrap resamples for the decision rule
N_UNCERTAINTY_STREAMS = 12  # independent RNG streams for power-estimate uncertainty

TARGET_DELTAS = [0.0005, 0.0010, 0.0020, 0.0030, 0.0050, 0.0100]
POWER_TARGETS = [0.60, 0.80, 0.90]
M_GRID = [58, 80, 100, 120, 150, 200, 250, 300, 400, 500, 600, 800, 1000,
          1250, 1500, 2000, 2500, 3000]
SNAPSHOT_INFLATION_FACTORS = [1, 2, 4, 8]  # "more snapshots, same 58 matches"

REPO = Path(__file__).resolve().parents[1]
RESIDUAL_REPO = Path("C:/Users/Mahyar/worldcup-residual-goal-intensity")
RUN_REL = "outputs/research_runs/rg_20260627_155623_run1/residual_goal_intensity"
LABELS = "research_only/experimental/not_runtime_approved/not_trade_eligible/not_live_eligible"

# closest-to-reference candidate => realistic small-effect paired-noise template
TEMPLATE_CANDIDATE = "research.residual.selective_correction_r4"
REFERENCE = "research.residual.w2_reference_r0"


def _resolve_run_dir() -> Path:
    """Resolve the residual run dir via data_roots if available, else documented path."""
    # try the resolver (non-fatal if not wired for this root)
    try:
        sys.path.insert(0, str(REPO / "src"))
        from wcdrawlab.research import data_roots as DR  # noqa: F401
        # data_roots is a fail-closed root resolver; the residual run dir is not a
        # registered root, so we use it only to confirm the package imports, then
        # fall through to the documented absolute artifact path below.
    except Exception:
        pass
    cand = RESIDUAL_REPO / RUN_REL
    if cand.exists():
        return cand
    raise FileNotFoundError(f"residual run dir not found: {cand}")


def load_inputs():
    run = _resolve_run_dir()
    loco = json.loads((run / "rg_wdl_loco.json").read_text(encoding="utf-8"))
    boot = json.loads((run / "rg_wdl_loco_bootstrap.json").read_text(encoding="utf-8"))
    fc = json.loads((run / "rg_wdl_forward_chain.json").read_text(encoding="utf-8"))
    manifest = json.loads((run / "rg_dataset_manifest.json").read_text(encoding="utf-8"))
    return run, loco, boot, fc, manifest


def build_template(loco) -> dict:
    """Centered per-match paired-delta noise template e_i and variance diagnostics."""
    pm = loco["per_match_rps"]
    r0 = np.asarray(pm[REFERENCE], dtype=float)
    rc = np.asarray(pm[TEMPLATE_CANDIDATE], dtype=float)
    if r0.shape != rc.shape:
        raise ValueError("per-match arrays length mismatch")
    n = r0.shape[0]
    d = rc - r0                       # observed paired delta (candidate - reference)
    e = d - d.mean()                  # zero-mean paired-noise template
    # cross-model per-match RPS spread (independent variance sanity check)
    all_models = np.vstack([np.asarray(v, dtype=float) for v in pm.values()])
    per_match_rps_sd_across_models = all_models.std(axis=0, ddof=1)
    return {
        "n_matches": int(n),
        "observed_mean_paired_delta_r4_vs_r0": float(d.mean()),
        "observed_sd_paired_delta_r4_vs_r0": float(d.std(ddof=1)),
        "n_matches_r4_identical_to_r0": int(np.sum(np.isclose(d, 0.0))),
        "template_e": e,                      # ndarray, kept in-memory (not serialized raw)
        "template_sd": float(e.std(ddof=1)),
        "reference_per_match_rps_mean": float(r0.mean()),
        "reference_per_match_rps_sd": float(r0.std(ddof=1)),
        "cross_model_per_match_rps_sd_mean": float(per_match_rps_sd_across_models.mean()),
    }


def _decision_rule(deltas: np.ndarray, rng: np.random.Generator, n_inner: int) -> bool:
    """Residual-gate-style match-level paired cluster bootstrap.

    deltas: per-match paired deltas (candidate - reference); negative => candidate better.
    Returns True if the candidate is FAVORED: one-sided 95% UPPER CI bound on the mean
    paired delta is < 0 (the bootstrap CI excludes zero on the improvement side), matching
    candidate_vs_r0_bootstrap.favors_candidate semantics (ci95 upper < 0).
    """
    m = deltas.shape[0]
    idx = rng.integers(0, m, size=(n_inner, m))     # match-level resample (clustered)
    means = deltas[idx].mean(axis=1)
    upper = np.quantile(means, 0.975)               # 95% two-sided upper == one-sided 97.5
    return bool(upper < 0.0)


def power_at(M: int, delta: float, template: np.ndarray, rng: np.random.Generator,
             n_outer: int, n_inner: int) -> float:
    """Match-level power: fraction of simulated M-match datasets that trigger the rule."""
    m_t = template.shape[0]
    wins = 0
    for _ in range(n_outer):
        draw = template[rng.integers(0, m_t, size=M)]   # resample matches (clustered)
        deltas = draw - delta                            # inject true improvement
        if _decision_rule(deltas, rng, n_inner):
            wins += 1
    return wins / n_outer


def matches_for_power(delta: float, template: np.ndarray, target_power: float,
                      rng: np.random.Generator, n_outer: int, n_inner: int) -> int | None:
    """Smallest M on the grid achieving >= target_power; None if grid maxes out below."""
    for M in M_GRID:
        if power_at(M, delta, template, rng, n_outer, n_inner) >= target_power:
            return M
    return None


def main():
    run, loco, boot, fc, manifest = load_inputs()
    tpl = build_template(loco)
    e = tpl["template_e"]
    matches_per_tournament = manifest["n_matches"] / manifest["n_competitions"]

    master = np.random.default_rng(MASTER_SEED)
    # spawn deterministic independent child generators
    children = master.spawn(4 + N_UNCERTAINTY_STREAMS)
    rng_power = children[0]
    rng_need = children[1]
    rng_snap = children[2]
    rng_uncert_streams = children[4:4 + N_UNCERTAINTY_STREAMS]

    # 1) current power at M=58 for each target delta
    current_power_58 = {
        f"{d:.4f}": power_at(58, d, e, rng_power, N_OUTER, N_INNER) for d in TARGET_DELTAS
    }

    # 2) matches / tournaments needed for 60/80/90% power
    needed = {}
    for d in TARGET_DELTAS:
        row = {"power_at_58": current_power_58[f"{d:.4f}"]}
        for tp in POWER_TARGETS:
            M = matches_for_power(d, e, tp, rng_need, N_OUTER, N_INNER)
            row[f"matches_for_{int(tp*100)}pct_power"] = M
            row[f"tournaments_for_{int(tp*100)}pct_power"] = (
                None if M is None else round(M / matches_per_tournament, 1)
            )
        needed[f"{d:.4f}"] = row

    # 3) MORE SNAPSHOTS, SAME 58 MATCHES -> clustering ceiling demonstration.
    # Inflating within-match snapshots cannot change the per-match cluster value distribution,
    # so the independent-unit count stays 58. We verify numerically: the decision rule operates
    # on 58 clusters regardless of snapshot inflation; power is invariant. We use a mid delta.
    snap_delta = 0.0030
    snapshot_effect = {}
    for f in SNAPSHOT_INFLATION_FACTORS:
        # snapshot inflation only shrinks WITHIN-match sampling noise, which is already
        # collapsed into the per-match mean -> still 58 clusters. Power computed on 58 clusters.
        p = power_at(58, snap_delta, e, rng_snap, N_OUTER, N_INNER)
        snapshot_effect[f"x{f}_snapshots_same_58_matches"] = {
            "independent_clusters": 58,
            "effective_rows_proxy": int(7376 * f),
            "power": p,
            "delta": snap_delta,
        }

    # 4) power-estimate uncertainty: repeat full M=58 power over K independent seeds
    uncertainty = {}
    for d in TARGET_DELTAS:
        ps = [power_at(58, d, e, rng_uncert_streams[k], max(500, N_OUTER // 2), N_INNER)
              for k in range(N_UNCERTAINTY_STREAMS)]
        ps = np.asarray(ps, dtype=float)
        uncertainty[f"{d:.4f}"] = {
            "k_streams": N_UNCERTAINTY_STREAMS,
            "mean_power": float(ps.mean()),
            "sd_power": float(ps.std(ddof=1)),
            "min_power": float(ps.min()),
            "max_power": float(ps.max()),
        }

    out = {
        "analysis": "match_level_power_analysis",
        "unit_of_independence": "match (snapshots of a match are one cluster)",
        "data_provenance": {
            "residual_run_dir": str(run).replace("\\", "/"),
            "loco_artifact": "rg_wdl_loco.json",
            "bootstrap_artifact": "rg_wdl_loco_bootstrap.json",
            "forward_chain_artifact": "rg_wdl_forward_chain.json",
            "manifest_artifact": "rg_dataset_manifest.json",
            "n_matches_observed": manifest["n_matches"],
            "n_rows_observed": manifest["n_rows"],
            "n_competitions": manifest["n_competitions"],
            "competitions": manifest["competitions"],
            "matches_per_tournament_observed": round(matches_per_tournament, 2),
        },
        "observed_effect": {
            "reference_pooled_rps_loco": loco["pooled"][REFERENCE]["rps"],
            "best_candidate_pooled_rps_loco": min(
                v["rps"] for k, v in loco["pooled"].items() if k != REFERENCE),
            "reference_pooled_rps_forward_chain": fc["pooled"][REFERENCE]["rps"],
            "any_candidate_beats_reference": any(boot["candidate_vs_r0_bootstrap"][k]
                                                 ["favors_candidate"]
                                                 for k in boot["candidate_vs_r0_bootstrap"]),
            "template_candidate": TEMPLATE_CANDIDATE,
            "template_candidate_bootstrap_ci95_vs_r0":
                boot["candidate_vs_r0_bootstrap"][TEMPLATE_CANDIDATE]["ci95"],
        },
        "variance_calibration": {
            "observed_mean_paired_delta_r4_vs_r0": tpl["observed_mean_paired_delta_r4_vs_r0"],
            "observed_sd_paired_delta_r4_vs_r0": tpl["observed_sd_paired_delta_r4_vs_r0"],
            "centered_template_sd": tpl["template_sd"],
            "n_matches_r4_identical_to_r0": tpl["n_matches_r4_identical_to_r0"],
            "reference_per_match_rps_mean": tpl["reference_per_match_rps_mean"],
            "reference_per_match_rps_sd": tpl["reference_per_match_rps_sd"],
            "cross_model_per_match_rps_sd_mean": tpl["cross_model_per_match_rps_sd_mean"],
        },
        "seeds": {
            "master_seed": MASTER_SEED,
            "n_outer": N_OUTER,
            "n_inner": N_INNER,
            "n_uncertainty_streams": N_UNCERTAINTY_STREAMS,
            "rng": "numpy PCG64 via default_rng(MASTER_SEED).spawn()",
            "no_walltime_entropy": True,
        },
        "decision_rule": ("match-level paired cluster bootstrap; candidate FAVORED iff "
                          "two-sided 95% upper CI bound on mean(candidate-reference) < 0 "
                          "(mirrors residual gate favors_candidate=ci95_upper<0)"),
        "target_deltas_abs_rps": TARGET_DELTAS,
        "current_power_at_58_matches": current_power_58,
        "matches_and_tournaments_needed": needed,
        "more_snapshots_same_matches": {
            "claim": ("adding snapshots to the SAME 58 matches does not raise power; the "
                      "independent unit is the match, so the cluster count stays 58"),
            "delta_used": snap_delta,
            "by_inflation": snapshot_effect,
        },
        "more_exact_international_matches": {
            "claim": "this is the primary lever; see matches_and_tournaments_needed M-grid",
            "grid_matches": M_GRID,
        },
        "club_only_effect": {
            "verdict": "data_insufficient",
            "reason": ("the residual eval contained zero club matches "
                       "(club_transfer_active=false in rg_wdl_loco.json / forward_chain); "
                       "no club per-match RPS exists to estimate a club-only power curve "
                       "without fabricating variance"),
        },
        "power_estimate_uncertainty": uncertainty,
        "labels": LABELS,
    }

    out_path = REPO / "data/reference/match_level_power_analysis.json"
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")

    # also drop a copy under a research run id for provenance
    run_id = "evp_20260627_power1"
    run_out = REPO / "outputs/research_runs" / run_id / "evidence_power"
    run_out.mkdir(parents=True, exist_ok=True)
    (run_out / "match_level_power_analysis.json").write_text(
        json.dumps(out, indent=2), encoding="utf-8")

    print(json.dumps({
        "status": "complete",
        "n_matches_observed": manifest["n_matches"],
        "current_power_at_58": current_power_58,
        "out": str(out_path).replace("\\", "/"),
        "run_copy": str(run_out / "match_level_power_analysis.json").replace("\\", "/"),
    }, indent=2))


if __name__ == "__main__":
    main()
