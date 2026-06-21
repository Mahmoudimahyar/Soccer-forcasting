from __future__ import annotations

import argparse
import json
from pathlib import Path
import pandas as pd

from wcdrawlab.ingest import download_default_sources, write_source_registry, normalize_worldcup_matches, normalize_international_results, load_seed_2026
from wcdrawlab.truth import write_truth_tables, filter_worldcup_group_stage
from wcdrawlab.pipeline import build_features, run_walkforward_backtest
from wcdrawlab.live import LivePredictionConfig, run_after_match_update, run_live_prediction_refresh, PREDICTION_TARGETS
from wcdrawlab.elo import EloUpdateConfig, update_elo_after_match_table, write_elo_outputs
from wcdrawlab.inplay import InPlayState, update_inplay_probabilities
from wcdrawlab.scraping import ScrapePolicy
from wcdrawlab.trading.service import policy_from_yaml, intent_from_json, quote_from_json, state_from_json, evaluate_intent, submit_if_approved


def cmd_sources(args: argparse.Namespace) -> None:
    path = write_source_registry(args.output)
    print(f"Wrote source registry: {path}")


def cmd_fetch(args: argparse.Namespace) -> None:
    names = args.names.split(",") if args.names else None
    paths = download_default_sources(args.root, names=names, overwrite=args.overwrite)
    for p in paths:
        print(f"Downloaded: {p}")


def cmd_truth(args: argparse.Namespace) -> None:
    raw = pd.read_csv(args.matches)
    if args.format == "jf-worldcup":
        matches = normalize_worldcup_matches(raw)
    elif args.format == "international-results":
        matches = normalize_international_results(raw)
    else:
        matches = raw
        if "kickoff_utc" in matches.columns:
            matches["kickoff_utc"] = pd.to_datetime(matches["kickoff_utc"], utc=True)
    if args.group_stage_only:
        matches = filter_worldcup_group_stage(matches, args.year_min, args.year_max)
    paths = write_truth_tables(matches, args.output)
    print("Wrote truth tables:")
    for name, path in paths.items():
        print(f"  {name}: {path}")


def _maybe_read(path: str | None, date_cols: list[str] | None = None) -> pd.DataFrame | None:
    if not path:
        return None
    if not Path(path).exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, parse_dates=date_cols or [])


def cmd_backtest(args: argparse.Namespace) -> None:
    matches = pd.read_csv(args.matches, parse_dates=["kickoff_utc"])
    elo = _maybe_read(args.elo, ["rating_date"])
    fifa = _maybe_read(args.fifa, ["release_date"])
    odds = _maybe_read(args.odds, ["snapshot_time"])
    features = build_features(matches, elo=elo, fifa=fifa, odds=odds)
    result = run_walkforward_backtest(features, test_start=args.test_start, outdir=args.output)
    print("\nMetrics:")
    print(result.metrics.to_string(index=False))
    if not result.edges.empty:
        print(f"\nEdges written: {Path(args.output) / 'edges.csv'}")


def cmd_seed_features(args: argparse.Namespace) -> None:
    matches = load_seed_2026(args.root)
    ratings_path = Path(args.root) / "data" / "seed" / "seed_ratings_2026.csv"
    odds_path = Path(args.root) / "data" / "seed" / "sample_odds_2026.csv"
    elo = pd.read_csv(ratings_path, parse_dates=["rating_date"]) if ratings_path.exists() else None
    odds = pd.read_csv(odds_path, parse_dates=["snapshot_time"]) if odds_path.exists() else None
    features = build_features(matches, elo=elo, odds=odds)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    features.to_csv(out, index=False)
    print(f"Wrote seed 2026 feature table: {out}")



def _live_config_from_args(args: argparse.Namespace) -> LivePredictionConfig:
    return LivePredictionConfig(
        n_sims=args.n_sims,
        utility_sims=args.utility_sims,
        random_seed=args.seed,
        risk_n_eff=args.risk_n_eff,
        update_elo_after_match=getattr(args, "update_elo", True),
        elo_k=getattr(args, "elo_k", 60.0),
        elo_scale=getattr(args, "elo_scale", 400.0),
        elo_home_advantage=getattr(args, "elo_home_advantage", 0.0),
        elo_round_change=not getattr(args, "no_elo_round_change", False),
    )


