"""Integrity invariants for the live-2026 shadow prediction set (pure functions; no I/O).

Each check returns (ok: bool, violations: list[str]). Used by tests (synthetic) and a runnable
checker against the live predictions CSV. These guard the prospective experiment's correctness:
no duplicate snapshots, no post-kickoff leakage, frozen blend weights, valid no-vig, valid probs.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

BLEND_W = {"M3_75_25": 0.75, "M4_50_50": 0.50, "M5_25_75": 0.25}  # weight on M1


def check_no_duplicate_snapshots(df: pd.DataFrame) -> tuple[bool, list[str]]:
    key = [c for c in ["match_id", "model_version", "snapshot_type", "source_snapshot_timestamp"] if c in df.columns]
    dups = df[df.duplicated(subset=key, keep=False)]
    return (dups.empty, [] if dups.empty else [f"{len(dups)} duplicate snapshot rows on {key}"])


def check_snapshots_pre_kickoff(df: pd.DataFrame) -> tuple[bool, list[str]]:
    v = []
    ko = pd.to_datetime(df["kickoff_utc"], utc=True, errors="coerce")
    if "source_snapshot_timestamp" in df.columns:
        snap = pd.to_datetime(df["source_snapshot_timestamp"], utc=True, errors="coerce")
        bad = df[(snap.notna()) & (snap > ko)]
        if len(bad):
            v.append(f"{len(bad)} snapshots dated after kickoff")
    if "prediction_timestamp" in df.columns:
        pt = pd.to_datetime(df["prediction_timestamp"], utc=True, errors="coerce")
        bad = df[(pt.notna()) & (pt > ko)]
        if len(bad):
            v.append(f"{len(bad)} predictions timestamped after kickoff")
    return (not v, v)


def check_probs_sum_to_one(df: pd.DataFrame, tol: float = 1e-6) -> tuple[bool, list[str]]:
    s = df[["p_team_a_win", "p_draw", "p_team_b_win"]].sum(axis=1)
    bad = df[(s - 1.0).abs() > tol]
    return (bad.empty, [] if bad.empty else [f"{len(bad)} rows whose 1X2 probs do not sum to 1"])


def check_novig_sums_to_one(df: pd.DataFrame, tol: float = 1e-3) -> tuple[bool, list[str]]:
    m = df.dropna(subset=["p_a_market", "p_draw_market", "p_b_market"])
    if m.empty:
        return (True, [])
    s = m[["p_a_market", "p_draw_market", "p_b_market"]].sum(axis=1)
    bad = m[(s - 1.0).abs() > tol]
    return (bad.empty, [] if bad.empty else [f"{len(bad)} market rows whose no-vig probs do not sum to 1"])


def check_blend_weights_frozen(df: pd.DataFrame, tol: float = 1e-6) -> tuple[bool, list[str]]:
    """For each (match, snapshot), verify M3/M4/M5 == w*M1 + (1-w)*M2 (renormalized) with frozen w."""
    v = []
    grp_keys = [c for c in ["match_id", "snapshot_type", "source_snapshot_timestamp"] if c in df.columns]
    for _, g in df.groupby(grp_keys):
        by = {r.model_version: np.array([r.p_team_a_win, r.p_draw, r.p_team_b_win]) for r in g.itertuples()}
        if "M1_B1" not in by or "M2_market" not in by:
            continue
        m1, m2 = by["M1_B1"], by["M2_market"]
        for name, w in BLEND_W.items():
            if name in by:
                exp = w * m1 + (1 - w) * m2
                exp = exp / exp.sum()
                if np.abs(by[name] - exp).max() > tol:
                    v.append(f"{name} blend weight drift at {g[grp_keys].iloc[0].to_dict()}")
    return (not v, v)


def run_all(df: pd.DataFrame) -> dict:
    checks = {
        "no_duplicate_snapshots": check_no_duplicate_snapshots,
        "snapshots_pre_kickoff": check_snapshots_pre_kickoff,
        "probs_sum_to_one": check_probs_sum_to_one,
        "novig_sums_to_one": check_novig_sums_to_one,
        "blend_weights_frozen": check_blend_weights_frozen,
    }
    out = {}
    for name, fn in checks.items():
        ok, viol = fn(df)
        out[name] = {"ok": ok, "violations": viol}
    out["all_ok"] = all(c["ok"] for c in out.values() if isinstance(c, dict))
    return out
