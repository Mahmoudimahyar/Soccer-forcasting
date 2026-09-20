import sys, json, subprocess
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent)); import _job
ROOT = Path(__file__).resolve().parents[2]
def main():
    sh=_job.shared(); sb=sh.get("statsbomb_rate",0.0); corpus=sh.get("corpus_rate",0.0)
    if sb < 0.90 or corpus < 0.95:
        _job.emit("skipped", reason=f"DATA GATE not met: statsbomb_rate {sb} < 0.90 or corpus_rate {corpus} < 0.95 -> xG join deferred"); return
    subprocess.run([sys.executable, str(ROOT/"scripts/join_complete_xg_into_dynamic_snapshots.py")],
                   capture_output=True, text=True, cwd=str(ROOT), timeout=1800)
    au = subprocess.run([sys.executable, str(ROOT/"scripts/audit_complete_xg_snapshot_join.py")],
                        capture_output=True, text=True, cwd=str(ROOT))
    a={}
    try: a=json.loads(au.stdout.strip().splitlines()[-1])
    except Exception: pass
    n=a.get("xg_eligible_international_snapshots",0)
    ok = a.get("ok",False) and n>0
    _job.emit("complete" if ok else "failed",
              reason=f"xG join audited: nonzero={n>0} xg_eligible_snapshots={n} matches={a.get('distinct_matches')} checks_ok={a.get('ok')}",
              state_updates={"xg_snapshots": n, "xg_join_nonzero": n>0})
main()
