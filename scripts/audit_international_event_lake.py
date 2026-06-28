"""audit_international_event_lake — run the fail-closed integrity sentinel over the lake.

Verifies EVERY indexed object: object present, bytes hash to recorded sha256, filename == sha256,
non-empty, valid JSON, non-empty event list, not HTML/error, id resolves to exactly one EXACT
international bridge row, and the object lives under the registered objects/ root. Exit code is
non-zero if ANY check fails (fail closed). research_only.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from wcdrawlab.research import international_event_lake as L  # noqa: E402


def main() -> int:
    lake = L.Lake.resolve()
    rep = L.run_sentinel(lake, write_report=True)
    L.log_run(lake, "audit", rep.to_dict())
    print(json.dumps(rep.to_dict()))
    return 0 if rep.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
