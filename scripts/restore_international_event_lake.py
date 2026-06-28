"""restore_international_event_lake — COPY valid local StatsBomb event files into the lake.

Scans the read-only local source roots (statsbomb_raw + statsbomb_raw_prior), and for every
EXACT-international-bridge match id whose local event file is valid + hash-verified, copies it into
the content-addressed lake atomically with an immutable manifest append. NEVER re-downloads a file
that is already locally valid. Invalid/ambiguous payloads go to quarantine, never the index.

EXTERNAL retrieval is intentionally NOT performed here (this is a restore-from-local step).
research_only. StatsBomb Open Data only.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from wcdrawlab.research import international_event_lake as L  # noqa: E402


def _candidate_event_files(source_root: Path) -> dict[int, Path]:
    """Map sb_match_id -> event json path under a source root (events/<id>.json or <id>.json)."""
    out: dict[int, Path] = {}
    if not source_root.exists():
        return out
    # canonical layout: <root>/events/<id>.json ; also accept <root>/<id>.json
    for p in list(source_root.glob("events/*.json")) + list(source_root.glob("*.json")):
        stem = p.stem
        if not stem.isdigit():
            continue
        sb_id = int(stem)
        out.setdefault(sb_id, p)  # first source wins (canonical before prior, see ordering)
    return out


def main() -> int:
    run_id = "restore_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lake = L.Lake.resolve()
    for d in (lake.objects, lake.indexes, lake.manifests, lake.quarantine, lake.integrity, lake.logs):
        d.mkdir(parents=True, exist_ok=True)

    bridge = L.load_exact_bridge()
    cfg = L.load_roots()
    url_tmpl = cfg["official_event_url_template"]

    # canonical root first, then prior (first-write-wins on the object; idempotent on identical bytes)
    source_roots: list[Path] = []
    for key in ("statsbomb_raw", "statsbomb_raw_prior"):
        sr = cfg["local_source_roots"].get(key)
        if sr:
            p = Path(sr)
            if not p.is_absolute():
                p = Path(__file__).resolve().parents[1] / sr
            source_roots.append(p)

    index = L.read_index(lake)
    copied, skipped_present, quarantined, not_in_bridge = 0, 0, 0, 0
    seen_ids: set[int] = set()

    for source_root in source_roots:
        for sb_id, path in sorted(_candidate_event_files(source_root).items()):
            if sb_id in seen_ids:
                continue
            # strict EXACT international bridge gate
            if sb_id not in bridge:
                not_in_bridge += 1
                continue
            seen_ids.add(sb_id)

            raw = path.read_bytes()
            vr = L.validate_event_bytes(raw)
            if not vr.ok:
                L.quarantine_payload(lake, sb_match_id=sb_id, raw=raw, reason=vr.reason, source=str(path))
                quarantined += 1
                continue

            sha = L.sha256_bytes(raw)
            already = str(sb_id) in index and index[str(sb_id)].get("sha256") == sha
            obj = lake.object_path(sha)
            if already and obj.exists():
                skipped_present += 1
                continue

            rec = L.store_object(
                lake,
                sb_match_id=sb_id,
                raw=raw,
                source_url=url_tmpl.format(sb_match_id=sb_id),
                ingestion_mode="copied_local",
                ingestion_run_id=run_id,
                bridge_row=bridge.get(sb_id),
                copied_from=str(path),
            )
            index[str(sb_id)] = rec
            copied += 1

    L.write_index(lake, index)

    out = {
        "run_id": run_id,
        "bridge_exact_international": len(bridge),
        "objects_copied": copied,
        "objects_already_present": skipped_present,
        "quarantined": quarantined,
        "candidates_not_in_exact_bridge": not_in_bridge,
        "lake_object_count": len(index),
    }
    L.log_run(lake, "restore", out)
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
