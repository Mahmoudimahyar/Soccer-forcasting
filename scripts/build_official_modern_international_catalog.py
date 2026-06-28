"""JOB: build the OFFICIAL senior MEN'S INTERNATIONAL StatsBomb Open Data catalog.

Fetches the official open-data competitions.json + per-(competition,season) match lists for the
senior men's international competitions only (FIFA World Cup, UEFA Euro, Copa America, African Cup
of Nations — from the lake roots config `allowed_competitions`) and writes:

  data/reference/official_modern_international_catalog.{csv,json}                (one row per match)
  data/reference/official_modern_international_selection_manifest.{csv,json}     (per comp-season)
  notes/research/official_modern_international_catalog_report.md

External retrieval = OFFICIAL StatsBomb Open Data ONLY (raw.githubusercontent.com/statsbomb/
open-data). No mirror/scrape/paid/credentials/360/video. Historical cutoff: a 2026 FIFA World Cup
season, if it ever appears in open data, is EXCLUDED (never enters any cohort).

research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible.
"""
from __future__ import annotations

import json
import sys

import _lakejob as J
import _lake_catalog_util as U
from wcdrawlab.research import international_event_lake as L

EXCLUDED_SEASON_NAMES = {"2026"}  # 2026 World Cup is strictly before-cutoff: excluded


def _is_2026_worldcup(comp_name: str, season_name: str) -> bool:
    return comp_name == "FIFA World Cup" and str(season_name).strip() in EXCLUDED_SEASON_NAMES


def main(argv=None) -> int:
    run_id = "official_catalog_" + U.now_iso().replace(":", "").replace("-", "")
    cfg = L.load_roots()
    admitted = set(cfg.get("allowed_competitions", []))

    comps = json.loads(U.get_bytes(U.competitions_url()).decode("utf-8"))

    selection: list[dict] = []
    catalog_rows: list[dict] = []
    excluded_for_cutoff: list[dict] = []

    for c in comps:
        if str(c.get("competition_gender")) != "male":
            continue
        comp_name = c.get("competition_name")
        if comp_name not in admitted:
            continue
        cid, sid = c.get("competition_id"), c.get("season_id")
        season_name = c.get("season_name")

        if _is_2026_worldcup(comp_name, season_name):
            excluded_for_cutoff.append({"competition": comp_name, "season": season_name,
                                        "competition_id": cid, "season_id": sid,
                                        "reason": "2026_world_cup_excluded_pre_cutoff"})
            continue

        sel = {"competition": comp_name, "season": season_name, "competition_id": cid,
               "season_id": sid, "country": c.get("country_name"), "matches_status": "",
               "n_matches": 0, "matches_sha256": "", "matches_url": U.matches_url(cid, sid)}
        try:
            mbytes = U.get_bytes(U.matches_url(cid, sid))
            matches = json.loads(mbytes.decode("utf-8"))
            sel["matches_status"] = "ok"
            sel["matches_sha256"] = L.sha256_bytes(mbytes)
        except Exception as e:  # noqa: BLE001
            sel["matches_status"] = f"error:{type(e).__name__}"
            matches = []

        for m in matches:
            home = (m.get("home_team") or {}).get("home_team_name")
            away = (m.get("away_team") or {}).get("away_team_name")
            hs, as_ = m.get("home_score"), m.get("away_score")
            catalog_rows.append({
                "sb_match_id": m.get("match_id"),
                "competition": comp_name, "season": season_name,
                "competition_id": cid, "season_id": sid,
                "competition_label": f"{comp_name} {season_name}",
                "match_date": U.normalize_date(m.get("match_date")),
                "home": home, "away": away,
                "norm_home": U.normalize_team(home), "norm_away": U.normalize_team(away),
                "home_score": hs, "away_score": as_,
                "fulltime_result": U.regulation_result(hs, as_),
                "competition_stage": (m.get("competition_stage") or {}).get("name"),
                "match_status": m.get("match_status"),
                "source_url": U.matches_url(cid, sid),
            })
        sel["n_matches"] = sum(1 for r in catalog_rows
                               if r["competition_id"] == cid and r["season_id"] == sid)
        selection.append(sel)

    catalog_rows.sort(key=lambda r: (str(r["competition"]), str(r["season"]), int(r["sb_match_id"] or 0)))

    cat_fields = ["sb_match_id", "competition", "season", "competition_id", "season_id",
                  "competition_label", "match_date", "home", "away", "norm_home", "norm_away",
                  "home_score", "away_score", "fulltime_result", "competition_stage",
                  "match_status", "source_url"]
    J.write_csv(J.REFERENCE / "official_modern_international_catalog.csv", catalog_rows, cat_fields)
    J.write_json(J.REFERENCE / "official_modern_international_catalog.json", catalog_rows)

    sel_fields = ["competition", "season", "competition_id", "season_id", "country",
                  "matches_status", "n_matches", "matches_sha256", "matches_url"]
    J.write_csv(J.REFERENCE / "official_modern_international_selection_manifest.csv", selection, sel_fields)
    J.write_json(J.REFERENCE / "official_modern_international_selection_manifest.json", {
        "schema_version": "official_modern_international_catalog_v1",
        "run_id": run_id, "built_ts": U.now_iso(), "source_base": U.OFFICIAL_BASE,
        "admitted_competitions": sorted(admitted),
        "excluded_for_cutoff": excluded_for_cutoff,
        "competition_seasons": selection,
    })

    by_comp: dict[str, int] = {}
    for r in catalog_rows:
        by_comp[r["competition"]] = by_comp.get(r["competition"], 0) + 1
    comp_seasons = sorted({(r["competition"], r["season"]) for r in catalog_rows})

    summary = {
        "official_catalog_matches": len(catalog_rows),
        "competition_seasons": len(comp_seasons),
        "distinct_match_ids": len({r["sb_match_id"] for r in catalog_rows}),
        "by_competition": by_comp,
        "excluded_for_cutoff": len(excluded_for_cutoff),
    }

    report = J.NOTES / "official_modern_international_catalog_report.md"
    report.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Official Modern International StatsBomb Catalog", "",
        f"- run_id: `{run_id}`  built_ts: {U.now_iso()}",
        f"- source: {U.OFFICIAL_BASE} (official StatsBomb Open Data only)",
        f"- admitted competitions: {', '.join(sorted(admitted))}",
        f"- historical cutoff: 2026 FIFA World Cup excluded ({len(excluded_for_cutoff)} comp-season(s))",
        "",
        f"**Official catalog matches: {summary['official_catalog_matches']}** across "
        f"{summary['competition_seasons']} competition-seasons "
        f"({summary['distinct_match_ids']} distinct match ids).",
        "", "## Matches by competition", "", "| competition | matches |", "| --- | --- |",
    ]
    for comp, n in sorted(by_comp.items()):
        lines.append(f"| {comp} | {n} |")
    lines += ["", "## Competition-seasons", "",
              "| competition | season | matches | status |", "| --- | --- | --- | --- |"]
    for s in selection:
        lines.append(f"| {s['competition']} | {s['season']} | {s['n_matches']} | {s['matches_status']} |")
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps(summary))
    return 0


if __name__ == "__main__":
    sys.exit(main())
