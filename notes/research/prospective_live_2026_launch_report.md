# Prospective Live-2026 Shadow Evaluation — Launch Report (2026-06-21)

The prospective shadow system is live. **No live trading; B1 is the sole approved runtime 1X2 model;
`candidate.py` untouched; nothing promoted.** This is a sequential, leakage-safe, out-of-sample test
that accumulates honest evidence on whether a market blend helps — without altering the approved model.

## 1. Frozen model definitions (fixed for the whole evaluation)
| id | definition | status |
|---|---|---|
| M1_B1 | approved Elo (ternary, r=0.4) | approved |
| M2_market | no-vig market consensus (h2h) | shadow |
| M3_75_25 | 0.75·B1 + 0.25·market | shadow |
| M4_50_50 | 0.50·B1 + 0.50·market | shadow |
| M5_25_75 | 0.25·B1 + 0.75·market | shadow |

Weights, features, calibration, hyperparameters, thresholds, and uncertainty rules are **frozen** and
will not be changed based on any 2026 result.

## 2. Snapshot schedule
Per remaining fixture, capture pre-kickoff snapshots at **T-24h, T-90m, T-15m, and final pre-kickoff**
(h2h/us only; no props/parlays/player/in-play markets). Each Odds API live call captures **all**
currently-upcoming matches at once.

## 3. Odds API quota
- **Remaining: 13,099** credits (1 spent on the launch snapshot).
- **Estimated through the remaining group stage:** ~140 credits worst-case (4 snapshots × 35 matches
  if run per-match); ~30–60 with a batched cadence (one call captures all upcoming). **Negligible**
  vs 13,099.

## 4. Storage locations
- Raw odds (immutable): `data/raw/odds/live_2026/<snapshot_ts>.json`
- Normalized snapshots: `data/processed/odds_live_2026/<snapshot_ts>.csv`
- Frozen predictions (immutable, append-only): `outputs/research/live_2026_shadow_predictions.csv`
- Scoring outputs: `outputs/research/live_2026_shadow_metrics.csv`, `..._calibration.csv`
- Log: `notes/research/live_2026_shadow_log.md`

## 5. First upcoming fixtures being tracked (35 total, through 2026-06-28)
Belgium–Iran (06-21 19:00Z), Uruguay–Cape Verde (06-21 22:00Z), New Zealand–Egypt (06-22 01:00Z),
Argentina–Austria (06-22 17:00Z), France–Iraq (06-22 21:00Z), Norway–Senegal (06-23 00:00Z), …

## 6. Data-quality safeguards
- Predictions are immutable after kickoff; appended by (match_id, model, snapshot_ts), never modified.
- Each prediction carries the full envelope (SE, draw CI, entropy, risk band, data_completeness,
  market probs, book count, overround) + approval_status (M1 approved, M2–M5 shadow).
- Market only used pre-kickoff (snapshot strictly before kickoff); team names canonicalized; no-vig
  de-margining; data_completeness flags thin/absent markets (M1-only fallback when no market).
- Scoring uses authoritative results (football-data.org); paired bootstrap vs B1; per-matchday
  cumulative tracking.

## 7. 2026 format / tournament state
MD2/MD3 use the 48-team format (12 groups of 4, top two advance, eight best thirds, official
tiebreakers, cross-group third-place ranking) via the validated `official_standings.py`. Dynamic
state (p_advance, third-place safety, mutual draw utility, must-win pressure, schedule-adjusted group
state) updates after each completed match; **core model architecture stays frozen.**

## 8. Remaining provider gap
Results/standings for 2026 are covered FREE (football-data.org). **Lineups / cards / subs / events for
2026 are NOT available** (API-Football free is 2022–2024 only). Preferred fix: API-Football Pro
(~$25–30/mo, reuses the existing adapter). Details: `live_2026_provider_recommendation.md`. The
in-play engine is already validated offline on 2022 events.

## 9. Exact conditions required before ANY paper/demo-trading trial
All must hold (none are met today):
1. A shadow model is **promoted to approved** via the frozen protocol — i.e., a statistically
   significant, pre-registered improvement over B1 (on dev folds, which currently lack pre-2020 odds,
   OR a pre-declared prospective live-2026 criterion met with adequate sample), with no fold regression.
2. The **approved-model registry** is updated and a human explicitly tags the new approved version.
3. The **risk gate** (already registry-bound) passes; intents carry the approved model_id.
4. `KALSHI_ENABLE_LIVE_TRADING` remains **false** — any trial is **paper/demo only**.
5. A **reviewed, explicit market mapping** exists (no model-inferred Kalshi book side).
6. Human sign-off on the specific paper-trade configuration.
Until then: shadow evaluation only; no trading of any kind.

## Continuation command
```bash
python scripts/live_2026_shadow.py freeze   # after refreshing a live odds snapshot (T-24h/-90m/-15m/final)
python scripts/live_2026_shadow.py score    # after results refresh; writes metrics + calibration
```
