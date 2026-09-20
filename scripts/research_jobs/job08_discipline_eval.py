import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent)); import _job
def main():
    rd = Path(_job.run_dir()); sh = _job.shared()
    so = sh.get("sendings_off", 0)
    intl = json.loads((rd/"snapshots_intl.json").read_text(encoding="utf-8"))
    # C0: yellow-card base-rate hazard (per snapshot, P that a card already shown) -> base discipline rate
    yellow_rate = round(sum(1 for r in intl if r["card_diff"]!=0)/len(intl),4) if intl else None
    res = {"C0_yellow_state_rate": yellow_rate, "sendings_off": so,
           "C1_sending_off_model": "run" if so>=150 else "SKIPPED",
           "C1_skip_reason": None if so>=150 else f"sendings_off {so} < 150 (preregistered threshold)"}
    (rd/"job08_discipline.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    status = "complete" if so>=150 else "skipped"
    _job.emit(status, reason=(f"C0 done; C1 {'run' if so>=150 else 'skipped (so='+str(so)+'<150)'}"),
              state_updates={"C1_run": so>=150})
main()
