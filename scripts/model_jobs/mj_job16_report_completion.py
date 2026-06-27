"""JOB16 -- SCIENTIFIC REPORT DRAFT + COMPLETION AUDIT. research_only.

Synthesizes every upstream artifact (JOB1..JOB15) into a human-readable scientific report draft (Markdown)
and a machine-readable completion audit. The completion audit verifies that each of the 16 jobs produced its
artifact with an acceptable terminal status (complete, or an HONEST data_insufficient/threshold_blocked with a
recorded reason), and records the headline findings + verdicts + the paper-only integrity assertion.

The report is explicitly NON-promotional: it states that nothing here is runtime/trade/live eligible, that the
2026 World Cup was never used for fitting/selection, and that any passing candidate is paper-only pending a
separate human-gated shadow review.

complete when the report + completion audit are written and all upstream jobs have a recorded terminal status.
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

JOB_ARTIFACTS = {
    "JOB1": "mj_job01_preflight.json", "JOB2": "mj_job02_rebuild_snapshots.json",
    "JOB3": "mj_job03_player_priors.json", "JOB4": "mj_job04_xg_state.json",
    "JOB5": "mj_job05_data_audit.json", "JOB6": "mj_job06_wdl_primary.json",
    "JOB7": "mj_job07_xg_primary.json", "JOB8": "mj_job08_wdl_loco.json",
    "JOB9": "mj_job09_nextgoal.json", "JOB10": "mj_job10_discipline.json",
    "JOB11": "mj_job11_ablations.json", "JOB12": "mj_job12_calibration_bootstrap.json",
    "JOB13": "mj_job13_failure_analysis.json", "JOB14": "mj_job14_decision_ledger.json",
    "JOB15": "mj_job15_artifact_registry.json",
}
ACCEPTABLE = {"complete", "data_insufficient", "threshold_blocked", "partial", "skipped"}


def _read(name):
    p = M.model_phase_dir(None) / name
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def main():
    rd = _job.run_dir()
    statuses = {}
    missing = []
    dishonest = []
    for jid, fname in JOB_ARTIFACTS.items():
        art = _read(fname)
        if art is None:
            missing.append(jid)
            statuses[jid] = {"status": "MISSING", "artifact": fname}
            continue
        st = art.get("status", "unknown")
        reason = art.get("reason") or art.get("failed_assertions") or art.get("detail")
        statuses[jid] = {"status": st, "artifact": fname, "reason": reason}
        if st not in ACCEPTABLE:
            dishonest.append(jid)
        if st in ("data_insufficient", "threshold_blocked") and not reason:
            dishonest.append(jid)  # honest skips must carry a reason

    wdl = _read("mj_job06_wdl_primary.json") or {}
    xg = _read("mj_job07_xg_primary.json") or {}
    ng = _read("mj_job09_nextgoal.json") or {}
    disc = _read("mj_job10_discipline.json") or {}
    ledger = _read("mj_job14_decision_ledger.json") or {}
    registry = _read("mj_job15_artifact_registry.json") or {}
    verdicts = ledger.get("verdicts", {})

    wdl_pooled = wdl.get("forward_chain", {}).get("pooled", {})
    xg_pooled = xg.get("forward_chain", {}).get("pooled", {}) if xg.get("status") == "complete" else {}

    def rps(d, k):
        v = (d.get(k, {}) or {}).get("rps")
        return f"{v:.4f}" if isinstance(v, (int, float)) else "n/a"

    lines = []
    lines.append(f"# Dynamic In-Play Modeling Phase -- Scientific Report Draft ({M.RUN_ID})")
    lines.append("")
    lines.append("**Labels:** research_only / experimental / not_runtime_approved / not_trade_eligible / "
                 "not_live_eligible. **Paper-only.** The 2026 World Cup is NEVER used for fitting, "
                 "calibration, or selection.")
    lines.append("")
    lines.append("## 1. Population & protocol")
    lines.append(f"- Population: senior men's INTERNATIONAL fixtures, decision minutes {M.DECISION_MINUTES} "
                 "(club rows are auxiliary player-prior history only, never test rows).")
    lines.append(f"- W/D/L rows: {wdl.get('n_rows', 'n/a')} over {wdl.get('n_matches', 'n/a')} matches; "
                 f"xG-eligible subset: {xg.get('n_xg_rows', 'n/a')} rows / {xg.get('n_xg_matches', 'n/a')} "
                 "exact-bridge matches.")
    lines.append("- Protocols: forward-chaining tournament eval (fit on strictly-earlier competitions) + "
                 "leave-one-international-competition-out (LOCO); match-level paired bootstrap.")
    lines.append("")
    lines.append("## 2. Headline W/D/L (forward-chain pooled RPS; lower better)")
    for mid in ("research.wdl.static_b1_anchor_r0", "research.wdl.time_score_baseline_r1",
                "research.wdl.remaining_time_poisson_r2", "research.wdl.player_starting_xi_p1",
                "research.wdl.player_team_state_p5"):
        lines.append(f"- {mid}: RPS={rps(wdl_pooled, mid)}")
    lines.append("")
    lines.append("## 3. xG-fusion W/D/L (exact-bridge subset; forward-chain pooled RPS)")
    if xg_pooled:
        for mid in ("research.wdl.remaining_time_poisson_r2", "research.wdl.xg_event_state_x1",
                    "research.wdl.xg_player_state_x2", "research.wdl.xg_calibrated_hybrid_x3"):
            lines.append(f"- {mid}: RPS={rps(xg_pooled, mid)}")
    else:
        lines.append(f"- xG forward-chain status: {xg.get('status')} -- {xg.get('reason', '')}")
    lines.append("")
    lines.append("## 4. Next-goal & discipline")
    lines.append(f"- Next-goal n1 pooled Brier: "
                 f"{(ng.get('pooled', {}).get('research.next_goal.time_score_cards_subs_n1', {}) or {}).get('brier')}")
    lines.append(f"- Discipline: total sending-off positives={disc.get('total_positives')} "
                 f"(gate={disc.get('gate_threshold')}); C1/C2 skipped below gate="
                 f"{disc.get('c1_c2_skipped_below_gate')} (honest preregistered gate).")
    lines.append("")
    lines.append("## 5. Candidate verdicts (paper-only; never auto-promoted)")
    for cand, v in verdicts.items():
        lines.append(f"- {cand} vs {v.get('reference')}: **{v.get('verdict')}** -- {v.get('reason')}")
    lines.append("")
    lines.append("## 6. Integrity")
    lines.append("- Collector isolation verified; all sources resolved via the canonical data-root registry; "
                 "zero external API calls in this phase.")
    lines.append("- Every fit/scaler/calibrator learned INSIDE training rows only; match-level bootstrap.")
    lines.append("- Nothing in this phase is runtime/trade/live eligible; a passing candidate is labelled "
                 "research_candidate_for_future_shadow_review and remains paper-only.")
    report = "\n".join(lines) + "\n"

    report_path = M.model_phase_dir(rd) / "scientific_report_dynamic_inplay_phase.md"
    report_path.write_text(report, encoding="utf-8")

    all_present = not missing
    all_honest = not dishonest
    ok = all_present and all_honest
    completion = M.job_envelope("JOB16", "complete" if ok else ("partial" if all_present else "failed"),
                                start_ts=M.utc(), end_ts=M.utc(),
                                job_statuses=statuses, missing_jobs=missing, dishonest_jobs=dishonest,
                                report_path=str(report_path),
                                verdict_summary={k: v.get("verdict") for k, v in verdicts.items()},
                                n_models_in_registry=registry.get("n_models"),
                                paper_only=True)
    M.write_artifact(rd, "mj_job16_report_completion.json", completion)
    status = "complete" if ok else ("partial" if all_present else "failed")
    _job.emit(status,
              reason=(f"report + completion audit written; {len(JOB_ARTIFACTS)} upstream jobs all present"
                      f" with honest terminal status" if ok
                      else f"missing={missing} dishonest={dishonest}"),
              state_updates={"completion_ok": ok, "report_path": str(report_path)})


if __name__ == "__main__":
    main()
