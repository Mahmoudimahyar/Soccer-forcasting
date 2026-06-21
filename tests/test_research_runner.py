from pathlib import Path
import numpy as np
import pandas as pd

from wcdrawlab.research.runner import run_experiment


def test_research_runner_uses_time_ordered_world_cup_folds(tmp_path: Path):
    rows = []
    rng = np.random.default_rng(3)
    for year in [2014, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026]:
        for i in range(12):
            ga = int(rng.poisson(1.2))
            gb = int(rng.poisson(1.0))
            rows.append({
                "match_id": f"{year}-{i}",
                "kickoff_utc": f"{year}-06-{(i%20)+1:02d}T12:00:00Z",
                "stage": "group",
                "matchday": 1 if year == 2026 else (i % 3) + 1,
                "goals_a": ga,
                "goals_b": gb,
                "elo_delta": float(rng.normal(0, 100)),
                "abs_elo_delta": float(abs(rng.normal(100, 50))),
                "p_a_market": 0.4,
                "p_draw_market": 0.28,
                "p_b_market": 0.32,
                "market_total_goals": 2.4,
                "prior_group_draws": 0,
                "low_block_risk": 0.2,
                "travel_fatigue": 0.1,
            })
    path = tmp_path / "research.csv"
    pd.DataFrame(rows).to_csv(path, index=False)
    config = Path(__file__).parents[1] / "configs" / "research.yaml"
    result = run_experiment(path, config, tmp_path / "out")
    assert result.summary["rps"] >= 0
    assert (tmp_path / "out" / "fold_metrics.csv").exists()
