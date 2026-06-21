"""Read-only provider health check (Data Enrichment Gate 1, section 1).

Loads .env into the process environment ONLY so keys can be sent in request headers/params, then
runs minimal read-only availability checks. No secret value is printed, logged, or written. Output
is the sanitized status table + a secrets-free JSON under outputs/ (gitignored).

Usage: python scripts/provider_health_check.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")  # populates os.environ; values never printed
except Exception:
    pass

from wcdrawlab.ingestion.health import run_all  # noqa: E402

OUT = ROOT / "outputs" / "research" / "source_readiness"


def main():
    results = run_all()
    cols = ["provider", "configured", "status_class", "auth_accepted", "mode_detected",
            "provider_error_flag", "rate_limit", "error_class"]
    w = {c: max(len(c), *(len(str(r.get(c))) for r in results)) for c in cols}
    print(" | ".join(c.ljust(w[c]) for c in cols))
    print("-+-".join("-" * w[c] for c in cols))
    for r in results:
        print(" | ".join(str(r.get(c)).ljust(w[c]) for c in cols))

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "health.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nWrote secrets-free results to {OUT / 'health.json'}")


if __name__ == "__main__":
    main()
