# Tier 1 Completion — Data, Provenance & Leakage Foundation

Version: `tier1-2026-06-20`. Status: **COMPLETE** (+ remediation applied — see
`notes/research/tier_1_remediation.md`). Active tier work stops here pending instruction.

> **Remediation (2026-06-20):** (1) secret-hygiene guard + policy added (`.env.example` cleanup is
> a residual operator step); (2) **official 2026 head-to-head tiebreak engine implemented** in
> `simulation/official_standings.py` (now the active simulator) — this changed 2026 advancement
> materially (max |Δp_advance| 0.107; Turkey 0.107→0.000). Pre-match W/D/L forecasts unchanged.
> Tests: 60 passed, 1 skipped.

## Tier-1 pass criteria — status
| Criterion | Status | Evidence |
|---|---|---|
| `pytest -q` passes | ✅ | **51 passed** |
| all leakage tests pass | ✅ | `tests/test_research_leakage.py` (incl. new simultaneity guard), `test_research_table_quality.py` |
| no pre-match feature uses post-kickoff info | ✅ | read-only leakage review: "no path by which post-kickoff information reaches a candidate model"; elo_before strict-<, group state strict-before, evaluator strips forbidden cols |
| tournament/group keys scoped by tournament+year | ✅ | `group_uid = year+'_'+group`; tests assert it |
| 2026 simulator passes deterministic tests | ✅ | `tests/test_simulation_2026.py` — exactly 32 advance (12+12+8), correct 8 best thirds, seed-stable |
| data inventory identifies every gap | ✅ | `current_repository_state.md`, `data_inventory.md`, `tier_1_data_card.md` |
| every source has provenance + storage rules | ✅ | `data/processed/source_provenance.json` (9 sources, content-hashed) + `provenance_policy.md` |

## Required Tier-1 outputs — status
- Canonical match table ✅ `data/processed/research_modeling_table.csv` (369 rows, 1998–2026)
- Canonical team-name mapping ✅ (ingest aliases + per-source extras)
- Pre-match Elo timeline ✅ `data/processed/elo_history.csv` (strict-before)
- 2010/2014/2018/2022 WC group data ✅ (jfjelstul)
- 2026 schedule + completed results ✅ (football-data.org; 33 played, 39 upcoming)
- 2026 48-team/12-group/best-third simulator ✅ + deterministic tests (new)
- Source registry ✅ `source_provenance.json` (replaces/augments the ingest `source_registry.json`)
- Event schema ✅ `schemas/events.yaml` (in-play envelope + leakage rules, for Tier 4)
- Data-quality report ✅ `data_inventory.md` + tests
- Leakage test suite ✅ (21 leakage/quality/simulator tests)
- Official 2026 tiebreak rules + provenance ✅ `data/reference/tiebreak_rules_2026.yaml`

## Exact test commands & results
```
python -m pytest -q                                  # 51 passed
python -m pytest tests/test_research_leakage.py tests/test_research_table_quality.py -q   # leakage
python -m pytest tests/test_simulation_2026.py -q    # 5 passed (deterministic 2026 simulator)
python scripts/build_research_table.py               # rebuild canonical table
python scripts/build_source_provenance.py            # rebuild provenance registry
```

## Data coverage & known limitations
- WC group stage **1998–2026** (369 played + 39 upcoming 2026). Intl odds set 2021–2025 (341).
- **Simulator tiebreak simplified** (overall GD before head-to-head); official rules stored;
  H2H + populating `fifa_rank` in the simulator are documented future fixes (low impact).
- **No historical odds < 2020**; **no free historical international xG/lineups**; API-Football
  key is RapidAPI-type (rejected by the direct-host adapter) → in-play feeds deferred to Tier 4.
- Provenance is file-level (hash+URL) for historical CSV datasets; per-record hashing applies to
  new structured pulls (tighten when the live event pipeline is built).

## Independent review
Read-only leakage/correctness review (general-purpose agent): verdict **"Tier-1 leakage
foundation is SOUND"** — no leakage path found. Its one actionable suggestion (always-on test for
the simultaneous final-matchday case) was implemented:
`test_strict_prior_aggregates_exclude_simultaneous_final_matchday`. Non-leak findings (simplified
tiebreak, inert `fifa_rank` in simulator) are recorded as limitations above.

## Safety
`KALSHI_ENABLE_LIVE_TRADING=false`, `TRADING_MODE=paper`. No secrets read/printed. Protected files
(configs/research.yaml, configs/trading.yaml, trading/**, providers/**, scraping/**, .env*,
simulation/standings.py) unchanged.

## Recommendation for the next tier
Proceed to **Tier 2 (pre-match outcome model)** — most of it already exists and can be formalized
to Tier-2's protocol: baselines B0–B7 are implemented (`scripts/evaluate_baselines.py`), the
dev/gate/locked folds run, and a **bootstrap confidence-interval report for model differences** is
the main missing Tier-2 artifact. The accepted model (Elo-blend logit) is Elo-grade on the release
gate; the validated market+Elo blend (beats Pinnacle close OOS) is the strongest result and should
be entered as the B7-class ensemble with its bootstrap CIs. Optionally backfill the simulator H2H
tiebreak (Tier-1.x) before Tier 3.

**STOP — awaiting instruction before beginning Tier 2.**
