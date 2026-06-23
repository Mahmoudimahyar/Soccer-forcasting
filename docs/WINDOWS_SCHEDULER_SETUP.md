# Windows Task Scheduler Setup (V1.5 prospective collector)

The collector runs as **bounded single-pass** jobs invoked by Task Scheduler — never a daemon, never an
infinite loop. **Nothing is installed automatically.** Safe by default (dry-run) until you opt in.

## 1. Review first (dry-run, no writes)
```
cd C:\Users\Mahyar\worldcup_draw_model_lab_FINAL
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\run_prospective_collection.ps1
```
This prints the capture plan, writes a session manifest + heartbeat, and writes NOTHING to the ledger.

## 2. Install the scheduled task (you run this; elevated PowerShell)
```
./scripts/install_windows_task_scheduler.ps1 -IntervalMinutes 15
```
Registers `WCDrawLab_ProspectiveCollector` to run the runner every 15 min, each run capped at 10 min,
`MultipleInstances IgnoreNew` (no overlap). Still **dry-run** until you enable capture.

## 3. Enable real capture (only when you're ready)
Set the task to run with `EXECUTE=1` in its environment (or set a user env var `EXECUTE=1` before the
task runs). With `EXECUTE=1` the collector records due predictions first-write-wins. In-play capture
additionally requires a verified live source.

## 4. Verify / stop
- Logs: `data/processed/prospective/sessions/` (manifest + heartbeat).
- Integrity: `python scripts/prospective_integrity_check.py`.
- Remove the task: `./scripts/uninstall_windows_task_scheduler.ps1`.

## Guarantees
Bounded runs; daily request budget + reserve in the adapter; graceful no-op when no fixture is due or
the source is unavailable; resumes cleanly after restart (idempotent ledger). It never trades, never
changes the model, never promotes research output.
