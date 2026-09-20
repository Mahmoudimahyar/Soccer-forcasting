"""Phase 4: deterministic prospective MARKET scorecard. Reads ONLY immutable ledgers + finalized
results. One primary snapshot per match (T-15 > T-90 > baseline > unscorable). Compares the frozen
prematch models (b1_elo, market_novig, elo_market_blend_*) with canonical IDs. Tier A/B/C gating.
NO model selection / recalibration / blend change / trading — scoring only.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from wcdrawlab.research.model_identity import resolve, load_aliases  # noqa: E402

SNAP_PRIORITY = {"T-15": 0, "T-90": 1, "baseline": 2}
YMAP = {"H": 0, "D": 1, "A": 2}
PREMATCH_SCORED = {"prematch.b1_elo", "prematch.market_novig",
                   "prematch.elo_market_blend_75_25", "prematch.elo_market_blend_50_50",
                   "prematch.elo_market_blend_25_75"}


def _rps(p, y):
    cp = np.cumsum(p); cy = np.cumsum([1 if i == y else 0 for i in range(3)])
    return float(np.sum((cp - cy) ** 2) / 2.0)


def select_primary(group, snapshot_col):
    """One row per match: T-15 preferred, then T-90, then baseline; else None (unscorable)."""
    if snapshot_col in group.columns and group[snapshot_col].notna().any():
        g = group.copy()
        g["_pri"] = g[snapshot_col].map(lambda s: SNAP_PRIORITY.get(str(s), 99))
        g = g[g["_pri"] < 99]
        if g.empty:
            return None
        return g.sort_values("_pri").iloc[0]
    return group.iloc[0] if len(group) else None


def canonical(alias, aliases):
    try:
        return resolve(str(alias), "prematch", aliases)
    except KeyError:
        return None


def score(ledger: pd.DataFrame, results: dict, alias_col="model_version", snapshot_col="snapshot_type"):
    aliases = load_aliases()
    ledger = ledger.copy()
    ledger["canonical_model_id"] = ledger[alias_col].map(lambda a: canonical(a, aliases))
    ledger = ledger[ledger.canonical_model_id.isin(PREMATCH_SCORED)]
    rows = []
    scorable_matches = set()
    for (mid, cmid), grp in ledger.groupby(["match_id", "canonical_model_id"]):
        res = results.get(str(mid)) or results.get(mid)
        if not res or res.get("status") != "FINISHED":
            continue
        prim = select_primary(grp, snapshot_col)
        if prim is None:
            continue
        y = YMAP.get(res["final_wld"])
        p = np.array([prim["p_team_a_win"], prim["p_draw"], prim["p_team_b_win"]], dtype=float)
        rows.append({"match_id": mid, "canonical_model_id": cmid, "rps": _rps(p, y),
                     "logloss": float(-np.log(max(p[y], 1e-12))),
                     "draw_brier": float((p[1] - (1 if y == 1 else 0)) ** 2),
                     "snapshot_type": prim.get(snapshot_col, None)})
        scorable_matches.add(mid)
    sc = pd.DataFrame(rows)
    n = len(scorable_matches)
    tier = "A" if n < 10 else ("B" if n < 20 else "C")
    summary = (sc.groupby("canonical_model_id")[["rps", "logloss", "draw_brier"]].mean()
               if len(sc) else pd.DataFrame())
    return {"per_match": sc, "summary": summary, "n_finalized_eligible": n, "tier": tier,
            "tier_meaning": {"A": "informational only (<10)", "B": "descriptive only, no model-selection (10-19)",
                             "C": "exploratory comparative, still no runtime promotion (>=20)"}[tier]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ledger", default=str(ROOT.parent / "worldcup_draw_model_lab_FINAL/outputs/research/live_2026_shadow_predictions.csv"))
    ap.add_argument("--results", default="")
    a = ap.parse_args()
    if not Path(a.ledger).exists():
        print(f"no ledger at {a.ledger}"); return
    led = pd.read_csv(a.ledger)
    results = json.loads(Path(a.results).read_text(encoding="utf-8")) if a.results and Path(a.results).exists() else {}
    out = score(led, results)
    print(f"finalized eligible matches: {out['n_finalized_eligible']} | TIER {out['tier']} — {out['tier_meaning']}")
    if len(out["summary"]):
        print(out["summary"].round(4).to_string())
    print("NOTE: scoring only — no model selection, no recalibration, no blend change, no trading, no market-edge claim.")


if __name__ == "__main__":
    main()