def cmd_predict_live(args: argparse.Namespace) -> None:
    cfg = _live_config_from_args(args)
    result = run_live_prediction_refresh(
        matches_path=args.matches,
        elo_path=args.elo,
        fifa_path=args.fifa,
        odds_path=args.odds,
        output_dir=args.output,
        config=cfg,
    )
    print("Prediction targets:")
    for key, desc in PREDICTION_TARGETS.items():
        print(f"  {key}: {desc}")
    print("\nWrote live outputs:")
    for name, path in result.output_paths.items():
        print(f"  {name}: {path}")
    print(f"\nRemaining matches predicted: {len(result.predictions)}")


def cmd_update_after_match(args: argparse.Namespace) -> None:
    cfg = _live_config_from_args(args)
    result = run_after_match_update(
        matches_path=args.matches,
        match_id=args.match_id,
        goals_a=args.goals_a,
        goals_b=args.goals_b,
        elo_path=args.elo,
        fifa_path=args.fifa,
        odds_path=args.odds,
        output_dir=args.output,
        current_matches_path=args.current_matches,
        source=args.source,
        completed_at=args.completed_at,
        config=cfg,
        current_elo_path=args.current_elo,
        update_elo=args.update_elo,
    )
    print(f"Updated result: {args.match_id} = {args.goals_a}-{args.goals_b}")
    print("\nWrote after-game refresh outputs:")
    for name, path in result.output_paths.items():
        print(f"  {name}: {path}")
    print(f"\nRemaining matches predicted: {len(result.predictions)}")
    if not result.predictions.empty:
        cols = ["match_id", "team_a", "team_b", "p_a_model", "p_draw_model", "p_b_model", "risk_band"]
        preview = result.predictions[cols].head(8)
        print("\nPrediction preview:")
        print(preview.to_string(index=False))


def cmd_update_elo(args: argparse.Namespace) -> None:
    matches = pd.read_csv(args.matches, parse_dates=["kickoff_utc"])
    ratings = pd.read_csv(args.elo, parse_dates=["rating_date"]) if Path(args.elo).exists() else pd.DataFrame(columns=["team", "rating_date", "elo", "source", "notes"])
    cfg = EloUpdateConfig(k=args.elo_k, scale=args.elo_scale, home_advantage=args.elo_home_advantage, round_change=not args.no_elo_round_change)
    updated, audit = update_elo_after_match_table(
        ratings,
        matches,
        match_id=args.match_id,
        goals_a=args.goals_a,
        goals_b=args.goals_b,
        completed_at=args.completed_at,
        config=cfg,
    )
    elo_path, audit_path = write_elo_outputs(updated, audit, args.output, args.audit)
    print(f"Updated Elo table: {elo_path}")
    print(f"Elo audit log: {audit_path}")
    print(audit[["match_id", "team_a", "team_b", "elo_a_pre", "elo_b_pre", "elo_change_a", "elo_change_b", "elo_a_post", "elo_b_post"]].to_string(index=False))


def cmd_inplay(args: argparse.Namespace) -> None:
    state = InPlayState(
        minute=args.minute,
        goals_a=args.goals_a,
        goals_b=args.goals_b,
        red_cards_a=args.red_cards_a,
        red_cards_b=args.red_cards_b,
        xg_a=args.xg_a,
        xg_b=args.xg_b,
    )
    pred = update_inplay_probabilities(args.lambda_a, args.lambda_b, state)
    print(pd.Series(pred.__dict__).to_string())


def cmd_validate_source(args: argparse.Namespace) -> None:
    policy = ScrapePolicy.from_yaml(args.allowlist)
    policy.validate_url(args.url)
    print(f"Approved by policy allowlist: {args.url}")


