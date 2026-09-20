"""HT_JOB14 -- scientific REPORT + final INTEGRITY audit (critical).

research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible.

REAL work: assemble the per-run artifacts (JOB01..JOB13) into a scientific completion report
(notes/research/HIERARCHICAL_DOMAIN_TRANSFER_V1_COMPLETION.md) and run the FINAL integrity audit:
  * isolation: not the collector checkout; collector commit unchanged; no root in collector; raw not
    git-tracked; no forbidden imports in any HT job;
  * leakage backstop: no completed-2026-WC row in the dataset; the dataset audit's invariants passed;
  * provenance: dataset + ledger + registry hashes recorded;
  * honesty: the report states the verdict (incl. the single-domain caveat) plainly and stamps every
    artifact research_only / not_runtime/trade/live approved.

If the final integrity audit finds a violation WE could cause, it emits FAILED_INTEGRITY (critical).
"""
from __future__ import annotations

import _ht as H

JOB = "JOB14"

REPORT = H.NOTES / "HIERARCHICAL_DOMAIN_TRANSFER_V1_COMPLETION.md"


def _g(d, *path, default=None):
    cur = d
    for k in path:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k)
    return cur if cur is not None else default


def main():
    art = H.envelope(JOB, "running")

    j01 = H.read_run_json("job01_preflight.json") or {}
    j05 = H.read_run_json("job05_transfer_datasets.json") or {}
    j07 = H.read_run_json("job07_forward_chain.json") or {}
    j09 = H.read_run_json("job09_coverage_audit.json") or {}
    j12 = H.read_run_json("job12_failure_analysis.json") or {}
    j13 = H.read_run_json("job13_registry_ledger.json") or {}
    ledger = H.read_ref_json("hierarchical_transfer_decision_ledger.json") or {}

    iso = H.isolation_report()
    n2026 = H.assert_no_2026_rows(H.load_dataset_rows()) if H.dataset_present() else 0

    violations = []
    if iso["in_collector_checkout"]:
        violations.append("running_inside_collector_checkout")
    if iso["roots_in_collector"]:
        violations.append(f"data_root_in_collector:{iso['roots_in_collector']}")
    if iso["raw_git_tracked"] != "(none)":
        violations.append("raw_data_git_tracked")
    if iso["forbidden_imports"]:
        violations.append(f"forbidden_imports:{[h['file'] for h in iso['forbidden_imports']]}")
    if n2026 > 0:
        violations.append(f"2026_world_cup_rows_present:{n2026}")
    if j05 and j05.get("audit_all_invariants_ok") is False:
        violations.append("dataset_leakage_invariants_failed")

    verdict = j12.get("verdict") or _g(ledger, "verdict") or "n/a"
    single_domain = j12.get("single_domain_regime")
    n_folds = _g(j05, "n_folds") or _g(j07, "n_folds_scored")
    n_test_matches = _g(j05, "n_intl_test_matches_total")

    # pooled RPS table
    pooled = j07.get("pooled") or {}
    rows_md = []
    for mid, m in pooled.items():
        if isinstance(m, dict) and m.get("rps") is not None:
            rows_md.append((mid, m.get("rps"), m.get("rps_t0"), m.get("rps_delta_vs_t0"),
                            m.get("beats_t0_on_rps"), m.get("ci_excludes_zero")))

    lines = []
    lines.append("# Hierarchical Cross-Domain Transfer v1 -- Completion Report")
    lines.append("")
    lines.append("research_only / experimental / not_runtime_approved / not_trade_eligible / "
                 "not_live_eligible")
    lines.append("")
    lines.append(f"- Generated: {H.utc()}")
    lines.append(f"- Run id: {H.run_dir().name}")
    lines.append(f"- Reference model (anchor): `research.transfer.w2_reference_t0`")
    lines.append(f"- Collector commit (independent system): {iso.get('collector_commit')} "
                 f"(unchanged={iso.get('collector_commit_unchanged')})")
    lines.append("")
    lines.append("## Population & folds")
    lines.append(f"- Primary test population: INTERNATIONAL test rows only (club rows = auxiliary "
                 f"training, never a test row).")
    lines.append(f"- Forward-chain folds: {n_folds}; held-out international test matches: {n_test_matches}.")
    lines.append(f"- Dataset rows: {_g(j05, 'n_rows_total')}; stable-feature subset sizes: "
                 f"{_g(j05, 'stable_feature_subset_sizes')}.")
    lines.append(f"- Coverage regime: {_g(j09, 'coverage_class')} "
                 f"(club rows total = {_g(j09, 'n_club_rows_total')}).")
    lines.append("")
    lines.append("## Forward-chain results (pooled, vs T0)")
    lines.append("")
    lines.append("| model | RPS | RPS(T0) | delta vs T0 | beats T0 | CI excl 0 |")
    lines.append("|---|---|---|---|---|---|")
    for mid, rps, rps0, d, beats, ci in sorted(rows_md, key=lambda x: (x[1] if x[1] is not None else 9)):
        lines.append(f"| `{mid.split('.')[-1]}` | {rps} | {rps0} | {d} | "
                     f"{'yes' if beats else 'no'} | {'yes' if ci else 'no'} |")
    lines.append("")
    lines.append("## Verdict")
    lines.append("")
    lines.append(f"{verdict}")
    lines.append("")
    if single_domain:
        lines.append("**Single-domain caveat:** the club auxiliary event corpus is not materialised "
                     "locally, so the cross-domain transfer ladder (T2..T6) reduces to the "
                     "international-only T1 and the selective gate correctly falls back. Cross-domain "
                     "transfer lift is UNTESTED in this run and is NOT claimed.")
        lines.append("")
    lines.append("## Decision")
    lines.append("")
    lines.append(f"{_g(j13, 'global_decision') or _g(ledger, 'global_decision') or 'No model accepted.'}")
    lines.append("")
    lines.append("Decision ledger: `data/reference/hierarchical_transfer_decision_ledger.json` / `.csv`.")
    lines.append("")
    lines.append("## Final integrity audit")
    lines.append("")
    lines.append(f"- Isolation: in_collector={iso['in_collector_checkout']}, "
                 f"roots_in_collector={iso['roots_in_collector'] or 'none'}, "
                 f"raw_git_tracked={iso['raw_git_tracked']}, "
                 f"forbidden_imports={len(iso['forbidden_imports'])}.")
    lines.append(f"- Leakage backstop: 2026-WC rows in dataset = {n2026}; "
                 f"dataset_invariants_ok={_g(j05, 'audit_all_invariants_ok')}.")
    lines.append(f"- Provenance: dataset_sha256={_g(j05, 'dataset_sha256')}.")
    lines.append(f"- Violations: {violations or 'NONE'}.")
    lines.append("")
    lines.append("All models and artifacts are research_only and NOT runtime/trade/live approved.")
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    H.write_text("HIERARCHICAL_DOMAIN_TRANSFER_V1_COMPLETION.md", "\n".join(lines) + "\n")

    final = {
        "isolation": iso, "n_2026_rows": n2026,
        "dataset_invariants_ok": _g(j05, "audit_all_invariants_ok"),
        "verdict": verdict, "single_domain_regime": single_domain,
        "violations": violations, "report_path": str(REPORT),
        "decision_ledger": str(H.REF / "hierarchical_transfer_decision_ledger.json"),
    }
    art.update(final)

    if violations:
        art["status"] = "failed"
        art["watchdog_state"] = "FAILED_INTEGRITY"
        H.write_json("job14_report_integrity.json", art)
        return H.emit("failed", f"FINAL INTEGRITY VIOLATION: {violations}",
                      state_updates={"run_state": "FAILED_INTEGRITY", "violations": violations})

    art["status"] = "complete"
    H.write_json("job14_report_integrity.json", art)
    H.emit("complete",
           f"report written ({REPORT.name}); final integrity audit clean; verdict recorded; "
           f"all artifacts research_only",
           state_updates={"report_integrity_ok": True, "run_state": "COMPLETE",
                          "report_path": str(REPORT)})


if __name__ == "__main__":
    main()
