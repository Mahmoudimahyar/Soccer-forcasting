> [!WARNING]
> **SUPERSEDED — historical Tier-1 snapshot (2026-06-20). Do not cite.** Kept unedited below as part of
> the audit trail. It is wrong on four counts today: (1) the repository *is* under git; (2) the test count is
> stale; (3) the "active accepted model" it names (`candidate.py`, V8) was **never approved** — the sole
> approved runtime model is **B1 ternary-Elo** (`configs/approved_models.yaml`); (4) its "validated finding"
> that a market+Elo blend *beats the no-vig market and Pinnacle close by ~4–7% RPS* is an **early
> retrospective point estimate with no confidence interval**, later reclassified as auxiliary
> (`notes/research/model_state_reconciliation.md`) and **not confirmed prospectively**: on 34 frozen 2026
> fixtures no model was distinguishable from the market
> (`notes/research/PROSPECTIVE_MARKET_BENCHMARK_V1.md`). See [`../ERRATA.md`](../ERRATA.md).

# Version Manifest

The repository is not under git in this environment, so the "exact data/model version" is
pinned here (content hashes are in `data/processed/source_provenance.json`).

## tier1-2026-06-20
- **Tier:** 1 (Data, Provenance & Leakage Foundation) — COMPLETE.
- **Tests:** `pytest -q` → 51 passed.
- **Canonical data table:** `data/processed/research_modeling_table.csv`
  (369 played WC group matches, 1998–2026).
- **Sources + content hashes:** `data/processed/source_provenance.json` (9 sources).
- **Active accepted model (carried from prior cycles, frozen for Tier 1):**
  `src/wcdrawlab/research/candidate.py` — standardized logit + 0.85 ternary-Elo blend.
- **Validated finding (carried):** market + ~0.4·Elo blend beats no-vig market + Pinnacle close
  ~4–7% RPS out-of-sample (notes/research/20260620_cycle_4.md, _cycle_5_true_alpha.md).
- **Safety:** `KALSHI_ENABLE_LIVE_TRADING=false`, `TRADING_MODE=paper`. Protected files
  (configs/research.yaml, configs/trading.yaml, trading/**, providers/**, scraping/**, .env*,
  simulation/standings.py) unchanged this tier.

## Key artifact hashes (see source_provenance.json for full list)
- martj42 international_results: sha256 64d75097f252…
- football-data 2026: sha256 e78a688bf28f…
- the_odds_api 2026 live: sha256 07b61eecd940…
- transfermarkt duckdb: sha256 e865db6cf719…
