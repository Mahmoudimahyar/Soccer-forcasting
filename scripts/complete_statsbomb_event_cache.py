"""JOB4: complete the StatsBomb event cache for the 198 missing EXACT bridge matches, from the APPROVED
OFFICIAL StatsBomb Open Data source only (github.com/statsbomb/open-data via raw.githubusercontent.com).
No scrape, no mirror, no paid product, no video, no 360 data, no unrelated competitions. Resolves the canonical
root via the data-root registry (data/raw/statsbomb_open/events). Resumable first-write-wins; <=4 concurrent;
exp backoff; <=2 retries; append-only manifest. research_only / not_runtime / not_trade / not_live.

Modes:
  --probe N : official-source AVAILABILITY test on a deterministic sample of N missing matches (no state change).
  (default) : full bounded cache completion of all missing exact-bridge matches.
"""
from __future__ import annotations
import argparse, csv, glob, hashlib, json, sys, time, urllib.error, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "src"))
from wcdrawlab.research import data_roots as DR  # noqa: E402

BASE = "https://raw.githubusercontent.com/statsbomb/open-data/master/data"
UA = "wcdrawlab-research/1.0 (StatsBomb open-data, non-commercial research; resumable GET)"
BRIDGE = Path("C:/Users/Mahyar/worldcup-player-impact-xg/data/processed/api_statsbomb_match_bridge_v1.csv")


def _utc():
    return datetime.now(timezone.utc).isoformat()


def _norm(s):
    return "".join(ch for ch in str(s).lower() if ch.isalnum())


def _bridge_rows():
    return list(csv.DictReader(open(BRIDGE, encoding="utf-8")))


def _cached_ids():
    ids = set()
    for rn in ("statsbomb_raw", "statsbomb_raw_prior"):
        try:
            ev = DR.get_root(rn) / "events"
            for fp in glob.glob(str(ev / "*.json")):
                p = Path(fp)
                if p.stat().st_size > 0:
                    ids.add(p.stem)
        except Exception:
            pass
    return ids


def _get(url, timeout=60):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:  # nosec B310 (https, public)
        return r.read()


def _validate(raw_bytes, row):
    """Return (ok, info|error_class). Validates parse, ordering, exact-bridge identity, xG-field presence."""
    try:
        events = json.loads(raw_bytes)
    except Exception:
        return False, {"error_class": "parse_failure"}
    if not isinstance(events, list) or not events:
        return False, {"error_class": "source_schema_invalid"}
    # event ordering: index strictly non-decreasing
    idx = [e.get("index") for e in events if isinstance(e, dict) and e.get("index") is not None]
    if idx != sorted(idx):
        return False, {"error_class": "source_schema_invalid", "detail": "event index not ordered"}
    # exact-bridge identity: the two team names present in events match the bridge's sb_home/sb_away
    teams = []
    for e in events:
        t = (e.get("team") or {}).get("name") if isinstance(e, dict) else None
        if t and t not in teams:
            teams.append(t)
        if len(teams) >= 2:
            break
    bridge_teams = {_norm(row["sb_home"]), _norm(row["sb_away"])}
    got_teams = {_norm(t) for t in teams}
    if not bridge_teams.issubset(got_teams):
        return False, {"error_class": "source_schema_invalid", "detail": f"team identity mismatch {teams}"}
    # xG-field availability: any shot event carries shot.statsbomb_xg
    xg_present = any(
        isinstance(e, dict) and (e.get("shot") or {}).get("statsbomb_xg") is not None for e in events
    )
    return True, {"event_count": len(events), "xg_field_available": xg_present,
                  "teams": teams[:2], "sha256": hashlib.sha256(raw_bytes).hexdigest()}


