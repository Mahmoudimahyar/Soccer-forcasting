"""Phase 1/JOB3: bounded resumable append-only player-history backfill (events+lineups). API-Football only.
>=1s/request, <=2 retries, exponential backoff, first-write-wins, per-fixture manifest. research_only."""
import argparse, json, sys, time
from datetime import datetime, timezone
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT/"src"))
from wcdrawlab.research.paid_source import safe_config
from wcdrawlab.operations.api_football_adapter import ApiFootballReadOnly, QuotaExceeded
RAW = ROOT/"data/raw/player_history_corpus"; PROG = RAW/"progress.json"; MAN = RAW/"backfill_manifest.jsonl"
class _Auth(RuntimeError): pass
def _get(af, ep, params, retries=2):
    delay=1.0
    for _ in range(retries+1):
        r = af.get(ep, params)
        if any(k in str(r.get("errors") or "").lower() for k in ("token","subscription","suspended","access","plan")): raise _Auth()
        if r["ok"] or r["status_class"]=="2xx": return r
        time.sleep(delay); delay*=2
    return r
def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--max-requests", type=int, default=1800); a=ap.parse_args()
    st=safe_config.load_paid_keys()
    if st["API_FOOTBALL_KEY"]!="SET": print("key missing"); return
    man=json.loads((ROOT/"data/reference/player_history_corpus_manifest.json").read_text(encoding="utf-8"))
    target=min(man.get("fixture_target",1500), len(man["fixtures"]))
    done=set(json.loads(PROG.read_text(encoding="utf-8")).get("done",[])) if PROG.exists() else set()
    af=ApiFootballReadOnly(daily_budget=min(a.max_requests,4200), reserve=0, min_interval_s=1.0, raw_dir=RAW)
    pulled=0; auth=False
    for fx in man["fixtures"][:target]:
        fid=fx["provider_fixture_id"]
        if str(fid) in done or af.remaining_budget()<2:
            if af.remaining_budget()<2: break
            continue
        try: ev=_get(af,"/fixtures/events",{"fixture":fid}); ln=_get(af,"/fixtures/lineups",{"fixture":fid})
        except QuotaExceeded: break
        except _Auth: auth=True; break
        RAW.mkdir(parents=True,exist_ok=True)
        with MAN.open("a",encoding="utf-8") as f:
            f.write(json.dumps({"provider_fixture_id":fid,"canonical_match_id":fx["canonical_match_id"],
                "events":bool(ev["ok"]),"lineups":bool(ln["ok"]),"retrieval_ts":datetime.now(timezone.utc).isoformat()})+"\n")
        done.add(str(fid)); pulled+=1
        if pulled%50==0: PROG.write_text(json.dumps({"done":sorted(done)}),encoding="utf-8"); print(f"pulled={pulled} reqs={af.stats.requests_made}",flush=True)
    PROG.write_text(json.dumps({"done":sorted(done)}),encoding="utf-8")
    print(f"DONE pulled={pulled} reqs={af.stats.requests_made} done_total={len(done)}/{target} auth={auth}")
if __name__=="__main__": main()
