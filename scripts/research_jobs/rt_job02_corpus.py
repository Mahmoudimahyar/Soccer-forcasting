import sys, json, subprocess
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent)); import _job
ROOT = Path(__file__).resolve().parents[2]
def main():
    rd = Path(_job.run_dir()); budget = _job.api_budget()
    p = subprocess.run([sys.executable, str(ROOT/"scripts/complete_full_player_history_backfill.py"),
                        "--max-requests", str(max(0, budget))], capture_output=True, text=True, cwd=str(ROOT))
    last = None
    for line in (p.stdout or "").splitlines():
        s=line.strip()
        if s.startswith("{") and s.endswith("}"):
            try: last=json.loads(s)
            except Exception: pass
    last = last or {"state":"FAILED_INTEGRITY","api_requests":0,"completion_rate":0.0}
    (rd/"job02_corpus.json").write_text(json.dumps(last, indent=2), encoding="utf-8")
    run_state = last.get("state","RUNNING"); rate = last.get("completion_rate",0.0)
    # bounded acquisition is a successful job step even when budget pauses it (WAITING_FOR_API_QUOTA)
    status = "failed" if run_state=="FAILED_INTEGRITY" else "complete"
    _job.emit(status, reason=f"corpus state={run_state} rate={rate} (gate95={rate>=0.95}) pulled={last.get('pulled_this_run')}",
              api_requests=last.get("api_requests",0),
              state_updates={"run_state": run_state, "corpus_rate": rate, "corpus_gate95": rate>=0.95})
main()
