"""Phase 3: bounded, resumable, append-only API-Football corpus backfill (events + lineups for the included
fixtures in the predeclared manifest). API-Football ONLY (no Odds API). Hard research budget; <=2 retries;
exponential backoff; idempotent resume; manifest after every fixture. Key read-only; never printed.
Raw under gitignored data/raw/api_football_historical_corpus/. research_only.
"""
import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from wcdrawlab.research.paid_source import safe_config  # noqa: E402
from wcdrawlab.operations.api_football_adapter import ApiFootballReadOnly, QuotaExceeded  # noqa: E402

RAW = ROOT / "data/raw/api_football_historical_corpus"
PROGRESS = RAW / "progress.json"
MANIFEST = RAW / "corpus_manifest.jsonl"
FIXTURE_MANIFEST = ROOT / "data/reference/api_football_corpus_fixture_manifest.json"
RESEARCH_BUDGET = 4200


def _load_progress():
    return set(json.loads(PROGRESS.read_text(encoding="utf-8")).get("done", [])) if PROGRESS.exists() else set()


def _save_progress(done):
    RAW.mkdir(parents=True, exist_ok=True)
    PROGRESS.write_text(json.dumps({"done": sorted(done)}), encoding="utf-8")


class _AuthError(RuntimeError):
    pass


def _get(af, endpoint, params, retries=2):
    delay = 1.0
    for attempt in range(retries + 1):
        r = af.get(endpoint, params)
        errs = str(r.get("errors") or "").lower()
        if any(k in errs for k in ("token", "subscription", "suspended", "access", "plan")):
            raise _AuthError()
        if r["ok"] or r["status_class"] == "2xx":
            return r, attempt
        time.sleep(delay); delay *= 2  # exponential backoff
    return r, retries


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-requests", type=int, default=1800)  # per-run cap (fits a background window)
    a = ap.parse_args()
    st = safe_config.load_paid_keys()
    print("API_FOOTBALL_KEY:", st["API_FOOTBALL_KEY"])
    if st["API_FOOTBALL_KEY"] != "SET":
        print("key missing -> abort"); return
    man = json.loads(FIXTURE_MANIFEST.read_text(encoding="utf-8"))
    included = [f for f in man["fixtures"] if f["eligibility"] == "included"]
    done = _load_progress()
    cap = min(a.max_requests, RESEARCH_BUDGET)
    af = ApiFootballReadOnly(daily_budget=cap, reserve=0, min_interval_s=0.3, raw_dir=RAW)

    pulled = 0
    auth = False
    for fx in included:
        fid = fx["provider_fixture_id"]
        if str(fid) in done:
            continue
        if af.remaining_budget() < 2:
            break
        row = {"provider": "api_football", "competition": fx["label"], "cohort": fx["cohort"],
               "comp_type": fx["comp_type"], "provider_fixture_id": fid,
               "canonical_match_id": fx["canonical_match_id"], "request_ts": datetime.now(timezone.utc).isoformat(),
               "retry": 0, "error": None}
        try:
            ev, r1 = _get(af, "/fixtures/events", {"fixture": fid})
            ln, r2 = _get(af, "/fixtures/lineups", {"fixture": fid})
        except QuotaExceeded:
            break
        except _AuthError:
            auth = True; row["error"] = "auth_or_entitlement"; _append(row); break
        row["retry"] = max(r1, r2)
        row["coverage"] = {"events": bool(ev["ok"]), "lineups": bool(ln["ok"]),
                           "n_events": len(ev.get("response", []) if ev["ok"] else []),
                           "n_lineup_teams": len(ln.get("response", []) if ln["ok"] else [])}
        row["completeness"] = round((int(bool(ev["ok"])) + int(bool(ln["ok"]))) / 2, 2)
        row["retrieval_ts"] = datetime.now(timezone.utc).isoformat()
        _append(row)
        done.add(str(fid)); pulled += 1
        if pulled % 50 == 0:
            _save_progress(done)
            print(f"  pulled={pulled} reqs={af.stats.requests_made} remaining={af.remaining_budget()}", flush=True)
    _save_progress(done)
    print(f"DONE pulled={pulled} reqs={af.stats.requests_made}/{cap} done_total={len(done)}/{len(included)} auth={auth}")


def _append(row):
    RAW.mkdir(parents=True, exist_ok=True)
    with MANIFEST.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")


if __name__ == "__main__":
    main()
