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
