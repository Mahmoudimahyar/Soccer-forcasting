# Prospective Data Dictionary (V1.5)

## Ledger record (`data/processed/prospective/ledger.jsonl`, append-only, first-write-wins)
| field | meaning |
|---|---|
| ledger_key | unique `"{match_id}:{window}"`; first write wins, never overwritten |
| schema_version | `prospective_v1` |
| model_id / model_version | `m2_frozen` / `v2` (the frozen research model) |
| approval_status / not_runtime_approved | `research_only` / `true` (never runtime/paper/Kalshi) |
| match_id / kickoff_utc | fixture identity |
| phase / capture_window | `pre_match`/`in_play` ; `T-90`,`T-15`,`m0`,`m15`,`m30`,`HT`,`m60`,`m75`,`m85` |
| decision_minute | match minute the prediction is conditioned on (0 for pre-match) |
| decision_timestamp | wall-clock decision time (UTC) — the point-in-time cutoff |
| retrieval_timestamp | when the source was read |
| event_source_timestamp | source time of the events used; MUST be `<= decision_timestamp` (leakage guard) |
| p_home_win / p_draw / p_away_win | frozen M2 W/D/L probabilities |
| anchor_p_home / anchor_p_draw / anchor_p_away | B1/Elo pre-match anchor (reference, not the model) |
| state | `{elo_delta_home, decision_minute, score_home, score_away, red_home, red_away}` |
| source_hashes | provenance hashes of the inputs |
| data_completeness | fraction of required state fields present (0–1) |

## Score record (`data/processed/prospective/scores.jsonl`)
| field | meaning |
|---|---|
| ledger_key / match_id / phase / capture_window / decision_minute | links back to the prediction |
| final_wld / final_score_home / final_score_away | the FINISHED result (used ONLY to score) |
| rps_model / rps_anchor | ranked probability score for the frozen model vs the Elo anchor |
| log_loss_model / draw_brier_model | additional metrics |
| result_event_time | when the result actually occurred (kept separate from retrieval) |
| result_retrieval_time | when we read the result |
| scored_with | `m2_frozen@v2` |

## Session manifest (`.../sessions/manifest_<id>.jsonl`) + heartbeat
Append-only events: `captured`, `planned`, `skipped`, `duplicate`, `missed` (MISSED_UNRECOVERABLE),
`shutdown`. Each has an idempotent `event_key`. `heartbeat_<id>.json` carries last-alive timestamp +
counts. `shutdown_summary` writes a clean-shutdown record.

## Adapter raw store (`data/raw/operations/...`, gitignored, append-only)
Content-addressed payload files + `index.jsonl` provenance envelopes (`source`, `endpoint`,
`param_keys`, `status_class`, `payload_sha256`). **No key, no header secret, ever.**

## Integrity guarantees
First-write-wins (no key overwrite); `event_source_timestamp <= decision_timestamp`; probabilities sum
to 1; `approval_status == research_only`; no secret strings in any record. Verified by
`scripts/prospective_integrity_check.py`.
