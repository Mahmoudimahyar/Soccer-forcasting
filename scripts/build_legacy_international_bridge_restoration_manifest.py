"""JOB: build the legacy bridge RESTORATION manifest (per legacy exact-international-bridge row).

For every row of the canonical exact international bridge (L.load_exact_bridge() — EXACT +
international + allowed-competition; ambiguity-free) record:
  - canonical bridge id + StatsBomb match id
  - competition / season / kickoff date / normalized teams / regulation result
  - the old cache root where its event JSON lives now (and whether a valid file is there)
  - current lake status (present / absent) + current content hash if present
  - retrieval_decision:
        copy_verified_local   - already in lake (hash-verified) OR a valid local file exists -> copy in
        retrieve_official     - no valid local file -> fetch from official open-data into the lake
        quarantine_invalid    - a local file exists but is invalid -> quarantine + retrieve official
        blocked_official      - (reserved) official source cannot serve the match
        excluded_with_reason  - row cannot enter the cohort (missing ids / schema issue)

Outputs:
  data/reference/legacy_international_bridge_restoration_manifest.{csv,json}
  notes/research/legacy_statsbomb_cache_restoration_protocol.md

READ-ONLY w.r.t. local caches and the lake (it inspects and decides; it writes no event objects).
research_only.
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import _lakejob as J
import _lake_catalog_util as U
from wcdrawlab.research import international_event_lake as L


def _local_source_roots(cfg) -> list[Path]:
    roots: list[Path] = []
    for key in ("statsbomb_raw", "statsbomb_raw_prior"):
        sr = (cfg.get("local_source_roots") or {}).get(key)
        if not sr:
            continue
        p = Path(sr)
        if not p.is_absolute():
            p = J.WORKTREE / sr
        roots.append(p)
    return roots


def _find_local(sb_id: int, roots: list[Path]) -> Path | None:
    for root in roots:
        for cand in (root / "events" / f"{sb_id}.json", root / f"{sb_id}.json"):
            if cand.exists() and cand.stat().st_size > 0:
                return cand
    return None


def main(argv=None) -> int:
    run_id = "legacy_restoration_" + U.now_iso().replace(":", "").replace("-", "")
    cfg = L.load_roots()
    bridge = L.load_exact_bridge()
    lake = L.Lake.resolve()
    lake_index = L.read_index(lake)  # {str(sb_id): record}
    source_roots = _local_source_roots(cfg)

    rows: list[dict] = []
    decisions: dict[str, int] = defaultdict(int)

    for sb_id, r in sorted(bridge.items()):
        bridge_id = r.get("bridge_id")
        comp = r.get("competition_label")
        date = U.normalize_date(r.get("kickoff_date"))
        nh = U.normalize_team(r.get("norm_home") or r.get("sb_home"))
        na = U.normalize_team(r.get("norm_away") or r.get("sb_away"))
        reg = U.regulation_result(r.get("api_regulation_home"), r.get("api_regulation_away"))

        if bridge_id is None:
            rows.append({"bridge_id": "", "sb_match_id": sb_id, "competition_label": comp,
                         "kickoff_date": date, "norm_home": nh, "norm_away": na,
                         "regulation_result": reg, "old_cache_root": "", "local_file_status": "n/a",
                         "local_sha256": "", "lake_status": "n/a", "lake_sha256": "",
                         "retrieval_decision": "excluded_with_reason", "reason": "missing canonical id"})
            decisions["excluded_with_reason"] += 1
            continue

        local_fp = _find_local(sb_id, source_roots)
        old_root = str(local_fp.parent) if local_fp is not None else ""
        local_status, local_sha = "absent", ""
        if local_fp is not None:
            raw = local_fp.read_bytes()
            vr = L.validate_event_bytes(raw)
            if vr.ok:
                local_status, local_sha = "valid", L.sha256_bytes(raw)
            else:
                local_status = "invalid"

        in_lake = str(sb_id) in lake_index
        lake_sha = lake_index.get(str(sb_id), {}).get("sha256", "") if in_lake else ""
        lake_status = "present" if in_lake else "absent"

        if in_lake:
            decision, reason = "copy_verified_local", "already in lake (hash-verified)"
        elif local_status == "valid":
            decision, reason = "copy_verified_local", f"valid local file at {old_root}"
        elif local_status == "invalid":
            decision, reason = "quarantine_invalid", "local file invalid (empty/html/json/non-event-list)"
        else:
            decision, reason = "retrieve_official", "no valid local file; fetch from official open-data"

        rows.append({"bridge_id": bridge_id, "sb_match_id": sb_id, "competition_label": comp,
                     "kickoff_date": date, "norm_home": nh, "norm_away": na,
                     "regulation_result": reg, "old_cache_root": old_root,
                     "local_file_status": local_status, "local_sha256": local_sha,
                     "lake_status": lake_status, "lake_sha256": lake_sha,
                     "retrieval_decision": decision, "reason": reason})
        decisions[decision] += 1

    fields = ["bridge_id", "sb_match_id", "competition_label", "kickoff_date", "norm_home",
              "norm_away", "regulation_result", "old_cache_root", "local_file_status",
              "local_sha256", "lake_status", "lake_sha256", "retrieval_decision", "reason"]
    J.write_csv(J.REFERENCE / "legacy_international_bridge_restoration_manifest.csv", rows, fields)
    J.write_json(J.REFERENCE / "legacy_international_bridge_restoration_manifest.json", {
        "schema_version": "legacy_international_bridge_restoration_v1",
        "run_id": run_id, "built_ts": U.now_iso(),
        "legacy_bridge_rows": len(bridge), "lake_objects_present": len(lake_index),
        "decision_counts": dict(decisions), "rows": rows,
    })

    summary = {"legacy_bridge_rows": len(bridge), "lake_objects_present": len(lake_index),
               "decision_counts": dict(decisions)}

    protocol = J.NOTES / "legacy_statsbomb_cache_restoration_protocol.md"
    protocol.parent.mkdir(parents=True, exist_ok=True)
    protocol.write_text(f"""# Legacy StatsBomb Cache Restoration Protocol

