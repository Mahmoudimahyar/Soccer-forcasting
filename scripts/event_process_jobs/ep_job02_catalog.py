import sys,json,subprocess
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent)); import _ep
ROOT=Path(__file__).resolve().parents[2]
def main():
    if (ROOT/"data/reference/statsbomb_event_process_catalog.csv").exists():
        import csv; n=len(list(csv.DictReader(open(ROOT/"data/reference/statsbomb_event_process_catalog.csv",encoding="utf-8"))))
        _ep.emit("complete",reason=f"catalog present ({n} men matches)",state_updates={"catalog_matches":n}); return
    p=subprocess.run([sys.executable,str(ROOT/"scripts/build_statsbomb_event_process_catalog.py")],capture_output=True,text=True,cwd=str(ROOT),timeout=900)
    _ep.emit("complete" if p.returncode==0 else "failed",reason=(p.stdout or p.stderr or "").strip()[-160:])
main()
