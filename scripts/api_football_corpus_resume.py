"""Phase 3: resume the corpus backfill (skips fixtures already in progress.json). research_only."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import api_football_corpus_backfill as B
if __name__ == "__main__":
    B.main()
