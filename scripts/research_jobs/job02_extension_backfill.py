import sys, csv, json
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent)); import _job
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT/"src"))
from wcdrawlab.research.paid_source import safe_config
from wcdrawlab.operations.api_football_adapter import ApiFootballReadOnly, QuotaExceeded
RAW = ROOT/"data/raw/api_football_historical_corpus"; PROG = RAW/"ext_progress.json"
def main():
    _job.run_dir()
    man = ROOT/"data/reference/api_football_red_threshold_extension_manifest.csv"
    if not man.exists():
        _job.emit("skipped", reason="extension manifest absent (Phase 2 not run)"); return
    st = safe_config.load_paid_keys()
    if st["API_FOOTBALL_KEY"] != "SET":
        _job.emit("failed", reason="API_FOOTBALL_KEY missing"); return
    rows = list(csv.DictReader(open(man, encoding="utf-8")))
    done = set(json.loads(PROG.read_text(encoding="utf-8")).get("done", [])) if PROG.exists() else set()
    budget = min(500, _job.api_budget())
    af = ApiFootballReadOnly(daily_budget=budget, reserve=0, min_interval_s=0.3, raw_dir=RAW)
    pulled=0; auth=False
    for r in rows:
        fid = r["provider_fixture_id"]
        if fid in done or af.remaining_budget() < 2: 
            if af.remaining_budget()<2: break
            continue
        try:
            ev = af.get("/fixtures/events", {"fixture": fid}); ln = af.get("/fixtures/lineups", {"fixture": fid})
        except QuotaExceeded: break
        if str(ev.get("errors") or "").lower().find("token")>=0: auth=True; break
        done.add(fid); pulled+=1
    RAW.mkdir(parents=True, exist_ok=True); PROG.write_text(json.dumps({"done":sorted(done)}), encoding="utf-8")
    _job.emit("failed" if auth else "complete", reason=f"extension pulled={pulled} reqs={af.stats.requests_made}",
              api_requests=af.stats.requests_made, state_updates={"ext_pulled": pulled})
main()
