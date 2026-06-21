# Market + Replay — Next Steps (2026-06-21)

Summary of the strict-discipline session. **No live trading; B1 remains the sole approved runtime
1X2 model; `candidate.py` untouched; no protected/`.env` edits; 2022 used only as a release gate.**

## 1. Market shadow evaluation verdict (2022, read-only)
Adding market info to B1 yields **statistically significant log-loss improvements** (equal & 75/25 &
50/50 blends: dLogLoss CIs exclude 0) and the **75/25 blend significantly improves RPS** (dRPS CI
[-0.013, -0.0005]). Market-alone is directionally best (RPS 0.224 vs B1 0.243) but its RPS CI
includes 0 (48 matches underpowered) and it is worse-calibrated on draws. Details:
`market_shadow_evaluation_2022.md`.

## 2. Does market signal appear incremental to B1?
**Yes — suggestively, on this single fold.** The effect is consistent and significant for log loss.
But one tournament (a release gate) is **not** sufficient evidence to promote a blend, and no blend
weight was selected from 2022.

## 3. Is 2022 event-time replay feasible?
**Yes — operational.** All 48 group matches' events were cached and a leakage-safe replay built
(288 rows). The in-play engine validates: RPS 0.255→0.000 and log loss 1.19→0.008 monotonically from
t=15 to t=90. Trustworthy historical variables: minute, score, goals, red cards, subs. **Missing: xG.**
Details: `api_football_2022_replay_report.md`.

## 4. API-Football quota used / remaining
**~51 of 100 used today** (fixtures + 2 probes + 48 events); **~49 remaining**, resets daily.
Per-minute cap is 10 (now respected by the quota-aware scheduler). Free plan = seasons 2022–2024
(no 2026).

## 5. Historical odds options for 2010/2014/2018
**None are clean, open, and timestamp-valid.** The Odds API starts 2020-06; football-data.co.uk has
no internationals; OddsPortal prohibits scraping; Betfair historical is paid and effectively
≥2016/2018; Kaggle/academic copies lack verifiable pre-kickoff timestamps and clean licensing.
Details + per-source table: `data_requests/pending/historical_odds_dev_folds.yaml`.

## 6. Exact blocker preventing leakage-safe market-model promotion
**No development-fold (pre-2022) odds exist.** A market blend can only be shown to help on the 2022
gate and (prospectively) on live 2026 — neither is a pre-selection dev fold. Without 2010/2014/2018
odds, **a market model cannot clear the frozen promotion protocol** (significant improvement on dev
folds, no regression). This is a **data** blocker, not a modeling one.

## 7. The one highest-value next experiment
**Prospective market-vs-B1 on live 2026 (paper, no promotion):** for each remaining 2026 match,
freeze B1 and a predeclared 75/25 B1/market blend before kickoff, log both, and score after the
final whistle (RPS/log loss/draw calibration). This is a *legitimate sequential out-of-sample test*
using the already-working Odds API live feed — the only way to accumulate honest, leakage-safe
evidence for a market blend without pre-2020 odds. It does not promote anything; it builds the
evidence file that *could* justify promotion later. (Requires your ok to log live 2026 odds snapshots
— modest credit use.)

Runner-up (no cost): bulk-cache 2022 lineups/statistics via the quota-aware scheduler to extend the
in-play replay with lineup-time features.

## 8. Is a paid provider upgrade justified?
- **Odds API upgrade:** not needed (13,100 credits remain; live 2026 capture is affordable).
- **API-Football paid:** justified **only if** live 2026 lineups/events/in-play become a priority
  (free tier can't do 2026). For *historical* in-play research, the free 2022–2024 window suffices.
- **A paid historical-odds feed for 2010–2018:** **not justified** — coverage with verifiable
  pre-kickoff timestamps is doubtful, so it likely still wouldn't enable dev-fold selection.

**Net:** the binding constraint remains data (pre-2020 odds don't exist openly). The honest path is
prospective live-2026 evaluation, not another historical purchase. B1 stays approved meanwhile.
