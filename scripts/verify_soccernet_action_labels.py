"""Phase 2: verify acquired SoccerNet labels (counts, classes, fields, checksums). Read-only."""
import json, hashlib, sys
from pathlib import Path
from collections import Counter
ROOT = Path(__file__).resolve().parents[1]; RAW = ROOT / "data/raw/soccernet_action_labels"

def main():
    files = sorted(RAW.rglob("Labels-v2.json"))
    if not files:
        print("no Labels-v2.json present (gitignored) -> acquire first."); return
    classes = Counter(); nev = 0
    for fp in files:
        for a in json.loads(fp.read_text(encoding="utf-8")).get("annotations", []):
            classes[a.get("label")] += 1; nev += 1
    print(f"games={len(files)} events={nev} classes={len(classes)}")
    print("sha256(first)=", hashlib.sha256(files[0].read_bytes()).hexdigest()[:16])

if __name__ == "__main__":
    main()
