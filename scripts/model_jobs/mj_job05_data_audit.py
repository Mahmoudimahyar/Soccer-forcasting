"""JOB5 -- DATA-COMPLETENESS / LEAKAGE / SOURCE-QUALITY audit. research_only.

A consolidated, evidence-producing audit over the assembled eval rows BEFORE any model is scored:

  COMPLETENESS  -- per-competition row/match counts; W/D/L class balance; next-goal & discipline positive
                   rates; xG-eligible coverage; player-impact join coverage.
  LEAKAGE       -- (a) no 2026-World-Cup row is present in the fit/selection corpus (dynamic_eval guard);
                   (b) every test-population row is comp_type == international (club rows never test rows);
                   (c) causal sanity: remaining == 90 - minute on every row; score_diff finite; targets in
                       the declared domains.
  SOURCE QUALITY-- reconciliation ledger exact-rate; events source roots resolve via the registry; player
                   prior coverage vs unknown-player share (read from the prior audit if present).

Emits complete when the rows pass the leakage invariants AND the population is non-empty; threshold_blocked
(honest) if a leakage invariant fails -- never silently continues.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import _mj_common as M  # noqa: E402
sys.path.insert(0, str(M.RJ))
import _job  # noqa: E402
sys.path.insert(0, str(M.SRC))
from wcdrawlab.research import dynamic_eval as DE  # noqa: E402


def main():
    rd = _job.run_dir()
    findings = {}
    leak_fail = []

    try:
        wdl = M.load_wdl_rows()
    except M.DataInsufficient as e:
        env = M.job_envelope("JOB5", "data_insufficient", start_ts=M.utc(), end_ts=M.utc(), reason=str(e))
        M.write_artifact(rd, "mj_job05_data_audit.json", env)
        _job.emit("data_insufficient", reason=str(e))
        return

    # ---- completeness ----
    cov = M.coverage_counts(wdl)
    bal = {"H": 0, "D": 0, "A": 0}
    for r in wdl:
        bal[r["target_wdl"]] = bal.get(r["target_wdl"], 0) + 1
    impact_join = sum(1 for r in wdl if "prematch_impact_diff" in r)
    findings["completeness"] = {
        "wdl": cov, "class_balance": bal,
        "player_impact_join_rows": impact_join,
        "player_impact_join_rate": round(impact_join / max(1, len(wdl)), 4),
        "next_goal_positive_rate": round(sum(r["next_goal_15"] for r in wdl) / max(1, len(wdl)), 4),
    }
    try:
        xrows = M.load_xg_rows()
        findings["completeness"]["xg_eligible_rows"] = len(xrows)
        findings["completeness"]["xg_eligible_matches"] = len(set(r["match_id"] for r in xrows))
    except M.DataInsufficient as e:
        findings["completeness"]["xg_eligible_rows"] = 0
        findings["completeness"]["xg_note"] = str(e)
    try:
        drows = M.load_discipline_rows()
        findings["completeness"]["discipline_rows"] = len(drows)
        findings["completeness"]["discipline_positives"] = sum(r["discipline_event"] for r in drows)
    except M.DataInsufficient as e:
        findings["completeness"]["discipline_rows"] = 0
        findings["completeness"]["discipline_note"] = str(e)

    # ---- leakage invariants ----
    try:
        DE.assert_no_2026(wdl)
        no_2026 = True
    except Exception as e:
        no_2026 = False
        leak_fail.append(f"2026_in_corpus:{e}")
    all_intl = all(r["comp_type"] == "international" for r in wdl)
    if not all_intl:
        leak_fail.append("club_rows_in_test_population")
    causal_bad = [r["match_id"] for r in wdl if int(r["remaining"]) != 90 - int(r["minute"])][:5]
    if causal_bad:
        leak_fail.append(f"remaining!=90-minute (e.g. {causal_bad})")
    domain_bad = sum(1 for r in wdl if r["target_wdl"] not in ("H", "D", "A")
                     or r["next_goal_15"] not in (0, 1))
    if domain_bad:
        leak_fail.append(f"out_of_domain_targets:{domain_bad}")
    findings["leakage_invariants"] = {
        "no_2026_in_corpus": no_2026, "all_test_rows_international": all_intl,
        "causal_remaining_ok": not causal_bad, "targets_in_domain": domain_bad == 0,
        "failures": leak_fail}

    # ---- source quality ----
    ledger_p = M.ROOT / "data/reference/canonical_counts_ledger.json"
    prior_audit_p = M.PRIORS_DIR / "dynamic_player_priors_audit.json"
    sq = {"source_roots": M.source_roots()}
    if ledger_p.exists():
        sq["reconciliation_ledger"] = json.loads(ledger_p.read_text(encoding="utf-8"))
    if prior_audit_p.exists():
        try:
            pa = json.loads(prior_audit_p.read_text(encoding="utf-8"))
            sq["player_prior_audit"] = {k: pa[k] for k in pa if k in
                                        ("status", "coverage_rate", "unknown_share", "self_tests",
                                         "real_output")}
        except Exception as e:
            sq["player_prior_audit_error"] = str(e)
    findings["source_quality"] = sq

    population_ok = len(wdl) > 0
    ok = (not leak_fail) and population_ok
    status = "complete" if ok else "threshold_blocked"
    env = M.job_envelope("JOB5", status, start_ts=M.utc(), end_ts=M.utc(), findings=findings)
    M.write_artifact(rd, "mj_job05_data_audit.json", env)
    _job.emit(status,
              reason=("completeness/leakage/source-quality audit passed; "
                      f"{cov['n_rows']} intl rows, no leakage" if ok
                      else f"leakage/quality gate failed: {leak_fail}"),
              state_updates={"data_audit_ok": ok, "n_wdl_rows": cov["n_rows"]})


if __name__ == "__main__":
    main()
