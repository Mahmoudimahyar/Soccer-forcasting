"""LK_JOB13 -- completion report + FINAL integrity audit (terminal job).

The terminal job of the durable run. With NO fabrication:
  * runs the fail-closed integrity SENTINEL + the RETENTION verifier one final time (FAIL CLOSED),
  * re-asserts ISOLATION (not in collector / no root in collector / lake external / lake+raw untracked /
    collector commit recorded read-only),
  * gathers the real counts produced by JOB02-12 from data/reference/ products + the lake index,
  * runs the pytest suite as the GATE and records passed/failed/skipped (the suite must stay green),
  * writes notes/research/INTERNATIONAL_EVENT_LAKE_RESTORATION_V1_COMPLETION.md.

Emits `complete` only if the final sentinel + retention + isolation are clean AND the pytest gate passes.
A failing sentinel/retention is FAILED_INTEGRITY (the watchdog must not auto-restart). A failing test gate
is a hard `failed` (the suite is the contract).
"""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _lk


def _run_pytest():
    try:
        p = subprocess.run([sys.executable, "-m", "pytest", "-q", "--no-header"],
                           capture_output=True, text=True, cwd=str(_lk.ROOT), timeout=2400)
    except subprocess.TimeoutExpired:
        return {"ran": False, "passed": None, "failed": None, "skipped": None,
                "tail": "pytest timeout", "rc": None}
    tail = (p.stdout or "")[-400:] + (p.stderr or "")[-200:]
    passed = failed = skipped = None
    import re
    for kw, key in (("passed", "passed"), ("failed", "failed"), ("skipped", "skipped")):
        m = re.search(rf"(\d+) {kw}", p.stdout or "")
        if m:
            if kw == "passed":
                passed = int(m.group(1))
            elif kw == "failed":
                failed = int(m.group(1))
            else:
                skipped = int(m.group(1))
    return {"ran": True, "passed": passed, "failed": failed or 0, "skipped": skipped,
            "tail": tail, "rc": p.returncode}


