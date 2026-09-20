"""JOB2 -- REBUILD canonical DYNAMIC in-play snapshot datasets. research_only.

Idempotently (re)builds the leakage-safe dynamic snapshot panel by invoking the canonical builder
``scripts/build_dynamic_inplay_panel.py`` as a subprocess (the same builder that produced the validated
parquet family under data/processed/model_phase). Resume-safe: if the full product family is already present
AND non-empty AND consistent with the build summary, the job records that and re-affirms counts WITHOUT a
needless rebuild (still real -- it verifies the on-disk products, never fabricates).

Emits complete when the international decision-minute panel + xG-enriched product exist with >0 rows;
data_insufficient (honest) if the builder cannot produce the international regulation product.
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

BUILDER = M.ROOT / "scripts/build_dynamic_inplay_panel.py"
REQUIRED = [M.IRS_PARQUET, M.XG_ENRICHED_PARQUET, M.NEXTGOAL_PARQUET, M.DISCIPLINE_PARQUET]


def _products_ok():
    import pandas as pd
    if not all(p.exists() for p in REQUIRED):
        return False, "missing product(s): " + ", ".join(p.name for p in REQUIRED if not p.exists())
    try:
        irs = pd.read_parquet(M.IRS_PARQUET)
        n_intl = int((irs["comp_type"] == "international").sum())
        if n_intl <= 0:
            return False, "international_regulation_state has 0 international rows"
        return True, f"international rows={n_intl}"
    except Exception as e:
        return False, f"product read error: {e}"


def main():
    rd = _job.run_dir()
    M.assert_not_collector(BUILDER, *REQUIRED)

    ok, detail = _products_ok()
    rebuilt = False
    builder_rc = None
    builder_tail = ""
    if not ok:
        if not BUILDER.exists():
            env = M.job_envelope("JOB2", "data_insufficient", start_ts=M.utc(), end_ts=M.utc(),
                                 reason="builder script absent and products missing", detail=detail)
            M.write_artifact(rd, "mj_job02_rebuild_snapshots.json", env)
            _job.emit("data_insufficient", reason="builder missing; cannot rebuild snapshots")
            return
        p = subprocess.run([sys.executable, str(BUILDER)], capture_output=True, text=True, cwd=str(M.ROOT))
        builder_rc = p.returncode
        builder_tail = (p.stdout or "")[-400:] + (("\nSTDERR:" + (p.stderr or "")[-400:]) if p.stderr else "")
        rebuilt = True
        ok, detail = _products_ok()

    if not ok:
        env = M.job_envelope("JOB2", "data_insufficient", start_ts=M.utc(), end_ts=M.utc(),
                             reason=detail, builder_rc=builder_rc, builder_tail=builder_tail)
        M.write_artifact(rd, "mj_job02_rebuild_snapshots.json", env)
        _job.emit("data_insufficient", reason=f"snapshot products unavailable after build: {detail}")
        return

    # affirm counts via the loader (which also proves the join is consistent)
    try:
        wdl = M.load_wdl_rows()
        cov = M.coverage_counts(wdl)
    except M.DataInsufficient as e:
        env = M.job_envelope("JOB2", "data_insufficient", start_ts=M.utc(), end_ts=M.utc(), reason=str(e))
        M.write_artifact(rd, "mj_job02_rebuild_snapshots.json", env)
        _job.emit("data_insufficient", reason=str(e))
        return

    env = M.job_envelope("JOB2", "complete", start_ts=M.utc(), end_ts=M.utc(),
                         rebuilt=rebuilt, builder_rc=builder_rc, builder_tail=builder_tail,
                         products=[str(p) for p in REQUIRED], wdl_coverage=cov, detail=detail)
    M.write_artifact(rd, "mj_job02_rebuild_snapshots.json", env)
    _job.emit("complete",
              reason=("rebuilt+verified " if rebuilt else "verified existing ")
              + f"dynamic snapshot panel ({cov['n_rows']} intl decision rows / {cov['n_matches']} matches)",
              state_updates={"n_wdl_rows": cov["n_rows"], "n_wdl_matches": cov["n_matches"]})


if __name__ == "__main__":
    main()
