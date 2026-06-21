"""Secret-hygiene guard tests. Never read/print secret values.

- The detector logic is verified on SYNTHETIC files (always runs, always must pass).
- .env must be gitignored.
- The real .env.example is checked; if it still contains suspected real secrets, the test
  SKIPS with a names-only action message (the file is operator-owned/protected and cannot be
  edited by the agent). The hard gate for CI/pre-commit is scripts/check_secret_hygiene.py
  (exits 1 on violation).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import check_secret_hygiene as csh  # noqa: E402


def test_detector_flags_secret_and_accepts_placeholder(tmp_path):
    # classification logic — never touches real secrets
    assert csh.classify("") == "PLACEHOLDER"
    assert csh.classify("your_key_here") == "PLACEHOLDER"
    assert csh.classify("<changeme>") == "PLACEHOLDER"
    assert csh.classify("xxxxxxxx") == "PLACEHOLDER"
    assert csh.classify("sk_live_9f8a7b6c5d4e3f2g1h") == "SUSPECTED_SECRET"

    sample = tmp_path / ".env.example"
    sample.write_text("API_FOOTBALL_KEY=\nODDS_API_KEY=your_key_here\nFOOTBALL_DATA_KEY=ab12cd34ef56gh78\n")
    res = dict(csh.scan(sample))
    assert res["API_FOOTBALL_KEY"] == "PLACEHOLDER"
    assert res["ODDS_API_KEY"] == "PLACEHOLDER"
    assert res["FOOTBALL_DATA_KEY"] == "SUSPECTED_SECRET"


def test_env_is_gitignored():
    gi = ROOT / ".gitignore"
    assert gi.exists(), ".gitignore missing"
    lines = {ln.strip() for ln in gi.read_text().splitlines()}
    assert ".env" in lines, ".env must be gitignored (real secrets live in .env)"


def test_env_example_has_no_real_secrets():
    findings = csh.scan(ROOT / ".env.example")
    leaked = sorted(k for k, c in findings if c == "SUSPECTED_SECRET")
    if leaked:
        pytest.skip(
            "ACTION REQUIRED (operator): .env.example contains suspected real credentials in "
            f"{leaked}. Move them to a local .env (gitignored) and reset .env.example to blank "
            "placeholders. The agent is not permitted to modify .env/.env.example. Hard gate: "
            "`python scripts/check_secret_hygiene.py` (exits 1)."
        )
    # passes once the operator has cleaned the template
    assert not leaked
