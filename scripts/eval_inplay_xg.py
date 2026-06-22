"""Does LEAKAGE-SAFE live xG improve the in-play forecast beyond score + Elo?

Joins StatsBomb per-shot xG (WC2022 + Copa2024 — the two competitions in our in-play foundation that
StatsBomb covers) onto the in-play decision rows, computing each team's accumulated xG STRICTLY BEFORE
the decision minute. Tests two questions on a leave-one-COMPETITION-out basis:
  (1) W/D/L: does adding live_xg_diff / xg_surprise to the in-play logit beat the score+Elo logit?
  (2) NEXT-GOAL: does live xG predict which team scores next, beyond score + Elo?
Data provided by StatsBomb (non-commercial research).
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from wcdrawlab.research.xg_inplay import attach_live_xg  # noqa: E402
from wcdrawlab.research import inplay_eval as E  # noqa: E402
from sklearn.linear_model import LogisticRegression  # noqa: E402
from sklearn.preprocessing import StandardScaler  # noqa: E402

OUT = ROOT / "outputs/research/inplay_xg"; OUT.mkdir(parents=True, exist_ok=True)
STATES = {"WC2022": "inplay_state_2022_group_stage", "COPA2024": "inplay_state_copa2024"}
SHOTS = {"WC2022": "statsbomb_shots_wc2022", "COPA2024": "statsbomb_shots_copa2024"}


def logo_wld(df, feats):
    Y = df.final_wld.map({"H": 0, "D": 1, "A": 2}).to_numpy()
    P = np.zeros((len(df), 3))
    for held in df.competition.unique():
        tr, te = df[df.competition != held], df[df.competition == held]
        sc = StandardScaler().fit(tr[feats].fillna(0))
        clf = LogisticRegression(max_iter=3000, C=1.0).fit(sc.transform(tr[feats].fillna(0)),
                                                            tr.final_wld.map({"H": 0, "D": 1, "A": 2}))
        proba = clf.predict_proba(sc.transform(te[feats].fillna(0)))
        full = np.full((len(te), 3), 1e-9)
        for j, c in enumerate(clf.classes_):
            full[:, int(c)] = proba[:, j]
        P[te.index.to_numpy()] = full / full.sum(1, keepdims=True)
    return P, Y


def main():
    frames = []
    for comp, st in STATES.items():
        d = pd.read_parquet(ROOT / f"data/processed/{st}.parquet")
        sh = pd.read_parquet(ROOT / f"data/processed/{SHOTS[comp]}.parquet")
        d = attach_live_xg(d, sh); d["competition"] = comp
        frames.append(d)
    df = pd.concat(frames, ignore_index=True)
    cov = df.groupby("competition").has_xg.mean()
    print(f"rows {len(df)} | xG-mapped coverage per comp: {dict(cov.round(2))}")
    df = df[df.has_xg].reset_index(drop=True)
    print(f"usable (xG-mapped) rows: {len(df)} across {df.competition.nunique()} comps "
          f"({df.match_id.nunique()} matches)")

    base = ["score_diff", "remaining_minutes", "elo_delta_home", "red_diff"]
    print("\n=== (1) W/D/L leave-one-competition-out RPS (lower=better) ===")
    Pb, Y = logo_wld(df, base); rb = E.rps_per_row(Pb, Y)
    print(f"  baseline score+Elo            : RPS {rb.mean():.4f}")
    for name, extra in [("+live_xg_diff", ["live_xg_diff"]), ("+xg_surprise", ["xg_surprise"]),
                        ("+xg_diff+surprise", ["live_xg_diff", "xg_surprise"])]:
        Pc, _ = logo_wld(df, base + extra); rc = E.rps_per_row(Pc, Y)
        bs = E.paired_match_bootstrap(rc, rb, df.match_id.to_numpy())
        flag = "BETTER*" if bs["a_better_sig"] else ("worse*" if bs["a_worse_sig"] else "ns")
        print(f"  {name:<22}: RPS {rc.mean():.4f} | dRPS {bs['delta_mean']:+.4f} "
              f"CI[{bs['ci_low']:+.4f},{bs['ci_high']:+.4f}] {flag}")

    # (2) NEXT-GOAL: among rows where a next goal occurs, predict the scorer
    ng = df[df.next_goal_team.isin(["H", "A", "home", "away"])].copy() if "next_goal_team" in df.columns else df.iloc[0:0]
    if len(ng) > 60:
        ng["y_home_next"] = ng.next_goal_team.isin(["H", "home"]).astype(int)
        print(f"\n=== (2) NEXT-GOAL (home scores next?) — {len(ng)} decision points with a next goal ===")
        def logo_bin(frame, feats):
            P = np.zeros(len(frame))
            for held in frame.competition.unique():
                tr, te = frame[frame.competition != held], frame[frame.competition == held]
                sc = StandardScaler().fit(tr[feats].fillna(0))
                clf = LogisticRegression(max_iter=3000).fit(sc.transform(tr[feats].fillna(0)), tr.y_home_next)
                P[te.index.to_numpy()] = clf.predict_proba(sc.transform(te[feats].fillna(0)))[:, list(clf.classes_).index(1)]
            return P
        yb = ng.y_home_next.to_numpy()
        for name, feats in [("score+Elo", base), ("+live_xg_diff", base + ["live_xg_diff"])]:
            ng = ng.reset_index(drop=True)
            p = np.clip(logo_bin(ng, feats), 1e-6, 1 - 1e-6)
            ll = -(yb * np.log(p) + (1 - yb) * np.log(1 - p)).mean()
            print(f"  {name:<16}: log-loss {ll:.4f}")
    print("\nwrote", OUT)


if __name__ == "__main__":
    main()
