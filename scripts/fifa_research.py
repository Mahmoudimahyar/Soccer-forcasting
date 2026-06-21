"""Research cycle 2b: does adding FIFA-ranking features improve the candidate on the FIXED
selection folds (2018 + 2022)? Reuses the autoresearch harness verbatim. 2026 is transfer-only.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from autoresearch_batch import (  # noqa: E402
    Variant, eval_variant, BASE_FEATURES, STATE_FEATURES, DATA, CONFIG,
)
from wcdrawlab.research.runner import load_research_config  # noqa: E402

FIFA = ["fifa_z_delta", "abs_fifa_z_delta", "fifa_rank_pct_delta", "abs_fifa_rank_pct_delta"]
F2018, F2022, F2026 = "world_cup_2018", "world_cup_2022", "world_cup_2026_matchday_1_locked"


def main():
    data = pd.read_csv(DATA, parse_dates=["kickoff_utc"])
    config, folds = load_research_config(CONFIG)

    variants = [
        # W0 = the currently ACCEPTED candidate (V8): base+state, scaled, 50% Elo blend, NO fifa
        Variant("W0_accepted_noFIFA", "current accepted candidate (no FIFA)",
                BASE_FEATURES + STATE_FEATURES, C=0.5, scaler=True, blend_elo=0.5),
        # W1 = accepted + FIFA deltas
        Variant("W1_accepted_plusFIFA", "FIFA ranking deltas add signal on top of Elo",
                BASE_FEATURES + STATE_FEATURES + FIFA, C=0.5, scaler=True, blend_elo=0.5),
        # W2 = accepted + FIFA, lighter Elo blend (let FIFA carry more)
        Variant("W2_plusFIFA_blend30", "FIFA + lighter Elo blend",
                BASE_FEATURES + STATE_FEATURES + FIFA, C=0.5, scaler=True, blend_elo=0.3),
        # W3 = FIFA-only logit = a real B2 (no Elo blend, fifa features only)
        Variant("W3_FIFA_only_B2", "FIFA-only multinomial logit (real B2)",
                FIFA, C=0.5, scaler=True, blend_elo=0.0),
        # W4 = Elo + FIFA deltas only (drop noisy state/market), 50% blend
        Variant("W4_elo_fifa_lean", "lean: Elo + FIFA deltas only",
                ["elo_delta", "abs_elo_delta"] + FIFA, C=0.5, scaler=True, blend_elo=0.5),
    ]

    rows = []
    base = None
    for v in variants:
        r = eval_variant(data, folds, config, v)
        dg = np.mean([r[F2018]["composite"], r[F2022]["composite"]])
        if base is None:
            base = dg
        rows.append({
            "variant": v.name,
            "devgate": round(dg, 4),
            "rel_vs_W0": round((base - dg) / base, 4),
            "c2018": round(r[F2018]["composite"], 4),
            "c2022": round(r[F2022]["composite"], 4),
            "c2026_locked": round(r[F2026]["composite"], 4) if r[F2026] else None,
            "drawcal2026": round(r[F2026]["draw_calibration_error"], 4) if r[F2026] else None,
        })
    out = pd.DataFrame(rows)
    OUT = ROOT / "outputs" / "research" / "autoresearch"
    OUT.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT / "fifa_cycle_2.csv", index=False)
    pd.set_option("display.width", 160)
    print(out.to_string(index=False))
    w0 = out.iloc[0]
    # GOVERNANCE: promote only if devgate improves >=0.2% AND neither 2018 nor 2022 regresses
    # by >0.001 (no trading one selection fold for another).
    promotable = []
    for _, r in out.iloc[1:].iterrows():
        rel = (w0["devgate"] - r["devgate"]) / w0["devgate"]
        if rel >= 0.002 and (r["c2018"] - w0["c2018"]) <= 0.001 and (r["c2022"] - w0["c2022"]) <= 0.001:
            promotable.append((r["variant"], r["devgate"]))
    print(f"\nW0 (accepted, no FIFA): devgate={w0['devgate']} c2018={w0['c2018']} c2022={w0['c2022']}")
    if promotable:
        win = min(promotable, key=lambda x: x[1])
        print(f"DECISION: ADOPT {win[0]} (devgate {win[1]}) — improves devgate with no fold regression")
    else:
        print("DECISION: KEEP W0 (no FIFA in candidate). Every FIFA variant either fails the "
              "0.2% bar or regresses a selection fold (FIFA is 0.78-corr with Elo and stale for 2026). "
              "FIFA data is retained for baseline B2 and future fresher-data cycles.")


if __name__ == "__main__":
    main()
