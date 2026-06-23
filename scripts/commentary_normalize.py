"""Phase 4: normalize a raw commentary sample into the canonical contract via the source adapter.
No-op if no raw sample present (gitignored). research_only."""
import argparse, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "src"))

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--source", required=True); a = ap.parse_args()
    raw = ROOT / f"data/raw/commentary/{a.source}"
    if not raw.exists():
        print(f"no raw sample at {raw} (gitignored) -> nothing to normalize. Acquire first (gate-checked)."); return
    print(f"would normalize {a.source} via adapter into canonical records (data/processed/commentary/).")

if __name__ == "__main__":
    main()
