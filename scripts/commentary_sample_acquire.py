"""Phase 4: gate-checked sample acquisition. DOWNLOADS ONLY a source classified
open_research_download_allowed with store_raw permitted; everything else is refused with a blocker.
Safe by default (dry-run). Raw goes to gitignored data/raw/commentary only."""
import argparse, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "src"))
from wcdrawlab.research.commentary import source_registry as SR

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True)
    ap.add_argument("--max-matches", type=int, default=10)
    ap.add_argument("--execute", action="store_true")
    a = ap.parse_args()
    cls = SR.classification(a.source)
    permitted = (cls == "open_research_download_allowed") and SR.is_use_permitted(a.source, "store_raw_text")
    if not permitted:
        print(f"BLOCKED: {a.source} classification={cls} -> not open_research_download_allowed (no download).")
        print("  required external action: NDA acceptance / paid license / rights verification (see rights schema).")
        return
    if not a.execute:
        print(f"DRY-RUN: {a.source} is acquisition-eligible ({cls}); would fetch <= {a.max_matches} matches to gitignored data/raw/commentary/.")
        return
    # Eligible open source (currently only soccernet_echoes). Bounded pull would go here.
    print(f"ELIGIBLE: {a.source}. Bounded pull command (run manually to keep large data out of this session):")
    if a.source == "soccernet_echoes":
        print("  huggingface-cli download SoccerNet/SN-echoes --repo-type dataset  # CC BY 4.0; store under data/raw/commentary/soccernet_echoes/ (gitignored)")
    print("  then: python scripts/commentary_normalize.py --source", a.source)

if __name__ == "__main__":
    main()