def _fetch_one(row, out_dir, retries=2, probe=False):
    sbid = str(row["sb_match_id"]); url = f"{BASE}/events/{sbid}.json"
    tgt = out_dir / f"{sbid}.json"
    if not probe and tgt.exists() and tgt.stat().st_size > 0:
        return {"sb_match_id": sbid, "bridge_status": "exact", "parse_status": "cached_skip"}
    delay = 1.0; last_err = None
    for _ in range(retries + 1):
        try:
            raw = _get(url)
            ok, info = _validate(raw, row)
            if not ok:
                return {"sb_match_id": sbid, "api_fixture_id": row["api_fixture_id"],
                        "competition": row["competition_label"], "source_ref": url,
                        "bridge_status": "rejected", "parse_status": "invalid", **info}
            if not probe:
                if not tgt.exists():  # first-write-wins
                    tmp = tgt.with_suffix(".json.tmp")
                    tmp.write_bytes(raw); tmp.replace(tgt)
            return {"sb_match_id": sbid, "api_fixture_id": row["api_fixture_id"],
                    "canonical_match_id": row["bridge_id"], "competition": row["competition_label"],
                    "source_ref": url, "retrieval_ts": _utc(), "file_sha256": info["sha256"],
                    "event_count": info["event_count"], "xg_field_available": info["xg_field_available"],
                    "parse_status": "ok", "bridge_status": "exact", "error_class": None}
        except urllib.error.HTTPError as e:
            cls = "source_url_missing" if e.code == 404 else ("rights_blocked" if e.code in (401, 403) else "transient_network_failure")
            last_err = cls
            if cls != "transient_network_failure":
                return {"sb_match_id": sbid, "source_ref": url, "bridge_status": "unresolved", "error_class": cls}
        except (urllib.error.URLError, TimeoutError, Exception) as e:
            last_err = "transient_network_failure"
        time.sleep(delay); delay *= 2
    return {"sb_match_id": sbid, "source_ref": url, "bridge_status": "unresolved",
            "error_class": last_err or "unavailable_official_source"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", type=int, default=0)
    ap.add_argument("--run-dir", default=None)
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()

    rows = _bridge_rows()
    cached = _cached_ids()
    missing = sorted((r for r in rows if str(r["sb_match_id"]) not in cached), key=lambda r: str(r["sb_match_id"]))
    out_dir = DR.get_root("statsbomb_raw") / "events"; out_dir.mkdir(parents=True, exist_ok=True)

    if a.probe:
        sample = missing[: a.probe]
        results = [_fetch_one(r, out_dir, probe=True) for r in sample]
        ok = sum(1 for r in results if r.get("parse_status") == "ok")
        by_class = {}
        for r in results:
            c = r.get("error_class")
            if c:
                by_class[c] = by_class.get(c, 0) + 1
        print(json.dumps({"mode": "probe", "sample": len(sample), "resolved_ok": ok,
                          "official_source_available": ok >= 1, "error_classes": by_class,
                          "results": results}, indent=2))
        return

    # full bounded cache completion
    rd = Path(a.run_dir) if a.run_dir else (ROOT / "outputs/research_runs/_statsbomb")
    rd.mkdir(parents=True, exist_ok=True)
    man_path = rd / "statsbomb_cache_manifest.jsonl"
    state_path = rd / "statsbomb_cache_state.json"
    done = 0; results = []; last_hb = time.time()
    with ThreadPoolExecutor(max_workers=min(4, a.workers)) as ex:
        futs = {ex.submit(_fetch_one, r, out_dir): r for r in missing}
        for fut in as_completed(futs):
            res = fut.result(); results.append(res)
            with man_path.open("a", encoding="utf-8") as f:  # append-only artifact manifest
                f.write(json.dumps(res) + "\n")
            if res.get("parse_status") in ("ok", "cached_skip"):
                done += 1
            if time.time() - last_hb >= 120:  # heartbeat every 2 min
                _atomic(state_path, {"ts": _utc(), "fetched_ok": done, "attempted": len(results),
                                     "total_missing": len(missing)})
                last_hb = time.time()
    final = {"ts": _utc(), "fetched_ok": done, "attempted": len(results), "total_missing": len(missing),
             "by_error_class": _tally(results)}
    _atomic(state_path, final)
    print(json.dumps(final))


def _tally(results):
    t = {}
    for r in results:
        c = r.get("error_class")
        if c:
            t[c] = t.get(c, 0) + 1
    return t


def _atomic(path, obj):
    tmp = Path(str(path) + ".tmp"); tmp.write_text(json.dumps(obj, indent=2), encoding="utf-8"); tmp.replace(path)


if __name__ == "__main__":
    main()
