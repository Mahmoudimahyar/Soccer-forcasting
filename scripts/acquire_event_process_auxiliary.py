"""JOB4: acquire ONLY official StatsBomb Open Data event JSON for the manifested auxiliary matches. Append-only
raw under data/raw/statsbomb_open/event_process_auxiliary/ (gitignored). <=4 concurrent, resumable first-write-wins,
<=2 retries, exp backoff, hash validation, records full provenance. No mirror/scrape/paid/video/360. research_only."""
import argparse, hashlib, json, sys, time, urllib.error, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
BASE = "https://raw.githubusercontent.com/statsbomb/open-data/master/data"
UA = "wcdrawlab-research/1.0 (StatsBomb open-data, non-commercial research)"
RAW = ROOT/"data/raw/statsbomb_open/event_process_auxiliary"
def _utc(): return datetime.now(timezone.utc).isoformat()
def _get(url, t=90):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=t) as r: return r.read()  # nosec B310
def _avail(events, key):
    return any(isinstance(e, dict) and e.get(key) is not None for e in events)
def _fetch(m, retries=2):
    mid = str(m["match_id"]); url = f"{BASE}/events/{mid}.json"; tgt = RAW/f"{mid}.json"
    if tgt.exists() and tgt.stat().st_size > 0:
        return {"match_id": mid, "parse_status": "cached_skip", "error_class": None}
    delay = 1.0
    for _ in range(retries+1):
        try:
            raw = _get(url); ev = json.loads(raw)
            if not isinstance(ev, list) or not ev:
                return {"match_id": mid, "parse_status": "invalid", "error_class": "source_schema_invalid"}
            idx=[e.get("index") for e in ev if isinstance(e,dict) and e.get("index") is not None]
            if idx != sorted(idx):
                return {"match_id": mid, "parse_status": "invalid", "error_class": "source_schema_invalid"}
            RAW.mkdir(parents=True, exist_ok=True)
            if not tgt.exists():
                tmp=tgt.with_suffix(".json.tmp"); tmp.write_bytes(raw); tmp.replace(tgt)
            return {"match_id": mid, "competition": m["competition"], "season": m["season"],
                    "match_date": m["match_date"], "home": m["home"], "away": m["away"],
                    "source_ref": url, "retrieval_ts": _utc(), "sha256": hashlib.sha256(raw).hexdigest(),
                    "event_count": len(ev), "xg_available": _avail([e.get("shot",{}) for e in ev if isinstance(e,dict)], "statsbomb_xg"),
                    "location_available": _avail(ev, "location"), "possession_available": _avail(ev, "possession"),
                    "pressure_available": any((e.get("type") or {}).get("name")=="Pressure" for e in ev if isinstance(e,dict)),
                    "pass_carry_available": any((e.get("type") or {}).get("name") in ("Pass","Carry") for e in ev if isinstance(e,dict)),
                    "parse_status": "ok", "source_quality": "available_verified", "error_class": None}
        except urllib.error.HTTPError as e:
            cls = "source_url_missing" if e.code==404 else ("rights_blocked" if e.code in (401,403) else "transient_network_failure")
            if cls!="transient_network_failure": return {"match_id": mid, "parse_status":"unresolved", "error_class": cls}
        except Exception:
            pass
        time.sleep(delay); delay*=2
    return {"match_id": mid, "parse_status": "unresolved", "error_class": "unavailable_official_source"}
def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--run-dir", default=str(ROOT/"outputs/research_runs/_ep")); a=ap.parse_args()
    rd=Path(a.run_dir); rd.mkdir(parents=True, exist_ok=True)
    man=json.load(open(ROOT/"data/reference/event_process_auxiliary_manifest.json"))["fixtures"]
    man_path=rd/"acquire_manifest.jsonl"; ok=0; results=[]; last_hb=time.time()
    with ThreadPoolExecutor(max_workers=4) as ex:
        futs={ex.submit(_fetch,m):m for m in man}
        for fut in as_completed(futs):
            r=fut.result(); results.append(r)
            with man_path.open("a",encoding="utf-8") as f: f.write(json.dumps(r)+"\n")
            if r.get("parse_status") in ("ok","cached_skip"): ok+=1
            if time.time()-last_hb>=120:
                (rd/"acquire_state.json").write_text(json.dumps({"ts":_utc(),"valid":ok,"attempted":len(results),"total":len(man)}),encoding="utf-8"); last_hb=time.time()
    by_cls={}
    for r in results:
        c=r.get("error_class")
        if c: by_cls[c]=by_cls.get(c,0)+1
    final={"ts":_utc(),"valid":ok,"attempted":len(results),"total":len(man),"by_error_class":by_cls,"min_gate_500":ok>=500}
    (rd/"acquire_state.json").write_text(json.dumps(final,indent=2),encoding="utf-8"); print(json.dumps(final))
if __name__=="__main__": main()
