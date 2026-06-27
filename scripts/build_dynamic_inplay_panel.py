"""Phase-1 build: canonical leakage-safe DYNAMIC in-play panel from the FULL API-Football corpus.

research_only / experimental / not_runtime_approved.

Resolves all sources through the data-root registry, builds the full causal snapshot panel via
``wcdrawlab.research.dynamic_state``, joins the already-validated StatsBomb xG snapshot product
(``data/processed/xg_snapshot_join_v1.csv``) onto the international state table on (api_fixture_id,
snapshot_minute), and writes the family of derived data products under
``data/processed/model_phase/`` (parquet). A run summary is mirrored to
``outputs/research_runs/truth_20260626_134931/model_phase/``.

Run:  python scripts/build_dynamic_inplay_panel.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import pandas as pd  # noqa: E402

from wcdrawlab.research import data_roots as DR  # noqa: E402
from wcdrawlab.research import dynamic_state as DS  # noqa: E402

OUT_PROC = ROOT / "data/processed/model_phase"
OUT_RUN = ROOT / "outputs/research_runs/truth_20260626_134931/model_phase"
XG_JOIN = ROOT / "data/processed/xg_snapshot_join_v1.csv"

# Columns carried from the xG snapshot product into the xG-enriched international table.
XG_FEATURE_COLS = [
    "sb_match_id", "cum_xg_home", "cum_xg_away", "cum_xg_diff", "roll5_xg_diff", "roll10_xg_diff",
    "xg_momentum", "shot_count_diff", "shot_on_target_diff", "time_since_last_shot",
    "time_since_last_major_chance", "n_shots_to_t", "xg_completeness", "source_event_order_ok",
    "extra_time_events_present", "sb_events_sha256", "xg_eligible",
]


def _write(df: pd.DataFrame, name: str) -> dict:
    OUT_PROC.mkdir(parents=True, exist_ok=True)
    p = OUT_PROC / f"{name}.parquet"
    df.to_parquet(p, index=False)
    return {"product": name, "path": str(p), "rows": int(len(df)),
            "matches": int(df["api_fixture_id"].nunique()) if "api_fixture_id" in df else None}


def main():
    fixtures, events, lineups, src_root = DS.load_full_corpus()

    usable = [fid for fid in fixtures
              if str(fid) in events and str(fid) in lineups]
    all_rows, skipped = [], []
    n_ok = n_aux = 0
    for fid in usable:
        fx = fixtures[fid]
        rows, status, reason = DS.build_snapshots_for_fixture(
            fid, fx, events[str(fid)], lineups[str(fid)], src_root)
        if not rows:
            skipped.append({"fixture": fid, "status": status, "reason": reason})
            continue
        all_rows.extend(rows)
        if status == "ok":
            n_ok += 1
        else:
            n_aux += 1

    panel = pd.DataFrame(all_rows)
    if panel.empty:
        summary = {"status": "data_insufficient", "reason": "no snapshots built from corpus",
                   "usable_fixtures": len(usable)}
        OUT_RUN.mkdir(parents=True, exist_ok=True)
        (OUT_RUN / "build_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(json.dumps(summary)); return summary

    products = []

    # 1. International regulation-time state table (the test population)
    intl = panel[panel.is_international == 1].copy()
    intl_reg = intl[intl.regulation_eligible == 1].copy()
    products.append(_write(intl_reg, "international_regulation_state"))

    # 2. Club auxiliary state table (player-prior history only; never a test row)
    club = panel[panel.is_international == 0].copy()
    products.append(_write(club, "club_auxiliary_state"))

    # 3. Player-on-pitch state (compact: ids + counts) for international rows
    onpitch_cols = ["canonical_match_id", "api_fixture_id", "competition", "season", "kickoff_date",
                    "comp_type", "snapshot_minute", "period", "players_on_pitch_home",
                    "players_on_pitch_away", "player_count_diff", "on_pitch_home_ids", "on_pitch_away_ids",
                    "regulation_target_eligible"]
    products.append(_write(panel[onpitch_cols].copy(), "player_on_pitch_state"))

    # 4. Starting-XI / bench state
    xi_cols = ["canonical_match_id", "api_fixture_id", "comp_type", "snapshot_minute",
               "n_starters_home", "n_starters_away", "n_bench_home", "n_bench_away",
               "starting_home_ids", "starting_away_ids", "bench_home_ids", "bench_away_ids",
               "has_lineups", "regulation_target_eligible"]
    products.append(_write(panel[xi_cols].copy(), "starting_xi_bench_state"))

    # 5. Substitution-delta state
    sub_cols = ["canonical_match_id", "api_fixture_id", "comp_type", "snapshot_minute", "period",
                "subs_home", "subs_away", "subs_diff", "regulation_target_eligible"]
    products.append(_write(panel[sub_cols].copy(), "substitution_delta_state"))

    # 6. Team-discipline state
    disc_cols = ["canonical_match_id", "api_fixture_id", "comp_type", "snapshot_minute", "period",
                 "yellow_home", "yellow_away", "second_yellow_home", "second_yellow_away",
                 "red_home", "red_away", "red_diff", "regulation_target_eligible"]
    products.append(_write(panel[disc_cols].copy(), "team_discipline_state"))

    # 7. Next-goal target state (intl + club; eligibility flagged)
    ng_cols = ["canonical_match_id", "api_fixture_id", "comp_type", "snapshot_minute", "remaining_minutes",
               "score_diff", "player_count_diff", "card_diff" if "card_diff" in panel else "yellow_home",
               "next_goal_15", "next_goal_team", "regulation_target_eligible"]
    ng_cols = [c for c in ng_cols if c in panel.columns]
    products.append(_write(panel[ng_cols].copy(), "next_goal_target_state"))

    # 8. Regulation W/D/L target state (international, reconciled, t<=90)
    wdl = intl_reg[intl_reg.regulation_target_eligible == 1].copy()
    products.append(_write(wdl, "regulation_wdl_target_state"))

    # 9. xG-enriched international state (join validated xG snapshot product)
    xg_status = _build_xg_enriched(intl_reg, products)

    # 10. Match-quality / source-completeness table
    mq = (panel.groupby(["api_fixture_id", "canonical_match_id", "comp_type", "competition", "season",
                         "kickoff_date"])
          .agg(n_snapshots=("snapshot_minute", "count"),
               reconciliation_status=("reconciliation_status", "first"),
               reconciliation_exception=("reconciliation_exception", "first"),
               has_lineups=("has_lineups", "first"),
               events_source_root=("events_source_root", "first"),
               final_result_type=("final_result_type", "first"),
               regulation_target_eligible=("regulation_target_eligible", "max"))
          .reset_index())
    products.append(_write(mq, "match_quality_source_completeness"))

    # 11. Player-history completeness (per match: on-pitch id coverage as proxy)
    ph = panel.groupby(["api_fixture_id", "comp_type"]).agg(
        max_on_pitch_ids_home=("n_on_pitch_ids_home", "max"),
        max_on_pitch_ids_away=("n_on_pitch_ids_away", "max"),
        n_starters_home=("n_starters_home", "first"),
        n_starters_away=("n_starters_away", "first"),
        has_lineups=("has_lineups", "first")).reset_index()
    ph["player_history_complete"] = ((ph.n_starters_home >= 11) & (ph.n_starters_away >= 11)).astype(int)
    products.append(_write(ph, "player_history_completeness"))

    # 13. event-timing / source-order table
    et = panel[["api_fixture_id", "comp_type", "snapshot_minute", "snapshot_kind", "period",
                "events_source_root", "events_sha256", "lineups_sha256",
                "source_semantics_version"]].copy()
    products.append(_write(et, "event_timing_source_order"))

    summary = {
        "status": "complete" if len(wdl) > 0 else "data_insufficient",
        "schema_version": DS.SCHEMA_VERSION,
        "source_semantics_version": DS.SOURCE_SEMANTICS_VERSION,
        "usable_fixtures_events_and_lineups": len(usable),
        "fixtures_with_regulation_target": n_ok,
        "fixtures_auxiliary_only": n_aux,
        "skipped_fixtures": len(skipped),
        "total_snapshot_rows": int(len(panel)),
        "international_regulation_rows": int(len(intl_reg)),
        "international_regulation_matches": int(intl_reg.api_fixture_id.nunique()),
        "regulation_wdl_target_rows": int(len(wdl)),
        "regulation_wdl_target_matches": int(wdl.api_fixture_id.nunique()),
        "club_auxiliary_rows": int(len(club)),
        "club_auxiliary_matches": int(club.api_fixture_id.nunique()),
        "wdl_class_balance": wdl.target_wdl.value_counts().to_dict() if len(wdl) else {},
        "xg_enriched": xg_status,
        "products": products,
    }

    OUT_RUN.mkdir(parents=True, exist_ok=True)
    (OUT_RUN / "build_summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    print(json.dumps(summary, indent=2, default=str))
    return summary


def _build_xg_enriched(intl_reg: pd.DataFrame, products: list) -> dict:
    """Join the validated xG snapshot product onto the international regulation state on
    (api_fixture_id, snapshot_minute). xG is a left-join feature add; rows without xG keep NaN +
    xg_join_available=0 (never imputed). The xG product's own cutoff guard already enforces no future xG."""
    if not XG_JOIN.exists():
        return {"status": "threshold_blocked", "reason": "xg_snapshot_join_v1.csv missing"}
    xg = pd.read_csv(XG_JOIN)
    keep = ["api_fixture_id", "snapshot_minute"] + [c for c in XG_FEATURE_COLS if c in xg.columns]
    xg = xg[keep].copy()
    # one row per (fixture, minute) in the xG product (dedupe defensively, keep first)
    xg = xg.drop_duplicates(["api_fixture_id", "snapshot_minute"], keep="first")
    merged = intl_reg.merge(xg, on=["api_fixture_id", "snapshot_minute"], how="left",
                            suffixes=("", "_xg"))
    merged["xg_join_available"] = merged["cum_xg_diff"].notna().astype(int)
    products.append(_write(merged, "international_state_xg_enriched"))
    matched_matches = int(merged.loc[merged.xg_join_available == 1, "api_fixture_id"].nunique())
    return {"status": "ok", "rows": int(len(merged)),
            "rows_with_xg": int(merged.xg_join_available.sum()),
            "matches_with_xg": matched_matches,
            "xg_product_matches": int(xg.api_fixture_id.nunique())}


if __name__ == "__main__":
    main()
