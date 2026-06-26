import sys, subprocess, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent)); import _job
ROOT = Path(__file__).resolve().parents[2]
def main():
    _job.run_dir()
    jobs = [f"scripts/research_jobs/job{n:02d}_{s}.py" for n,s in
            [(1,"validate"),(2,"extension_backfill"),(3,"reconcile_quality"),(4,"build_datasets"),
             (5,"readiness"),(6,"wdl_eval"),(7,"nextgoal_eval"),(8,"discipline_eval"),(9,"transfer"),
             (10,"calibration_failure"),(11,"summary")]]
    missing = [j for j in jobs if not (ROOT/j).exists()]
    r = subprocess.run([sys.executable,"-m","pytest","-q","tests/test_deep_research_controller.py",
                        "tests/test_result_semantics.py","tests/test_historical_datasets.py"],
                       capture_output=True, text=True, cwd=str(ROOT))
    ok = r.returncode == 0 and not missing
    _job.emit("complete" if ok else "failed",
              reason=("all job scripts present; unit tests pass" if ok else f"missing={missing} tests_rc={r.returncode}"))
main()
