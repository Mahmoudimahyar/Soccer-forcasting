"""Build the canonical 2022 in-play state dataset + data card (research-only)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from wcdrawlab.research.inplay_dataset import build_state_table, SCHEMA_VERSION  # noqa: E402

OUT = ROOT / "data/processed"
df = build_state_table(ROOT / "data/raw/api_football_2022_worldcup",
                       ROOT / "data/processed/research_modeling_table.csv",
                       ROOT / "data/processed/market_features_2022.csv")

target = OUT / "inplay_state_2022_group_stage.parquet"
fmt = "parquet"
try:
    df.to_parquet(target, index=False)
except Exception:
    target = OUT / "inplay_state_2022_group_stage.csv"; fmt = "csv"
    df.to_csv(target, index=False)

print(f"wrote {target.name} ({fmt}): {len(df)} rows, {df.match_id.nunique()} matches, {df.shape[1]} cols")
print("decision_type counts:", df.decision_type.value_counts().to_dict())

card = ROOT / "data/processed/inplay_state_2022_group_stage_data_card.md"
card.write_text(f"""# In-Play State Dataset — 2022 WC Group Stage (data card)

**Research-only / experimental / not_runtime_approved.** Built by `scripts/build_inplay_state_2022.py`
from the validated 2022 event replay (`event-replay-2022-validated`). Schema `{SCHEMA_VERSION}`.

## Volume
- rows (decision points): **{len(df)}** · matches: **{df.match_id.nunique()}** · columns: {df.shape[1]}
- decision points: fixed {{0,15,30,45,60,75,85}} + event-triggered (goal/card/sub/VAR).
- decision_type counts: {df.decision_type.value_counts().to_dict()}

## Leakage rule
At decision minute t, features use ONLY events with minute <= t (via `event_semantics.interpret_event`).
Targets use future events (labels only). Each row carries `source_snapshot_sha256` (raw events hash).

## Features (available)
score_home/away, score_diff, remaining_minutes, wld_state; yellow/red/second-yellow by team, red_diff;
subs_home/away; pre-match B1 Elo probs (p_*_elo) + elo_delta_home; pre-match market probs (p_*_market,
where present); pregame_completeness.

## Unavailable (flagged, NOT imputed)
shots, shots-on-target, xG, corners, set-pieces, starting XI / on-pitch player IDs, formations
(`shots_available=xg_available=corners_available=setpieces_available=0`, `unknown_lineup_flag=1`).

## Targets
final_wld, final_score, final_gd, next_goal_team, goal_within_{{1,3,5,10}}, red_within_{{5,10}},
remaining_goals_home/away.

## Provenance / governance
2022 only (48 matches) — a foundation, NOT production-generalizable. Raw events immutable + gitignored;
this derived table is gitignored (data/processed/); builder + card + tests are tracked.
""", encoding="utf-8")
print("wrote data card")
