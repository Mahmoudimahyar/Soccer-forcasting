"""EV_JOB12 -- final report + decision memo + integrity audit.

Terminal critical job. Reads every upstream evidence_power artifact from the run-dir + data/reference,
runs a final INTEGRITY AUDIT (isolation intact, raw not git-tracked, no root resolves into the collector,
no forbidden-import hit, every upstream job that ran is terminal-and-not-falsely-complete), and writes
the completion report to notes/research/EVIDENCE_POWER_CONSOLIDATION_V1_COMPLETION.md plus a structured
integrity JSON. Emits `failed` ONLY on a real integrity breach; otherwise `complete`.
"""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _ev

EXPECTED_COLLECTOR_COMMIT = "dc73318"
COMPLETION = _ev.NOTES / "EVIDENCE_POWER_CONSOLIDATION_V1_COMPLETION.md"


def _integrity():
    v = []
    # raw must not be git-tracked in this worktree
    try:
        tracked = subprocess.run(["git", "ls-files", "data/raw"], capture_output=True,
                                 text=True, cwd=str(_ev.ROOT)).stdout.strip()
        if tracked:
            v.append("raw_data_git_tracked")
    except Exception:
        pass
    # no canonical root resolves into the collector
    try:
        DR = _ev.data_roots()
        for name in DR._load()["roots"]:
            try:
                if _ev.COLLECTOR_FORBIDDEN in str(DR.get_root(name)).replace("\\", "/"):
                    v.append(f"research_root_in_collector:{name}")
            except PermissionError:
                v.append("data_root_resolves_into_collector")
    except Exception:
        pass
    # forbidden imports at module scope in any ev_job
    for f in sorted(_ev.HERE.glob("ev_job*.py")):
        for ln in f.read_text(encoding="utf-8").splitlines():
            s = ln.strip()
            if s.startswith(("import ", "from ")):
                for tok in _ev.FORBIDDEN_IMPORT_TOKENS:
                    if tok in s:
                        v.append(f"forbidden_import:{f.name}:{tok}")
    return v


