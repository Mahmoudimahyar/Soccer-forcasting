"""JOB6 (durable acquisition): bring missing/invalid event JSON INTO THE LAKE for the EXACT
international bridge matches, built entirely on the canonical lake engine
(wcdrawlab.research.international_event_lake).

Per match, in priority order:
  1. copy a VALID + hash-verified local file (prior StatsBomb cache) into the lake — never re-download
  2. otherwise retrieve `events/<sb_match_id>.json` from OFFICIAL StatsBomb Open Data only
     (raw.githubusercontent.com/statsbomb/open-data), <=4 concurrent, first-write-wins,
     exponential backoff, <=2 retries.

Every write goes through L.store_object (validate -> sha256 -> atomic tmp->rename -> immutable
manifest append). Invalid bodies are quarantined via L.quarantine_payload (fail-closed) and never
indexed. Richness (xg/possession/location) is recorded by the engine; the engine also records
source_url + retrieval_ts.

Cohort: senior men's international only; EXACT bridge only; historical cutoff before the 2026 WC
(the bridge contains no completed-2026-WC match).

By default this performs LOCAL COPIES ONLY (no network). Pass --allow-network to enable official
retrieval of matches with no valid local file. Use --limit to bound a run.

research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import _lakejob as J  # noqa: F401  (ensures src on path)
from wcdrawlab.research import international_event_lake as L

MAX_CONCURRENCY = 4
MAX_RETRIES = 2
USER_AGENT = "wcdrawlab-research/1.0 (StatsBomb open-data, non-commercial research; resumable GET)"


def _official_get(url: str, timeout: int = 60) -> bytes:
    if not url.startswith("https://") or "raw.githubusercontent.com" not in url \
            or "/statsbomb/open-data/" not in url:
        raise ValueError(f"non-official url refused: {url}")
    last: Exception | None = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=timeout) as r:  # nosec B310 (https official public)
                return r.read()
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (404, 410):
                raise
            time.sleep(min(8.0, 0.5 * (2 ** attempt)))
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(min(8.0, 0.5 * (2 ** attempt)))
    raise RuntimeError(f"official GET failed: {url}: {last}")


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
    ap = argparse.ArgumentParser(description="Acquire missing/invalid official international events into the lake.")
    ap.add_argument("--limit", type=int, default=0, help="max matches to attempt this run (0 = all eligible)")
    ap.add_argument("--allow-network", action="store_true",
                    help="enable OFFICIAL retrieval for matches with no valid local file")
    ap.add_argument("--concurrency", type=int, default=MAX_CONCURRENCY)
    args = ap.parse_args(argv)

    run_id = "acquire_" + time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    cfg = L.load_roots()
    url_tmpl = cfg["official_event_url_template"]
    bridge = L.load_exact_bridge()
    source_roots = _local_source_roots(cfg)

    lake = L.Lake.resolve()
    for d in (lake.objects, lake.indexes, lake.manifests, lake.quarantine, lake.integrity, lake.logs):
        d.mkdir(parents=True, exist_ok=True)
    index = L.read_index(lake)

    actions = {"already_in_lake": 0, "copied_local": 0, "retrieved_official": 0,
               "quarantined": 0, "fetch_error": 0, "skipped_no_network": 0}

    attempted = 0
    pending_official: list[int] = []

    # Pass 1: local copies (no network)
    for sb_id in sorted(bridge):
        if str(sb_id) in index:
            actions["already_in_lake"] += 1
            continue
        if args.limit and attempted >= args.limit:
            break
        fp = _find_local(sb_id, source_roots)
        if fp is None:
            pending_official.append(sb_id)
            continue
        raw = fp.read_bytes()
        vr = L.validate_event_bytes(raw)
        if not vr.ok:
            L.quarantine_payload(lake, sb_match_id=sb_id, raw=raw, reason=vr.reason, source=str(fp))
            actions["quarantined"] += 1
            pending_official.append(sb_id)
            attempted += 1
            continue
        rec = L.store_object(lake, sb_match_id=sb_id, raw=raw,
                             source_url=url_tmpl.format(sb_match_id=sb_id),
                             ingestion_mode="copied_local", ingestion_run_id=run_id,
                             bridge_row=bridge.get(sb_id), copied_from=str(fp))
        index[str(sb_id)] = rec
        actions["copied_local"] += 1
        attempted += 1

    # Pass 2: official retrieval (bounded concurrency), only if explicitly allowed
    if pending_official and args.allow_network:
        want = pending_official
        if args.limit:
            want = pending_official[: max(0, args.limit - attempted)]
        conc = max(1, min(MAX_CONCURRENCY, args.concurrency))

        def _fetch(sb_id: int):
            url = url_tmpl.format(sb_match_id=sb_id)
            try:
                return sb_id, _official_get(url), url, None
            except Exception as e:  # noqa: BLE001
                return sb_id, None, url, f"{type(e).__name__}"

        with ThreadPoolExecutor(max_workers=conc) as ex:
            futs = {ex.submit(_fetch, s): s for s in want}
            for fut in as_completed(futs):
                sb_id, raw, url, err = fut.result()
                if err or raw is None:
                    actions["fetch_error"] += 1
                    continue
                vr = L.validate_event_bytes(raw)
                if not vr.ok:
                    L.quarantine_payload(lake, sb_match_id=sb_id, raw=raw, reason=vr.reason, source=url)
                    actions["quarantined"] += 1
                    continue
                rec = L.store_object(lake, sb_match_id=sb_id, raw=raw, source_url=url,
                                     ingestion_mode="retrieved_official", ingestion_run_id=run_id,
                                     bridge_row=bridge.get(sb_id))
                index[str(sb_id)] = rec
                actions["retrieved_official"] += 1
    elif pending_official and not args.allow_network:
        actions["skipped_no_network"] = len(pending_official)

    L.write_index(lake, index)

    summary = {
        "run_id": run_id,
        "bridge_exact_international": len(bridge),
        "lake_objects_after": len(index),
        "actions": actions,
        "still_missing_from_lake": len([s for s in bridge if str(s) not in index]),
        "network_enabled": bool(args.allow_network),
    }
    L.log_run(lake, "acquire", summary)
    print(json.dumps(summary))
    return 0


if __name__ == "__main__":
    sys.exit(main())
