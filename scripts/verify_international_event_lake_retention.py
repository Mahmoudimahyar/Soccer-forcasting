"""verify_international_event_lake_retention — assert retention guarantees hold.

Checks (read-only; never deletes, never git-cleans):
  - every manifest line references an object that still exists with the recorded sha256
    (no valid object was dropped/orphaned),
  - the index is a subset of the manifest history (no index entry without a manifest record),
  - the lake root is external to every git worktree,
  - the objects/ tree contains no object that is referenced by the index but missing on disk.
Exit non-zero if any retention guarantee is violated. research_only.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from wcdrawlab.research import international_event_lake as L  # noqa: E402


def _read_manifest(lake: L.Lake) -> list[dict]:
    if not lake.manifest_jsonl.exists():
        return []
    out = []
    for line in lake.manifest_jsonl.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def main() -> int:
    lake = L.Lake.resolve()
    violations: list[dict] = []

    manifest = _read_manifest(lake)
    index = L.read_index(lake)

    # 1) every manifest-recorded object must still exist with its recorded sha
    for rec in manifest:
        sha = rec.get("sha256")
        obj = lake.object_path(sha) if sha else None
        if not sha or obj is None or not obj.exists():
            violations.append({"sb_match_id": rec.get("sb_match_id"), "reason": "manifest_object_absent",
                               "sha256": sha})
            continue
        if L.sha256_bytes(obj.read_bytes()) != sha:
            violations.append({"sb_match_id": rec.get("sb_match_id"), "reason": "manifest_object_hash_mismatch",
                               "sha256": sha})

    # 2) every index entry must have a manifest record (no index without lineage)
    manifest_shas = {r.get("sha256") for r in manifest}
    for sb_id, rec in index.items():
        if rec.get("sha256") not in manifest_shas:
            violations.append({"sb_match_id": sb_id, "reason": "index_without_manifest_record"})
        obj = lake.root / rec.get("local_path", "")
        if not obj.exists():
            violations.append({"sb_match_id": sb_id, "reason": "indexed_object_missing_on_disk"})

    # 3) lake externality (Lake.resolve already enforces, but assert explicitly)
    norm = str(lake.root).replace("\\", "/")
    external_ok = ("worldcup-international-event-lake" not in norm
                   and "worldcup_draw_model_lab_FINAL" not in norm)
    if not external_ok:
        violations.append({"reason": "lake_root_not_external_to_worktrees", "path": str(lake.root)})

    out = {
        "manifest_records": len(manifest),
        "index_objects": len(index),
        "retention_ok": len(violations) == 0,
        "violation_count": len(violations),
        "violations": violations,
        "lake_root_external": external_ok,
    }
    L.log_run(lake, "retention", out)
    print(json.dumps(out))
    return 0 if out["retention_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
