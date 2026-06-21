# Tier 1 Baseline Commit

Reproducible research baseline created before Tier 2.

## Commit
- **Hash:** `e78cde4376605f6e787a375fe12162c3f81240d0`
- **Tag:** `tier-1-complete`
- **Subject:** `Baseline: Tier 1 provenance, leakage guards, and official 2026 standings`
- Files committed: 183 (code, docs, tests, schemas, configs, seed/reference data, `.gitignore`,
  safe `.env.example` placeholders, source registry).

## `.env` ignored — confirmed safely
- `git check-ignore -v .env` → `.gitignore:8:.env  .env` (ignored).
- `.env` was never staged or committed; `git ls-files` / `git status` do not list it.
  `.env.example` (placeholders only) IS tracked via the `!.env.example` negation after `.env.*`.
- Secret-hygiene guard `python scripts/check_secret_hygiene.py` → exit 0 (all secret vars PLACEHOLDER).
- **Committed blob verified:** `git show HEAD:.env.example` scanned → every secret var is PLACEHOLDER,
  `COMMITTED SECRETS: NONE`. No real credential is in the commit or git history.
- Secrets were separated by `scripts/migrate_secrets_to_env.py` (one-time, in the baseline): it
  relocated the 3 real values from `.env.example` into the gitignored `.env`, reading them **in
  memory only** to move them — never printed, logged, hashed, staged, or committed. The agent did
  not read or expose any secret value.

## Files intentionally EXCLUDED (gitignored)
- `.env` and `.env.*` (real secrets; only `.env.example` placeholders tracked); `*.pem`/`*.key`/`*.p8`/`credentials*`/`secrets*`.
- `data/raw/` — raw provider/API responses + large open datasets (martj42, football-data JSON, odds JSON, **transfermarkt.duckdb 206MB**).
- `data/processed/` — generated modeling tables/datasets/forecast ledger (reproducible from scripts).
  - **Exception (force-added):** `data/processed/source_provenance.json` (the source registry; small, no secrets).
- `outputs/` — generated predictions, baseline metrics, advancement, scorecards (reproducible).
- `data/cache/`, `data/raw/private/`, caches (`__pycache__/`, `.pytest_cache/`, `.venv/`).

## Protected files — committed UNCHANGED from original repo state
`git diff` pre-commit was empty (nothing tracked yet). The following are committed at their
original content (never modified this project): `configs/trading.yaml`, `src/wcdrawlab/trading/**`,
`src/wcdrawlab/providers/**`, `src/wcdrawlab/scraping/**`, `configs/research.yaml`, legacy
`simulation/standings.py` + `group_simulator.py`. `.env.example` is committed in its remediated
(placeholders-only) form.

## Test result
`python -m pytest -q` → **61 passed, 0 skipped** (at the committed tree).

## Current active simulator module
`src/wcdrawlab/simulation/official_standings.py` — official 2026 Article-13 tiebreak engine
(head-to-head before overall GD, recursive; lots removed; best-third by points/GD/goals/conduct/
FIFA rank). Wired into `scripts/forecast_2026.py` and `scripts/market_anchored_forecast.py`.
Legacy `standings.py`/`group_simulator.py` retained as a baseline only (not used for 2026).

## Known limitations (carried into Tier 2+)
- Simulator `conduct` (cards) and `fifa_rank` act as tiebreak separators only when supplied in
  fixture data (default neutral otherwise); H2H / overall GD / goals are fully implemented + tested.
- Official FIFA regulations PDF not archived with a content hash (FIFA.com page is JS-rendered;
  used the official article + corroborating sources MLS/FOX/Yahoo for Article 13).
- No historical odds before 2020-06 (The Odds API limit) → 2018 has no market data.
- No free historical international xG/lineups; API-Football key is RapidAPI-type (rejected by the
  direct-host adapter) → in-play feeds deferred to Tier 4.
- Provenance is file-level (URL + content hash) for historical CSV datasets; per-record envelope
  applies to new structured pulls and will be tightened when the live event pipeline is built.
- Repo is local-only (no remote); LF→CRLF normalization warnings on Windows are cosmetic.

## Reproduce the data/outputs (excluded from git)
`python examples/fetch_public_data.py` → `scripts/fetch_footballdata_2026.py` →
`scripts/build_research_table.py` → (odds) `scripts/fetch_odds_2026.py` →
`scripts/build_market_features.py` → `scripts/forecast_2026.py` →
`scripts/market_anchored_forecast.py`.
