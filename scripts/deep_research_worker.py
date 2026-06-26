"""Deep Research worker: run a SINGLE job script and relay its JSON result. Used by the supervisor's queue
and for manual/parallel execution. research_only."""
import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_job(job_script: str, run_dir: str, timeout: int = 3600):
    script = ROOT / job_script
    if not script.exists():
        return {"status": "failed", "reason": f"missing {job_script}"}
    p = subprocess.run([sys.executable, str(script), "--run-dir", run_dir],
                       capture_output=True, text=True, timeout=timeout, cwd=str(ROOT))
    last = None
    for line in (p.stdout or "").splitlines():
        s = line.strip()
        if s.startswith("{") and s.endswith("}"):
            try:
                last = json.loads(s)
            except Exception:
                pass
    return last or {"status": "failed" if p.returncode else "complete", "reason": (p.stderr or "")[-200:]}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--job-script", required=True)
    a = ap.parse_args()
    print(json.dumps(run_job(a.job_script, a.run_dir)))
