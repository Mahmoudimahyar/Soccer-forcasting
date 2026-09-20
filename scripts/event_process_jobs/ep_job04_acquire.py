import sys,json,subprocess
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent)); import _ep
ROOT=Path(__file__).resolve().parents[2]
def main():
    rd=_ep.run_dir()
    p=subprocess.run([sys.executable,str(ROOT/"scripts/acquire_event_process_auxiliary.py"),"--run-dir",rd],capture_output=True,text=True,cwd=str(ROOT),timeout=28800)
    try: r=json.loads((p.stdout or "").strip().splitlines()[-1])
    except Exception: r={"valid":0,"min_gate_500":False}
    _ep.emit("complete" if r.get("valid",0)>=500 else "skipped",
             reason=f"auxiliary acquired valid={r.get('valid')}/{r.get('total')} min_gate_500={r.get('min_gate_500')} errors={r.get('by_error_class')}",
             state_updates={"aux_valid":r.get("valid"),"aux_gate500":r.get("valid",0)>=500})
main()
