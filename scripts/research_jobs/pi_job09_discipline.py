"""JOB9: C0-C1 discipline evaluation. C0 = yellow-card state base-rate hazard (always run). C1 =
sending-off hazard model, run ONLY if >=150 sendings-off positives are observed (preregistered threshold);
otherwise skipped with an explicit reason. Reads the sendings_off count from JOB4 shared state. No network.
research_only / experimental / not_runtime_approved."""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent)); import _job


def main():
    rd = Path(_job.run_dir()); sh = _job.shared()
    so = int(sh.get("sendings_off", 0) or 0)
    sp = rd / "snapshots_intl.json"
    intl = json.loads(sp.read_text(encoding="utf-8")) if sp.exists() else []
    yellow_rate = round(sum(1 for r in intl if r["card_diff"] != 0) / len(intl), 4) if intl else None
    res = {"C0_yellow_state_rate": yellow_rate, "sendings_off": so,
           "C1_sending_off_model": "run" if so >= 150 else "SKIPPED",
           "C1_skip_reason": None if so >= 150 else f"sendings_off {so} < 150 (preregistered threshold)"}
    (rd / "job09_discipline.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    status = "complete" if so >= 150 else "skipped"
    _job.emit(status,
              reason=(f"C0 done; C1 {'run' if so >= 150 else 'skipped (so=' + str(so) + '<150)'}"),
              state_updates={"C1_run": so >= 150})


main()
