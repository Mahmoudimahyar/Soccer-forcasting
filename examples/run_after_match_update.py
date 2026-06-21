from pathlib import Path
from wcdrawlab.live import LivePredictionConfig, run_after_match_update

ROOT = Path(__file__).resolve().parents[1]

if __name__ == "__main__":
    out = ROOT / "outputs" / "live_example"
    current = ROOT / "data" / "live" / "current_matches.csv"
    current.parent.mkdir(parents=True, exist_ok=True)
    # Start from seed snapshot for the demo.
    seed_matches = ROOT / "data" / "seed" / "worldcup_2026_seed_matches.csv"
    if not current.exists():
        current.write_text(seed_matches.read_text(), encoding="utf-8")

    result = run_after_match_update(
        matches_path=current,
        match_id="2026_A_03",
        goals_a=1,
        goals_b=1,
        elo_path=ROOT / "data" / "seed" / "seed_ratings_2026.csv",
        odds_path=ROOT / "data" / "seed" / "sample_odds_2026.csv",
        output_dir=out,
        current_matches_path=current,
        source="demo_manual",
        config=LivePredictionConfig(n_sims=20, utility_sims=5, random_seed=7),
    )
    print("Wrote:")
    for name, path in result.output_paths.items():
        print(f"  {name}: {path}")
    print(result.predictions[["match_id", "team_a", "team_b", "p_a_model", "p_draw_model", "p_b_model", "risk_band"]].head().to_string(index=False))
