"""Phase 3: reconcile events vs official fixture score (own-goal beneficiary, goal counting, event ordering).
Reads gitignored raw. Writes notes/research/_phase3_reconcile.json. research_only.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/api_football_historical"


def _fixtures_map():
    m = {}
    for fp in RAW.glob("fixtures_*.json"):
        if "events" in fp.name or "lineups" in fp.name:
            continue
        try:
            p = json.loads(fp.read_text(encoding="utf-8"))
        except Exception:
            continue
        for fx in p.get("response", []) or []:
            fid = str(fx.get("fixture", {}).get("id"))
            g = fx.get("goals", {})
            t = fx.get("teams", {})
            if g.get("home") is not None:
                m[fid] = {"home": g["home"], "away": g["away"],
                          "home_id": t.get("home", {}).get("id"), "away_id": t.get("away", {}).get("id")}
    return m


def _events_map():
    out = {}
    for fp in RAW.glob("fixtures_events_*.json"):
        try:
            p = json.loads(fp.read_text(encoding="utf-8"))
        except Exception:
            continue
        fid = (p.get("parameters") or {}).get("fixture")
        if fid is not None:
            out[str(fid)] = p.get("response", []) or []
    return out


def reconcile_one(events, fx):
    """Return (events_home, events_away, ordering_ok). Regulation+ET goals; own-goal credits opponent;
    shootout (elapsed>120 with penalty shootout) excluded heuristically by elapsed<=120."""
    home = away = 0
    last = -1
    ordering_ok = True
    for e in events:
        el = (e.get("time") or {}).get("elapsed")
        if el is not None:
            if el < last:
                ordering_ok = False
            last = el
        t = (e.get("type") or "").lower(); d = (e.get("detail") or "").lower()
        if t != "goal":
            continue
        if el is not None and el > 120:
            continue  # exclude shootout
        team_id = (e.get("team") or {}).get("id")
        if "own" in d:
            if team_id == fx["home_id"]:
                away += 1
            elif team_id == fx["away_id"]:
                home += 1
        else:
            if team_id == fx["home_id"]:
                home += 1
            elif team_id == fx["away_id"]:
                away += 1
    return home, away, ordering_ok


def main():
    fmap = _fixtures_map()
    emap = _events_map()
    matched = [fid for fid in emap if fid in fmap]
    exact = mismatch = ordering_bad = 0
    examples = []
    for fid in matched:
        h, a, ok = reconcile_one(emap[fid], fmap[fid])
        off = fmap[fid]
        if h == off["home"] and a == off["away"]:
            exact += 1
        else:
            mismatch += 1
            if len(examples) < 8:
                examples.append({"fixture": fid, "events_score": [h, a], "official": [off["home"], off["away"]]})
        if not ok:
            ordering_bad += 1
    summary = {"matched": len(matched), "score_exact": exact, "score_mismatch": mismatch,
               "ordering_issues": ordering_bad,
               "score_exact_rate": round(exact / len(matched), 4) if matched else None,
               "mismatch_examples": examples,
               "note": "mismatches are commonly ET/shootout boundary or VAR-adjusted goals (informational)"}
    (ROOT / "notes/research/_phase3_reconcile.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "mismatch_examples"}, indent=2))


if __name__ == "__main__":
    main()
