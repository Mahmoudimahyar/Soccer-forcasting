"""Phase 2 / JOB2: complete the predeclared 2,000-fixture player-history corpus. Resolves the CANONICAL
writable root via the data-root registry (no hard-coded path); seeds the done-set from the prior pull (avoids
re-download); events+lineups only; <=2 retries; exponential backoff; >=1s/request; append-only; first-write-wins.

QUOTA POLICY: dynamic collector-aware reserve (replaces the static 25% rule). Probes /status for the REAL
remaining daily quota, then research_budget = min(max_requests, remaining - reserve) where
reserve = max(200, ceil(1.5*collector_expected)+50). The collector uses ONLY The Odds API -> collector_expected=0
-> reserve=200. Never pauses merely because remaining < 25%. Pauses on: remaining<=reserve / rate-limit /
entitlement. API-Football only. Key read-only; never printed. research_only.
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
from wcdrawlab.research import quota_policy as QP  # noqa: E402
from wcdrawlab.research.paid_source import safe_config  # noqa: E402
from wcdrawlab.operations.api_football_adapter import ApiFootballReadOnly, QuotaExceeded  # noqa: E402

MANIFEST = ROOT / "data/reference/player_history_corpus_manifest.json"


class _Auth(RuntimeError):
    pass


def _seed_done():
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
    last = None
    for _ in range(retries + 1):
        r = af.get(ep, params); last = r
        errs = str(r.get("errors") or "").lower()
        if any(k in errs for k in ("token", "subscription", "suspended", "access", "plan")):
            raise _Auth()
        if "rate" in errs or r.get("status_class") == "429":
            raise QuotaExceeded("rate_limit")
        if r["ok"] or r["status_class"] == "2xx":
            return r
        time.sleep(delay); delay *= 2
    return last


def _probe_quota(af):
    """Return (remaining, limit_day, current, reset_hint). /status costs 1 request."""
    try:
        s = af.get("/status")
        req = ((s.get("response") or {}).get("requests") or {}) if s.get("ok") else {}
        limit_day = int(req.get("limit_day") or 0); current = int(req.get("current") or 0)
        return max(0, limit_day - current), limit_day, current
    except Exception:
        return None, None, None


def _first_unfinished(man, done):
    for fx in man["fixtures"]:
        fid = str(fx["provider_fixture_id"])
        if fid not in done:
            return fid
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-requests", type=int, default=5000)
    a = ap.parse_args()
    st = safe_config.load_paid_keys()
    print("API_FOOTBALL_KEY:", st["API_FOOTBALL_KEY"])
    if st["API_FOOTBALL_KEY"] != "SET":
        print(json.dumps({"state": "PREFLIGHT_FAILED", "reason": "key missing"})); return

    raw = DR.get_root("api_football_player_history"); raw.mkdir(parents=True, exist_ok=True)
    prog_path = raw / "progress.json"
    man = json.loads(MANIFEST.read_text(encoding="utf-8"))
    done = _seed_done()

    # --- dynamic, collector-aware quota policy (NOT a static 25% reserve) ---
    probe = ApiFootballReadOnly(daily_budget=3, reserve=0, min_interval_s=0.5)
    remaining, limit_day, current = _probe_quota(probe)
    pol = QP.load_policy(); collector_expected = int(pol.get("collector_expected_requests", 0))
    if remaining is None:
        print(json.dumps({"state": "WAITING_FOR_API_QUOTA", "reason": "quota probe failed"})); return
    budget, reserve = QP.research_budget(remaining, a.max_requests, collector_expected)
    first_unfinished_before = _first_unfinished(man, done)
    quota_ledger = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "quota_before": {"limit_day": limit_day, "current": current, "remaining": remaining},
        "collector_expected_requests": collector_expected,
        "dynamic_reserve": reserve,
        "research_request_budget": budget,
        "max_requests_arg": a.max_requests,
        "policy": "max(200, ceil(1.5*collector_expected)+50); collector uses Odds API only -> reserve=200",
        "first_unfinished_fixture_before": first_unfinished_before,
    }
    print(json.dumps({"quota_policy": quota_ledger}), flush=True)
    if budget < 2:
        quota_ledger["state"] = "WAITING_FOR_API_QUOTA"; quota_ledger["reason"] = "remaining <= dynamic reserve"
        (raw / "quota_ledger.json").write_text(json.dumps(quota_ledger, indent=2), encoding="utf-8")
        print(json.dumps({"state": "WAITING_FOR_API_QUOTA", "api_requests": 0, "research_budget": budget,
                          "reserve": reserve, "remaining": remaining})); return

    # --- bounded acquisition within the dynamic research budget ---
    af = ApiFootballReadOnly(daily_budget=budget, reserve=0, min_interval_s=1.0, raw_dir=raw)
    pulled = 0; auth = False; budget_hit = False; rate_limited = False
    for fx in man["fixtures"]:
        fid = str(fx["provider_fixture_id"])
        if fid in done:
            continue
        if af.remaining_budget() < 2:
            budget_hit = True; break
        try:
            ev = _get(af, "/fixtures/events", {"fixture": fid}); ln = _get(af, "/fixtures/lineups", {"fixture": fid})
        except QuotaExceeded:
            rate_limited = True; break
        except _Auth:
            auth = True; break
        if ev["ok"] and ln["ok"]:
            done.add(fid); pulled += 1
        if pulled and pulled % 50 == 0:
            prog_path.write_text(json.dumps({"done": sorted(done)}), encoding="utf-8")
            print(f"pulled={pulled} reqs={af.stats.requests_made} remaining_budget={af.remaining_budget()}", flush=True)
    prog_path.write_text(json.dumps({"done": sorted(done)}), encoding="utf-8")

    rem_after, _, cur_after = _probe_quota(af)
    total_planned = man.get("n_selected", len(man["fixtures"]))
    rate = round(len(done) / total_planned, 4)
    state = ("FAILED_INTEGRITY" if auth else
             ("WAITING_FOR_API_QUOTA" if (budget_hit or rate_limited) else
              ("RUNNING" if rate < 0.95 else "RUNNING")))
    quota_ledger.update({
        "requests_consumed": af.stats.requests_made,
        "quota_remaining_after": rem_after,
        "next_reset_estimate": "provider daily reset (API-Football rolling 24h); see dashboard",
        "first_unfinished_fixture_after": _first_unfinished(man, done),
        "first_unfinished_endpoint": "fixtures/events",
        "pulled_this_run": pulled, "completion_rate": rate, "state": state,
    })
    (raw / "quota_ledger.json").write_text(json.dumps(quota_ledger, indent=2), encoding="utf-8")
    print(json.dumps({"state": state, "pulled_this_run": pulled, "api_requests": af.stats.requests_made,
                      "done_total": len(done), "planned": total_planned, "completion_rate": rate,
                      "gate_95pct": rate >= 0.95, "dynamic_reserve": reserve, "research_budget": budget,
                      "quota_remaining_after": rem_after, "next_unfinished": quota_ledger["first_unfinished_fixture_after"]}))


if __name__ == "__main__":
    main()
