"""Phase 1 / 7B: reconcile every AVAILABLE 2022 WC match from cached API-Football events and emit a
quality table. Reads the active checkout's gitignored cache READ-ONLY (default path). Unavailable
matches/categories are explicitly classified — never silently inferred.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from wcdrawlab.research import replay_semantics as RS  # noqa: E402

DEFAULT_RAW = Path("C:/Users/Mahyar/worldcup_draw_model_lab_FINAL/data/raw/api_football_2022_worldcup")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw-dir", default=str(DEFAULT_RAW))
    ap.add_argument("--out", default=str(ROOT / "data/processed/replay_2022_full_tournament_quality.csv"))
    a = ap.parse_args()
    raw = Path(a.raw_dir)
    fxp = raw / "fixtures.json"
    rows = []
    if not fxp.exists():
        print(f"NO fixtures.json at {fxp} -> cannot reconcile; classify all not_available")
    else:
        fixtures = json.loads(fxp.read_text(encoding="utf-8")).get("response", [])
        for f in fixtures:
            fx = f.get("fixture", {}); fid = fx.get("id")
            home = (f.get("teams", {}).get("home") or {}).get("name")
            away = (f.get("teams", {}).get("away") or {}).get("name")
            rnd = (f.get("league", {}) or {}).get("round", "")
            status = (fx.get("status", {}) or {}).get("short")
            goals = f.get("goals", {}) or {}; fscore = f.get("score", {}) or {}
            evp = raw / f"events_{fid}.json"
            base = {"fixture_id": fid, "round": rnd, "home_team": home, "away_team": away,
                    "status": status, "reported_home": goals.get("home"), "reported_away": goals.get("away")}
            if not evp.exists():
                rows.append({**base, "quality_status": "not_cached",
                             "reason": "event file not in local cache (knockouts uncached)"}); continue
            try:
                ev = json.loads(evp.read_text(encoding="utf-8")).get("response", [])
            except Exception as e:
                rows.append({**base, "quality_status": "unreadable", "reason": str(e)}); continue
            ev = RS.dedupe_events(ev)
            rec = RS.reconcile_match(ev, home, away, {"home": goals.get("home"), "away": goals.get("away")}, fscore)
            cards = RS.count_cards(ev, home, away); subs = RS.count_subs(ev, home, away)
            rows.append({**base, "recon_home": rec["recon_home"], "recon_away": rec["recon_away"],
                         "reconciles_exact": rec["reconciles_exact"], "chronological": rec["chronological"],
                         "shootout": rec["shootout"], "n_events": len(ev),
                         "red_home": cards[home]["red"], "red_away": cards[away]["red"],
                         "subs_home": subs[home], "subs_away": subs[away],
                         "source_events_sha256": hashlib.sha256(evp.read_bytes()).hexdigest()[:16],
                         "quality_status": rec["quality_status"], "reason": ""})
    import pandas as pd
    df = pd.DataFrame(rows)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(a.out, index=False)
    if len(df):
        vc = dict(df.quality_status.value_counts())
        ok = int((df.quality_status == "ok").sum())
        exc = int((df.quality_status == "exception").sum())
        print(f"matches in fixtures: {len(df)} | status: {vc}")
        print(f"reconciled exact (ok): {ok} | exceptions: {exc} | wrote {a.out}")
    else:
        print("no rows")


if __name__ == "__main__":
    main()