run_id: `{run_id}`  built_ts: {U.now_iso()}

## Purpose
Restore the durable event lake for the legacy exact international bridge ({len(bridge)} rows) without
re-downloading any file that already exists locally as valid + hash-verified. External retrieval is
**official StatsBomb Open Data only** (`raw.githubusercontent.com/statsbomb/open-data`).

## Decision rule (per bridge row)
1. **copy_verified_local** — already in the lake (hash-verified) OR a valid local event file exists
   under a prior cache root. Copy bytes into the lake atomically (tmp -> validate -> sha256 ->
   atomic rename -> immutable manifest append). Never re-download.
2. **retrieve_official** — no valid local file. Fetch `events/<sb_match_id>.json` from the official
   open-data path (<=4 concurrent, <=2 retries, exponential backoff, atomic, sha256).
3. **quarantine_invalid** — a local file exists but fails validation (empty / HTML / invalid JSON /
   non-event-list). Quarantine it and treat the match as retrieve_official.
4. **blocked_official** — reserved for the case where the official source cannot serve the match
   (permanent 404). Such rows never enter evaluation.
5. **excluded_with_reason** — the row lacks a canonical/StatsBomb id and cannot be bridged. It never
   enters any cohort, fit, calibration, or selection.

## Integrity (fail-closed)
Every written object is content-addressed and re-verifiable. The sentinel fails closed on
manifest-present-but-absent, hash mismatch, empty file, HTML/error body, invalid JSON,
non-event-list, ambiguous id, filename/hash disagreement, or an object under an unregistered root.

## Current state
- legacy bridge rows: **{len(bridge)}**
- objects already in lake (hash-verified): **{len(lake_index)}**
- decisions: {json.dumps(dict(decisions))}

## Cohort discipline
Senior men's international only; historical cutoff before the 2026 World Cup; no completed-2026-WC
match in any cohort/fit/calibration/selection. Match-level bootstrap only (independent unit = MATCH).
Ambiguous rows never enter evaluation.
""", encoding="utf-8")

    print(json.dumps(summary))
    return 0


if __name__ == "__main__":
    sys.exit(main())
