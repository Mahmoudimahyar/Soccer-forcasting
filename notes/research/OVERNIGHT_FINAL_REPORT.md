# Overnight Autoresearch — Final Report (2026-06-21)

Honest scope note: this session executed **Cycle 1** of the autoresearch run on branch
`autoresearch-overnight`. A single agent turn cannot literally stay open for 8 hours; this report
documents real, verified results from Cycle 1 and gives the exact command to resume further cycles.
All safety rules held: **no live trading, no promotion, no `.env`/trading/risk/provider/Kalshi
changes, no secret exposure.** `KALSHI_ENABLE_LIVE_TRADING` stays false. `pytest -q` → **91 passed**.

## 1. What was built or improved
- Safe config + connectivity audit (`setup_status.md`), processed-table census (`data_inventory.md §10`).
- Research-only evaluation harness: `configs/research_dev.yaml` (dev folds 2010/2014/2018, separate
  from the frozen evaluator), `scripts/research_eval.py`, `scripts/research_sweep.py`,
  `scripts/research_exp_draw.py`.
- Cycle 1 experiment batch (20 experiments) with honest accept/reject (`20260621_cycle_1.md`).
- **No model change accepted** — `candidate.py` is unchanged (V8); B1 remains the sole approved model.

## 2. Data sources connected and status
| source | status | use |
|---|---|---|
| The Odds API | ✅ working (~13.1k req left) | odds (live + 2020-06→ historical) |
| football-data.org | ✅ working | authoritative 2026 results/standings |
| Open-Meteo | ✅ working (keyless) | weather |
| open datasets (martj42, jfjelstul, FIFA, Transfermarkt) | ✅ ingested w/ hashes | Elo, structure, strength |
| API-Football | ❌ blocked (key invalid both auth modes) | lineups/events/injuries — unavailable |

## 3. Data-source requests requiring your action
- **API-Football** (`data_requests/pending/api_football.yaml`): supply a valid direct api-sports.io
  key OR a subscribed RapidAPI key + approve a one-line adapter change. (BLOCKERS.md B-1)
- **Historical odds backfill approval**: spend Odds API historical credits to load 2020-06→ odds
  (BLOCKERS.md B-2) — the single highest-value next step.
- Pending (Gate 1, awaiting sign-off): `open_meteo`, `statsbomb_open_data`, `fbref_player_minutes`,
  `referee_history`.

## 4. Baseline and best-model metric tables (DEV selection folds)
| model | RPS | LogLoss | drawBrier | drawECE | **J** |
|---|---|---|---|---|---|
| B0 frequency prior | 0.2471 | 1.1018 | — | — | 0.4187 |
| B1 Elo (approved) | 0.1901 | 0.9391 | — | — | 0.3553 |
| **V8 candidate (current)** | **0.1901** | **0.9389** | **0.1733** | **0.0581** | **0.3541** |
| best sweep variant (blend 0.90) | 0.190 | — | — | 0.0568 | 0.3539 (rejected: <0.002, noise) |

V8 ≈ B1 (no significant gap, prior paired bootstrap CI includes 0). **No candidate beats V8/B1 by the
promotion threshold.**

## 5. 2018 / 2022 / 2026-MD1 results (separately, V8 — unchanged)
| fold | RPS | LogLoss | drawBrier | drawECE | J | role |
|---|---|---|---|---|---|---|
| 2018 | 0.1976 | 0.9404 | 0.1592 | 0.0543 | 0.3541 | dev |
| 2022 | 0.2445 | 1.1240 | 0.1558 | 0.0417 | 0.4162 | release gate |
| 2026-MD1 | 0.1865 | 1.0543 | 0.2757 | 0.2104 | 0.4249 | **locked transfer** |

## 6. Remaining-2026 prequential prediction status
- Frozen pre-kickoff forecasts for the 39 remaining MD2/MD3 matches exist (`forecast_ledger.csv`,
  snapshot 2026-06-20, immutable). The **approved** runtime forecast (B1) is in
  `outputs/research/forecasts/approved_forecast_2026.csv`; the market blend is shadow-only.
- Prequential over the **33 finished 2026 group matches** (per-match refit): B1 RPS **0.174**,
  LogLoss 0.958, drawECE 0.178; V8 RPS 0.225, LogLoss 1.092, drawECE 0.004; B0 RPS 0.215. **B1 leads
  on RPS/log-loss; V8 leads on draw calibration.** No architecture/threshold was tuned to these.
- 0 of the 39 ledger matches are scorable yet in the frozen results cache (not refreshed this session).

## 7. Calibration and uncertainty coverage
- V8 draw calibration is good on dev (drawECE ~0.058) but **poor on the locked 2026-MD1 fold
  (0.2104)** for the fixed pre-2026 model — a drift signal, not an architecture gain.
- Draw-recalibration experiments (Platt, temperature) did **not** improve dev calibration without
  regressing folds → rejected.

## 8. Accepted model changes
**None.** `candidate.py` unchanged (V8). No promotion; B1 remains the approved runtime model.

## 9. Rejected hypotheses and why
- **18-combo hyperparameter/feature sweep (C × blend × full/lean):** best gain 0.0002 (< 0.002
  threshold) → noise; `full ≡ lean` (market/proxy features inert in historical data).
- **Draw Platt recalibration:** dev J 0.3541→0.3579 (overfits train draw structure).
- **Draw temperature shrink:** noise-level mean change AND regresses 2 of 3 dev folds.

## 10. Known weaknesses
- Candidate is **saturated** on the historical feature set (architecture ≈ tapped out).
- Market signal (the only thing shown to beat Elo) is **not validatable pre-2020** → no significant
  promotion path without the odds backfill.
- No lineups/injuries/event data (API-Football blocked) → in-play + availability work blocked.
- Locked-fold draw calibration drift on 2026-MD1.

## 11. Recommended next 24-hour research plan
1. **(highest value)** On approval: backfill timestamped odds 2020-06→ into schema N (append-only
   store); build a market-anchored candidate; paired-bootstrap vs B1 on odds-covered folds. This is
   the only evidenced route to beat Elo.
2. Unblock API-Football (valid key) → ingest confirmed lineups/injuries → pre-match strength
   adjustment; ablate on dev folds.
3. Historical event-level data (StatsBomb open) → offline xG / in-play replay harness (priority #12),
   scored by minute-bucket calibration.
4. Keep `candidate.py` frozen until one of the above yields a bootstrap-significant dev gain.

## 12. Exact command to resume another research cycle
```bash
cd /c/Users/Mahyar/worldcup_draw_model_lab_FINAL
git switch autoresearch-overnight
python -m pytest -q
python scripts/research_eval.py configs/research_dev.yaml      # dev baseline (selection)
python scripts/research_eval.py configs/research.yaml          # gate 2022 + locked 2026-MD1
python scripts/research_sweep.py                               # architecture sweep (exhausted)
# then iterate candidate.py per docs/AUTORESEARCH_GOVERNANCE.md; accept only >=0.002 dev gain, no fold regression
```
