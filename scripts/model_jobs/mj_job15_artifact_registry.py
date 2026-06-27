"""JOB15 -- MACHINE-READABLE MODEL ARTIFACT REGISTRY. research_only.

Builds a single machine-readable registry of every model family evaluated in this phase: canonical model id,
family, feature blocks, the eval protocol(s) it was scored under, its headline metric, the candidate verdict
(from JOB14), and the integrity labels. It also enumerates the on-disk JSON artifacts produced by JOB1..JOB14
with sizes + sha256, so a downstream consumer can verify the run without re-reading every file.

The registry is the contract other tools read; it asserts (and records) that NO model here is runtime/trade/
live eligible. complete when the registry is written; it degrades to partial (honest) if upstream metric
artifacts are absent (registry still lists the models with status notes).
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import _mj_common as M  # noqa: E402
sys.path.insert(0, str(M.RJ))
import _job  # noqa: E402

FAMILIES = {
    "research.wdl.static_b1_anchor_r0": ("wdl", "static base-rate anchor (B1-equivalent)", "forward_chain+loco"),
    "research.wdl.time_score_baseline_r1": ("wdl", "minute+score multinomial logistic", "forward_chain+loco"),
    "research.wdl.remaining_time_poisson_r2": ("wdl", "remaining-time Poisson (reference)", "forward_chain+loco"),
    "research.wdl.player_starting_xi_p1": ("wdl", "r2 + pre-match XI impact", "forward_chain+loco"),
    "research.wdl.player_on_pitch_p2": ("wdl", "p1 + on-pitch impact", "forward_chain+loco"),
    "research.wdl.player_substitution_delta_p3": ("wdl", "p2 + sub-delta history", "forward_chain+loco"),
    "research.wdl.player_composition_p4": ("wdl", "p3 + composition/continuity", "forward_chain+loco"),
    "research.wdl.player_team_state_p5": ("wdl", "p4 + full team-state", "forward_chain+loco"),
    "research.wdl.xg_event_state_x1": ("wdl_xg", "r2 + xG event-state", "forward_chain(xg-subset)"),
    "research.wdl.xg_player_state_x2": ("wdl_xg", "r2 + player impact (xG subset)", "forward_chain(xg-subset)"),
    "research.wdl.xg_calibrated_hybrid_x3": ("wdl_xg", "calibrated blend r2/x1/x2", "forward_chain(xg-subset)"),
    "research.next_goal.time_score_n0": ("next_goal", "base-rate hazard", "loco"),
    "research.next_goal.time_score_cards_subs_n1": ("next_goal", "+cards/subs hazard", "loco"),
    "research.next_goal.player_on_pitch_n2": ("next_goal", "+on-pitch impact", "loco"),
    "research.next_goal.substitution_delta_n3": ("next_goal", "+sub delta", "loco"),
    "research.next_goal.xg_player_fusion_n4": ("next_goal", "+xG player fusion", "loco"),
    "research.discipline.yellow_hazard_c0": ("discipline", "yellow base-rate hazard", "loco"),
    "research.discipline.sending_off_hazard_c1": ("discipline", "sending-off hazard (gated >=150)", "loco(gated)"),
    "research.discipline.player_team_prior_c2": ("discipline", "+player/team prior (gated >=150)", "loco(gated)"),
}


def _read(name):
    p = M.model_phase_dir(None) / name
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _sha(p: Path):
    h = hashlib.sha256()
    h.update(p.read_bytes())
    return h.hexdigest()


def main():
    rd = _job.run_dir()
    wdl_fwd = _read("mj_job06_wdl_primary.json")
    xg_fwd = _read("mj_job07_xg_primary.json")
    ng = _read("mj_job09_nextgoal.json")
    disc = _read("mj_job10_discipline.json")
    ledger = _read("mj_job14_decision_ledger.json")
    verdicts = (ledger or {}).get("verdicts", {})

    def headline(mid, family):
        if family == "wdl" and wdl_fwd:
            return {"rps": (wdl_fwd.get("forward_chain", {}).get("pooled", {}).get(mid, {}) or {}).get("rps")}
        if family == "wdl_xg" and xg_fwd and xg_fwd.get("status") == "complete":
            return {"rps": (xg_fwd.get("forward_chain", {}).get("pooled", {}).get(mid, {}) or {}).get("rps")}
        if family == "next_goal" and ng:
            return {"brier": (ng.get("pooled", {}).get(mid, {}) or {}).get("brier")}
        if family == "discipline" and disc:
            return {"brier": (disc.get("pooled_brier", {}) or {}).get(mid)}
        return {"status": "metric_artifact_absent"}

    # discipline C1/C2 are preregistered-gated; if the gate is closed their absent metric is EXPECTED,
    # not a real gap -- mark them gated rather than counting them as a missing-metric degradation.
    gate_open = bool((disc or {}).get("gate_open_any_fold", False))
    gated_ids = {"research.discipline.sending_off_hazard_c1", "research.discipline.player_team_prior_c2"}

    models = []
    missing_metric = 0
    for mid, (family, desc, protocol) in FAMILIES.items():
        hm = headline(mid, family)
        absent = hm.get("status") == "metric_artifact_absent" or all(v is None for v in hm.values())
        gated_off = (mid in gated_ids) and not gate_open
        if absent and gated_off:
            hm = {"status": "gated_off_below_positive_threshold", "gate_open": False}
        elif absent:
            missing_metric += 1
        models.append({
            "model_id": mid, "family": family, "description": desc, "eval_protocol": protocol,
            "headline_metric": hm, "candidate_verdict": verdicts.get(mid, {}).get("verdict"),
            "gated_off": bool(gated_off),
            "runtime_eligible": False, "trade_eligible": False, "live_eligible": False,
            "class": "transparent_regularized (multinomial logistic / Poisson / discrete-time hazard / "
                     "fixed-form calibrated blend)",
        })

    # enumerate on-disk artifacts with sha256
    artifacts = []
    for p in sorted(M.model_phase_dir(None).glob("mj_job*.json")) + \
            [q for q in [M.model_phase_dir(None) / "candidate_verdicts.json"] if q.exists()]:
        artifacts.append({"file": p.name, "bytes": p.stat().st_size, "sha256": _sha(p)})

    status = "complete" if missing_metric == 0 else "partial"
    env = M.job_envelope("JOB15", status, start_ts=M.utc(), end_ts=M.utc(),
                         n_models=len(models), n_models_missing_metric=missing_metric,
                         models=models, artifacts=artifacts,
                         eligibility_assertion="every model: runtime/trade/live eligible = False (research_only)")
    M.write_artifact(rd, "mj_job15_artifact_registry.json", env)
    M.write_artifact(rd, "model_artifact_registry.json",
                     {"run_id": M.RUN_ID, "model_version": M.MODEL_VERSION, "eval_version": M.EVAL_VERSION,
                      "models": models, "artifacts": artifacts,
                      "labels": "research_only/experimental/not_runtime_approved/not_trade_eligible/"
                                "not_live_eligible"})
    _job.emit(status,
              reason=f"model artifact registry written ({len(models)} models, "
                     f"{missing_metric} missing-metric, {len(artifacts)} artifacts)",
              state_updates={"registry_models": len(models), "registry_missing_metric": missing_metric})


if __name__ == "__main__":
    main()
