"""JOB: (re)build the International Event Lake index from the lake's immutable append-only manifest,
then run the canonical fail-closed sentinel.

Reads manifests/international_event_lake_manifest_v1.jsonl (first-write-wins per sb_match_id),
rewrites the canonical index (JSON + JSONL) via L.write_index, and runs L.run_sentinel. Coverage is
RAW-BACKED: an object is only counted when it exists on disk and hash-verifies against its record.
It never fabricates records. research_only.
"""
from __future__ import annotations

import json
import sys

import _lakejob as J
from wcdrawlab.research import international_event_lake as L


def main(argv=None) -> int:
    lake = L.Lake.resolve()
    for d in (lake.objects, lake.indexes, lake.manifests, lake.quarantine, lake.integrity, lake.logs):
        d.mkdir(parents=True, exist_ok=True)

    # Reconstruct the index from the immutable manifest (first-write-wins per sb_match_id).
    objects: dict[str, dict] = {}
    n_lines = 0
    if lake.manifest_jsonl.exists():
        for line in lake.manifest_jsonl.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            n_lines += 1
            try:
                rec = json.loads(line)
            except Exception:
                continue
            key = str(rec.get("sb_match_id"))
            if key and key not in objects:
                objects[key] = rec

    L.write_index(lake, objects)
    sentinel = L.run_sentinel(lake, write_report=True)

    # RAW-BACKED verified count.
    verified = 0
    for rec in objects.values():
        obj = lake.root / rec["local_path"]
        if obj.exists() and L.sha256_bytes(obj.read_bytes()) == rec["sha256"]:
            verified += 1

    summary = {
        "manifest_lines": n_lines,
        "index_object_count": len(objects),
        "hash_verified_objects": verified,
        "integrity_all_ok": sentinel.ok,
        "integrity_failures": len(sentinel.failures),
    }
    J.write_json(J.REFERENCE / "international_event_lake_index_summary.json", {
        "schema_version": "international_event_lake_manifest_v1",
        "lake_root": str(lake.root),
        "updated_ts": L._utc_now(),
        "object_count": len(objects),
        "hash_verified_objects": verified,
        "integrity_all_ok": sentinel.ok,
    })
    L.log_run(lake, "build_manifest", summary)
    print(json.dumps(summary))
    return 0 if sentinel.ok else 2


if __name__ == "__main__":
    sys.exit(main())
