"""Component 3 BUILDER -- DYNAMIC xG STATE (Phase 3).

Builds data/processed/dynamic_xg_state_v1.csv from EXACT API<->StatsBomb bridge matches + StatsBomb events
(match-clock minute <= each snapshot). Extends the JOB5 base join (xg_snapshot_join_v1.csv) with per-minute
xG rate, momentum, acceleration, big-chance proxy, time-since events, source-aware completeness, and a
strictly-prior-match xG-quality team prior. Writes a data card + coverage report.

research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible.

Leakage rules (enforced): xG at t excludes shots after t; per-match extraction (no cross-match leakage);
regulation grid only (t<=90, period<=2); StatsBomb minutes are MATCH-CLOCK; prior-xG-quality uses ONLY
strictly-earlier matches by kickoff date. Missing xG is NEVER imputed and NEVER written into a non-StatsBomb
fixture. status=complete only if >0 real xG-eligible snapshots are produced.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from wcdrawlab.research import data_roots as DR  # noqa: E402
from wcdrawlab.research import dynamic_xg_state as DXG  # noqa: E402
from wcdrawlab.ingest import canonical_team_name  # noqa: E402

BRIDGE_CSV = Path("C:/Users/Mahyar/worldcup-player-impact-xg/data/processed/api_statsbomb_match_bridge_v1.csv")
OUT = ROOT / "data/processed/dynamic_xg_state_v1.csv"
CARD = ROOT / "notes/dynamic_xg_state_data_card.md"
COVERAGE = ROOT / "data/reference/dynamic_xg_state_coverage.json"
RUN_PHASE = ROOT / "outputs/research_runs/truth_20260626_134931/model_phase"


def _full_match_team_xg(me: DXG.MatchEvents) -> dict:
    """Full-regulation per-team xG totals for this match (used only as a PRIOR for LATER matches)."""
    h = sum(s.xg for s in me.shots if s.side == "H")
    a = sum(s.xg for s in me.shots if s.side == "A")
    return {"H": h, "A": a}


def main():
    if not BRIDGE_CSV.exists():
        print(json.dumps({"status": "data_insufficient", "reason": "bridge csv missing"})); sys.exit(1)

    bridge = list(csv.DictReader(open(BRIDGE_CSV, encoding="utf-8")))
    ev_files = DXG.resolve_event_files()

    exact = [b for b in bridge if b.get("bridge_confidence") == "exact"]
    ambiguous_excluded = len(bridge) - len(exact)

    # process matches in strict chronological order so prior-xG-quality only ever sees earlier matches
    exact_sorted = sorted(exact, key=lambda b: (b["kickoff_date"], str(b["sb_match_id"])))

    # running per-team xG history (full-match totals from STRICTLY EARLIER matches only)
    team_hist: dict[str, list[float]] = {}

    out_rows = []
    matches_with_events = 0
    matches_missing_events = 0
    parsed = {}     # sb_match_id -> MatchEvents (cache)

    for b in exact_sorted:
        sid = str(b["sb_match_id"])
        fp = ev_files.get(sid)
        if not fp:
            matches_missing_events += 1
            continue
        raw = Path(fp).read_bytes()
        home_c = canonical_team_name(b["sb_home"]); away_c = canonical_team_name(b["sb_away"])
        me = DXG.parse_match_events(raw, home_c, away_c, sid)
        parsed[sid] = me
        matches_with_events += 1

        # prior xG quality = mean of full-match team-xG over strictly-earlier matches (leakage-safe)
        h_hist = team_hist.get(home_c, []); a_hist = team_hist.get(away_c, [])
        prior_quality = {
            "home": round(sum(h_hist) / len(h_hist), 6) if h_hist else None,
            "away": round(sum(a_hist) / len(a_hist), 6) if a_hist else None,
            "n_home": len(h_hist), "n_away": len(a_hist),
        }

        # xG-state available iff the match has at least one parsed shot carrying an xG model value
        xg_state_available = int(any(s.has_xg for s in me.shots))
        for t in DXG.GRID:
            f = DXG.dynamic_features_at(me, float(t), prior_quality=prior_quality)
            row = {
                "canonical_match_id": b["bridge_id"], "api_fixture_id": b["api_fixture_id"],
                "sb_match_id": sid, "competition_label": b["competition_label"],
                "comp_type": "international", "kickoff_date": b["kickoff_date"],
                "home": b["api_home"], "away": b["api_away"],
                "snapshot_minute": t, "source_cutoff_minute": t,
                "regulation_eligible": int(t <= 90),
                **f,
                # source-aware provenance / missingness flags
                "xg_source": DXG.XG_SOURCE,
                "has_xg_model": 1,
                "xg_state_available": xg_state_available,
                "big_chance_xg_threshold": DXG.BIG_CHANCE_XG,
                "big_chance_is_proxy": 1,
                "source_event_order_ok": me.event_order_ok,
                "extra_time_events_present": int(me.extra_time_count > 0),
                "sb_events_sha256": me.sha256,
                "xg_eligible": int(t <= 90),
                "feature_builder_version": DXG.FEATURE_BUILDER_VERSION,
            }
            out_rows.append(row)

        # AFTER emitting this match's rows, fold its full-match xG into the running history for FUTURE matches
        full = _full_match_team_xg(me)
        team_hist.setdefault(home_c, []).append(full["H"])
        team_hist.setdefault(away_c, []).append(full["A"])

    if not out_rows:
        msg = {"status": "data_insufficient", "reason": "no xG-eligible snapshots produced",
               "matches_with_events": matches_with_events}
        COVERAGE.parent.mkdir(parents=True, exist_ok=True)
        COVERAGE.write_text(json.dumps(msg, indent=2), encoding="utf-8")
        print(json.dumps(msg)); sys.exit(1)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    cols = list(out_rows[0].keys())
    out_rows.sort(key=lambda x: (x["competition_label"], x["kickoff_date"], x["sb_match_id"], x["snapshot_minute"]))
    with OUT.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for r in out_rows:
            w.writerow(r)

    # --- coverage report -------------------------------------------------------------------------
    import collections
    by_comp = collections.Counter(r["competition_label"] for r in out_rows)
    distinct_matches = len({r["sb_match_id"] for r in out_rows})
    xg_eligible = sum(r["xg_eligible"] for r in out_rows)
    rows_nonzero = sum(1 for r in out_rows if r["cum_xg_home"] + r["cum_xg_away"] > 0)
    rows_with_prior = sum(1 for r in out_rows
                          if r["prior_xg_quality_home"] is not None or r["prior_xg_quality_away"] is not None)
    completeness_vals = [r["xg_completeness"] for r in out_rows]
    coverage = {
        "status": "complete",
        "feature_builder_version": DXG.FEATURE_BUILDER_VERSION,
        "out_csv": str(OUT),
        "exact_bridge_matches": len(exact),
        "ambiguous_excluded": ambiguous_excluded,
        "matches_with_events": matches_with_events,
        "matches_missing_events": matches_missing_events,
        "distinct_matches_in_output": distinct_matches,
        "snapshots_built": len(out_rows),
        "xg_eligible_international_snapshots": xg_eligible,
        "rows_with_nonzero_xg": rows_nonzero,
        "rows_with_prior_xg_quality": rows_with_prior,
        "grid_minutes": DXG.GRID,
        "by_competition_rows": dict(by_comp),
        "xg_completeness_min": min(completeness_vals),
        "xg_completeness_mean": round(sum(completeness_vals) / len(completeness_vals), 5),
        "big_chance_proxy_threshold": DXG.BIG_CHANCE_XG,
        "xg_source": DXG.XG_SOURCE,
        "leakage_rules": [
            "xG at t excludes shots after t (per-shot match-clock minute <= t)",
            "per-match extraction; no cross-match leakage",
            "regulation grid only (t<=90, period<=2); ET/shootout excluded from features",
            "prior_xg_quality uses strictly-earlier matches only (kickoff-date ordered)",
            "missing statsbomb_xg counted in shot COUNTS but contributes 0 to xG SUMS; never imputed",
            "no fixture without a StatsBomb model receives an xG-state row",
        ],
    }
    COVERAGE.parent.mkdir(parents=True, exist_ok=True)
    COVERAGE.write_text(json.dumps(coverage, indent=2), encoding="utf-8")

    # mirror coverage into the model_phase run dir
    RUN_PHASE.mkdir(parents=True, exist_ok=True)
    (RUN_PHASE / "dynamic_xg_state_coverage.json").write_text(json.dumps(coverage, indent=2), encoding="utf-8")

    # --- data card -------------------------------------------------------------------------------
    feature_cols = [c for c in cols if c not in (
        "canonical_match_id", "api_fixture_id", "sb_match_id", "competition_label", "comp_type",
        "kickoff_date", "home", "away", "snapshot_minute", "source_cutoff_minute", "regulation_eligible",
        "xg_source", "has_xg_model", "xg_state_available", "big_chance_xg_threshold", "big_chance_is_proxy",
        "source_event_order_ok", "extra_time_events_present", "sb_events_sha256", "xg_eligible",
        "feature_builder_version")]
    CARD.parent.mkdir(parents=True, exist_ok=True)
    CARD.write_text(_data_card(coverage, feature_cols), encoding="utf-8")

    print(json.dumps({k: coverage[k] for k in (
        "status", "snapshots_built", "xg_eligible_international_snapshots", "distinct_matches_in_output",
        "rows_with_nonzero_xg", "rows_with_prior_xg_quality", "matches_with_events")}))


def _data_card(cov: dict, feature_cols: list) -> str:
    lines = []
    lines.append("# Data Card -- Dynamic xG State v1 (Component 3, Phase 3)")
    lines.append("")
    lines.append("research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible")
    lines.append("")
    lines.append("## Source & scope")
    lines.append("- Population: senior men's INTERNATIONAL fixtures only (World Cup 2018/2022, Euro 2020/2024, "
                 "Copa America 2024).")
    lines.append("- xG source: StatsBomb open data (`statsbomb_xg`), joined to API-Football fixtures via the "
                 "EXACT bridge `api_statsbomb_match_bridge_v1.csv` (258 exact matches).")
    lines.append(f"- Matches with events used: {cov['matches_with_events']} "
                 f"(missing events: {cov['matches_missing_events']}).")
    lines.append(f"- Snapshots: {cov['snapshots_built']} over grid minutes {cov['grid_minutes']} "
                 f"(regulation only).")
    lines.append("- Event files resolved ONLY through the canonical data-root registry "
                 "(`statsbomb_raw`, then `statsbomb_raw_prior`). No hard-coded paths; the active collector "
                 "checkout is never a data source.")
    lines.append("")
    lines.append("## Leakage / causal guarantees")
    for r in cov["leakage_rules"]:
        lines.append(f"- {r}")
    lines.append("")
    lines.append("## Source-aware missingness")
    lines.append("- `xg_source` = statsbomb_open and `has_xg_model` = 1 on every row; rows exist ONLY for "
                 "exact-bridge StatsBomb matches.")
    lines.append("- A shot whose `statsbomb_xg` is null contributes to `n_shots_to_t` and to shot-count "
                 "diffs, but contributes 0.0 to xG sums; this is recorded via `xg_completeness` "
                 "(`n_shots_with_xg_to_t / n_shots_to_t`). Such shots are NOT imputed.")
    lines.append(f"- `xg_completeness` over all rows: min={cov['xg_completeness_min']}, "
                 f"mean={cov['xg_completeness_mean']}.")
    lines.append("- No fixture lacking a StatsBomb xG model receives a fabricated xG-state row.")
    lines.append("")
    lines.append("## Big-chance proxy")
    lines.append(f"- StatsBomb open data has NO Opta-style big-chance tag. `big_chance_proxy_*` count shots "
                 f"with `statsbomb_xg` >= {cov['big_chance_proxy_threshold']} (`big_chance_is_proxy` = 1). "
                 f"This is an xG-threshold PROXY, not a vendor big-chance flag.")
    lines.append("")
    lines.append("## Prior xG quality")
    lines.append("- `prior_xg_quality_{home,away}` = mean full-regulation team xG over STRICTLY EARLIER "
                 "matches (by kickoff date) in this corpus; null when the team has no earlier match here. "
                 "`prior_xg_n_matches_{home,away}` gives the support. This is the only feature that crosses "
                 "match boundaries, and it only ever looks backward in time.")
    lines.append("")
    lines.append("## Feature columns (dynamic state)")
    for c in feature_cols:
        lines.append(f"- `{c}`")
    lines.append("")
    lines.append("## Provenance / integrity")
    lines.append("- `sb_events_sha256`: SHA-256 of the exact StatsBomb event file used (xG source hash).")
    lines.append("- `source_event_order_ok`: 1 if the raw event index sequence is non-decreasing.")
    lines.append("- `extra_time_events_present`: 1 if the match had ET/shootout shots (EXCLUDED from features).")
    lines.append("- This card is generated by `scripts/build_dynamic_xg_state.py`; audited by "
                 "`scripts/audit_dynamic_xg_state.py`.")
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    main()
