"""Phase 2: predeclare the historical corpus fixture manifest (committed BEFORE event/lineup retrieval).
Selection is purely fixture-metadata based (cohort + date order + league rotation) — NEVER results/events/
cards/goals. Fetches only fixture LISTS (+/status). Writes data/reference/api_football_corpus_fixture_manifest.{csv,json}.
research_only. Key read-only; never printed.
"""
import csv
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from wcdrawlab.research.paid_source import safe_config  # noqa: E402
from wcdrawlab.operations.api_football_adapter import ApiFootballReadOnly, QuotaExceeded  # noqa: E402

RAW = ROOT / "data/raw/api_football_historical_corpus"
# (label, league_id, season, cohort, comp_type, country_or_confed)
COHORT_A = [
    ("FIFA_WC_2018", 1, 2018, "A", "international", "FIFA"), ("FIFA_WC_2022", 1, 2022, "A", "international", "FIFA"),
    ("UEFA_Euro_2020", 4, 2020, "A", "international", "UEFA"), ("UEFA_Euro_2024", 4, 2024, "A", "international", "UEFA"),
    ("Copa_America_2024", 9, 2024, "A", "international", "CONMEBOL"), ("AFCON_2023", 6, 2023, "A", "international", "CAF"),
    ("AFC_Asian_Cup_2023", 7, 2023, "A", "international", "AFC"),
]
COHORT_B = [  # rotation order EPL, LaLiga, SerieA, Bundesliga, Ligue1 (2023-24)
    ("EPL_2023", 39, 2023, "B", "club", "England"), ("LaLiga_2023", 140, 2023, "B", "club", "Spain"),
    ("SerieA_2023", 135, 2023, "B", "club", "Italy"), ("Bundesliga_2023", 78, 2023, "B", "club", "Germany"),
    ("Ligue1_2023", 61, 2023, "B", "club", "France"),
]
FINISHED = {"FT", "AET", "PEN"}
RESEARCH_BUDGET_CAP = 4200
FALLBACK_BUDGET = 1800


def _canonical(fx, lid, season):
    f = fx["fixture"]; t = fx["teams"]
    return f"{lid}/{season}/{(f.get('date') or '')[:10]}/{t['home']['id']}/{t['away']['id']}"


def collect(af, specs):
    out = []
    for label, lid, season, cohort, ctype, region in specs:
        if af.remaining_budget() <= 0:
            break
        try:
            r = af.get("/fixtures", {"league": lid, "season": season})
        except QuotaExceeded:
            break
        fixtures = r.get("response", []) if r["ok"] else []
        for fx in fixtures:
            st = fx.get("fixture", {}).get("status", {}).get("short")
            if st not in FINISHED:
                continue
            out.append({"label": label, "league": lid, "season": season, "cohort": cohort,
                        "comp_type": ctype, "region": region,
                        "canonical_match_id": _canonical(fx, lid, season),
                        "provider_fixture_id": fx["fixture"]["id"],
                        "kickoff_utc": fx["fixture"].get("date"), "status": st})
    return out


def main():
    st = safe_config.load_paid_keys()
    print("API_FOOTBALL_KEY:", st["API_FOOTBALL_KEY"])
    if st["API_FOOTBALL_KEY"] != "SET":
        print("key missing -> abort"); return
    af = ApiFootballReadOnly(daily_budget=20, reserve=0, min_interval_s=1.0, raw_dir=RAW)
    # remaining allowance
    remaining = None
    try:
        s = af.get("/status")
        if s["ok"] and s["response"]:
            req = s["response"].get("requests", {})
            limit = req.get("limit_day"); cur = req.get("current")
            if limit is not None and cur is not None:
                remaining = max(0, limit - cur)
    except QuotaExceeded:
        pass
    if remaining is not None:
        reserve = max(1500, math.ceil(0.25 * remaining))
        research_budget = min(RESEARCH_BUDGET_CAP, max(0, remaining - reserve))
    else:
        reserve = None
        research_budget = FALLBACK_BUDGET
    fixture_budget = research_budget // 2  # 2 calls/fixture (events + lineups)
    print(f"remaining={remaining} reserve={reserve} research_budget={research_budget} fixture_budget={fixture_budget}")

    a_fixtures = collect(af, COHORT_A)
    b_fixtures = collect(af, COHORT_B)
    # truncation: all A first, then B by league-rotation + date order until fixture_budget
    a_sorted = sorted(a_fixtures, key=lambda x: (x["label"], x["kickoff_utc"] or ""))
    # group B by league, sort by date; round-robin rotate
    from collections import defaultdict, deque
    bylg = defaultdict(list)
    for x in b_fixtures:
        bylg[x["label"]].append(x)
    for lg in bylg:
        bylg[lg].sort(key=lambda x: x["kickoff_utc"] or "")
    queues = [deque(bylg[lab]) for lab, *_ in COHORT_B if lab in bylg]
    b_rotated = []
    while any(queues):
        for q in queues:
            if q:
                b_rotated.append(q.popleft())

    included = []
    for fx in a_sorted:
        fx["eligibility"] = "included"; fx["inclusion_rule"] = "cohort_A_all_completed"; included.append(fx)
    remaining_slots = max(0, fixture_budget - len(included))
    for i, fx in enumerate(b_rotated):
        if i < remaining_slots:
            fx["eligibility"] = "included"; fx["inclusion_rule"] = "cohort_B_rotation_date_order"
        else:
            fx["eligibility"] = "excluded_truncated"; fx["inclusion_rule"] = "cohort_B_rotation_date_order"
        included.append(fx)

    for fx in included:
        fx["expected_endpoints"] = "events,lineups"
        fx["raw_status"] = "pending"
        fx["reconciliation_status"] = "pending"

    (ROOT / "data/reference").mkdir(parents=True, exist_ok=True)
    cols = ["canonical_match_id", "provider_fixture_id", "label", "cohort", "comp_type", "region", "league",
            "season", "kickoff_utc", "status", "eligibility", "inclusion_rule", "expected_endpoints",
            "raw_status", "reconciliation_status"]
    with open(ROOT / "data/reference/api_football_corpus_fixture_manifest.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore"); w.writeheader(); w.writerows(included)
    (ROOT / "data/reference/api_football_corpus_fixture_manifest.json").write_text(
        json.dumps({"truncation_rule": "all Cohort A; then Cohort B league-rotation+date-order until fixture_budget",
                    "research_budget": research_budget, "reserve": reserve, "fixture_budget": fixture_budget,
                    "remaining_allowance": remaining, "fixtures": included}, indent=2), encoding="utf-8")
    inc = sum(1 for x in included if x["eligibility"] == "included")
    print(f"manifest: total={len(included)} included={inc} A={len(a_sorted)} B_included={inc-len(a_sorted)} "
          f"B_excluded_truncated={len(included)-inc}")


if __name__ == "__main__":
    main()
