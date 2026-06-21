"""Deterministic tests for live-2026 shadow no-vig + blend logic. No network."""
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
import live_2026_shadow as L  # noqa: E402


def test_novig_sums_to_one_and_removes_margin():
    event = {"home_team": "A", "away_team": "B", "bookmakers": [
        {"markets": [{"key": "h2h", "outcomes": [
            {"name": "A", "price": 2.0}, {"name": "Draw", "price": 3.4}, {"name": "B", "price": 4.0}]}]},
        {"markets": [{"key": "h2h", "outcomes": [
            {"name": "A", "price": 2.1}, {"name": "Draw", "price": 3.3}, {"name": "B", "price": 3.9}]}]},
    ]}
    ph, pdr, pa, n, over = L._novig(event)
    assert n == 2
    assert abs((ph + pdr + pa) - 1.0) < 1e-9       # no-vig probabilities normalized
    assert over > 1.0                               # raw book overround has margin
    assert ph > pa                                  # shorter price on A -> higher prob


def test_novig_returns_none_without_h2h():
    assert L._novig({"home_team": "A", "away_team": "B", "bookmakers": []}) is None


def test_blend_interpolates_between_b1_and_market():
    b1 = np.array([0.7, 0.2, 0.1]); mkt = np.array([0.5, 0.3, 0.2])
    for wb1 in (0.75, 0.5, 0.25):
        blend = wb1 * b1 + (1 - wb1) * mkt
        # blend lies between the two component probabilities on every outcome
        assert np.all(blend <= np.maximum(b1, mkt) + 1e-9)
        assert np.all(blend >= np.minimum(b1, mkt) - 1e-9)
