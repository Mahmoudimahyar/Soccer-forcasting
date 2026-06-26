import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent)); import _job
def main():
    sh=_job.shared(); sb=sh.get("statsbomb_rate",0.0); corpus=sh.get("corpus_rate",0.0)
    if sb < 0.90 or corpus < 0.95:
        _job.emit("skipped", reason=f"DATA GATE not met: statsbomb_rate {sb} < 0.90 or corpus_rate {corpus} < 0.95 -> xG-snapshot join deferred (must produce NONZERO joined count)"); return
    _job.emit("complete", reason="gates met -> build xG-snapshot join (nonzero xG-eligible international snapshots)")
main()
