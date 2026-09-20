"""JOB3 -- BUILD + AUDIT temporal player priors. research_only.

Re-affirms (and, if absent, rebuilds) the leakage-safe TEMPORAL PLAYER PRIORS, then runs the deterministic
prior AUDIT (no-future-appearance-leakage + correct-shrinkage self-tests + real-output invariants).

Reuses the canonical scripts as subprocesses:
  * scripts/build_dynamic_temporal_player_priors.py   (build, --run-dir aware)
  * scripts/audit_dynamic_player_priors.py            (deterministic self-test + real-output audit)

Resume-safe: when the four prior products already exist the build is skipped; the AUDIT always runs (it is
the leakage proof). Emits complete only if the audit passes AND the priors join onto >0 international rows;
threshold_blocked / data_insufficient (honest) otherwise.
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

BUILD = M.ROOT / "scripts/build_dynamic_temporal_player_priors.py"
AUDIT = M.ROOT / "scripts/audit_dynamic_player_priors.py"
PRODUCTS = [M.PRIORS_DIR / n for n in ("player_exposure_priors.csv", "player_contribution_priors.csv",
                                       "team_composition_features.csv", "substitution_delta_features.csv")]


def main():
    rd = _job.run_dir()
    M.assert_not_collector(BUILD, AUDIT, *PRODUCTS)
    built = False
    build_rc = None
    build_tail = ""
    if not all(p.exists() for p in PRODUCTS):
        if not BUILD.exists():
            env = M.job_envelope("JOB3", "data_insufficient", start_ts=M.utc(), end_ts=M.utc(),
                                 reason="prior build script absent and products missing")
            M.write_artifact(rd, "mj_job03_player_priors.json", env)
            _job.emit("data_insufficient", reason="player-prior builder missing")
            return
        p = subprocess.run([sys.executable, str(BUILD), "--run-dir", str(M.resolve_run_dir(rd))],
                           capture_output=True, text=True, cwd=str(M.ROOT))
        built = True
        build_rc = p.returncode
        build_tail = (p.stdout or "")[-300:] + (("\nERR:" + (p.stderr or "")[-300:]) if p.stderr else "")

    missing = [p.name for p in PRODUCTS if not p.exists()]
    if missing:
        env = M.job_envelope("JOB3", "data_insufficient", start_ts=M.utc(), end_ts=M.utc(),
                             reason=f"prior products still missing: {missing}", build_rc=build_rc,
                             build_tail=build_tail)
        M.write_artifact(rd, "mj_job03_player_priors.json", env)
        _job.emit("data_insufficient", reason=f"prior products missing: {missing}")
        return

    # deterministic + real-output audit (this is the leakage proof; always run)
    audit_rc = None
    audit_tail = ""
    audit_ok = False
    if AUDIT.exists():
        a = subprocess.run([sys.executable, str(AUDIT), "--run-dir", str(M.resolve_run_dir(rd))],
                           capture_output=True, text=True, cwd=str(M.ROOT))
        audit_rc = a.returncode
        audit_tail = (a.stdout or "")[-400:] + (("\nERR:" + (a.stderr or "")[-300:]) if a.stderr else "")
        audit_ok = audit_rc == 0
    else:
        audit_tail = "audit script absent"

    # confirm priors actually join onto international rows
    join_n = 0
    try:
        impact = M._player_impact_map()
        join_n = len(impact)
    except Exception as e:
        audit_tail += f"\njoin-check error: {e}"

    ok = audit_ok and join_n > 0
    status = "complete" if ok else ("threshold_blocked" if not audit_ok else "data_insufficient")
    env = M.job_envelope("JOB3", status, start_ts=M.utc(), end_ts=M.utc(),
                         built=built, build_rc=build_rc, build_tail=build_tail,
                         audit_rc=audit_rc, audit_ok=audit_ok, audit_tail=audit_tail,
                         prior_join_pairs=join_n, products=[str(p) for p in PRODUCTS])
    M.write_artifact(rd, "mj_job03_player_priors.json", env)
    _job.emit(status,
              reason=(f"player priors audited (rc={audit_rc}); join pairs={join_n}" if ok
                      else f"prior audit failed rc={audit_rc} or no join (pairs={join_n})"),
              state_updates={"player_priors_audit_ok": audit_ok, "prior_join_pairs": join_n})


if __name__ == "__main__":
    main()
