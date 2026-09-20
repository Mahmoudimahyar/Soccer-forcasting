"""Phase 5: event-taxonomy coverage check against the canonical taxonomy. research_only."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "src"))
from wcdrawlab.research.commentary.contracts import EVENT_TAXONOMY

def main():
    print(f"canonical event taxonomy: {len(EVENT_TAXONOMY)} classes")
    for e in sorted(EVENT_TAXONOMY): print("  -", e)
    print("per-event-type quality requires a permitted aligned sample (pending NDA/license).")

if __name__ == "__main__":
    main()
