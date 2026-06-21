"""Build time-safe starting-XI squad features from the Transfermarkt dataset (player valuations
as-of match date, age, share of players in a top-5 league) for national-team tournament games
that HAVE lineups in TM (Copa America, AFCON, Asian Cup — World Cup/Euro lineups are absent in
this dataset). Then test whether these features are (a) redundant with Elo and (b) add anything
beyond market+Elo on the odds-matched subset.

Leakage controls: valuation date <= match date (ASOF join); age from DOB at match date; starting
XI is known ~1h pre-kickoff (looser than the T-90 market, noted in the report).
"""
from __future__ import annotations

import sys
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from wcdrawlab.ingest import canonical_team_name  # noqa: E402
from wcdrawlab.ratings import ternary_elo_probs  # noqa: E402
from wcdrawlab.evaluation import metric_report, normalize_probs  # noqa: E402
from wcdrawlab.research.runner import draw_calibration_error  # noqa: E402

DB = ROOT / "data" / "raw" / "transfermarkt.duckdb"
TOP5 = ("GB1", "ES1", "IT1", "L1", "FR1")
EXTRA = {"Czech Republic": "Czechia", "Democratic Republic of the Congo": "Congo DR",
         "South Korea": "Korea Republic", "Korea, South": "Korea Republic", "USA": "United States",
         "Cape Verde Islands": "Cape Verde", "Türkiye": "Turkey"}
W = {"rps": 0.40, "log_loss": 0.25, "draw_brier": 0.20, "draw_calibration_error": 0.15}


def canon(n):
    return EXTRA.get(str(n).strip(), canonical_team_name(n))


def comp(y, P):
    P = normalize_probs(P)
    m = metric_report(y, P); m["draw_calibration_error"] = draw_calibration_error(y, P[:, 1])
    return float(sum(W[k] * m[k] for k in W))


def build_team_xi():
    con = duckdb.connect(str(DB), read_only=True)
    sql = f"""
    WITH xi AS (
      SELECT CAST(gl.game_id AS VARCHAR) game_id, gl.club_id, gl.player_id,
             CAST(g.date AS DATE) gdate, g.competition_id,
             g.home_club_id, g.away_club_id, g.home_club_name, g.away_club_name,
             g.home_club_goals, g.away_club_goals
      FROM game_lineups gl
      JOIN games g ON CAST(g.game_id AS VARCHAR)=CAST(gl.game_id AS VARCHAR)
      WHERE gl.type='starting_lineup' AND g.competition_id IN ('COPA','AFCN','AFAC')
        AND CAST(g.date AS DATE) >= DATE '2020-06-01'
    ),
    valued AS (
      SELECT xi.*, pv.market_value_in_eur mv, pv.player_club_domestic_competition_id league
      FROM xi ASOF LEFT JOIN player_valuations pv
        ON xi.player_id = pv.player_id AND xi.gdate >= pv.date
    ),
    aged AS (
      SELECT v.*, p.date_of_birth dob FROM valued v LEFT JOIN players p ON v.player_id=p.player_id
    )
    SELECT game_id, gdate, competition_id, home_club_id, away_club_id, home_club_name, away_club_name,
           ANY_VALUE(home_club_goals) home_club_goals, ANY_VALUE(away_club_goals) away_club_goals,
           club_id,
           COUNT(*) n_xi,
           SUM(COALESCE(mv,0))/1e6 xi_value_m,
           AVG(mv)/1e6 xi_value_mean_m,
           AVG(DATE_DIFF('day', dob, gdate)/365.25) xi_age,
           AVG(CASE WHEN league IN {TOP5} THEN 1.0 ELSE 0.0 END) xi_top5_share
    FROM aged
    GROUP BY game_id, gdate, competition_id, home_club_id, away_club_id,
             home_club_name, away_club_name, club_id
    """
    df = con.execute(sql).fetchdf()
    con.close()
    return df


