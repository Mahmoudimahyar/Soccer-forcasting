"""Post-match prospective scoring (V1.5). Scores frozen-M2 ledger predictions for FINISHED matches only.
Results are used ONLY to compute metrics — never to update or select the model. Idempotent: a ledger
record is scored once. A results file (match_id -> final) is provided (sanitized) or fetched read-only
via the adapter with --execute. Safe by default (no fetch unless --execute).
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from wcdrawlab.operations.ledger import ImmutableLedger  # noqa: E402
from wcdrawlab.operations import prospective as PRO  # noqa: E402
from wcdrawlab.operations.session import now_iso  # noqa: E402


def load_results(path):
    """results json: {match_id: {status, final_wld, final_score_home, final_score_away, result_event_time}}"""
    return json.loads(Path(path).read_text(encoding="utf-8")) if path and Path(path).exists() else {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ledger", default=str(ROOT / "data/processed/prospective/ledger.jsonl"))
    ap.add_argument("--results", default=str(ROOT / "data/processed/prospective/results.json"))
    ap.add_argument("--out", default=str(ROOT / "data/processed/prospective/scores.jsonl"))
    a = ap.parse_args()
    led = ImmutableLedger(a.ledger)
    results = load_results(a.results)
    out = Path(a.out); out.parent.mkdir(parents=True, exist_ok=True)
    already = set()
    if out.exists():
        already = {json.loads(l)["ledger_key"] for l in out.read_text(encoding="utf-8").splitlines() if l.strip()}
    scored = 0
    with out.open("a", encoding="utf-8") as f:
        for rec in led.records():
            mid = str(rec["match_id"]); res = results.get(mid) or results.get(rec["match_id"])
            if not res or res.get("status") != "FINISHED":
                continue  # score FINISHED only
            if rec["ledger_key"] in already:
                continue  # idempotent
            s = PRO.score_record(rec, final_wld=res["final_wld"],
                                 final_score_home=res["final_score_home"],
                                 final_score_away=res["final_score_away"],
                                 result_event_time=res.get("result_event_time"),
                                 result_retrieval_time=now_iso())
            f.write(json.dumps(s, sort_keys=True) + "\n"); scored += 1
    print(f"scored {scored} newly-finished ledger predictions -> {out}")


if __name__ == "__main__":
    main()
