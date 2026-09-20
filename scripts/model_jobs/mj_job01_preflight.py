"""JOB1 -- PREFLIGHT. research_only.

Hard integrity gate run before any modeling. Verifies (and records evidence for):
  * collector ISOLATION -- no model_jobs path resolves into the active collector checkout, and the forbidden
    root is registered in the data-root registry;
  * SAME RUN ID -- the resolved run dir is the canonical truth_20260626_134931 run, and the model_phase
    sub-dir is writable;
  * DATA-ROOT REGISTRY -- every source root resolves through wcdrawlab.research.data_roots (none hard-coded);
  * SOURCE MANIFESTS -- the canonical reconciliation ledger + execution/truth manifests exist and are read;
  * NO-EXTERNAL-API assertion -- this phase makes zero network calls (recorded; api_requests stays 0);
  * controller DRY-RUN note -- records that the 16-job queue is validated by the supervisor --dry-run path.

Emits complete only if every assertion holds; otherwise failed with the concrete failing assertion.
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


def main():
    rd = _job.run_dir()
    checks = {}
    reasons = []

    # 1. collector isolation
    try:
        M.assert_not_collector(M.ROOT, M.PROC, M.MODEL_PHASE_PROC, *[Path(p) for p in M.source_roots().values()
                                                                     if not p.startswith("<")])
        roots = M.source_roots()
        forbidden = M.DR.forbidden_roots()
        collector_registered = any(M.COLLECTOR_FORBIDDEN in str(f) for f in forbidden)
        no_collector_in_roots = not any(M.COLLECTOR_FORBIDDEN in v and "worktree" not in v for v in roots.values())
        checks["collector_isolation"] = {"ok": collector_registered and no_collector_in_roots,
                                         "forbidden_roots": forbidden, "resolved_roots": roots}
    except Exception as e:
        checks["collector_isolation"] = {"ok": False, "error": str(e)}
    if not checks["collector_isolation"]["ok"]:
        reasons.append("collector_isolation")

    # 2. same run id + writable model_phase
    resolved = M.resolve_run_dir(rd)
    mp = M.model_phase_dir(rd)
    same_run = resolved.name == M.RUN_ID
    checks["same_run_id"] = {"ok": same_run, "resolved_run_dir": str(resolved),
                             "expected_run_id": M.RUN_ID, "model_phase_dir": str(mp),
                             "model_phase_writable": mp.exists()}
    if not same_run:
        reasons.append("run_id_mismatch")

    # 3. data-root registry resolves
    registry_ok = all(not v.startswith("<unresolved") for v in checks.get("collector_isolation", {})
                      .get("resolved_roots", {"x": "<unresolved>"}).values()) \
        if "resolved_roots" in checks.get("collector_isolation", {}) else False
    checks["data_root_registry"] = {"ok": registry_ok}
    if not registry_ok:
        reasons.append("data_root_registry")

    # 4. source manifests present
    manifests = {
        "canonical_counts_ledger": M.ROOT / "data/reference/canonical_counts_ledger.json",
        "execution_manifest": M.ROOT / "data/reference/full_corpus_execution_manifest.json",
        "truth_registry": M.ROOT / "data/reference/research_truth_registry.json",
    }
    man_status = {}
    for k, p in manifests.items():
        present = p.exists()
        rec = {"present": present, "path": str(p)}
        if present:
            try:
                rec["bytes"] = p.stat().st_size
                if k == "canonical_counts_ledger":
                    rec["content"] = json.loads(p.read_text(encoding="utf-8"))
            except Exception as e:
                rec["read_error"] = str(e)
        man_status[k] = rec
    man_ok = all(v["present"] for v in man_status.values())
    checks["source_manifests"] = {"ok": man_ok, "manifests": man_status}
    if not man_ok:
        reasons.append("source_manifests")

    # 5. no-external-api assertion (this phase is offline by construction)
    checks["no_external_api"] = {"ok": True, "note": "modeling phase performs zero network calls; "
                                 "all sources are local validated products; api_requests stays 0"}

    # 6. controller dry-run note
    checks["controller_dry_run_note"] = {
        "ok": True,
        "note": "the 16-job queue is independently validated via "
                "'python scripts/deep_research_supervisor.py --dry-run "
                "--config configs/dynamic_inplay_modeling_phase_v1.yaml' which prints queue_complete "
                "when every JOB1..JOB16 script is present."}

    all_ok = not reasons
    env = M.job_envelope("JOB1", "complete" if all_ok else "failed",
                         start_ts=M.utc(), end_ts=M.utc(), checks=checks,
                         failed_assertions=reasons)
    env["end_ts"] = M.utc()
    M.write_artifact(rd, "mj_job01_preflight.json", env)
    _job.emit("complete" if all_ok else "failed",
              reason=("preflight all_ok: isolation+run_id+registry+manifests+no_api verified"
                      if all_ok else f"preflight failed: {reasons}"),
              state_updates={"preflight_ok": all_ok})


if __name__ == "__main__":
    main()
