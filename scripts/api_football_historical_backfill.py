"""Phase 3: bounded, resumable, append-only API-Football historical pilot (events + lineups for finished
international fixtures; international tournaments first). Hard cap 300 requests; stop on auth/entitlement
error; retries<=2; single worker (<=2); raw appended to gitignored data/raw/api_football_historical/.
Key loaded read-only; never printed. research_only.
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from wcdrawlab.research.paid_source import safe_config  # noqa: E402
from wcdrawlab.operations.api_football_adapter import ApiFootballReadOnly, QuotaExceeded  # noqa: E402

RAW = ROOT / "data/raw/api_football_historical"
PROGRESS = RAW / "progress.json"
MANIFEST = RAW / "manifest.jsonl"
HARD_CAP = 300
TARGET_MATCHES = 120
INTL = [("FIFA_WC_2022", 1, 2022), ("UEFA_Euro_2024", 4, 2024), ("Copa_America_2024", 9, 2024),
        ("AFCON_2023", 6, 2023), ("AFC_Asian_Cup_2023", 7, 2023)]


def _canonical(fx):
    f = fx["fixture"]; t = fx["teams"]
    date = (f.get("date") or "")[:10]
    return f"{fx['league']['id']}/{fx['league']['season']}/{date}/{t['home']['id']}/{t['away']['id']}"


def _load_progress():
    if PROGRESS.exists():
        return set(json.loads(PROGRESS.read_text(encoding="utf-8")).get("done", []))
    return set()


def _save_progress(done):
    RAW.mkdir(parents=True, exist_ok=True)
    PROGRESS.write_text(json.dumps({"done": sorted(done)}), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--target", type=int, default=TARGET_MATCHES); a = ap.parse_args()
    st = safe_config.load_paid_keys()
    print("API_FOOTBALL_KEY:", st["API_FOOTBALL_KEY"])
    if st["API_FOOTBALL_KEY"] != "SET":
        print("key missing -> abort"); return
    RAW.mkdir(parents=True, exist_ok=True)
    done = _load_progress()
    af = ApiFootballReadOnly(daily_budget=HARD_CAP, reserve=0, min_interval_s=2.0, raw_dir=RAW)

    # collect finished fixtures (intl first); list calls
    fixtures = []
    for label, lid, season in INTL:
        if af.remaining_budget() < 2:
            break
        try:
            f = af.get("/fixtures", {"league": lid, "season": season})
        except QuotaExceeded:
            break
        for fx in (f.get("response", []) if f["ok"] else []):
            if fx.get("fixture", {}).get("status", {}).get("short") == "FT":
                fx.setdefault("league", {})["id"] = lid; fx["league"]["season"] = season
                fixtures.append((label, fx))

    pulled = 0
    auth_error = False
    for label, fx in fixtures:
        fid = fx["fixture"]["id"]
        if fid in done:
            continue
        if pulled >= a.target or af.remaining_budget() < 2:
            break
        canon = _canonical(fx)
        row = {"provider": "api_football", "competition": label, "provider_match_id": fid,
               "canonical_match_id": canon, "request_ts": datetime.now(timezone.utc).isoformat(),
               "endpoints": [], "coverage": {}, "completeness": None, "retry": 0, "error": None}
        try:
            ev = _with_retry(af, "/fixtures/events", {"fixture": fid}, row)
            ln = _with_retry(af, "/fixtures/lineups", {"fixture": fid}, row)
        except QuotaExceeded:
            break
        except _AuthError:
            auth_error = True
            row["error"] = "auth_or_entitlement"
            _append_manifest(row)
            break
        ev_ok = ev and ev.get("ok"); ln_ok = ln and ln.get("ok")
        row["coverage"] = {"events": bool(ev_ok), "lineups": bool(ln_ok),
                           "n_events": len(ev.get("response", []) if ev_ok else []),
                           "n_lineup_teams": len(ln.get("response", []) if ln_ok else [])}
        row["completeness"] = round((int(bool(ev_ok)) + int(bool(ln_ok))) / 2, 2)
        row["retrieval_ts"] = datetime.now(timezone.utc).isoformat()
        _append_manifest(row)
        done.add(fid)
        pulled += 1
        if pulled % 10 == 0:
            _save_progress(done)
            print(f"  pulled={pulled} reqs={af.stats.requests_made} remaining_budget={af.remaining_budget()}")
    _save_progress(done)
    print(f"DONE pulled={pulled} total_reqs={af.stats.requests_made}/{HARD_CAP} done_total={len(done)} auth_error={auth_error}")


class _AuthError(RuntimeError):
    pass


def _with_retry(af, endpoint, params, row, retries=2):
    last = None
    for attempt in range(retries + 1):
        r = af.get(endpoint, params)
        row["endpoints"].append(endpoint)
        if r.get("errors") and isinstance(r["errors"], dict) and any(
                k in str(r["errors"]).lower() for k in ("token", "subscription", "suspended", "access")):
            raise _AuthError()
        if r["ok"] or r["status_class"] == "2xx":
            return r
        last = r
        row["retry"] = attempt + 1
    return last


def _append_manifest(row):
    RAW.mkdir(parents=True, exist_ok=True)
    with MANIFEST.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")


if __name__ == "__main__":
    main()
