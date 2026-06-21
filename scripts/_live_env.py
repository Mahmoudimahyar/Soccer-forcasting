"""Load API keys from a local env file into os.environ at runtime WITHOUT printing values.

Reads .env (preferred) then .env.example as fallback. Never logs or returns secret values.
This module does not modify any credential file.
"""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_keys(verbose: bool = True) -> list[str]:
    loaded: list[str] = []
    for fname in (".env", ".env.example"):
        p = ROOT / fname
        if not p.exists():
            continue
        for line in p.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip().strip('"').strip("'")
            if v and not os.environ.get(k):  # .env wins over .env.example
                os.environ[k] = v
                loaded.append(k)
    if verbose:
        # report only NAMES that are now set, never values
        names = sorted({k for k in loaded})
        print(f"[env] loaded {len(names)} keys (names only): {names}")
    return loaded
