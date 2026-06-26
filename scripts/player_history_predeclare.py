"""Phase 1: predeclare the player-history corpus (metadata-only). Fetches league-season fixture LISTS and
stratifies 100 completed fixtures per league-season by a deterministic fixture-ID hash with a FIXED seed —
NO results/goals/cards/player/team/event-volume used for selection. Writes the manifest BEFORE any event
retrieval. Key read-only; never printed. NO Odds API. research_only.
"""
import csv
import hashlib
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from wcdrawlab.research.paid_source import safe_config  # noqa: E402
from wcdrawlab.operations.api_football_adapter import ApiFootballReadOnly, QuotaExceeded  # noqa: E402

RAW = ROOT / "data/raw/player_history_corpus"
SEED = "player_impact_v1_fixed_seed"
PER_LEAGUE_SEASON = 100
LEAGUES = [("EPL", 39), ("LaLiga", 140), ("SerieA", 135), ("Bundesliga", 78), ("Ligue1", 61)]
SEASONS = [2020, 2021, 2022, 2023]
FINISHED = {"FT", "AET", "PEN"}
CAP_FIXTURES = 2000
RESEARCH_CAP = 4200


def _hrank(fid):
    return hashlib.sha256(f"{SEED}:{fid}".encode()).hexdigest()


def main():
    st = safe_config.load_paid_keys()
    print("API_FOOTBALL_KEY:", st["API_FOOTBALL_KEY"])
    if st["API_FOOTBALL_KEY"] != "SET":
        print("key missing -> abort"); return
    af = ApiFootballReadOnly(daily_budget=30, reserve=0, min_interval_s=1.0, raw_dir=RAW)
    remaining = None
    try:
        s = af.get("/status")
        if s["ok"] and s["response"]:
            r = s["response"].get("requests", {})
            if r.get("limit_day") is not None and r.get("current") is not None:
                remaining = max(0, r["limit_day"] - r["current"])
    except QuotaExceeded:
        pass
    if remaining is not None:
        reserve = max(1500, math.ceil(0.25 * remaining))
        research_budget = min(RESEARCH_CAP, max(0, remaining - reserve))
        fixture_target = min(CAP_FIXTURES, (research_budget - 50) // 2)
    else:
        reserve = None; research_budget = None; fixture_target = 1500
    print(f"remaining={remaining} reserve={reserve} research_budget={research_budget} fixture_target={fixture_target}")

    selected = []
    for lname, lid in LEAGUES:
        for season in SEASONS:
            if af.remaining_budget() <= 0:
                break
            try:
                f = af.get("/fixtures", {"league": lid, "season": season})
            except QuotaExceeded:
                break
            fixtures = [x for x in (f.get("response", []) if f["ok"] else [])
                        if x.get("fixture", {}).get("status", {}).get("short") in FINISHED]
            # deterministic stratified pick: sort by fixture-ID hash, take first PER_LEAGUE_SEASON
            fixtures.sort(key=lambda x: _hrank(x["fixture"]["id"]))
            for x in fixtures[:PER_LEAGUE_SEASON]:
                t = x["teams"]
                selected.append({"canonical_match_id": f"{lid}/{season}/{(x['fixture'].get('date') or '')[:10]}/{t['home']['id']}/{t['away']['id']}",
                                 "provider_fixture_id": x["fixture"]["id"], "league_name": lname, "league": lid,
                                 "season": season, "kickoff_utc": x["fixture"].get("date"),
                                 "status": x["fixture"]["status"]["short"], "comp_type": "club",
                                 "inclusion_rule": "hash_stratified_100_per_league_season_fixed_seed",
                                 "raw_status": "pending", "reconciliation_status": "pending"})
    (ROOT / "data/reference").mkdir(parents=True, exist_ok=True)
    cols = ["canonical_match_id", "provider_fixture_id", "league_name", "league", "season", "kickoff_utc",
            "status", "comp_type", "inclusion_rule", "raw_status", "reconciliation_status"]
    with open(ROOT / "data/reference/player_history_corpus_manifest.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore"); w.writeheader(); w.writerows(selected)
    (ROOT / "data/reference/player_history_corpus_manifest.json").write_text(json.dumps(
        {"seed": SEED, "per_league_season": PER_LEAGUE_SEASON, "leagues": [l[0] for l in LEAGUES],
         "seasons": SEASONS, "remaining_allowance": remaining, "reserve": reserve,
         "research_budget": research_budget, "fixture_target": fixture_target, "n_selected": len(selected),
         "fixtures": selected}, indent=2), encoding="utf-8")
    from collections import Counter
    print(f"selected={len(selected)} per league-season:", dict(Counter((s['league_name'], s['season']) for s in selected).__len__() and Counter(s['league_name'] for s in selected)))


if __name__ == "__main__":
    main()
