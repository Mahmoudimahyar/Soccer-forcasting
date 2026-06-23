# Prospective Collection Runbook (V1.5)

Operate the durable, restart-safe prospective collector for the **frozen research model `m2_frozen`
(M2)**. This NEVER trades, never changes the model, and never touches B1/runtime/Kalshi. All output is
`research_only`.

## Components
- `scripts/prospective_collect.py` — capture predictions for due windows (SAFE BY DEFAULT = dry-run).
- `scripts/prospective_score.py` — score FINISHED matches' ledger predictions (metrics only).
- `scripts/prospective_integrity_check.py` — validate the ledger (first-write-wins, point-in-time, no secrets).
- Adapter: `src/wcdrawlab/operations/api_football_adapter.py` (read-only, rate-limited, key never logged).
- Ledger: `data/processed/prospective/ledger.jsonl` (immutable, first-write-wins; gitignored).

## Capture windows
- Pre-match: **T-90, T-15** (deterministic — Elo anchor from the queue; no API call needed).
- In-play: **0, 15, 30, HT(45), 60, 75, 85** + immediately after confirmed goals / red cards / subs
  (in-play requires a verified live source and `--execute`).
- A window is captured only inside `[target, target+grace]` (default 10 min); earlier = pending, later =
  `MISSED_UNRECOVERABLE`. No silent backfill.

## Daily operation (bounded, no infinite loop)
1. Dry-run first (default): `python scripts/prospective_collect.py`
   → prints the plan, writes a session manifest + heartbeat, writes NOTHING to the ledger.
2. Execute (when ready to actually record): `python scripts/prospective_collect.py --execute`
   → records due predictions first-write-wins; idempotent on re-run.
3. After matches finish: `python scripts/prospective_score.py` (provide `--results` JSON or `--execute`
   to fetch read-only).
4. Anytime: `python scripts/prospective_integrity_check.py` (exits non-zero on any violation).

The collector is meant to be invoked **periodically by a scheduler** (see `WINDOWS_SCHEDULER_SETUP.md` /
`CRON_SETUP.md`) in short bounded runs — not run as a daemon.

## Safety invariants (enforced)
- First-write-wins immutable ledger; idempotent writes; duplicate detection.
- Leakage guard: `event_source_timestamp <= decision_timestamp` (records that violate it are rejected).
- Fail-closed on critical source disagreement (score/status/goal/red).
- Quota-aware: daily budget + reserve in the adapter; no fetch when budget exhausted.
- Clean-shutdown summary + resume (re-running continues; already-captured keys are skipped).
- No trading, no model mutation, no promotion of research output.

## Resume after restart
Just re-run the same command. Existing ledger keys are skipped; missed windows are marked; due windows
are captured. State is reconstructed from the append-only ledger + manifest.
