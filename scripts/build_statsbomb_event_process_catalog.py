"""JOB2: inventory the APPROVED official StatsBomb Open Data catalog (men's competitions + match metadata).
Official source only (raw.githubusercontent.com/statsbomb/open-data). No mirror/scrape/paid/video/360. research_only."""
import csv, json, sys, urllib.request
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
BASE = "https://raw.githubusercontent.com/statsbomb/open-data/master/data"
UA = "wcdrawlab-research/1.0 (StatsBomb open-data, non-commercial research)"
def _get(url, t=60):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=t) as r:  # nosec B310
        return json.loads(r.read())
def main():
    comps = _get(f"{BASE}/competitions.json")
    rows = []
    for c in comps:
        if str(c.get("competition_gender")) != "male":
            continue
        cid, sid = c["competition_id"], c["season_id"]
        try:
            matches = _get(f"{BASE}/matches/{cid}/{sid}.json")
        except Exception:
            matches = []
        for m in matches:
            rows.append({"match_id": m.get("match_id"), "competition_id": cid, "season_id": sid,
                         "competition": c.get("competition_name"), "season": c.get("season_name"),
                         "match_date": m.get("match_date"),
                         "home": (m.get("home_team") or {}).get("home_team_name"),
                         "away": (m.get("away_team") or {}).get("away_team_name")})
    out = ROOT / "data/reference"; out.mkdir(parents=True, exist_ok=True)
    (out/"statsbomb_event_process_catalog.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
    with (out/"statsbomb_event_process_catalog.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    cs = sorted({(r["competition"], r["season"]) for r in rows})
    print(json.dumps({"men_match_rows": len(rows), "competition_seasons": len(cs),
                      "distinct_matches": len({r["match_id"] for r in rows})}))
if __name__ == "__main__": main()
