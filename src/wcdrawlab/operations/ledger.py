"""Immutable, append-only, first-write-wins prediction ledger (JSONL).

A prediction, once written for a given (match, capture key), is NEVER overwritten — so it stays a true
point-in-time forecast even if the collector re-runs after the result is known. Idempotent: re-writing
the same key is a no-op. No silent backfill.
"""
from __future__ import annotations

import json
from pathlib import Path


class ImmutableLedger:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def keys(self) -> set:
        if not self.path.exists():
            return set()
        out = set()
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                out.add(json.loads(line)["ledger_key"])
        return out

    def records(self) -> list:
        if not self.path.exists():
            return []
        return [json.loads(l) for l in self.path.read_text(encoding="utf-8").splitlines() if l.strip()]

    def record(self, ledger_key: str, payload: dict) -> dict:
        """First-write-wins. Returns {'wrote': bool, 'ledger_key': key}."""
        if ledger_key in self.keys():
            return {"wrote": False, "ledger_key": ledger_key, "reason": "exists (first-write-wins)"}
        row = {"ledger_key": ledger_key, **payload}
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, sort_keys=True) + "\n")
        return {"wrote": True, "ledger_key": ledger_key}
