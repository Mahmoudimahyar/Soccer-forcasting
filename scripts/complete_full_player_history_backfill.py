"""Phase 2 / JOB2: complete the predeclared 2,000-fixture player-history corpus. Resolves the CANONICAL
writable root via the data-root registry (no hard-coded path); seeds the done-set from the prior pull (avoids
re-download); events+lineups only; <=2 retries; exponential backoff; >=1s/request; append-only; first-write-wins.
Stops on auth/entitlement/budget -> WAITING_FOR_API_QUOTA. API-Football only. Key read-only; never printed.
research_only.
"""
import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from wcdrawlab.research import data_roots as DR  # noqa: E402
from wcdrawlab.research.paid_source import safe_config  # noqa: E402
from wcdrawlab.operations.api_football_adapter import ApiFootballReadOnly, QuotaExceeded  # noqa: E402

MANIFEST = ROOT / "data/reference/player_history_corpus_manifest.json"


class _Auth(RuntimeError):
    pass


def _seed_done():
    """Union the canonical progress + the read-only prior-pull progress (avoid re-download)."""
    done = set()
    for root_name in ("api_football_player_history", "api_football_player_history_prior"):
        try:
            prog = DR.get_root(root_name) / "progress.json"
            if prog.exists():
                done |= set(json.loads(prog.read_text(encoding="utf-8")).get("done", []))
        except Exception:
            pass
    return done


def _get(af, ep, params, retries=2):
    delay = 1.0
    for _ in range(retries + 1):
        r = af.get(ep, params)
        if any(k in str(r.get("errors") or "").lower() for k in ("token", "subscription", "suspended", "access", "plan")):
            raise _Auth()
        if r["ok"] or r["status_class"] == "2xx":
            return r
        time.sleep(delay); delay *= 2
    return r


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--max-requests", type=int, default=3000); a = ap.parse_args()
    st = safe_config.load_paid_keys()
    print("API_FOOTBALL_KEY:", st["API_FOOTBALL_KEY"])
    if st["API_FOOTBALL_KEY"] != "SET":
        print(json.dumps({"state": "PREFLIGHT_FAILED", "reason": "key missing"})); return
    raw = DR.get_root("api_football_player_history"); raw.mkdir(parents=True, exist_ok=True)
    prog_path = raw / "progress.json"
    man = json.loads(MANIFEST.read_text(encoding="utf-8"))
    done = _seed_done()
    af = ApiFootballReadOnly(daily_budget=min(a.max_requests, 4500), reserve=0, min_interval_s=1.0, raw_dir=raw)
    pulled = 0; auth = False; budget_hit = False
    for fx in man["fixtures"]:
        fid = str(fx["provider_fixture_id"])
        if fid in done:
            continue
        if af.remaining_budget() < 2:
            budget_hit = True; break
        try:
            ev = _get(af, "/fixtures/events", {"fixture": fid}); ln = _get(af, "/fixtures/lineups", {"fixture": fid})
        except QuotaExceeded:
            budget_hit = True; break
        except _Auth:
            auth = True; break
        if ev["ok"] and ln["ok"]:
            done.add(fid); pulled += 1
        if pulled % 50 == 0 and pulled:
            prog_path.write_text(json.dumps({"done": sorted(done)}), encoding="utf-8")
            with (raw / "completion_manifest.jsonl").open("a", encoding="utf-8") as f:
                f.write(json.dumps({"checkpoint_pulled": pulled, "reqs": af.stats.requests_made,
                                    "ts": datetime.now(timezone.utc).isoformat()}) + "\n")
            print(f"pulled={pulled} reqs={af.stats.requests_made} remaining={af.remaining_budget()}", flush=True)
    prog_path.write_text(json.dumps({"done": sorted(done)}), encoding="utf-8")
    total_planned = man.get("n_selected", len(man["fixtures"]))
    state = ("FAILED_INTEGRITY" if auth else ("WAITING_FOR_API_QUOTA" if budget_hit else "RUNNING"))
    rate = round(len(done) / total_planned, 4)
    print(json.dumps({"state": state, "pulled_this_run": pulled, "api_requests": af.stats.requests_made,
                      "done_total": len(done), "planned": total_planned, "completion_rate": rate,
                      "gate_95pct": rate >= 0.95}))


if __name__ == "__main__":
    main()
