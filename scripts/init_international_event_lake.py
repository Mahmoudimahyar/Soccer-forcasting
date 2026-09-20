"""init_international_event_lake — validate the persistent lake structure + write manifest skeleton.

Creates (idempotently) the lake sub-tree (objects/indexes/manifests/quarantine/integrity/logs),
writes an empty index skeleton if none exists, and verifies the lake lives OUTSIDE every git
worktree. Never deletes anything. research_only.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from wcdrawlab.research import international_event_lake as L  # noqa: E402


def main() -> int:
    lake = L.Lake.resolve()
    for d in (lake.root, lake.objects, lake.indexes, lake.manifests,
              lake.quarantine, lake.integrity, lake.logs):
        d.mkdir(parents=True, exist_ok=True)

    created_index = False
    if not lake.index_json.exists():
        L.write_index(lake, {})  # empty skeleton
        created_index = True
    if not lake.manifest_jsonl.exists():
        lake.manifest_jsonl.write_text("", encoding="utf-8")

    index = L.read_index(lake)
    out = {
        "lake_root": str(lake.root),
        "subdirs_ok": all(d.is_dir() for d in (
            lake.objects, lake.indexes, lake.manifests, lake.quarantine, lake.integrity, lake.logs)),
        "index_created": created_index,
        "object_count": len(index),
        "manifest_exists": lake.manifest_jsonl.exists(),
    }
    L.log_run(lake, "init", out)
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
