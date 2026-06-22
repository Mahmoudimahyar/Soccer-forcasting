"""Pre-match player-plane evaluation (research-only).

Question: does a LEAKAGE-SAFE starting-XI form signal (mean prior-match rating of the announced XI,
computed only from matches before kickoff) add 1X2 predictive value BEYOND Elo supremacy?

Design: leave-one-COMPETITION-out multinomial logistic.
  baseline  features = [elo_delta_home]
  candidate features = [elo_delta_home, strength_diff, coverage]
Metrics: RPS + log loss (held-out, pooled) and a match-resampled paired bootstrap candidate-vs-baseline.
No tuning to any held-out competition; xG is never a feature. 2026 is NOT touched here.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from wcdrawlab.research.player_plane_dataset import build_player_plane_features  # noqa: E402
from wcdrawlab.research.inplay_dataset import (  # noqa: E402
    _elo_lookup_from_history, _resolve_elo)
from wcdrawlab.ingest import canonical_team_name  # noqa: E402
from wcdrawlab.research import inplay_eval as E  # noqa: E402
from sklearn.linear_model import LogisticRegression  # noqa: E402

COMPS = {
    "WC2022": "2022_worldcup", "EURO2024": "euro2024", "COPA2024": "copa2024",
    "AFCON2023": "afcon2023", "ASIANCUP2023": "asiancup2023",
}
OUT = ROOT / "outputs/research/player_plane"; OUT.mkdir(parents=True, exist_ok=True)


def elo_delta_home(lut, row):
    pair = frozenset((canonical_team_name(row.home_name), canonical_team_name(row.away_name)))
    res = _resolve_elo(lut, row.kickoff_utc, pair, tol_days=3)
    if not res:
        return np.nan
    listed_a, ea, eb = res
    return (ea - eb) if listed_a == canonical_team_name(row.home_name) else (eb - ea)


def fit_predict_logo(df, feat_cols):
    """Leave-one-competition-out OOF probabilities (columns ordered H,D,A)."""
    Y = df.final_wld.map({"H": 0, "D": 1, "A": 2}).to_numpy()
    P = np.zeros((len(df), 3))
    for held in df.competition.unique():
        tr = df[df.competition != held]; te = df[df.competition == held]
        clf = LogisticRegression(max_iter=2000, C=1.0)
        clf.fit(tr[feat_cols].to_numpy(), tr.final_wld.map({"H": 0, "D": 1, "A": 2}).to_numpy())
        proba = clf.predict_proba(te[feat_cols].to_numpy())
        full = np.zeros((len(te), 3))
        for j, c in enumerate(clf.classes_):
            full[:, c] = proba[:, j]
        P[te.index.to_numpy()] = full
    return P, Y


def main():
    caches = {c: (ROOT / f"data/raw/api_football_{cid}/player_plane",
                  ROOT / f"data/raw/api_football_{cid}/fixtures.json") for c, cid in COMPS.items()}
    caches = {c: v for c, v in caches.items() if v[0].exists() and v[1].exists()}
    feats = build_player_plane_features(caches)
    print(f"player-plane matches built: {len(feats)} across {feats.competition.nunique()} competitions")

    elo = pd.read_csv(ROOT / "data/processed/elo_history.csv")
    lut = _elo_lookup_from_history(elo)
    feats["elo_delta_home"] = [elo_delta_home(lut, r) for r in feats.itertuples()]
    feats["coverage"] = (feats.home_cov + feats.away_cov) / 2.0

    # honest coverage report
    n_elo = feats.elo_delta_home.notna().sum()
    n_str = feats.strength_diff.notna().sum()
    print(f"  elo resolved: {n_elo}/{len(feats)} | strength_diff present: {n_str}/{len(feats)}")
    feats.to_csv(OUT / "player_plane_features.csv", index=False)

    d = feats.dropna(subset=["elo_delta_home", "strength_diff", "keyavail_diff", "final_wld"]).reset_index(drop=True)
    print(f"  usable rows (elo & strength & keyavail present): {len(d)} | per comp: {dict(d.competition.value_counts())}")
    if d.competition.nunique() < 2 or len(d) < 40:
        print("  insufficient usable data for LOGO comparison yet."); return

    candidates = {
        "elo+strength":          ["elo_delta_home", "strength_diff", "coverage"],
        "elo+keyavail":          ["elo_delta_home", "keyavail_diff"],
        "elo+strength+keyavail": ["elo_delta_home", "strength_diff", "keyavail_diff", "coverage"],
    }
    Pb, Y = fit_predict_logo(d, ["elo_delta_home"])
    rb = E.rps_per_row(Pb, Y)
    print("\n=== leave-one-competition-out RPS (lower=better) ===")
    print(f"  baseline Elo-only: RPS {rb.mean():.4f} | logloss {E.logloss_per_row(Pb,Y).mean():.4f}")
    out_rows = [{"model": "elo_only", "rps": float(rb.mean())}]
    for name, cols in candidates.items():
        Pc, _ = fit_predict_logo(d, cols)
        rc = E.rps_per_row(Pc, Y)
        bs = E.paired_match_bootstrap(rc, rb, d.match_id.to_numpy())
        flag = "BETTER*" if bs["a_better_sig"] else ("worse*" if bs["a_worse_sig"] else "~ns")
        print(f"  {name:<24}: RPS {rc.mean():.4f} | dRPS {bs['delta_mean']:+.4f} "
              f"CI[{bs['ci_low']:+.4f},{bs['ci_high']:+.4f}] {flag}")
        out_rows.append({"model": name, "rps": float(rc.mean()), "dRPS_vs_elo": bs["delta_mean"],
                         "ci_low": bs["ci_low"], "ci_high": bs["ci_high"],
                         "sig_better": bs["a_better_sig"], "sig_worse": bs["a_worse_sig"]})
    pd.DataFrame(out_rows).to_csv(OUT / "prematch_logo_result.csv", index=False)
    print("\nwrote", OUT)


if __name__ == "__main__":
    main()
