#!/usr/bin/env bash
# Bounded single-pass prospective collection (V1.5). SAFE BY DEFAULT: dry-run unless EXECUTE=1.
# Designed to be invoked by cron in short windows — NOT a daemon, no infinite loop. Never trades.
set -euo pipefail
cd "$(dirname "$0")/.."

ARGS=""
if [ "${EXECUTE:-0}" = "1" ]; then
  ARGS="--execute"
fi
SID="sched_$(date -u +%Y%m%dT%H%M%SZ)"

# Graceful no-op if no queue exists yet (collector handles missing queue itself).
python scripts/prospective_collect.py $ARGS --session-id "$SID"
# Score any finished matches (metrics only; never updates the model). Dry by default (no fetch).
python scripts/prospective_score.py || true
exit 0
