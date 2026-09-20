"""Resume player-history backfill (idempotent; skips done)."""
import sys; from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent)); import player_history_backfill as B
if __name__=="__main__": B.main()
