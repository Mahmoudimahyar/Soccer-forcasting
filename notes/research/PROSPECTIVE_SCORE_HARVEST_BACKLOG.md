# Prospective Score Harvest — Backlog (dependency order)

- [P0] Forensic freeze + input inventory (hash frozen predictions/queue/odds; validate each prediction).
- [P1] Root-cause forensic audit writeup + failure matrix (root cause already demonstrated: stale results, never refreshed).
- [P2] Read-only result reconciliation layer: refresh FINAL results (football-data.org → API-Football Pro fallback), canonical result records, schemas, audit, deterministic tests.
- [P3] Primary snapshot-selection preregistration (latest common valid pre-kickoff snapshot per fixture) + selection script + tests.
- [P4] Independent idempotent harvester `prospective_score_harvester_v1` (append-only scoring root) + tests.
- [P5] Backfill the completed prospective pool; every completed fixture scored or explicitly excluded.
- [P6] Model + market no-vig benchmark (RPS/log-loss/Brier/calibration/strata) + decision ledger + reports.
- [P7] Deployment decision: narrow collector score-adapter patch (add results-refresh) vs retain independent harvester.
- [P8] Durable scheduled harvester + watchdog (15-min, append-only, no Odds API).
- [P9] Final audit (28 hard gates), pytest, git fsck, completion report, commit, tag, disable tasks.
