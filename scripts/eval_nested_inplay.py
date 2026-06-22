"""Phase 5: NESTED leave-one-competition-out evaluation on StatsBomb men's international data.
Model selection happens ONLY in the inner loop (historical competitions); the outer competition is
untouched until its selected model is scored. No 2026 match is used anywhere here.

Candidates: M1, M2, M2temp, M2fit, M2fit_temp, M5, and M1 + each pre-registered xG family (+ all).
Reports: per-fold selection, outer RPS, match-level bootstrap, calibration by minute/score/card state,
and a separate club->international transfer test. Data provided by StatsBomb (non-commercial).
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from wcdrawlab.research.inplay_models.models import (  # noqa: E402
    M1_TimeScore, M2_RemainingPoisson, M2fit_FittedPoisson, M5_Ensemble, TemperatureScaled)
from wcdrawlab.research.xg_features import attach_xg_families, FAMILIES, ALL_XG_COLS  # noqa: E402
from wcdrawlab.research import inplay_eval as E  # noqa: E402
from sklearn.linear_model import LogisticRegression  # noqa: E402
from sklearn.preprocessing import StandardScaler  # noqa: E402

OUT = ROOT / "outputs/research/nested_inplay"; OUT.mkdir(parents=True, exist_ok=True)
M1_FEATS = ["score_diff", "remaining_minutes", "elo_delta_home", "red_diff"]
YMAP = {"H": 0, "D": 1, "A": 2}


class GenericLogit:
    def __init__(self, feats): self.feats = feats
    def fit(self, tr):
        self.sc = StandardScaler().fit(tr[self.feats].fillna(0))
        self.clf = LogisticRegression(max_iter=3000).fit(self.sc.transform(tr[self.feats].fillna(0)),
                                                          tr.final_wld.map(YMAP))
        return self
    def predict_wld(self, te):
        raw = self.clf.predict_proba(self.sc.transform(te[self.feats].fillna(0)))
        full = np.full((len(te), 3), 1e-9)
        for j, c in enumerate(self.clf.classes_):
            full[:, int(c)] = raw[:, j]
        return full / full.sum(1, keepdims=True)


def candidates():
    c = {"M1": M1_TimeScore, "M2": M2_RemainingPoisson,
         "M2temp": lambda: TemperatureScaled(M2_RemainingPoisson), "M2fit": M2fit_FittedPoisson,
         "M2fit_temp": lambda: TemperatureScaled(M2fit_FittedPoisson), "M5": M5_Ensemble}
    for fam, cols in FAMILIES.items():
        c[f"M1+{fam}"] = (lambda cc: (lambda: GenericLogit(M1_FEATS + cc)))(cols)
    c["M1+allxg"] = lambda: GenericLogit(M1_FEATS + ALL_XG_COLS)
    return c


def prep():
    st = pd.read_parquet(ROOT / "data/processed/inplay_state_sb_international.parquet")
    mt = pd.read_parquet(ROOT / "data/processed/sb_match_targets.parquet")
    sh = pd.read_parquet(ROOT / "data/processed/statsbomb_shots_international.parquet")
    df = st.merge(mt, on="sb_match_id", how="inner")
    df = attach_xg_families(df, sh)
    df["red_diff"] = df.red_home - df.red_away
    df["match_id"] = df.sb_match_id
    df["competition"] = df.competition_id
    df = df.dropna(subset=["elo_delta_home", "final_wld"]).reset_index(drop=True)
    return df


def oof_logo(df, fac):
    P = np.zeros((len(df), 3)); d = df.reset_index(drop=True)
    for c in d.competition.unique():
        tr, te = d[d.competition != c], d[d.competition == c]
        P[te.index.to_numpy()] = fac().fit(tr).predict_wld(te)
    return P


def main():
    df = prep()
    Y = df.final_wld.map(YMAP).to_numpy()
    comps = sorted(df.competition.unique())
    print(f"international nested CV: {comps} | {df.match_id.nunique()} matches / {len(df)} rows")
    CAND = candidates()

    outer = np.zeros((len(df), 3)); selected = {}
    for oc in comps:
        otr = df[df.competition != oc]
        inner_scores = {}
        for name, fac in CAND.items():
            P = oof_logo(otr, fac)
            inner_scores[name] = float(E.rps_per_row(P, otr.final_wld.map(YMAP).to_numpy()).mean())
        best = min(inner_scores, key=inner_scores.get)
        selected[oc] = {"selected": best, "inner_rps": round(inner_scores[best], 4),
                        "M1_inner": round(inner_scores["M1"], 4)}
        te = df[df.competition == oc]
        outer[te.index.to_numpy()] = CAND[best]().fit(otr).predict_wld(te)
        print(f"  outer={oc:<10} selected={best:<14} inner_rps={inner_scores[best]:.4f}")

    rps_outer = E.rps_per_row(outer, Y)
    # fixed-baseline references (no selection) for context
    m1 = oof_logo(df, M1_TimeScore); m2 = oof_logo(df, M2_RemainingPoisson)
    print(f"\nNESTED selected-model outer RPS = {rps_outer.mean():.4f}")
    print(f"  reference M1 (LOGO) = {E.rps_per_row(m1,Y).mean():.4f} | M2 (LOGO) = {E.rps_per_row(m2,Y).mean():.4f}")
    bs = E.paired_match_bootstrap(rps_outer, E.rps_per_row(m1, Y), df.match_id.to_numpy())
    print(f"  nested vs M1: dRPS {bs['delta_mean']:+.4f} CI[{bs['ci_low']:+.4f},{bs['ci_high']:+.4f}] "
          f"{'BETTER*' if bs['a_better_sig'] else ('worse*' if bs['a_worse_sig'] else 'ns')}")

    # calibration by state buckets (draw reliability)
    print("\n=== calibration / RPS by state bucket (selected nested model) ===")
    df2 = df.copy(); df2["rps"] = rps_outer
    df2["mbucket"] = pd.cut(df2.decision_minute, [0, 30, 60, 96], labels=["0-30", "30-60", "60-95"])
    df2["sstate"] = np.sign(df2.score_diff).map({1: "lead", 0: "level", -1: "trail"})
    df2["cstate"] = np.where((df2.red_home + df2.red_away) > 0, "red", "no_red")
    for col in ["mbucket", "sstate", "cstate"]:
        g = df2.groupby(col, observed=True).rps.agg(["mean", "count"])
        print(f"  by {col}: " + " | ".join(f"{i}={r['mean']:.3f}(n{int(r['count'])})" for i, r in g.iterrows()))

    pd.DataFrame(selected).T.to_csv(OUT / "outer_fold_selection.csv")
    pd.DataFrame([{"model": "nested_selected", "rps": float(rps_outer.mean()),
                   "dRPS_vs_M1": bs["delta_mean"], "ci_low": bs["ci_low"], "ci_high": bs["ci_high"],
                   "sig_better": bs["a_better_sig"]},
                  {"model": "M1_logo", "rps": float(E.rps_per_row(m1, Y).mean())},
                  {"model": "M2_logo", "rps": float(E.rps_per_row(m2, Y).mean())}]).to_csv(
        OUT / "nested_summary.csv", index=False)

    # club -> international transfer (separate, never mixed in selection)
    club_p = ROOT / "data/processed/inplay_state_sb_club.parquet"
    if club_p.exists() and len(pd.read_parquet(club_p)):
        cl = pd.read_parquet(club_p).merge(pd.read_parquet(ROOT / "data/processed/sb_match_targets.parquet"),
                                           on="sb_match_id", how="inner")
        cl["red_diff"] = cl.red_home - cl.red_away
        cl = cl.dropna(subset=["elo_delta_home", "final_wld"])
        if len(cl) > 100:
            for name, fac in [("M2", M2_RemainingPoisson), ("M1", M1_TimeScore)]:
                mdl = fac().fit(cl)
                P = mdl.predict_wld(df)
                print(f"\n[club->intl transfer] {name} trained on {cl.match_id.nunique() if 'match_id' in cl else cl.sb_match_id.nunique()} club matches -> intl RPS {E.rps_per_row(P,Y).mean():.4f}")
    print("\nwrote", OUT)


if __name__ == "__main__":
    main()
