"""Phase 3: corpus backfill status (counts only; no secrets). research_only."""
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/api_football_historical_corpus"
def main():
    prog = RAW / "progress.json"
    done = len(json.loads(prog.read_text(encoding="utf-8"))["done"]) if prog.exists() else 0
    man = ROOT / "data/reference/api_football_corpus_fixture_manifest.json"
    included = sum(1 for f in json.loads(man.read_text(encoding="utf-8"))["fixtures"] if f["eligibility"] == "included") if man.exists() else 0
    cm = RAW / "corpus_manifest.jsonl"
    lines = sum(1 for _ in cm.open(encoding="utf-8")) if cm.exists() else 0
    print(json.dumps({"fixtures_done": done, "included_target": included, "manifest_rows": lines}))
if __name__ == "__main__":
    main()
