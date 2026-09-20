"""Phase 0 model-identity tests: namespace disambiguation, invariants, immutability of rows."""
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from wcdrawlab.research.model_identity import (  # noqa: E402
    load_identity, load_aliases, resolve, check_invariants, annotate)


def test_market_m2_is_not_inplay_m2():
    al = load_aliases()
    assert resolve("M2", "prematch", al) == "prematch.market_novig"
    assert resolve("M2", "inplay", al) == "inplay.remaining_time_poisson_m2"
    assert resolve("M2", "prematch", al) != resolve("M2", "inplay", al)


def test_invariants_hold():
    assert check_invariants(load_identity()) == []


def test_no_research_model_is_runtime_or_trade_eligible():
    ident = load_identity()
    for cid, m in ident.items():
        if m["approval_status"] != "approved":
            assert m["runtime_eligible"] is False
        assert m["trade_eligible"] is False           # paper-only: nothing trade-eligible
    runtime = [c for c, m in ident.items() if m["runtime_eligible"]]
    assert runtime == ["prematch.b1_elo"]             # B1 is the sole runtime model


def test_every_alias_resolves_to_known_model():
    ident = load_identity(); al = load_aliases()
    for (ctx, alias), cid in al.items():
        assert cid in ident, f"({ctx},{alias})->{cid} not in identity"


def test_unknown_alias_raises():
    with pytest.raises(KeyError):
        resolve("M9", "prematch", load_aliases())
    with pytest.raises(KeyError):
        resolve("M2", "no_such_context", load_aliases())


def test_annotate_adds_canonical_without_mutating_rows():
    df = pd.DataFrame({"match_id": ["x", "y"], "model": ["M2", "M1"], "p_home": [0.4, 0.6]})
    before = df.copy(deep=True)
    out = annotate(df, "prematch")
    # original frame untouched; original columns/values preserved in output
    assert df.equals(before)
    assert list(out["p_home"]) == [0.4, 0.6] and list(out["model"]) == ["M2", "M1"]
    # canonical columns added + correct
    assert list(out["canonical_model_id"]) == ["prematch.market_novig", "prematch.b1_elo"]
    assert list(out["runtime_eligible"]) == [False, True]
    assert "legacy_model_alias" in out.columns


def test_scorecard_annotation_shows_canonical_ids_inplay():
    df = pd.DataFrame({"model": ["M2_remaining_poisson", "M6_market_inplay"]})
    out = annotate(df, "inplay")
    assert list(out["canonical_model_id"]) == ["inplay.remaining_time_poisson_m2", "inplay.market_inplay_m6"]
    assert all(out["runtime_eligible"] == False)  # noqa: E712