def main():
    raw = build_team_xi()
    # pivot to per-game home/away
    rows = []
    for gid, g in raw.groupby("game_id"):
        if len(g) != 2:
            continue
        hc = g[g["club_id"] == g["home_club_id"].iloc[0]]
        ac = g[g["club_id"] == g["away_club_id"].iloc[0]]
        if len(hc) != 1 or len(ac) != 1:
            continue
        hc, ac = hc.iloc[0], ac.iloc[0]
        ga, gb = hc["home_club_goals"], hc["away_club_goals"]
        outcome = None if pd.isna(ga) or pd.isna(gb) else ("A" if ga > gb else "D" if ga == gb else "B")
        rows.append({
            "date": g["gdate"].iloc[0], "comp": g["competition_id"].iloc[0],
            "team_a": canon(hc["home_club_name"]), "team_b": canon(ac["away_club_name"]),
            "outcome": outcome,
            "value_delta": hc["xi_value_m"] - ac["xi_value_m"],
            "age_delta": hc["xi_age"] - ac["xi_age"],
            "top5_delta": hc["xi_top5_share"] - ac["xi_top5_share"],
            "n_xi_a": hc["n_xi"], "n_xi_b": ac["n_xi"],
        })
    sf = pd.DataFrame(rows)
    sf.to_csv(ROOT / "data" / "processed" / "squad_features_tm.csv", index=False)
    print(f"TM NT games with XI features (Copa/AFCON/AsianCup): {len(sf)}")
    print("  value_delta(m EUR) range:", round(sf.value_delta.min(), 1), "->", round(sf.value_delta.max(), 1),
          "| mean abs age_delta:", round(sf.age_delta.abs().mean(), 2))

    # Broader null test (largest N): does squad data add beyond Elo across ALL 128 TM games?
    from build_research_table import build_elo_history, elo_before
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    from sklearn.model_selection import KFold
    hist = build_elo_history()
    g = sf.dropna(subset=["outcome"]).copy()
    g[["value_delta", "age_delta", "top5_delta"]] = g[["value_delta", "age_delta", "top5_delta"]].fillna(0.0)
    g["kick"] = pd.to_datetime(g["date"], utc=True)
    g["elo_delta"] = [elo_before(hist, a, d) - elo_before(hist, b, d)
                      for a, b, d in zip(g["team_a"], g["team_b"], g["kick"])]
    yi = g["outcome"].map({"A": 0, "D": 1, "B": 2})
    Xelo = g[["elo_delta"]].to_numpy()
    Xall = g[["elo_delta", "value_delta", "age_delta", "top5_delta"]].to_numpy()
    kf = KFold(5, shuffle=True, random_state=0)

    def cv_ll(X):
        from wcdrawlab.evaluation import log_loss_3way, normalize_probs as nz
        P = np.zeros((len(g), 3)); sc = StandardScaler()
        for tr, te in kf.split(X):
            lr = LogisticRegression(C=1.0, max_iter=2000)
            lr.fit(sc.fit_transform(X[tr]), yi.iloc[tr])
            raw = lr.predict_proba(sc.transform(X[te]))
            for j, c in enumerate(lr.classes_):
                P[te, int(c)] = raw[:, j]
        return log_loss_3way(g["outcome"], nz(P))
    print(f"  [N={len(g)} all TM tourn games] 5-fold logloss: Elo-only {cv_ll(Xelo):.4f}"
          f" vs Elo+squad {cv_ll(Xall):.4f}  (lower=better)")

    # join to intl odds dataset
    ds = pd.read_csv(ROOT / "data" / "processed" / "intl_market_dataset.csv", parse_dates=["kickoff_utc"])
    ds["date"] = ds["kickoff_utc"].dt.date.astype(str)
    sf["date"] = sf["date"].astype(str)
    ds["pair"] = ds.apply(lambda r: frozenset((r.team_a, r.team_b)), axis=1)
    sf["pair"] = sf.apply(lambda r: frozenset((r.team_a, r.team_b)), axis=1)
    # align orientation of value_delta to ds team_a
    m = ds.merge(sf[["date", "pair", "team_a", "value_delta", "age_delta", "top5_delta"]],
                 on=["date", "pair"], suffixes=("", "_sf"), how="inner")
    flip = m["team_a"] != m["team_a_sf"]
    for c in ["value_delta", "age_delta", "top5_delta"]:
        m.loc[flip, c] = -m.loc[flip, c]
    print(f"\nmatched to odds dataset: {len(m)} matches (comps: {m['sport'].value_counts().to_dict()})")
    if len(m) < 20:
        print("too few matched matches for a meaningful test."); return

    # (a) redundancy with Elo
    print("\n--- redundancy ---")
    print("corr(value_delta, elo_delta):", round(m["value_delta"].corr(m["elo_delta"]), 3))
    print("corr(value_delta, market_p_a - market_p_b):",
          round(m["value_delta"].corr(m["p_a_market"] - m["p_b_market"]), 3))

    # (b) does value add beyond market+Elo? compare composite of blends (in-sample, small N -> caveat)
    y = m["outcome"]
    Pm = normalize_probs(m[["p_a_market", "p_draw_market", "p_b_market"]].to_numpy())
    Pe = ternary_elo_probs(m["elo_delta"].to_numpy())
    base = normalize_probs(0.6 * Pm + 0.4 * Pe)
    # value as a tilt: convert value_delta to a logit nudge on A vs B
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    # stacked logit: outcome ~ [market logits, elo_delta, value_delta, age_delta, top5_delta]
    def logit(p): p = np.clip(p, 1e-4, 1 - 1e-4); return np.log(p / (1 - p))
    X = np.column_stack([logit(Pm[:, 0]), logit(Pm[:, 1]), logit(Pm[:, 2]), m["elo_delta"],
                         m["value_delta"], m["age_delta"], m["top5_delta"]])
    Xb = X[:, :4]  # market+elo only
    yi = y.map({"A": 0, "D": 1, "B": 2})
    from sklearn.model_selection import KFold
    kf = KFold(5, shuffle=True, random_state=0)
    def cv_comp(Xuse):
        P = np.zeros((len(m), 3))
        sc = StandardScaler()
        for tr, te in kf.split(Xuse):
            lr = LogisticRegression(C=1.0, max_iter=2000)
            lr.fit(sc.fit_transform(Xuse[tr]), yi.iloc[tr])
            raw = lr.predict_proba(sc.transform(Xuse[te]))
            for j, c in enumerate(lr.classes_):
                P[te, int(c)] = raw[:, j]
        return comp(y, normalize_probs(P))
    print("\n--- does squad data add beyond market+Elo? (5-fold CV stacked logit, small N) ---")
    print(f"  market+Elo blend (no fit)        composite {comp(y, base):.4f}")
    print(f"  stacked [market+Elo]             composite {cv_comp(Xb):.4f}")
    print(f"  stacked [market+Elo+squad]       composite {cv_comp(X):.4f}")
    print("\nNote: N is small and these comps include AFCON/Copa (thinner markets) only;"
          " treat any difference cautiously.")


if __name__ == "__main__":
    main()