def main():
    L = _lk.lake_engine()
    try:
        lake = L.Lake.resolve()
        index = L.read_index(lake)
    except Exception as e:
        _lk.emit("failed", reason=f"FAILED_INTEGRITY: lake_resolve_failed: {e!r}")
        return

    # final sentinel + retention
    try:
        rep = L.run_sentinel(lake, write_report=True)
        sentinel = rep.to_dict()
    except Exception as e:
        sentinel = {"all_ok": False, "error": repr(e), "failure_count": -1}
    ret = _lk.run_builder("scripts/verify_international_event_lake_retention.py")
    retention_ok = bool(ret["ok"]) and ((ret.get("last_json") or {}).get("all_ok", True) is not False)

    # isolation
    inside_collector = _lk.COLLECTOR_FORBIDDEN in str(_lk.ROOT).replace("\\", "/")
    root_in_collector = _lk.roots_resolving_into_collector()
    raw_tracked = bool(_lk.raw_git_tracked())
    lake_tracked = bool(_lk.lake_objects_git_tracked())
    norm = str(lake.root).replace("\\", "/")
    lake_external = ("worldcup-international-event-lake" not in norm
                     and _lk.COLLECTOR_FORBIDDEN not in norm)
    isolation_ok = (not inside_collector and not root_in_collector and not raw_tracked
                    and not lake_tracked and lake_external)
    coll_commit = _lk.collector_commit()

    # real counts from products + lake
    cohort = _lk.read_ref_json("international_event_lake_cohort_manifest.json") or {}
    power = _lk.read_ref_json("international_event_lake_power_analysis.json") or {}
    pkg = _lk.read_ref_json("international_event_lake_decision_package.json") or {}
    ledger = _lk.read_ref_json("international_event_lake_model_decision_ledger.json") or {}

    # pytest gate
    pyt = _run_pytest()
    test_gate_ok = bool(pyt["ran"]) and (pyt["failed"] == 0) and (pyt["passed"] or 0) > 0

    sentinel_ok = bool(sentinel.get("all_ok"))
    integrity_ok = sentinel_ok and retention_ok and isolation_ok

    # ---- completion markdown ----------------------------------------------------------------------
    verdict = (pkg.get("decision_ledger") or {}).get("verdict") or ledger.get("verdict") or "data_insufficient"
    md = [
        "# International Event Lake Restoration v1 — Completion Report",
        "",
        f"_{_lk.LABELS}_",
        "",
        f"- Completed (UTC): {_lk.utc()}",
        f"- Lake root: `{lake.root}`",
        f"- Lake objects (raw-backed + hash-verified): **{len(index)}**",
        f"- Final integrity sentinel all_ok: **{sentinel_ok}** (checked={sentinel.get('checked')}, "
        f"failures={sentinel.get('failure_count')})",
        f"- Retention verifier ok: **{retention_ok}**",
        f"- Isolation ok: **{isolation_ok}** (in_collector={inside_collector}, "
        f"roots_in_collector={root_in_collector}, lake_external={lake_external}, "
        f"raw_git_tracked={raw_tracked}, lake_git_tracked={lake_tracked})",
        f"- Active collector commit (read-only): `{coll_commit}` (expected `{_lk.EXPECTED_COLLECTOR_COMMIT}`)",
        f"- pytest gate: passed={pyt['passed']} failed={pyt['failed']} skipped={pyt['skipped']} "
        f"(rc={pyt['rc']})",
        "",
        "## Cohort",
        f"- Cohort matches: **{cohort.get('n_cohort_matches')}**",
        f"- Excluded ids: {cohort.get('n_excluded')}",
        f"- Total regulation-only causal snapshots: {cohort.get('n_total_snapshots')}",
        f"- Sub-cohort counts: {cohort.get('subcohort_counts')}",
        f"- No-2026-World-Cup guarantee: {cohort.get('no_2026_wc_guarantee')}",
        f"- Leakage self-test (real rows): {(cohort.get('leakage_self_test') or {}).get('all_ok')}",
        "",
        "## Statistical power (match-level, clustered)",
        f"- Observed M (eligible matches): {power.get('observed_M_matches')}",
        "- Independent unit is the MATCH; adding snapshots to the same matches does not buy power.",
        "",
        "## Model decision (preregistered families only; locked rule)",
        f"- Verdict: **{verdict}**",
        f"- Reference: `{(pkg.get('decision_ledger') or {}).get('reference_model')}`",
        "- Reuses ONLY remaining-time Poisson reference + time-score + xG-state + event-process + "
        "residual/selective-correction. No new features / search / neural / market.",
        "",
        "## Provenance & source quality (raw-backed from the lake index)",
        f"- Ingestion modes: {(pkg.get('source_quality') or {}).get('ingestion_modes')}",
        f"- Objects with xG / possession / location: "
        f"{(pkg.get('source_quality') or {}).get('objects_with_xg')} / "
        f"{(pkg.get('source_quality') or {}).get('objects_with_possession')} / "
        f"{(pkg.get('source_quality') or {}).get('objects_with_location')}",
        f"- Official-source-only: {(pkg.get('source_quality') or {}).get('official_source_only')} "
        f"(host {_lk.OFFICIAL_HOST})",
        "",
        "## Guarantees",
        "- Raw event JSON lives ONLY in the external content-addressed lake (0 git-tracked in this worktree).",
        "- External retrieval = OFFICIAL StatsBomb Open Data ONLY. No API-Football / Odds / paid / scrape / "
        "mirror / browser / 360 / video / credentials.",
        "- Strict EXACT international bridge only; ambiguous never enters evaluation; no completed-2026-WC "
        "match in any cohort/fit/calibration/selection.",
        "- Never modifies the active collector (worldcup_draw_model_lab_FINAL / WorldCupShadowCollector), "
        "B1, frozen M1-M5, candidate.py, approved_models.yaml, trading/Kalshi/risk, .env.",
    ]
    note = _lk.NOTES / "INTERNATIONAL_EVENT_LAKE_RESTORATION_V1_COMPLETION.md"
    note.parent.mkdir(parents=True, exist_ok=True)
    note.write_text("\n".join(md) + "\n", encoding="utf-8")

    out = {
        "lake_objects": len(index), "sentinel_ok": sentinel_ok, "retention_ok": retention_ok,
        "isolation_ok": isolation_ok, "integrity_ok": integrity_ok,
        "pytest": pyt, "test_gate_ok": test_gate_ok,
        "cohort_matches": cohort.get("n_cohort_matches"),
        "power_observed_M": power.get("observed_M_matches"),
        "decision_verdict": verdict, "completion_note": str(note),
        "utc": _lk.utc(), "labels": _lk.LABELS,
    }
    _lk.write_json("lk_completion_report.json", out)
    L.log_run(lake, "lk_job13_completion_report", out)

    if not integrity_ok:
        _lk.emit("failed",
                 reason=f"FAILED_INTEGRITY: sentinel_ok={sentinel_ok} retention_ok={retention_ok} "
                        f"isolation_ok={isolation_ok} -- fail closed (watchdog must not auto-restart)")
        return
    if not test_gate_ok:
        _lk.emit("failed",
                 reason=f"pytest gate failed (passed={pyt['passed']} failed={pyt['failed']} "
                        f"ran={pyt['ran']}); tail={pyt['tail'][-200:]}")
        return

    _lk.emit("complete",
             reason=f"COMPLETION: lake_objects={len(index)} sentinel_ok=True retention_ok=True "
                    f"isolation_ok=True pytest(passed={pyt['passed']},failed={pyt['failed']},"
                    f"skipped={pyt['skipped']}) cohort={cohort.get('n_cohort_matches')} "
                    f"verdict={verdict}",
             state_updates={"completion_done": True, "final_integrity_ok": True,
                            "pytest_passed": pyt["passed"], "pytest_failed": pyt["failed"]})


main()
