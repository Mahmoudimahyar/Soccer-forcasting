from __future__ import annotations

from pathlib import Path
import sys
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from wcdrawlab.ingest import normalize_worldcup_matches
from wcdrawlab.truth import filter_worldcup_group_stage, write_truth_tables


def main():
    raw_path = ROOT / "data" / "raw" / "jf_worldcup_matches.csv"
    if not raw_path.exists():
        raise SystemExit("Missing data/raw/jf_worldcup_matches.csv. Run: python examples/fetch_public_data.py")
    raw = pd.read_csv(raw_path)
    matches = normalize_worldcup_matches(raw)
    matches = filter_worldcup_group_stage(matches, 1998, 2022)
    paths = write_truth_tables(matches, ROOT / "outputs" / "truth_tables")
    print("Truth tables:")
    for k, v in paths.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
