import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent)); import _job, _common as C, _models as M
def main():
    rd = Path(_job.run_dir())
    intl = json.loads((rd/"snapshots_intl.json").read_text(encoding="utf-8"))
    club = json.loads((rd/"snapshots_club.json").read_text(encoding="utf-8"))
    if len({r["competition"] for r in intl})<2 or not club:
        _job.emit("skipped", reason="insufficient intl comps or no club aux data"); return
    # held-out international evaluation: baseline A = intl-only W3; experiment B = club+intl-train W3
    def eval_w3(train, test):
        preds = M.wdl_predictors(train); fn = preds["W3"]
        return sum(C.rps(fn(r), r["target_wdl"]) for r in test)/len(test)
    a_rps=[]; b_rps=[]
    for held, tr_intl, te in C.loco_folds(intl):
        a_rps.append(eval_w3(tr_intl, te))                      # intl-only
        b_rps.append(eval_w3(tr_intl + club, te))               # club as auxiliary (labeled, held-out intl test)
    a=round(sum(a_rps)/len(a_rps),4); b=round(sum(b_rps)/len(b_rps),4)
    verdict = "transfer_helps" if b < a-0.001 else ("transfer_neutral" if abs(b-a)<=0.001 else "transfer_hurts")
    res = {"intl_only_W3_rps": a, "club_aux_W3_rps": b, "verdict": verdict,
           "note": "club is AUXILIARY only; evaluation is held-out INTERNATIONAL competitions; no pooled-without-labels claim"}
    (rd/"job09_transfer.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    _job.emit("complete", reason=f"transfer {verdict}: intl-only {a} vs club-aux {b}", state_updates={"transfer_verdict": verdict})
main()
