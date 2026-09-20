import sys,json,subprocess
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent)); import _ep
ROOT=Path(__file__).resolve().parents[2]
def main():
    p=subprocess.run([sys.executable,str(ROOT/"scripts/build_event_process_auxiliary_manifest.py")],capture_output=True,text=True,cwd=str(ROOT),timeout=300)
    try: r=json.loads((p.stdout or "").strip().splitlines()[-1])
    except Exception: r={"selected":0,"min_gate_500":False}
    _ep.emit("complete" if r.get("selected",0)>0 else "failed",
             reason=f"manifest selected={r.get('selected')} min_gate_500={r.get('min_gate_500')}",
             state_updates={"manifest_selected":r.get("selected")})
main()
