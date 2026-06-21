"""Did the official tiebreak correction change prior 2026 forecasts?
Run the LEGACY (simplified) and OFFICIAL simulators on the SAME 2026 fixtures + blend probs with
the SAME seed (identical sampled scorelines), so any difference isolates the tiebreak-rule effect.
Also demonstrates Tier-3 features (draw utility / must-win) computed from the corrected engine.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from wcdrawlab.evaluation import normalize_probs  # noqa: E402
from wcdrawlab.simulation.group_simulator import simulate_group_stage as legacy_sim  # noqa: E402
from wcdrawlab.simulation.official_standings import (  # noqa: E402
    simulate_group_stage_official as official_sim, match_advance_utilities_official,
)

PROC = ROOT / "data" / "processed"
OUT = ROOT / "outputs" / "research" / "forecasts"
N_SIMS = 10000
SEED = 42


def build_fixtures_and_probs():
    common = ["match_id", "group", "team_a", "team_b", "goals_a", "goals_b", "tournament"]
    played = pd.read_csv(PROC / "research_modeling_table.csv")
    played = played[played["tournament"].astype(str).str.contains("2026")][common]
    up = pd.read_csv(PROC / "forecast_targets_2026.csv")[common]
    fixtures = pd.concat([played, up], ignore_index=True).reset_index(drop=True)
    fc = pd.read_csv(OUT / "forecast_2026_market_anchored.csv")
    fmap = fc.set_index("match_id")[["p_a_final", "p_draw_final", "p_b_final"]].to_dict("index")
    probs = []
    for _, r in fixtures.iterrows():
        f = fmap.get(r["match_id"])
        probs.append([f["p_a_final"], f["p_draw_final"], f["p_b_final"]] if f else [1/3, 1/3, 1/3])
    return fixtures, normalize_probs(np.array(probs))


def main():
    fixtures, probs = build_fixtures_and_probs()
    leg = legacy_sim(fixtures, probs, n_sims=N_SIMS, third_place_slots=8, seed=SEED)
    off = official_sim(fixtures, probs, n_sims=N_SIMS, third_place_slots=8, seed=SEED)
    off.to_csv(OUT / "advancement_2026_official.csv", index=False)

    m = leg.merge(off, on="team", suffixes=("_legacy", "_official"))
    for c in ["p_advance", "p_first", "p_second", "p_third_advance"]:
        m[f"d_{c}"] = (m[f"{c}_official"] - m[f"{c}_legacy"]).abs()
    print(f"=== LEGACY vs OFFICIAL simulator on 2026 (n_sims={N_SIMS}, same seed) ===")
    print("max abs d_p_advance:", round(m["d_p_advance"].max(), 4),
          "| mean:", round(m["d_p_advance"].mean(), 4))
    print("max abs d_p_first:", round(m["d_p_first"].max(), 4),
          "| max abs d_p_third_advance:", round(m["d_p_third_advance"].max(), 4))
    changed = m[m["d_p_advance"] > 0.01].sort_values("d_p_advance", ascending=False)
    print(f"\nteams with abs d_p_advance > 0.01: {len(changed)}")
    if len(changed):
        print(changed[["team", "p_advance_legacy", "p_advance_official", "d_p_advance"]]
              .head(15).round(3).to_string(index=False))
    # advancement set change (who is in the top-32 expected order can shift)
    print("\ndid the headline advancement probabilities materially change?",
          "YES" if (m["d_p_advance"] > 0.02).any() else "NO (differences <= 0.02, MC + rare ties)")

    # Tier-3 audit: draw/must-win utilities from the OFFICIAL engine for a live-stakes MD3 match
    up = pd.read_csv(PROC / "forecast_targets_2026.csv")
    md3 = up[up["matchday"] == 3]
    if len(md3):
        r = md3.iloc[0]
        u = match_advance_utilities_official(fixtures, probs, r["match_id"], r["team_a"], r["team_b"],
                                             n_sims=3000, seed=SEED)
        print(f"\n=== Tier-3 features from OFFICIAL engine: {r['team_a']} vs {r['team_b']} ({r['match_id']}) ===")
        for k in ["p_adv_a_if_win", "p_adv_a_if_draw", "p_adv_a_if_loss", "draw_utility_a",
                  "must_win_pressure_a", "mutual_draw_utility", "must_win_pressure_max"]:
            print(f"   {k}: {u[k]:.3f}")
    print("\nProduction forecast scripts now import simulate_group_stage_official (active engine).")


if __name__ == "__main__":
    main()
