"""JOB10 -- DISCIPLINE discrete-time hazard evaluation (C0-C2). research_only.

Evaluates the discipline family P(new sending-off in next 15') on the international decision-minute rows
(dynamic_models.discipline_predictors). C1/C2 are PREREGISTERED-GATED on >=150 positive train examples;
when the corpus has fewer sending-off positives than the gate, C1/C2 are HONESTLY SKIPPED (the engine
returns gate_open=False) and only the C0 base-rate hazard is scored. This is a real gate, not a stub.

complete when C0 scores (always possible) AND the gate decision is recorded with the true positive count;
the artifact records gate_open + n_positives so the skip of C1/C2 is auditable.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import _mj_common as M  # noqa: E402
sys.path.insert(0, str(M.RJ))
import _job  # noqa: E402
sys.path.insert(0, str(M.SRC))
import _common as C  # noqa: E402
from wcdrawlab.research import dynamic_eval as DE, dynamic_models as DM  # noqa: E402


def main():
    rd = _job.run_dir()
    try:
        rows = M.load_discipline_rows()
    except M.DataInsufficient as e:
        M.write_artifact(rd, "mj_job10_discipline.json",
                         M.job_envelope("JOB10", "data_insufficient", reason=str(e), start_ts=M.utc(),
                                        end_ts=M.utc()))
        _job.emit("data_insufficient", reason=str(e))
        return

    total_pos = sum(r["discipline_event"] for r in rows)
    gate = DM.DISCIPLINE_POSITIVE_GATE

    folds = []
    gate_open_any = False
    for held, train, test in C.loco_folds(rows):
        fam = DM.discipline_predictors(train, target_key="discipline_event")
        gate_open_any = gate_open_any or fam["gate_open"]
        fold = {"held_competition": held, "n_train_rows": len(train), "n_test_rows": len(test),
                "n_train_positives": fam["n_positives"], "gate_open": fam["gate_open"],
                "gated_status": fam["gated_status"], "models": {}}
        for name, fn in fam["predictors"].items():
            sc = DE._score_binary(fn, test, "discipline_event")
            fold["models"][name] = {k: v for k, v in sc.items() if k != "per_match_brier"}
        folds.append(fold)

    if not folds:
        M.write_artifact(rd, "mj_job10_discipline.json",
                         M.job_envelope("JOB10", "data_insufficient", reason="no discipline folds",
                                        start_ts=M.utc(), end_ts=M.utc()))
        _job.emit("data_insufficient", reason="no discipline LOCO folds")
        return

    pooled = {}
    for f in folds:
        for n, m in f["models"].items():
            if m.get("brier") is not None:
                pooled.setdefault(n, []).append(m["brier"])
    pooled_mean = {n: float(np.mean(v)) for n, v in pooled.items()}

    c1c2_skipped = not gate_open_any
    env = M.job_envelope("JOB10", "complete", start_ts=M.utc(), end_ts=M.utc(),
                         n_rows=len(rows), total_positives=int(total_pos), gate_threshold=gate,
                         gate_open_any_fold=gate_open_any,
                         c1_c2_skipped_below_gate=c1c2_skipped,
                         n_folds=len(folds), folds=folds, pooled_brier=pooled_mean)
    M.write_artifact(rd, "mj_job10_discipline.json", env)
    reason = (f"discipline C0 scored over {len(folds)} folds; total positives={int(total_pos)} "
              + (f"(< gate {gate}) -> C1/C2 honestly skipped" if c1c2_skipped
                 else f"(>= gate {gate}) -> C1/C2 fit"))
    _job.emit("complete", reason=reason,
              state_updates={"discipline_positives": int(total_pos),
                             "discipline_gate_open": gate_open_any,
                             "discipline_pooled_brier": pooled_mean})


if __name__ == "__main__":
    main()
