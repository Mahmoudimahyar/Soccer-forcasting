# Contributing

Corrections are the most valuable contribution to this repository. If a number is wrong, a link is
broken, or a claim is stronger than its evidence, please open an issue — that is exactly what
[`docs/ERRATA.md`](docs/ERRATA.md) exists for.

## Ground rules

1. **Evidence before claims.** Every reported improvement needs its sample size and an interval from a
   *match-level* (fixture-level) bootstrap. The match is the independent unit — never the snapshot or the row.
2. **Nulls are results.** Report "no evidence of improvement at this sample size", keep the note, and record
   the verdict in a decision ledger under `data/reference/`. Do not delete superseded notes; add a banner
   that links to what replaced them.
3. **No selection on the test set.** Choose models, features and hyper-parameters on the development folds
   only. The 2022 gate is read once. Anything touching 2026 outcomes is prospective evaluation, not tuning.
4. **Nothing promotes itself.** Only a reviewed edit to `configs/approved_models.yaml` can approve a model.
   The evaluator hard-codes `promoted=False`.
5. **Paper-only.** Do not add, arm or exercise any live order path. `KALSHI_ENABLE_LIVE_TRADING` stays
   `false` and `TRADING_MODE` stays `paper`.
6. **No secrets, no raw third-party data.** `.env` is gitignored; `scripts/check_secret_hygiene.py` runs in
   CI. Raw provider payloads and derived tables stay out of git (`data/raw/`, `data/processed/`, `outputs/`).
   See [`docs/DATA_SOURCES.md`](docs/DATA_SOURCES.md) and [`docs/DATA_SOURCE_GOVERNANCE.md`](docs/DATA_SOURCE_GOVERNANCE.md);
   a new data source starts as a written request under `data_requests/`.

## Development

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt && pip install -e .
python -m pytest tests -q -rs                           # fresh clone: 817 passed, 51 skipped
python scripts/check_secret_hygiene.py
```

The skipped tests are integration tests that need datasets this repository does not redistribute —
[`docs/TESTING_AND_DATA_DEPENDENCIES.md`](docs/TESTING_AND_DATA_DEPENDENCIES.md) explains the two tiers.
When a test needs local data, **skip with a reason; never `return` early** (a bare return counts as a pass
and makes the pass count dishonest).

New pipeline code should come with leakage/integrity tests in the style of
`tests/test_research_leakage.py` and `tests/test_shadow_integrity.py`: feature time ≤ decision time,
first-write-wins, idempotent re-runs, fail-closed on missing inputs.

## Protected paths

`program.md` lists files the autonomous research loop may not modify (trading, providers, scraping policy,
credentials templates, governance docs). Human contributors may change them, but such changes need an
explicit rationale in the pull request.

## Style

Python 3.10+, standard library + the scientific stack in `requirements.txt`. Keep modules small and
side-effect-free at import. Prefer repo-relative paths and environment-variable overrides
(`PSH_COLLECTOR_ROOT`, `WCLAB_MAIN_ROOT`) over absolute paths.
