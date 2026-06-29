"""HT_JOB12 -- FAILURE ANALYSIS.

research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible.

REAL work: read the forward-chain (JOB07) + LOCO (JOB08) + ablation (JOB10) artifacts and produce an honest
failure analysis:
  * which models BEAT T0 and which did NOT (pooled + per fold);
  * whether any apparent improvement is inside the match-level bootstrap noise (CI overlaps 0);
  * where the worst per-fold regressions are;
  * the structural reason transfer did/did not help (single-domain: no club evidence -> T2..T6 collapse
    toward T1; the honest conclusion that cross-domain transfer is UNTESTED until club events land).

This job NEVER invents a positive result; if no model beats T0 with CI excluding 0, it says so plainly.
Honest data_insufficient if the upstream eval artifacts are absent.
"""
from __future__ import annotations

import _ht as H

JOB = "JOB12"


def main():
    art = H.envelope(JOB, "running")
    fc = H.read_run_json("job07_forward_chain.json")
    loco = H.read_run_json("job08_loco.json")
    abl = H.read_run_json("job10_ablations.json")

    if fc is None:
        art["status"] = "data_insufficient"
        H.write_json("job12_failure_analysis.json", art)
        return H.emit("data_insufficient", "forward-chain artifact (JOB07) absent -- nothing to analyse")

    pooled = fc.get("pooled") or {}
    beats = []
    no_beat = []
    significant = []
    for mid, m in pooled.items():
        if not isinstance(m, dict) or m.get("status") == "no_scored_rows":
            continue
        if m.get("beats_t0_on_rps"):
            beats.append((mid, m.get("rps_delta_vs_t0")))
            if m.get("ci_excludes_zero"):
                significant.append((mid, m.get("rps_delta_vs_t0"), m.get("rps_delta_ci95")))
        else:
            no_beat.append((mid, m.get("rps_delta_vs_t0")))

    # worst per-fold regression for the selective T6
    T = H.transfer_ids()
    worst_fold = None
    worst_delta = None
    for fold, fv in (fc.get("per_fold") or {}).items():
        if not isinstance(fv, dict):
            continue
        sc = (fv.get("scores") or {}).get(T.T6_SELECTIVE_TRANSFER)
        if sc and isinstance(sc, dict):
            d = sc.get("rps_delta_vs_t0")
            if d is not None and (worst_delta is None or d > worst_delta):
                worst_delta = d; worst_fold = fold

    # structural reason
    n_club = (H.read_run_json("job09_coverage_audit.json") or {}).get("n_club_rows_total")
    if n_club is None:
        rows = H.load_dataset_rows() if H.dataset_present() else []
        n_club = sum(1 for r in rows if (r.get("domain") or "international") == "club")
    single_domain = (n_club == 0)

    if significant:
        verdict = (f"{len(significant)} model(s) beat T0 with match-level CI excluding 0: "
                   f"{[s[0] for s in significant]}")
    elif beats:
        verdict = ("some models edge T0 on point RPS but NO model's improvement is outside the "
                   "match-level bootstrap CI -> NOT yet evidence of real transfer lift")
    else:
        verdict = "NO model beat T0 on pooled RPS"

    structural = (
        "SINGLE-DOMAIN regime: club auxiliary events are not materialised locally, so T2..T6 reduce to the "
        "international-only T1 (the selective gate correctly falls back). Cross-domain transfer lift is "
        "therefore UNTESTED in this run; it cannot be claimed until the club event corpus lands and the "
        "gate is allowed to enable transfer." if single_domain else
        "CROSS-DOMAIN regime: club rows present; the ladder's domain correction is exercised and the "
        "verdict above reflects real transfer behaviour."
    )

    art.update({
        "verdict": verdict,
        "models_beating_t0": beats,
        "models_not_beating_t0": no_beat,
        "statistically_separated_from_t0": significant,
        "worst_t6_fold": {"fold": worst_fold, "rps_delta_vs_t0": worst_delta},
        "single_domain_regime": single_domain,
        "n_club_rows_total": n_club,
        "structural_reason": structural,
        "loco_present": loco is not None,
        "ablations_present": abl is not None,
    })
    art["status"] = "complete"
    H.write_json("job12_failure_analysis.json", art)
    H.emit("complete", f"failure analysis: {verdict}; single_domain={single_domain}",
           state_updates={"failure_analysis_ok": True, "any_model_separated_from_t0": bool(significant),
                          "single_domain_regime": single_domain})


if __name__ == "__main__":
    main()
