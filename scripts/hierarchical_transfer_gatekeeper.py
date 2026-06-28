"""Read-only gatekeeper for Hierarchical Cross-Domain Transfer V1. Every 15 min: checks whether the event-lake
dependency is terminal + tagged + report-present + collector-unchanged, and logs readiness. Never writes into the
event-lake worktree; never starts a parallel worker; no external calls. If all conditions are met AND the
hierarchical task is registered, it starts it once; otherwise it only logs. research_only."""
import json, subprocess, time
from datetime import datetime, timezone
from pathlib import Path
LAKEWT = Path("C:/Users/Mahyar/worldcup-international-event-lake")
COLL = Path("C:/Users/Mahyar/worldcup_draw_model_lab_FINAL")
LOG = Path(__file__).resolve().parents[1] / "notes/research/HIERARCHICAL_TRANSFER_DEPENDENCY_STATUS.md"
def _ps(c):
    try: return subprocess.run(["powershell","-NoProfile","-Command",c],capture_output=True,text=True,timeout=30).stdout.strip()
    except Exception: return ""
def main():
    rid_f = LAKEWT/"outputs/research_runs/active_run_id.txt"
    rid = rid_f.read_text(encoding="utf-8").strip() if rid_f.exists() else None
    sp = LAKEWT/f"outputs/research_runs/{rid}/state.json" if rid else None
    jobs = {}
    if sp and sp.exists():
        try: jobs = {k: v.get("status") for k,v in json.loads(sp.read_text(encoding="utf-8"))["jobs"].items()}
        except Exception: pass
    terminal = len(jobs) >= 13 and not any(v == "running" for v in jobs.values())
    tag = subprocess.run(["git","-C",str(LAKEWT),"rev-list","-n1","refs/tags/international-event-lake-restoration-v1"],
                         capture_output=True,text=True).stdout.strip()
    report = (LAKEWT/"notes/research/INTERNATIONAL_EVENT_LAKE_RESTORATION_V1_COMPLETION.md").exists()
    coll = subprocess.run(["git","-C",str(COLL),"rev-parse","--short","HEAD"],capture_output=True,text=True).stdout.strip()
    ready = terminal and bool(tag) and report and coll == "dc73318"
    htask = _ps("try{(Get-ScheduledTask -TaskName WorldCupHierarchicalDomainTransferRun -ErrorAction Stop).State}catch{'ABSENT'}")
    action = "observe"
    if ready and htask not in ("ABSENT","Running"):
        _ps("Start-ScheduledTask -TaskName WorldCupHierarchicalDomainTransferRun"); action = "started_hierarchical_run"
    elif ready and htask == "ABSENT":
        action = "deps_ready: hierarchical worker not yet built (operator builds + registers it)"
    with LOG.open("a", encoding="utf-8") as f:
        f.write(f"\n- gatekeeper {datetime.now(timezone.utc).isoformat()}: event_lake_terminal={terminal} tag={bool(tag)} "
                f"report={report} collector={coll} -> ready={ready} htask={htask} action={action}\n")
    print(json.dumps({"event_lake_terminal": terminal, "tag": bool(tag), "report": report, "collector_ok": coll=="dc73318",
                      "ready": ready, "htask": htask, "action": action}))
if __name__ == "__main__": main()
