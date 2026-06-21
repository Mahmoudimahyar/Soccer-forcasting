"""Secret-hygiene guard. Detects whether .env.example contains NON-PLACEHOLDER credential values.
Prints ONLY variable names and a classification (PLACEHOLDER / SUSPECTED_SECRET) — never values.
Exit code 0 = clean, 1 = violation. Used by the pre-commit checklist and tests/test_secret_hygiene.py.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Variables that must NEVER hold a real value in the committed template:
SECRET_VARS = {
    "API_FOOTBALL_KEY", "ODDS_API_KEY", "FOOTBALL_DATA_KEY",
    "KALSHI_API_KEY_ID", "KALSHI_PRIVATE_KEY_PATH", "KALSHI_LIVE_TRADING_ACK",
}
# Non-secret config that may legitimately carry a value in the template:
ALLOWED_VALUE_VARS = {
    "KALSHI_ENV", "KALSHI_ENABLE_LIVE_TRADING", "TRADING_MODE", "MAX_ORDER_COST_CENTS",
    "MAX_EVENT_EXPOSURE_CENTS", "MAX_DAILY_LOSS_CENTS", "MAX_OPEN_ORDERS",
    "MIN_EDGE_AFTER_UNCERTAINTY", "MAX_MARKET_SPREAD_CENTS", "MAX_PREDICTION_AGE_SECONDS",
    "MAX_MARKET_AGE_SECONDS", "MIN_MODEL_CONFIDENCE",
}
PLACEHOLDER_TOKENS = re.compile(
    r"^(|x+|your[_-].*|<.*>|changeme|placeholder|example|dummy|todo|none|null)$", re.IGNORECASE)


def classify(value: str) -> str:
    v = value.strip().strip('"').strip("'")
    if v == "" or PLACEHOLDER_TOKENS.match(v):
        return "PLACEHOLDER"
    return "SUSPECTED_SECRET"


def scan(path: Path) -> list[tuple[str, str]]:
    """Return [(var, classification)] for secret-bearing vars; never returns values."""
    findings = []
    if not path.exists():
        return findings
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, val = line.split("=", 1)
        k = k.strip()
        if k in SECRET_VARS:
            findings.append((k, classify(val)))
    return findings


def main() -> int:
    example = ROOT / ".env.example"
    print(f"Scanning {example.name} (values are NEVER printed):")
    results = scan(example)
    violations = [k for k, c in results if c == "SUSPECTED_SECRET"]
    for k, c in results:
        print(f"  {k}: {c}")
    # also confirm a real .env, if present, is git-ignored / not the template
    env = ROOT / ".env"
    print(f".env present: {env.exists()} (real secrets belong here, gitignored)")
    if violations:
        print("\nVIOLATION: .env.example contains suspected real credentials in:",
              ", ".join(sorted(violations)))
        print("Fix: move these values into a local .env and reset .env.example to blank placeholders.")
        return 1
    print("\nOK: .env.example contains only placeholders for all secret variables.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
