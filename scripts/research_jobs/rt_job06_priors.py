import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent)); import _job
def main():
    sh=_job.shared(); rate=sh.get("corpus_rate",0.0)
    if rate < 0.95:
        _job.emit("skipped", reason=f"DATA GATE not met: corpus_rate {rate} < 0.95 -> temporal player priors deferred"); return
    _job.emit("skipped", reason=f"corpus_rate {rate} >= 0.95 (GATE MET) but temporal-prior builder not wired in this scope -> deferred (no false completion)")
main()
