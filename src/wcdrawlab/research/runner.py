from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from wcdrawlab.evaluation import metric_report
from wcdrawlab.research.candidate import CandidateModel


TARGET_COLUMNS = {"goals_a", "goals_b", "outcome", "is_draw", "final_score", "result", "post_match_xg", "closing_odds_after_kickoff"}


@dataclass(frozen=True)
class FoldSpec:
    name: str
    train_before_year: int
    test_year: int
    stage: str = "group"
    matchday: int | None = None
    locked: bool = False


@dataclass(frozen=True)
class ExperimentResult:
    candidate_name: str
    summary: dict[str, float]
    folds: list[dict[str, Any]]
    promoted: bool
    promotion_reason: str


def _year(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s, utc=True).dt.year


def _ensure_outcome(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "outcome" not in out.columns:
        if not {"goals_a", "goals_b"}.issubset(out.columns):
            raise ValueError("Research input needs outcome or goals_a/goals_b.")
        out["outcome"] = np.select([out.goals_a > out.goals_b, out.goals_a == out.goals_b], ["A", "D"], default="B")
    return out


def load_research_config(path: str | Path) -> tuple[dict[str, Any], list[FoldSpec]]:
    raw = yaml.safe_load(Path(path).read_text())
    folds = [FoldSpec(**x) for x in raw["folds"]]
    return raw, folds


def leakage_safe_feature_frame(df: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    forbidden = set(config.get("leakage_guard", {}).get("forbidden_columns", [])) | TARGET_COLUMNS
    safe = df.drop(columns=[c for c in forbidden if c in df.columns], errors="ignore").copy()
    # Row IDs / time metadata are allowed for grouping but are never supplied as numeric
    # candidate inputs. Keep only numeric and approved categorical state columns.
    numeric = safe.select_dtypes(include=[np.number, "bool"]).copy()
    numeric = numeric.replace([np.inf, -np.inf], np.nan).fillna(0.0)
    return numeric


def draw_calibration_error(y: pd.Series, p_draw: np.ndarray, bins: int = 8) -> float:
    y_draw = (pd.Series(y).astype(str).to_numpy() == "D").astype(float)
    edges = np.linspace(0.0, 1.0, bins + 1)
    total = 0.0
    n = len(y_draw)
    for lo, hi in zip(edges[:-1], edges[1:]):
        mask = (p_draw >= lo) & ((p_draw < hi) if hi < 1 else (p_draw <= hi))
        if mask.any():
            total += mask.mean() * abs(y_draw[mask].mean() - p_draw[mask].mean())
    return float(total)


def evaluate_fold(df: pd.DataFrame, fold: FoldSpec, config: dict[str, Any]) -> dict[str, Any]:
    work = _ensure_outcome(df)
    years = _year(work["kickoff_utc"])
    stage = work.get("stage", pd.Series("group", index=work.index)).astype(str).str.lower()
    train = work[(years < fold.train_before_year) & (stage == fold.stage)].copy()
    test = work[(years == fold.test_year) & (stage == fold.stage)].copy()
    if fold.matchday is not None and "matchday" in test.columns:
        test = test[test["matchday"].astype(int) == int(fold.matchday)].copy()
    if train.empty or test.empty:
        return {"fold": fold.name, "skipped": True, "reason": "empty train or test split"}

    X_train = leakage_safe_feature_frame(train, config)
    X_test = leakage_safe_feature_frame(test, config)
    # Ensure stable column shape. Candidate only sees features present before kickoff.
    X_test = X_test.reindex(columns=X_train.columns, fill_value=0.0)
    candidate = CandidateModel(random_state=7).fit(X_train, train["outcome"])
    probs = candidate.predict_proba(X_test)
    metrics = metric_report(test["outcome"], probs)
    metrics["draw_calibration_error"] = draw_calibration_error(test["outcome"], probs[:, 1])
    metrics["fold"] = fold.name
    metrics["n_train"] = int(len(train))
    metrics["n_test"] = int(len(test))
    metrics["skipped"] = False
    return metrics


def composite_score(metrics: dict[str, float], weights: dict[str, float]) -> float:
    # Lower is better for every component here.
    return float(
        weights["rps"] * metrics["rps"]
        + weights["log_loss"] * metrics["log_loss"]
        + weights["draw_brier"] * metrics["draw_brier"]
        + weights["draw_calibration_error"] * metrics["draw_calibration_error"]
    )


def run_experiment(data_path: str | Path, config_path: str | Path, output_dir: str | Path) -> ExperimentResult:
    data = pd.read_csv(data_path, parse_dates=["kickoff_utc"])
    config, folds = load_research_config(config_path)
    rows = [evaluate_fold(data, f, config) for f in folds]
    usable = [r for r in rows if not r.get("skipped")]
    if not usable:
        raise RuntimeError("No usable research folds. Build a leakage-safe modeling table first.")
    weights = config["objective"]["weights"]
    for r in usable:
        r["composite"] = composite_score(r, weights)
    summary = {k: float(np.mean([r[k] for r in usable])) for k in ["rps", "log_loss", "draw_brier", "draw_calibration_error", "composite"]}

    # Promotion is intentionally impossible without a human comparison baseline. The
    # agent logs evidence; a human explicitly marks a candidate approved in the registry.
    result = ExperimentResult(
        candidate_name="CandidateModel",
        summary=summary,
        folds=rows,
        promoted=False,
        promotion_reason="Research outputs require human review and explicit runtime approval.",
    )
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    payload = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "candidate": result.candidate_name,
        "summary": result.summary,
        "folds": result.folds,
        "promoted": result.promoted,
        "promotion_reason": result.promotion_reason,
    }
    (output / "latest_result.json").write_text(json.dumps(payload, indent=2))
    with (output / "experiment_log.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload) + "\n")
    pd.DataFrame(rows).to_csv(output / "fold_metrics.csv", index=False)
    return result


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="Fixed autoresearch evaluator for World Cup models")
    p.add_argument("--data", required=True, help="Leakage-safe match modeling table with current/past results")
    p.add_argument("--config", default="configs/research.yaml")
    p.add_argument("--output", default="outputs/research")
    args = p.parse_args(argv)
    result = run_experiment(args.data, args.config, args.output)
    print(json.dumps({"summary": result.summary, "promotion": result.promotion_reason}, indent=2))


if __name__ == "__main__":
    main()
