import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent)); import _job
def main():
    rd = Path(_job.run_dir()); sh = _job.shared()
    intl = json.loads((rd/"snapshots_intl.json").read_text(encoding="utf-8"))
    matches = len({r["match_id"] for r in intl})
    wdl = {"H":0,"D":0,"A":0}; ng=0
    for r in intl: wdl[r["target_wdl"]]+=1; ng+=r["next_goal_15"]
    so = sh.get("sendings_off", 0)
    res = {"intl_matches": matches, "player_sub_ready": matches>=500, "next_goal_ready": matches>=500,
           "inplay_wdl_ready": matches>=500, "discipline_C1_ready": so>=150, "sendings_off": so,
           "wdl_balance": wdl, "next_goal_rate": round(ng/len(intl),4) if intl else None}
    (rd/"job05_readiness.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    _job.emit("complete", reason=f"intl_matches={matches} C1_ready={so>=150}",
              state_updates={"intl_matches": matches, "C1_ready": so>=150})
main()
