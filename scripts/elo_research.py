"""Research cycle 2a: test Elo construction variants against the FIXED evaluator folds.

Elo is the dominant feature, so improving it improves every fold. We test match-importance
weighting (friendlies count less, World Cup more), base K, home advantage, and time decay.
Selection is on DEV+GATE (2018 + 2022) only; the 2026 fold is transfer-reported, never tuned.

Reuses runner.evaluate_fold verbatim (same candidate, same leakage guard) — we only swap the
elo_a/elo_b/elo_delta/abs_elo_delta columns per config.
"""
from __future__ import annotations

import sys
from bisect import bisect_left
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from wcdrawlab.elo import goal_difference_multiplier  # noqa: E402
from wcdrawlab.ratings import elo_expected_score  # noqa: E402
from wcdrawlab.research.runner import evaluate_fold, load_research_config, composite_score  # noqa: E402
from build_research_table import canon  # noqa: E402

RAW = ROOT / "data" / "raw"
PROC = ROOT / "data" / "processed"
INIT_ELO, SCALE = 1500.0, 400.0


def importance(tournament: str) -> float:
    t = str(tournament).lower()
    if "world cup" in t and "qual" not in t:
        return 1.5
    if any(k in t for k in ["uefa euro", "copa am", "african cup", "asian cup", "gold cup",
                            "confederations"]) and "qual" not in t:
        return 1.25
    if "qualif" in t or "nations league" in t:
        return 1.0
    if "friendly" in t:
        return 0.5
    return 0.8


@dataclass
class EloCfg:
    name: str
    k: float = 40.0
    home_adv: float = 65.0
    weighted: bool = False
    decay_per_year: float = 0.0  # pull toward mean each year (0 = none)


def build_hist(cfg: EloCfg):
    intl = pd.read_csv(RAW / "international_results.csv")
    intl["date"] = pd.to_datetime(intl["date"], errors="coerce", utc=True)
    intl = intl.dropna(subset=["date"]).sort_values("date", kind="stable").reset_index(drop=True)
    intl["ta"] = intl["home_team"].map(canon)
    intl["tb"] = intl["away_team"].map(canon)
    elo: dict[str, float] = {}
    hist: dict[str, tuple[list, list]] = {}
    for r in intl.itertuples(index=False):
        a, b = r.ta, r.tb
        ea, eb = elo.get(a, INIT_ELO), elo.get(b, INIT_ELO)
        ha = 0.0 if bool(r.neutral) else cfg.home_adv
        if pd.notna(r.home_score) and pd.notna(r.away_score):
            ga, gb = int(r.home_score), int(r.away_score)
            exp_a = float(elo_expected_score(np.array([(ea + ha) - eb]), SCALE)[0])
            sa = 1.0 if ga > gb else 0.5 if ga == gb else 0.0
            w = importance(r.tournament) if cfg.weighted else 1.0
            delta = cfg.k * w * goal_difference_multiplier(abs(ga - gb)) * (sa - exp_a)
            elo[a], elo[b] = ea + delta, eb - delta
            for t, e in ((a, elo[a]), (b, elo[b])):
                d, v = hist.setdefault(t, ([], []))
                d.append(r.date); v.append(e)
    return hist


def elo_before(hist, team, date):
    if team not in hist:
        return INIT_ELO
    dates, vals = hist[team]
    i = bisect_left(dates, date)
    return vals[i - 1] if i > 0 else INIT_ELO


def main():
    base = pd.read_csv(PROC / "research_modeling_table.csv", parse_dates=["kickoff_utc"])
    config, folds = load_research_config(ROOT / "configs" / "research.yaml")
    weights = config["objective"]["weights"]

    configs = [
        EloCfg("E0_current_flatK40", k=40, home_adv=65, weighted=False),
        EloCfg("E1_weighted_K40", k=40, home_adv=65, weighted=True),
        EloCfg("E2_weighted_K50", k=50, home_adv=65, weighted=True),
        EloCfg("E3_weighted_K40_ha100", k=40, home_adv=100, weighted=True),
        EloCfg("E4_weighted_K30", k=30, home_adv=65, weighted=True),
        EloCfg("E5_weighted_K50_ha100", k=50, home_adv=100, weighted=True),
        EloCfg("E6_flatK40_ha100", k=40, home_adv=100, weighted=False),
    ]

    rows = []
    for cfg in configs:
        hist = build_hist(cfg)
        df = base.copy()
        df["elo_a"] = [elo_before(hist, t, d) for t, d in zip(df["team_a"], df["kickoff_utc"])]
        df["elo_b"] = [elo_before(hist, t, d) for t, d in zip(df["team_b"], df["kickoff_utc"])]
        df["elo_delta"] = df["elo_a"] - df["elo_b"]
        df["abs_elo_delta"] = df["elo_delta"].abs()
        res = {f.name: evaluate_fold(df, f, config) for f in folds}
        for r in res.values():
            if not r.get("skipped"):
                r["composite"] = composite_score(r, weights)
        c2018 = res["world_cup_2018"]["composite"]
        c2022 = res["world_cup_2022"]["composite"]
        lk = res["world_cup_2026_matchday_1_locked"]
        rows.append({
            "config": cfg.name,
            "devgate": round((c2018 + c2022) / 2, 4),
            "c2018": round(c2018, 4), "c2022": round(c2022, 4),
            "c2026_locked": round(lk["composite"], 4) if not lk.get("skipped") else None,
            "drawcal2026": round(lk["draw_calibration_error"], 4) if not lk.get("skipped") else None,
        })
    out = pd.DataFrame(rows).sort_values("devgate")
    OUT = ROOT / "outputs" / "research" / "autoresearch"
    OUT.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT / "elo_cycle_2.csv", index=False)
    pd.set_option("display.width", 160)
    print(out.to_string(index=False))
    base_dg = out[out.config == "E0_current_flatK40"]["devgate"].iloc[0]
    best = out.iloc[0]
    print(f"\nbaseline E0 devgate={base_dg} | best={best['config']} devgate={best['devgate']} "
          f"(rel {((base_dg-best['devgate'])/base_dg*100):+.2f}%)")


if __name__ == "__main__":
    main()