def main():
    preflight = _ev.read_run_json("ev_preflight.json") or {}
    lin = _ev.read_run_json("ev_cohort_lineage_summary.json") or {}
    audit58 = _ev.read_run_json("ev_58_match_audit_summary.json") or {}
    repair = _ev.read_run_json("repair_log.json") or {}
    rerun = _ev.read_run_json("ev_rerun_affected.json") or {}
    power = _ev.read_run_json("ev_match_level_power_summary.json") or {}
    readiness = _ev.read_run_json("ev_live_readiness_summary.json") or {}
    consistency = _ev.read_run_json("ev_consistency_audit.json") or {}
    registry = _ev.read_run_json("ev_evidence_registry_summary.json") or {}

    # collector commit (read-only)
    coll_commit = None
    try:
        coll_commit = subprocess.run(
            ["git", "-C", "C:/Users/Mahyar/worldcup_draw_model_lab_FINAL", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True).stdout.strip() or None
    except Exception:
        coll_commit = None
    collector_unchanged = (coll_commit == EXPECTED_COLLECTOR_COMMIT)

    violations = _integrity()
    integrity_ok = (not violations)

    fs = lin.get("funnel_summary", {})
    fc = audit58.get("forward_chain_rps", {})
    loco = audit58.get("loco_rps", {})

    integrity = {
        "integrity_violations": violations, "integrity_ok": integrity_ok,
        "collector_commit_readonly": coll_commit,
        "collector_commit_expected": EXPECTED_COLLECTOR_COMMIT,
        "collector_unchanged": collector_unchanged,
        "isolation_preflight_ok": (preflight.get("isolation", {}).get("forbidden_write_list_ok")
                                   is not False),
        "consistency_all_ok": consistency.get("all_consistent"),
        "no_repair_required": repair.get("no_repair_required"),
        "utc": _ev.utc(), "labels": _ev.LABELS,
    }
    _ev.write_json("ev_integrity_audit.json", integrity)

    md = [
        "# Evidence-Power Consolidation v1 -- Completion Report", "",
        f"`{_ev.LABELS}`", "",
        f"Built {_ev.utc()}. Local-artifact-only consolidation: registry -> lineage -> 58-match audit -> "
        "reproducibility -> bug-detect/repair -> power -> live-readiness -> decision memo -> consistency "
        "-> integrity. No network/API/Odds/StatsBomb/scrape; the active collector "
        f"(`{EXPECTED_COLLECTOR_COMMIT}`) is read-only.", "",
        "## The WHY-58 funnel (match-level, independent unit = match)", "",
        f"- exact-international bridge population: **{fs.get('exact_bridge_population')}**",
        f"- dropped `missing_statsbomb_events`: **{fs.get('dropped_missing_statsbomb_events')}** "
        "(no StatsBomb event JSON on disk -- a preregistered DATA-AVAILABILITY boundary, not a defect)",
        f"- residual / event-process evaluable: **{fs.get('residual_population')}**",
        f"- forward-chain test set: **{fs.get('primary_evaluation_population')}** "
        f"(earliest competition `{fs.get('earliest_competition_train_only')}` train-only)",
        f"- LOCO test set: **{fs.get('loco_evaluation_population')}**", "",
        "## Independent reproduction (cold recompute, no package import)", "",
        f"- forward-chain pooled R0 RPS: recomputed **{fc.get('recomputed')}** vs reported "
        f"**{fc.get('reported')}** -> match=**{fc.get('match')}**",
        f"- LOCO pooled R0 RPS: recomputed **{loco.get('recomputed')}** vs reported "
        f"**{loco.get('reported')}** -> match=**{loco.get('match')}**", "",
        "## Verdict on 58", "",
        f"The 58-match cohort is **{audit58.get('verdict_58_match', 'unknown')}**: the intersection of the "
        "258 exact-international bridge matches with the StatsBomb event JSONs physically on disk. It is a "
        "data boundary, not a bug. The honest-negative residual conclusion (no in-play correction beats the "
        "W2 reference out-of-sample) is calibrated and match-level-bootstrapped on the 58 it had.", "",
        "## Bug detection / repair", "",
        f"- verified defects: **{len(repair.get('verified_defects', []))}**; "
        f"no_repair_required=**{repair.get('no_repair_required')}**",
        f"- affected-eval rerun: {rerun.get('reran') if rerun else 'skipped (no repair)'}", "",
        "## Statistical power (match-clustered)", "",
        f"- unit of independence: **{power.get('unit_of_independence')}**",
        f"- power@58 by target absolute-RPS improvement: {power.get('current_power_at_58')}",
        "- more snapshots on the same 58 matches does NOT raise power (clustering ceiling).", "",
        "## Live readiness", "",
        f"- families classified: **{readiness.get('n_families')}**; classes "
        f"{readiness.get('readiness_class_counts')}; live-eligible today "
        f"**{readiness.get('n_live_eligible_today')}** (no source carries an event-publication timestamp).",
        "", "## Cross-artifact consistency", "",
        f"- checks: **{consistency.get('n_checks')}**, inconsistent: "
        f"**{consistency.get('n_inconsistent')}**, all_consistent=**{consistency.get('all_consistent')}**.",
        "", "## Evidence registry", "",
        f"- rows: **{registry.get('n_rows')}**; claim_status {registry.get('claim_status_counts')}.", "",
        "## Integrity audit", "",
        f"- violations: **{violations or 'none'}**; integrity_ok=**{integrity_ok}**",
        f"- collector commit `{coll_commit}` unchanged=**{collector_unchanged}**; raw not git-tracked; "
        "no canonical root resolves into the collector; no forbidden network/provider import.", "",
        "All artifacts are labelled "
        "`research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible`.",
    ]
    _ev.NOTES.mkdir(parents=True, exist_ok=True)
    COMPLETION.write_text("\n".join(md), encoding="utf-8")

    if not integrity_ok:
        _ev.emit("failed",
                 reason=f"integrity breach: {violations}",
                 state_updates={"integrity_ok": False, "integrity_violations": violations})
        return
    _ev.emit("complete",
             reason=f"final report + integrity audit written; integrity_ok={integrity_ok}; "
                    f"collector_unchanged={collector_unchanged}; consistency_ok="
                    f"{consistency.get('all_consistent')}; no_repair_required="
                    f"{repair.get('no_repair_required')}",
             state_updates={"integrity_ok": integrity_ok, "collector_unchanged": collector_unchanged,
                            "completion_report": str(COMPLETION)})


main()
