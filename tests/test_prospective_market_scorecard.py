"""Phase 4 prospective scorecard tests — sanitized synthetic ledger fixtures only. No live ledger, no API."""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))
import prospective_market_scorecard as PS  # noqa: E402


def _ledger():
    rows = []
    for mid in ["MA", "MB"]:
        for model in ["M1_B1", "M2_market"]:
            for snap, ph in [("T-90", 0.50), ("T-15", 0.70)]:
                rows.append({"match_id": mid, "model_version": model, "snapshot_type": snap,
                             "p_team_a_win": ph, "p_draw": 0.2, "p_team_b_win": round(1 - ph - 0.2, 3)})
    return pd.DataFrame(rows)


def test_select_primary_prefers_t15():
    g = _ledger()
    g = g[(g.match_id == "MA") & (g.model_version == "M1_B1")]
    prim = PS.select_primary(g, "snapshot_type")
    assert prim["snapshot_type"] == "T-15"


def test_score_canonical_ids_and_tierA():
    results = {"MA": {"status": "FINISHED", "final_wld": "H"},
               "MB": {"status": "NS"}}  # MB not finalized -> excluded
    out = PS.score(_ledger(), results)
    assert out["n_finalized_eligible"] == 1 and out["tier"] == "A"
    ids = set(out["per_match"].canonical_model_id)
    assert ids == {"prematch.b1_elo", "prematch.market_novig"}     # canonical, not legacy
    # the T-15 snapshot (p_home 0.70) was used, not T-90 (0.50)
    assert all(out["per_match"].snapshot_type == "T-15")


def test_perfect_prediction_zero_rps():
    led = pd.DataFrame([{"match_id": "MZ", "model_version": "M1_B1", "snapshot_type": "T-15",
                         "p_team_a_win": 1.0, "p_draw": 0.0, "p_team_b_win": 0.0}])
    out = PS.score(led, {"MZ": {"status": "FINISHED", "final_wld": "H"}})
    assert float(out["per_match"].iloc[0]["rps"]) == 0.0


def test_tier_boundaries():
    def n_matches(n):
        rows = [{"match_id": f"M{i}", "model_version": "M2_market", "snapshot_type": "T-15",
                 "p_team_a_win": 0.4, "p_draw": 0.3, "p_team_b_win": 0.3} for i in range(n)]
        res = {f"M{i}": {"status": "FINISHED", "final_wld": "D"} for i in range(n)}
        return PS.score(pd.DataFrame(rows), res)["tier"]
    assert n_matches(5) == "A" and n_matches(12) == "B" and n_matches(25) == "C"
