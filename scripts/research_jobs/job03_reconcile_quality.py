import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent)); import _job, _common as C
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT/"src"))
from wcdrawlab.research.paid_source import result_semantics as RS, historical_datasets as HD
def main():
    rd = Path(_job.run_dir())
    fixtures, events, lineups = C.load_corpus()
    n=exact=so=0; intl=club=0
    for fid, fx in fixtures.items():
        ev = events.get(fid)
        if ev is None: continue
        can = RS.canonical_result(fx, ev); n+=1
        if can["reconciliation_status"]=="exact": exact+=1
        else: continue
        intl += C._is_intl(fx); club += (not C._is_intl(fx))
        for c in HD.cards_table(ev):
            if c["card_class"] in ("direct_red","second_yellow_red"): so+=1
    res = {"fixtures": n, "regulation_exact": exact, "exact_rate": round(exact/n,4) if n else None,
           "sendings_off": so, "intl_fixtures": intl, "club_fixtures": club}
    (rd/"job03_quality.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    _job.emit("complete", reason=f"reconciled {n}; exact {exact}; sendings_off {so}",
              state_updates={"sendings_off": so, "fixtures": n, "exact": exact})
main()
