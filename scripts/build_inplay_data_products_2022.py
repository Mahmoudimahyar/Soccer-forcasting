"""Split the 2022 in-play state table into separate research data products + a manifest (Phase D).
Available products are written (gitignored); blocked ones are recorded with reasons. Research-only.
"""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/processed/inplay_products_2022"; OUT.mkdir(parents=True, exist_ok=True)
df = pd.read_parquet(ROOT / "data/processed/inplay_state_2022_group_stage.parquet")

ident = ["match_id", "group", "matchday", "home_team", "away_team", "decision_minute"]
products = {}

# 1 pre-match state (one row per match at minute 0)
pm = df[df.decision_minute == 0][["match_id", "group", "matchday", "home_team", "away_team",
        "elo_delta_home", "p_home_elo", "p_draw_elo", "p_away_elo",
        "p_home_market", "p_draw_market", "p_away_market", "pregame_completeness", "final_wld"]]
products["pre_match_state"] = ("available", pm)

# 2 in-play team-state (W/D/L)
team = df[ident + ["score_home", "score_away", "score_diff", "remaining_minutes",
        "yellow_home", "yellow_away", "red_home", "red_away", "red_diff",
        "subs_home", "subs_away", "elo_delta_home", "final_wld"]]
products["inplay_team_state"] = ("available", team)

# 4 event-horizon targets
ev = df[ident + ["score_diff", "remaining_minutes", "elo_delta_home", "red_diff",
        "goal_within_1", "goal_within_3", "goal_within_5", "goal_within_10", "next_goal_team"]]
products["event_horizon_targets"] = ("available", ev)

# 5 card/discipline targets
card = df[ident + ["yellow_home", "yellow_away", "red_home", "red_away", "secondyellow_home",
        "secondyellow_away", "red_within_5", "red_within_10"]]
products["card_discipline_targets"] = ("available_low_signal", card)  # red targets ~unlearnable

# 6 substitution-state (counts only; impact blocked)
sub = df[ident + ["subs_home", "subs_away", "next_goal_team"]]
products["substitution_state"] = ("available_counts_only", sub)

# 3 player/on-pitch state — BLOCKED
products["player_on_pitch_state"] = ("blocked", None)
# 7 weather/travel context — BLOCKED (not joined for 2022; archive fetch not done)
products["weather_travel_context"] = ("blocked", None)
# 8 in-play tournament qualification state — PARTIAL (pre-match group state only; not in this table)
products["tournament_qualification_state"] = ("partial_prematch_only", None)

manifest = ["# In-Play Data Products 2022 — manifest (research-only)\n",
            "Built by `scripts/build_inplay_data_products_2022.py` from the validated 2022 state table.",
            "Products written to `data/processed/inplay_products_2022/` (gitignored).\n",
            "| product | status | rows | cols | note |", "|---|---|---|---|---|"]
for name, (status, d) in products.items():
    if d is not None:
        d.to_csv(OUT / f"{name}.csv", index=False)
        note = {"available": "ready", "available_low_signal": "red targets <1% positive -> not modelable",
                "available_counts_only": "no player IDs/positions -> impact not modelable"}.get(status, "")
        manifest.append(f"| {name} | {status} | {len(d)} | {d.shape[1]} | {note} |")
    else:
        reason = {"player_on_pitch_state": "no on-pitch player IDs/positions in available feed",
                  "weather_travel_context": "venue weather not joined (archive fetch not approved)",
                  "tournament_qualification_state": "in-play qualification state needs group-stage live standings"}[name]
        manifest.append(f"| {name} | {status} | 0 | 0 | BLOCKED: {reason} |")

(ROOT / "notes/research/inplay_data_products_2022_manifest.md").write_text("\n".join(manifest) + "\n", encoding="utf-8")
print("\n".join(manifest))
