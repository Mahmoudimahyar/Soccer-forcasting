"""JOB4 -- BUILD + AUDIT dynamic xG state. research_only.

Re-affirms (and, if absent, rebuilds) the dynamic xG state product (per-minute xG rate / momentum / shot
state from the EXACT API<->StatsBomb bridge), then runs the deterministic xG AUDIT (no-future-xG,
monotonic-xG, no-cross-match-leakage, regulation-only, no-imputation self-tests + structural audit).

Reuses canonical scripts as subprocesses:
  * scripts/build_dynamic_xg_state.py    (build dynamic_xg_state_v1.csv)
  * scripts/audit_dynamic_xg_state.py    (deterministic self-test + structural audit; exit 0 == pass)

Emits complete only if the audit passes AND >0 xG-eligible international snapshots join into the eval rows;
data_insufficient (honest) if no real xG-eligible snapshots exist (NEVER imputes / fabricates xG).
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import _mj_common as M  # noqa: E402
sys.path.insert(0, str(M.RJ))
import _job  # noqa: E402

BUILD = M.ROOT / "scripts/build_dynamic_xg_state.py"
AUDIT = M.ROOT / "scripts/audit_dynamic_xg_state.py"


def main():
    rd = _job.run_dir()
    M.assert_not_collector(BUILD, AUDIT, M.XG_STATE_CSV, M.XG_ENRICHED_PARQUET)
    built = False
    build_rc = None
    build_tail = ""
    if not M.XG_STATE_CSV.exists():
        if not BUILD.exists():
            env = M.job_envelope("JOB4", "data_insufficient", start_ts=M.utc(), end_ts=M.utc(),
                                 reason="xG-state builder absent and product missing")
            M.write_artifact(rd, "mj_job04_xg_state.json", env)
            _job.emit("data_insufficient", reason="xG-state builder missing")
            return
        p = subprocess.run([sys.executable, str(BUILD)], capture_output=True, text=True, cwd=str(M.ROOT))
        built = True
        build_rc = p.returncode
        build_tail = (p.stdout or "")[-300:] + (("\nERR:" + (p.stderr or "")[-300:]) if p.stderr else "")

    if not M.XG_STATE_CSV.exists():
        env = M.job_envelope("JOB4", "data_insufficient", start_ts=M.utc(), end_ts=M.utc(),
                             reason="dynamic_xg_state_v1.csv absent after build", build_rc=build_rc,
                             build_tail=build_tail)
        M.write_artifact(rd, "mj_job04_xg_state.json", env)
        _job.emit("data_insufficient", reason="dynamic xG state product unavailable")
        return

    audit_rc = None
    audit_tail = ""
    audit_ok = False
    if AUDIT.exists():
        a = subprocess.run([sys.executable, str(AUDIT)], capture_output=True, text=True, cwd=str(M.ROOT))
        audit_rc = a.returncode
        audit_tail = (a.stdout or "")[-400:] + (("\nERR:" + (a.stderr or "")[-300:]) if a.stderr else "")
        audit_ok = audit_rc == 0
    else:
        audit_tail = "xG audit script absent"

    # confirm real xG-eligible rows join into eval rows
    n_xg_rows = 0
    n_xg_matches = 0
    try:
        xrows = M.load_xg_rows()
        n_xg_rows = len(xrows)
        n_xg_matches = len(set(r["match_id"] for r in xrows))
    except M.DataInsufficient as e:
        audit_tail += f"\nxg-join: {e}"

    nonzero_xg = any(abs(r.get("cum_xg_diff", 0.0)) > 0 for r in (M.load_xg_rows() if n_xg_rows else []))
    ok = audit_ok and n_xg_rows > 0
    status = "complete" if ok else ("threshold_blocked" if not audit_ok else "data_insufficient")
    env = M.job_envelope("JOB4", status, start_ts=M.utc(), end_ts=M.utc(),
                         built=built, build_rc=build_rc, build_tail=build_tail,
                         audit_rc=audit_rc, audit_ok=audit_ok, audit_tail=audit_tail,
                         n_xg_eligible_rows=n_xg_rows, n_xg_eligible_matches=n_xg_matches,
                         xg_subset_nonzero=bool(nonzero_xg))
    M.write_artifact(rd, "mj_job04_xg_state.json", env)
    _job.emit(status,
              reason=(f"xG state audited (rc={audit_rc}); {n_xg_rows} xG-eligible rows / {n_xg_matches} matches"
                      if ok else f"xG audit failed rc={audit_rc} or no xG-eligible rows ({n_xg_rows})"),
              state_updates={"xg_audit_ok": audit_ok, "n_xg_rows": n_xg_rows,
                             "n_xg_matches": n_xg_matches, "xg_subset_nonzero": bool(nonzero_xg)})


if __name__ == "__main__":
    main()
