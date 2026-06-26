import sys, json, csv
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent)); import _job
ROOT = Path(__file__).resolve().parents[2]
def main():
    rd=Path(_job.run_dir()); sh=_job.shared()
    corpus=sh.get("corpus_rate",0.0); evals_run = corpus>=0.95
    models=["R2","P1","P2","P3","P4","P5","N0","N1","N2","N3","N4","C0","C1","C2","X0","X1","X2","X3"]
    rows=[]
    for m in models:
        concl = "reference_only" if m=="R2" else ("data_insufficient" if not evals_run else "rejected")
        rows.append({"model":m,"dataset_version":"partial (corpus %.0f%%)"%(corpus*100),"evals_run":evals_run,
                     "conclusion":concl,"candidate_for_future_review":False,
                     "note":"no candidate from partial data; full eval gated on corpus>=95% + xG join"})
    with open(ROOT/"data/reference/model_decision_ledger.csv","w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    (ROOT/"data/reference/model_decision_ledger.json").write_text(json.dumps(rows,indent=2),encoding="utf-8")
    (rd/"scientific_report_draft.md").write_text(
        f"# Research Truth Run — Draft\nrun_state from JOB2; corpus_rate={corpus}; evals_run={evals_run}.\n"
        f"All models: reference_only (R2) or data_insufficient (eval gated on corpus>=95%). NO candidate from partial data.\n", encoding="utf-8")
    _job.emit("complete", reason=f"decision ledger written ({len(rows)} models); evals_run={evals_run}; no candidate from partial data",
              state_updates={"decision_ledger": True, "evals_run": evals_run})
main()
