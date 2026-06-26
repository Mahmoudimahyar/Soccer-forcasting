import sys, json, subprocess
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent)); import _job
ROOT = Path(__file__).resolve().parents[2]
def main():
    rd = _job.run_dir()
    # 1) official-source availability probe (deterministic) — fail closed to WAITING_FOR_SOURCE if unavailable
    pr = subprocess.run([sys.executable, str(ROOT/"scripts/complete_statsbomb_event_cache.py"), "--probe", "3"],
                        capture_output=True, text=True, cwd=str(ROOT))
    avail = False
    try: avail = json.loads(pr.stdout).get("official_source_available", False)
    except Exception: pass
    if not avail:
        _job.emit("skipped", reason="official StatsBomb source probe FAILED -> WAITING_FOR_SOURCE (verified block)",
                  state_updates={"run_state":"WAITING_FOR_SOURCE"}); return
    # 2) full bounded cache completion (<=4 concurrent, resumable, append-only)
    subprocess.run([sys.executable, str(ROOT/"scripts/complete_statsbomb_event_cache.py"), "--run-dir", rd],
                   capture_output=True, text=True, cwd=str(ROOT), timeout=7200)
    # 3) audit -> valid exact-bridge completion rate (gate ceil(0.90*258)=233)
    au = subprocess.run([sys.executable, str(ROOT/"scripts/audit_statsbomb_event_cache.py")],
                        capture_output=True, text=True, cwd=str(ROOT))
    a = {}
    try: a = json.loads(au.stdout.strip().splitlines()[-1])
    except Exception: a = {"completion_rate":0.0,"gate_90pct_met":False,"valid_cached":0}
    rate = a.get("completion_rate",0.0)
    _job.emit("complete" if a.get("gate_90pct_met") else "skipped",
              reason=f"StatsBomb cache valid={a.get('valid_cached')}/{a.get('total_exact_bridge')} rate={rate} "
                     f"gate90={a.get('gate_90pct_met')} xg_fields={a.get('xg_field_available')}",
              state_updates={"statsbomb_rate":rate,"statsbomb_gate90":a.get("gate_90pct_met",False),
                             "statsbomb_valid":a.get("valid_cached"),"run_state":"RUNNING"})
main()
