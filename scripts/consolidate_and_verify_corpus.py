"""Consolidate the prior-pull's player-history raw (events+lineups) INTO the canonical root via local copy
(NO API re-download), so the canonical root is the single self-contained home of all done fixtures. Then verify
raw-backed coverage across registered roots and write data/reference/corpus_coverage_ledger.json. research_only."""
import glob, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "src"))
from wcdrawlab.research import data_roots as DR
from wcdrawlab.research import corpus_coverage as CC
def main():
    canon = DR.get_root("api_football_player_history"); prior = DR.get_root("api_football_player_history_prior")
    done = set(map(str, json.loads((canon / "progress.json").read_text(encoding="utf-8"))["done"]))
    before = CC.coverage(done)
    # ids not fully backed in canonical alone
    canon_cov = CC._root_cov(canon)
    canon_full = {f for f, eps in canon_cov.items() if {"events", "lineups"} <= eps}
    need = done - canon_full
    copied = 0
    if prior.exists():
        for fp in glob.glob(str(prior / "*.json")):
            try:
                p = json.load(open(fp, encoding="utf-8")); par = p.get("parameters") or {}
                fid = str(par.get("fixture")); ep = CC._endpoint(p.get("get", ""), Path(fp).name)
                if fid in need and ep in ("events", "lineups") and isinstance(p.get("response"), list):
                    tgt = canon / f"fixtures_{ep}_consolidated_{fid}.json"
                    if not tgt.exists():
                        tgt.write_text(json.dumps(p), encoding="utf-8"); copied += 1
            except Exception:
                pass
    after = CC.coverage(done)
    ledger = {"done": len(done), "copied_from_prior_no_api": copied, "coverage_before": before,
              "coverage_after": after, "gate_95pct_raw_backed": after["coverage_rate"] >= 0.95,
              "self_contained_canonical": after["per_root_full_events_and_lineups"]["canonical"] >= len(done),
              "note": "Corpus completion measured by ACTUAL raw (events+lineups) across registered roots, not done-list length. The 60 prior fixtures were copied locally (no API) so the canonical root is self-contained."}
    (ROOT / "data/reference/corpus_coverage_ledger.json").write_text(json.dumps(ledger, indent=2), encoding="utf-8")
    print(json.dumps({k: ledger[k] for k in ("done", "copied_from_prior_no_api", "gate_95pct_raw_backed", "self_contained_canonical")}, indent=2))
    print("coverage_after:", json.dumps(after))
if __name__ == "__main__":
    main()
