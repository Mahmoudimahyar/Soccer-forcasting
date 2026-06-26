"""Phase 3: resume the bounded backfill. The backfill is inherently resumable (skips fixtures already in
progress.json); this wrapper re-invokes it under the same hard cap. research_only.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import api_football_historical_backfill as B

if __name__ == "__main__":
    B.main()  # reads progress.json, skips completed fixtures, continues under the 300-request cap
