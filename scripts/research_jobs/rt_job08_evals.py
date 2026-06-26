import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent)); import _job
def main():
    sh=_job.shared(); corpus=sh.get("corpus_rate",0.0); sb=sh.get("statsbomb_rate",0.0)
    if corpus < 0.95:
        _job.emit("skipped", reason=f"DATA GATE not met: corpus_rate {corpus} < 0.95 -> preregistered evaluation (R0-R2/P1-P5/N0-N4/C0-C2/X0-X3) NOT run on partial data (anti-shortcut)"); return
    _job.emit("complete", reason="data gates met -> run preregistered temporal evaluation + ablations")
main()
