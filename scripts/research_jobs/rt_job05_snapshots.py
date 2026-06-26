import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent)); import _job
def main():
    sh=_job.shared(); rate=sh.get("corpus_rate",0.0)
    if rate < 0.95:
        _job.emit("skipped", reason=f"DATA GATE not met: corpus_rate {rate} < 0.95 -> dynamic snapshot rebuild deferred"); return
    # corpus gate MET, but the dynamic-snapshot builder is out of scope for the quota-reserve task -> do NOT
    # claim false completion; leave as an honest deferred step for the next phase.
    _job.emit("skipped", reason=f"corpus_rate {rate} >= 0.95 (GATE MET) but dynamic-snapshot builder not wired in this scope -> deferred (no false completion)")
main()