def cmd_trade_check(args: argparse.Namespace) -> None:
    policy = policy_from_yaml(args.policy)
    intent = intent_from_json(args.intent)
    quote = quote_from_json(args.quote)
    state = state_from_json(args.state)
    decision = evaluate_intent(intent, quote, state, policy, confidence_score=args.confidence_score)
    print(pd.Series({"approved": decision.approved, "reasons": list(decision.reasons)}).to_string())


def cmd_trade_submit(args: argparse.Namespace) -> None:
    policy = policy_from_yaml(args.policy)
    intent = intent_from_json(args.intent)
    quote = quote_from_json(args.quote)
    state = state_from_json(args.state)
    result = submit_if_approved(
        intent, quote, state, policy,
        confidence_score=args.confidence_score,
        require_live=args.require_live,
    )
    print(json.dumps(result, default=str, indent=2))

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="wcdrawlab", description="World Cup draw model lab CLI")
    sub = p.add_subparsers(required=True)

    s = sub.add_parser("sources", help="write the public source registry to JSON")
    s.add_argument("--output", default="data/source_registry.json")
    s.set_defaults(func=cmd_sources)

    f = sub.add_parser("fetch-public", help="download configured public datasets")
    f.add_argument("--root", default=".")
    f.add_argument("--names", default=None, help="comma-separated source names; default all")
    f.add_argument("--overwrite", action="store_true")
    f.set_defaults(func=cmd_fetch)

    t = sub.add_parser("truth-tables", help="build draw-rate truth tables from match data")
    t.add_argument("--matches", required=True)
    t.add_argument("--format", choices=["project", "jf-worldcup", "international-results"], default="project")
    t.add_argument("--output", default="outputs/truth_tables")
    t.add_argument("--group-stage-only", action="store_true")
    t.add_argument("--year-min", type=int, default=1998)
    t.add_argument("--year-max", type=int, default=2022)
    t.set_defaults(func=cmd_truth)

    b = sub.add_parser("backtest", help="run a walk-forward backtest")
    b.add_argument("--matches", required=True)
    b.add_argument("--elo", default=None)
    b.add_argument("--fifa", default=None)
    b.add_argument("--odds", default=None)
    b.add_argument("--test-start", required=True)
    b.add_argument("--output", default="outputs/backtest")
    b.set_defaults(func=cmd_backtest)

    sf = sub.add_parser("seed-2026-features", help="build features from the included partial 2026 seed snapshot")
    sf.add_argument("--root", default=".")
    sf.add_argument("--output", default="outputs/seed_2026_features.csv")
    sf.set_defaults(func=cmd_seed_features)


    pl = sub.add_parser("predict-live", help="refresh predictions for all remaining matches from the current match table")
    pl.add_argument("--matches", default="data/seed/worldcup_2026_seed_matches.csv")
    pl.add_argument("--elo", default="data/seed/seed_ratings_2026.csv")
    pl.add_argument("--fifa", default=None)
    pl.add_argument("--odds", default="data/seed/sample_odds_2026.csv")
    pl.add_argument("--output", default="outputs/live")
    pl.add_argument("--n-sims", type=int, default=100)
    pl.add_argument("--utility-sims", type=int, default=100)
    pl.add_argument("--risk-n-eff", type=float, default=120.0)
    pl.add_argument("--seed", type=int, default=42)
    pl.set_defaults(func=cmd_predict_live)

    ua = sub.add_parser("update-after-match", help="insert a final result, then refresh standings, utilities, predictions, risks, and edges")
    ua.add_argument("--matches", default="data/seed/worldcup_2026_seed_matches.csv")
    ua.add_argument("--match-id", required=True)
    ua.add_argument("--goals-a", type=int, required=True)
    ua.add_argument("--goals-b", type=int, required=True)
    ua.add_argument("--elo", default="data/seed/seed_ratings_2026.csv")
    ua.add_argument("--fifa", default=None)
    ua.add_argument("--odds", default="data/seed/sample_odds_2026.csv")
    ua.add_argument("--output", default="outputs/live")
    ua.add_argument("--current-matches", default="data/live/current_matches.csv")
    ua.add_argument("--source", default="manual")
    ua.add_argument("--completed-at", default=None)
    ua.add_argument("--n-sims", type=int, default=100)
    ua.add_argument("--utility-sims", type=int, default=100)
    ua.add_argument("--risk-n-eff", type=float, default=120.0)
    ua.add_argument("--seed", type=int, default=42)
    ua.add_argument("--current-elo", default="data/live/current_elo.csv", help="Where to write/read the live Elo table after each result")
    ua.add_argument("--update-elo", dest="update_elo", action="store_true", default=True, help="Append post-match Elo rows and use them for remaining predictions; default true")
    ua.add_argument("--no-update-elo", dest="update_elo", action="store_false", help="Do not update Elo after inserting the result")
    ua.add_argument("--elo-k", type=float, default=60.0, help="Elo K factor for this match/tournament")
    ua.add_argument("--elo-scale", type=float, default=400.0, help="Elo logistic scale")
    ua.add_argument("--elo-home-advantage", type=float, default=0.0, help="Home advantage added to team_a before expected-score calculation")
    ua.add_argument("--no-elo-round-change", action="store_true", help="Keep fractional Elo changes instead of World-Football-Elo-style rounding")
    ua.set_defaults(func=cmd_update_after_match)

    ue = sub.add_parser("update-elo", help="append post-match Elo rows for a completed match without refreshing predictions")
    ue.add_argument("--matches", default="data/live/current_matches.csv")
    ue.add_argument("--elo", default="data/live/current_elo.csv")
    ue.add_argument("--output", default="data/live/current_elo.csv")
    ue.add_argument("--audit", default="outputs/live/elo_update_log.csv")
    ue.add_argument("--match-id", required=True)
    ue.add_argument("--goals-a", type=int, required=True)
    ue.add_argument("--goals-b", type=int, required=True)
    ue.add_argument("--completed-at", default=None)
    ue.add_argument("--elo-k", type=float, default=60.0)
    ue.add_argument("--elo-scale", type=float, default=400.0)
    ue.add_argument("--elo-home-advantage", type=float, default=0.0)
    ue.add_argument("--no-elo-round-change", action="store_true")
    ue.set_defaults(func=cmd_update_elo)

    ip = sub.add_parser("inplay", help="compute a transparent in-play probability benchmark")
    ip.add_argument("--lambda-a", type=float, required=True, help="Pregame expected goals for team_a")
    ip.add_argument("--lambda-b", type=float, required=True, help="Pregame expected goals for team_b")
    ip.add_argument("--minute", type=float, required=True)
    ip.add_argument("--goals-a", type=int, required=True)
    ip.add_argument("--goals-b", type=int, required=True)
    ip.add_argument("--red-cards-a", type=int, default=0)
    ip.add_argument("--red-cards-b", type=int, default=0)
    ip.add_argument("--xg-a", type=float, default=None)
    ip.add_argument("--xg-b", type=float, default=None)
    ip.set_defaults(func=cmd_inplay)

    vs = sub.add_parser("validate-source", help="verify a URL is in the approved scraping allowlist")
    vs.add_argument("--url", required=True)
    vs.add_argument("--allowlist", default="configs/scraping_allowlist.yaml")
    vs.set_defaults(func=cmd_validate_source)

    tc = sub.add_parser("trade-check", help="evaluate a paper/demo/live order intent against deterministic risk gates")
    tc.add_argument("--intent", required=True)
    tc.add_argument("--quote", required=True)
    tc.add_argument("--state", default=None)
    tc.add_argument("--policy", default="configs/trading.yaml")
    tc.add_argument("--confidence-score", type=float, default=None)
    tc.set_defaults(func=cmd_trade_check)

    ts = sub.add_parser("trade-submit", help="submit only a risk-approved mapped order; paper mode is the default")
    ts.add_argument("--intent", required=True)
    ts.add_argument("--quote", required=True)
    ts.add_argument("--state", default=None)
    ts.add_argument("--policy", default="configs/trading.yaml")
    ts.add_argument("--confidence-score", type=float, default=None)
    ts.add_argument("--require-live", action="store_true", help="required in addition to external production arming")
    ts.set_defaults(func=cmd_trade_submit)
    return p


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
