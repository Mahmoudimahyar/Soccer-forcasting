import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent)); import _job
def main():
    sh=_job.shared(); corpus=sh.get("corpus_rate",0.0); sb=sh.get("statsbomb_rate",0.0)
    if corpus < 0.95:
        _job.emit("skipped", reason=f"DATA GATE not met: corpus_rate {corpus} < 0.95 -> preregistered eval NOT run on partial data"); return
    if sb < 0.90:
        _job.emit("skipped", reason=f"corpus MET but StatsBomb {sb} < 0.90 + xG join unwired -> eval deferred (anti-shortcut; no eval on incomplete data)"); return
    _job.emit("skipped", reason="data gates met but eval harness not wired in this scope -> deferred (no false completion)")
main()
