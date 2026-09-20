"""Phase 4: source-quality summary for acquired commentary (timing semantics, pub-time presence,
language, dup/correction rate). No-op if no processed sample. research_only."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "src"))

def main():
    proc = ROOT / "data/processed/commentary"
    files = list(proc.glob("*.parquet")) + list(proc.glob("*.csv")) if proc.exists() else []
    if not files:
        print("no processed commentary sample yet -> quality audit pending acquisition (gate-checked)."); return
    print(f"processed commentary files: {len(files)} (run adapter quality summary).")

if __name__ == "__main__":
    main()
