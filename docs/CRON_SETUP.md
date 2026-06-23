# cron Setup (V1.5 prospective collector, Linux/macOS/WSL)

Bounded single-pass runs invoked by cron — never a daemon. Nothing auto-installed; safe by default
(dry-run until `EXECUTE=1`).

## 1. Review (dry-run)
```
cd /path/to/worldcup_draw_model_lab_FINAL
bash scripts/run_prospective_collection.sh
```

## 2. Add a cron entry (you run `crontab -e`)
Every 15 minutes, dry-run:
```
*/15 * * * * cd /path/to/worldcup_draw_model_lab_FINAL && /usr/bin/env bash scripts/run_prospective_collection.sh >> data/processed/prospective/cron.log 2>&1
```
To actually capture, prefix with the opt-in env var:
```
*/15 * * * * cd /path/to/worldcup_draw_model_lab_FINAL && EXECUTE=1 /usr/bin/env bash scripts/run_prospective_collection.sh >> data/processed/prospective/cron.log 2>&1
```

## 3. Optional: only run during the tournament window
Restrict to the WC dates/hours, e.g. only June–July:
```
*/15 * 11-31 6,7 * cd ... && bash scripts/run_prospective_collection.sh ...
```
(Outside relevant fixtures the collector is a graceful no-op anyway.)

## 4. Verify / stop
- `python scripts/prospective_integrity_check.py`
- Remove the cron line with `crontab -e`.

## Guarantees
Same as the Windows path: bounded, quota-aware, idempotent/resumable, no trading, no model changes.
`set -euo pipefail` ensures a failed run surfaces in `cron.log`; the next run resumes cleanly.
