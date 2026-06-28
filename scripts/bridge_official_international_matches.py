"""JOB: STRICT exact bridge — map OFFICIAL catalog matches to LOCAL exact international fixtures.

LOCAL fixtures = the authoritative exact international bridge, loaded via the canonical lake engine
`L.load_exact_bridge()` (EXACT + international + allowed-competition rows only; ambiguous duplicate
sb_match_ids are dropped and never enter evaluation). This job does NOT mutate it.

For each official catalog match (official_modern_international_catalog.json) it applies a STRICT key:

    competition + season  AND  match_date  AND  normalized {home,away} set
    AND regulation-result agreement (regulation home/draw/away)

Classification (NO fuzzy, NO forced bridge):
    exact                  - all strict keys agree (sb_match_ids agree)
    score_mismatch         - matched by comp/season/date/teams but regulation result disagrees
    date_mismatch          - matched by comp/season/teams but date disagrees
    team_name_mismatch     - matched by comp/season/date, teams differ but at least one team is local
    ambiguous              - >1 local fixture matches the strict key (never enters evaluation)
    missing_local_match    - official match has no corresponding local exact fixture
    source_schema_issue    - a row lacks fields required to even attempt a match

Outputs:
    data/reference/expanded_international_bridge_manifest.{csv,json}
    notes/research/expanded_international_bridge_report.md

research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible.
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict

import _lakejob as J
import _lake_catalog_util as U
from wcdrawlab.research import international_event_lake as L


def _split_label(label: str) -> tuple[str, str]:
    s = (label or "").strip()
    if len(s) >= 5 and s[-4:].isdigit():
        return s[:-4].strip(), s[-4:]
    return s, ""


def main(argv=None) -> int:
    run_id = "expanded_bridge_" + U.now_iso().replace(":", "").replace("-", "")

    catalog = json.loads((J.REFERENCE / "official_modern_international_catalog.json").read_text(encoding="utf-8"))
    bridge = L.load_exact_bridge()  # {sb_match_id: row}, exact+international+allowed, ambiguity-free

    # Index local fixtures by (competition, season).
    local_by_cs: dict[tuple, list[dict]] = defaultdict(list)
    for sb_id, r in bridge.items():
        comp, season = _split_label(r.get("competition_label", ""))
        nh = U.normalize_team(r.get("norm_home") or r.get("sb_home"))
        na = U.normalize_team(r.get("norm_away") or r.get("sb_away"))
        local_by_cs[(comp, season)].append({
            "sb_match_id": sb_id,
            "bridge_id": r.get("bridge_id", ""),
            "_date": U.normalize_date(r.get("kickoff_date")),
            "_nh": nh, "_na": na,
            "_teamkey": U.team_set(nh, na),
            "_reg": U.regulation_result(r.get("api_regulation_home"), r.get("api_regulation_away")),
        })

    rows: list[dict] = []
    counts: dict[str, int] = defaultdict(int)

    for m in catalog:
        comp, season = m.get("competition"), str(m.get("season"))
        date = U.normalize_date(m.get("match_date"))
        nh, na = m.get("norm_home"), m.get("norm_away")
        off_id = m.get("sb_match_id")

        base = {
            "official_sb_match_id": off_id, "competition": comp, "season": season,
            "competition_label": m.get("competition_label"), "match_date": date,
            "official_norm_home": nh, "official_norm_away": na,
            "official_fulltime_result": m.get("fulltime_result"),
            "local_bridge_id": "", "local_sb_match_id": "", "local_regulation_result": "",
            "orientation": "", "classification": "",
        }

        if not all([comp, season, date, nh, na, off_id is not None]):
            base["classification"] = "source_schema_issue"; counts["source_schema_issue"] += 1
            rows.append(base); continue

        candidates = local_by_cs.get((comp, season), [])
        if not candidates:
            base["classification"] = "missing_local_match"; counts["missing_local_match"] += 1
            rows.append(base); continue

        off_key = U.team_set(nh, na)

        strict = [c for c in candidates if c["_date"] == date and c["_teamkey"] == off_key]
        if len(strict) > 1:
            base["classification"] = "ambiguous"; counts["ambiguous"] += 1
            rows.append(base); continue
        if len(strict) == 1:
            c = strict[0]
            orientation = "same" if c["_nh"] == nh else "swapped"
            base.update({"local_bridge_id": c["bridge_id"], "local_sb_match_id": c["sb_match_id"],
                         "local_regulation_result": c["_reg"], "orientation": orientation})
            off_reg = m.get("fulltime_result")
            if orientation == "swapped":
                off_reg = {"home": "away", "away": "home", "draw": "draw", "": ""}.get(off_reg, off_reg)
            if off_reg and c["_reg"] and off_reg != c["_reg"]:
                base["classification"] = "score_mismatch"; counts["score_mismatch"] += 1
            else:
                base["classification"] = "exact"; counts["exact"] += 1
            rows.append(base); continue

        teammatch = [c for c in candidates if c["_teamkey"] == off_key]
        if teammatch:
            c = teammatch[0]
            base.update({"local_bridge_id": c["bridge_id"], "local_sb_match_id": c["sb_match_id"],
                         "local_regulation_result": c["_reg"]})
            base["classification"] = "date_mismatch"; counts["date_mismatch"] += 1
            rows.append(base); continue

        datematch = [c for c in candidates if c["_date"] == date]
        local_teams: set = set()
        for c in candidates:
            local_teams |= set(c["_teamkey"])
        if datematch and ({nh, na} & local_teams):
            base["classification"] = "team_name_mismatch"; counts["team_name_mismatch"] += 1
            rows.append(base); continue

        base["classification"] = "missing_local_match"; counts["missing_local_match"] += 1
        rows.append(base)

    matched_local_ids = {str(r["local_sb_match_id"]) for r in rows
                         if r["classification"] in ("exact", "score_mismatch", "date_mismatch")
                         and r["local_sb_match_id"] != ""}
    local_unmatched = [sid for sid in bridge if str(sid) not in matched_local_ids]

    fields = ["official_sb_match_id", "competition", "season", "competition_label", "match_date",
              "official_norm_home", "official_norm_away", "official_fulltime_result",
              "local_bridge_id", "local_sb_match_id", "local_regulation_result", "orientation",
              "classification"]
    J.write_csv(J.REFERENCE / "expanded_international_bridge_manifest.csv", rows, fields)
    J.write_json(J.REFERENCE / "expanded_international_bridge_manifest.json", {
        "schema_version": "expanded_international_bridge_v1",
        "run_id": run_id, "built_ts": U.now_iso(),
        "official_catalog_matches": len(catalog),
        "local_exact_fixtures": len(bridge),
        "classification_counts": dict(counts),
        "exact_bridge_count": counts.get("exact", 0),
        "local_fixtures_without_official_row": len(local_unmatched),
        "rows": rows,
    })

    summary = {
        "official_catalog_matches": len(catalog), "local_exact_fixtures": len(bridge),
        "classification_counts": dict(counts), "exact_bridge_count": counts.get("exact", 0),
        "local_fixtures_without_official_row": len(local_unmatched),
    }

    report = J.NOTES / "expanded_international_bridge_report.md"
    report.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Expanded International Bridge (STRICT, official -> local exact fixtures)", "",
        f"- run_id: `{run_id}`  built_ts: {U.now_iso()}",
        f"- official catalog matches: **{len(catalog)}**",
        f"- local exact international fixtures: **{len(bridge)}**",
        f"- **exact bridge count: {counts.get('exact', 0)}**", "",
        "Strict key: competition + season + match_date + normalized team-set + regulation-result "
        "agreement. No fuzzy, no forced bridge. Ambiguous rows never enter evaluation.", "",
        "## Classification counts", "", "| classification | n |", "| --- | --- |",
    ]
    for k in ["exact", "score_mismatch", "date_mismatch", "team_name_mismatch", "ambiguous",
              "missing_local_match", "source_schema_issue"]:
        lines.append(f"| {k} | {counts.get(k, 0)} |")
    lines += ["", f"- local fixtures with no official catalog row: {len(local_unmatched)}"]
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps(summary))
    return 0


if __name__ == "__main__":
    sys.exit(main())
