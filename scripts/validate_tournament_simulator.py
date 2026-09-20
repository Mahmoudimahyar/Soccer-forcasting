"""Phase 2 / 7C: deterministic validation battery for the official 2026 standings/tiebreak engine +
group-stage simulator. Exits non-zero on any failure. No randomness in assertions."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from wcdrawlab.simulation.official_standings import (  # noqa: E402
    OfficialGroupTable, rank_third_place_official, simulate_group_stage_official)


def rr(results):
    t = OfficialGroupTable("G")
    for (a, b, ga, gb) in results:
        t.add_result(a, b, ga, gb)
    return t


def main():
    checks = []
    # 1 points/GD order
    t = rr([("A", "B", 1, 0), ("A", "C", 1, 0), ("A", "D", 1, 0), ("B", "C", 1, 0), ("B", "D", 1, 0), ("C", "D", 1, 0)])
    checks.append(("points_order", t.ranked() == ["A", "B", "C", "D"]))
    # 2 H2H breaks equal points+GD
    t = rr([("A", "B", 1, 0), ("A", "C", 0, 1), ("A", "D", 3, 0), ("B", "C", 2, 0), ("B", "D", 2, 0), ("C", "D", 0, 1)])
    checks.append(("h2h_tiebreak", t.ranked().index("A") < t.ranked().index("B")))
    # 3 overall GD fallback when H2H drawn
    t = rr([("A", "B", 1, 1), ("A", "C", 3, 0), ("A", "D", 1, 0), ("B", "C", 1, 0), ("B", "D", 1, 0), ("C", "D", 0, 0)])
    checks.append(("overall_gd_fallback", t.ranked().index("A") < t.ranked().index("B")))
    # 4 conduct tiebreak
    t = rr([("A", "B", 0, 0), ("A", "C", 1, 0), ("A", "D", 1, 0), ("B", "C", 1, 0), ("B", "D", 1, 0), ("C", "D", 0, 0)])
    t.set_conduct("A", 0.0); t.set_conduct("B", -2.0)
    checks.append(("conduct_tiebreak", t.ranked().index("A") < t.ranked().index("B")))
    # 5 best-third ranking
    thirds = pd.DataFrame([{"group": "A", "team": "T1", "points": 4, "gd": 1, "gf": 3},
                           {"group": "B", "team": "T2", "points": 4, "gd": 2, "gf": 4}])
    checks.append(("best_third", list(rank_third_place_official(thirds).team) == ["T2", "T1"]))
    # 6 simulator deterministic when fully played
    fx = pd.DataFrame([{"match_id": f"G{i}", "group": "G", "team_a": a, "team_b": b, "goals_a": ga, "goals_b": gb}
                       for i, ((a, b), (ga, gb)) in enumerate(
                       {("A", "B"): (1, 0), ("A", "C"): (1, 0), ("A", "D"): (1, 0),
                        ("B", "C"): (1, 0), ("B", "D"): (1, 0), ("C", "D"): (1, 0)}.items())])
    p = np.tile([1/3, 1/3, 1/3], (len(fx), 1))
    a = simulate_group_stage_official(fx, p, n_sims=30, seed=1).sort_values("team").reset_index(drop=True)
    b = simulate_group_stage_official(fx, p, n_sims=30, seed=7).sort_values("team").reset_index(drop=True)
    checks.append(("simulate_deterministic", np.allclose(a.p_advance, b.p_advance)))

    print("tournament simulator validation:")
    for name, ok in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    if not all(ok for _, ok in checks):
        sys.exit(1)
    print("ALL SIMULATOR CHECKS PASS")


if __name__ == "__main__":
    main()
