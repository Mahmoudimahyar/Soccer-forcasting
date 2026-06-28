"""Shared bootstrap for international-event-lake jobs: add src/ to sys.path so both
`international_event_lake` and `wcdrawlab.research.data_roots` resolve, and provide small
CSV/JSON writers. research_only."""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

WORKTREE = Path(__file__).resolve().parents[1]
SRC = WORKTREE / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

REFERENCE = WORKTREE / "data" / "reference"
NOTES = WORKTREE / "notes" / "research"


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1, ensure_ascii=False), encoding="utf-8")


def write_csv(path: Path, rows: list[dict], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fn = fieldnames or list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fn)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fn})
