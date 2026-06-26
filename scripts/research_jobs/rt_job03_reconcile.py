import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent)); import _job
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT/"src"))
from wcdrawlab.research import data_roots as DR
from wcdrawlab.research.paid_source import result_semantics as RS, historical_datasets as HD
def _scan(root):
    fixtures, events = {}, {}
    if not root.exists(): return fixtures, events
    for fp in root.glob("fixtures_*.json"):
        if "events" in fp.name or "lineups" in fp.name: continue
        try:
            for fx in (json.loads(fp.read_text(encoding="utf-8")).get("response",[]) or []): fixtures[str(fx["fixture"]["id"])]=fx
        except Exception: pass
    for fp in root.glob("fixtures_events_*.json"):
        try:
            p=json.loads(fp.read_text(encoding="utf-8")); fid=(p.get("parameters") or {}).get("fixture")
            if fid is not None: events[str(fid)]=p.get("response",[]) or []
        except Exception: pass
    return fixtures, events
def main():
    rd = Path(_job.run_dir())
    tot_exact=tot=so=0
    for rn in ("api_football_corpus","api_football_player_history","api_football_player_history_prior"):
        try: root=DR.get_root(rn)
        except Exception: continue
        fx,ev=_scan(root)
        for fid,f in fx.items():
            e=ev.get(fid)
            if e is None: continue
            tot+=1
            if RS.canonical_result(f,e)["reconciliation_status"]=="exact":
                tot_exact+=1
                for c in HD.cards_table(e):
                    if c["card_class"] in ("direct_red","second_yellow_red"): so+=1
    ledger={"reconciled_fixtures":tot,"regulation_exact":tot_exact,
            "exact_rate":round(tot_exact/tot,4) if tot else None,
            "canonical_sendings_off_total":so,
            "scope_note":"123=900-corpus, 176=1120(incl ext); this is the union across resolved roots"}
    (rd/"job03_counts_ledger.json").write_text(json.dumps(ledger, indent=2), encoding="utf-8")
    (ROOT/"data/reference/canonical_counts_ledger.json").write_text(json.dumps(ledger, indent=2), encoding="utf-8")
    _job.emit("complete", reason=f"reconciled {tot}; exact {tot_exact} ({ledger['exact_rate']}); sendings_off {so}",
              state_updates={"reconciled": tot, "exact_rate": ledger["exact_rate"], "sendings_off": so})
main()
