"""Prospective scoring loop for the 2026 group stage.

Two parts, run as a single reusable command:
  1) LEDGER  — append the current pre-kickoff forecasts (model B7 + market consensus) from
     forecast_2026_market_anchored.csv into a frozen, append-only ledger. First-write-wins:
     a match's forecast is NEVER overwritten once recorded, so it stays a true pre-kickoff
     prediction even if re-run after the result is known.
  2) SCORER  — re-fetch the latest football-data.org results and grade every ledger forecast
     whose match has FINISHED (model vs market vs the market-primary headline), plus refresh
     the prequential model/Elo/prior scorecard over all finished matches.

Run anytime (e.g. after each matchday): `python scripts/prospective_scorecard.py`
Add `--no-refresh` to skip the live results re-fetch and score against the cached results.
"""
from __future__ import annotations

import sys
import urllib.request
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from wcdrawlab.evaluation import normalize_probs  # noqa: E402
from wcdrawlab.ingest import canonical_team_name  # noqa: E402
from _live_env import load_keys  # noqa: E402

PROC = ROOT / "data" / "processed"
OUTD = ROOT / "outputs" / "research"
LEDGER = PROC / "forecast_ledger.csv"
MA = OUTD / "forecasts" / "forecast_2026_market_anchored.csv"

EXTRA = {"Bosnia-Herzegovina": "Bosnia", "Bosnia and Herzegovina": "Bosnia",
         "Czech Republic": "Czechia", "South Korea": "Korea Republic",
         "Curaçao": "Curacao", "DR Congo": "Congo DR", "USA": "United States",
         "Republic of Ireland": "Ireland"}


def canon(n):
    return EXTRA.get(str(n).strip(), canonical_team_name(n))


def pair(a, b):
    return frozenset((canon(a), canon(b)))


def update_ledger() -> pd.DataFrame:
    if not MA.exists():
        raise SystemExit("Run scripts/market_anchored_forecast.py first to produce forecasts.")
    fc = pd.read_csv(MA)
    cols = {"match_id", "matchday", "group", "team_a", "team_b", "snapshot",
            "p_a", "p_draw", "p_b", "p_a_market", "p_draw_market", "p_b_market",
            "p_a_final", "p_draw_final", "p_b_final"}
    fc = fc[[c for c in fc.columns if c in cols]].copy()
    fc = fc.rename(columns={"p_a": "model_a", "p_draw": "model_d", "p_b": "model_b",
                            "p_a_market": "mkt_a", "p_draw_market": "mkt_d", "p_b_market": "mkt_b",
                            "p_a_final": "blend_a", "p_draw_final": "blend_d", "p_b_final": "blend_b"})
    if LEDGER.exists():
        led = pd.read_csv(LEDGER)
        new = fc[~fc["match_id"].isin(set(led["match_id"]))]
        led = pd.concat([led, new], ignore_index=True)
        added = len(new)
    else:
        led = fc
        added = len(fc)
    led.to_csv(LEDGER, index=False)
    print(f"[ledger] {len(led)} frozen forecasts ({added} newly added this run)")
    return led


def fetch_results(refresh: bool) -> pd.DataFrame:
    # own cache file — never clobber the canonical results_2026_footballdata.csv (which the
    # table build relies on and which carries the full schema incl. kickoff_utc/group).
    cache = PROC / "results_2026_live.csv"
    if refresh:
        load_keys(verbose=False)
        import os
        key = os.environ.get("FOOTBALL_DATA_KEY")
        if key:
            try:
                req = urllib.request.Request("https://api.football-data.org/v4/competitions/WC/matches",
                                             headers={"X-Auth-Token": key})
                with urllib.request.urlopen(req, timeout=30) as r:
                    payload = json.load(r)
                rows = []
                for m in payload["matches"]:
                    if m.get("stage") != "GROUP_STAGE":
                        continue
                    ft = m.get("score", {}).get("fullTime", {})
                    rows.append({"team_a": canon(m["homeTeam"]["name"]), "team_b": canon(m["awayTeam"]["name"]),
                                 "matchday": m.get("matchday"), "goals_a": ft.get("home"),
                                 "goals_b": ft.get("away"), "status": m.get("status")})
                df = pd.DataFrame(rows)
                df.to_csv(cache, index=False)
                print(f"[results] refreshed: {int((df['status']=='FINISHED').sum())} finished")
                return df
            except Exception as e:  # noqa: BLE001
                print("[results] refresh failed, using cache:", repr(e)[:100])
    df = pd.read_csv(cache)
    df["team_a"] = df["team_a"].map(canon); df["team_b"] = df["team_b"].map(canon)
    print(f"[results] cached: {int((df['status']=='FINISHED').sum())} finished")
    return df


def outcome(ga, gb):
    return "A" if ga > gb else "D" if ga == gb else "B"


def rps(p, y):  # ordered ranked probability score, 3-way
    c = np.cumsum(p); o = np.cumsum([1 if k == y else 0 for k in [0, 1, 2]])
    return float(((c - o) ** 2).sum() / 2)


def logloss(p, y):
    return float(-np.log(max(p[y], 1e-12)))


def main():
    refresh = "--no-refresh" not in sys.argv
    led = update_ledger()
    res = fetch_results(refresh)
    fin = res[(res["status"] == "FINISHED") & res["goals_a"].notna()].copy()
    fin["pair"] = [pair(a, b) for a, b in zip(fin["team_a"], fin["team_b"])]
    fin["y"] = [outcome(a, b) for a, b in zip(fin["goals_a"], fin["goals_b"])]
    res_map = {(r["pair"], int(r["matchday"])): r["y"] for _, r in fin.iterrows()}

    scored = []
    yi = {"A": 0, "D": 1, "B": 2}
    for _, r in led.iterrows():
        y = res_map.get((pair(r["team_a"], r["team_b"]), int(r["matchday"])))
        if y is None:
            continue
        mp = normalize_probs(np.array([[r["model_a"], r["model_d"], r["model_b"]]]))[0]
        row = {"match_id": r["match_id"], "matchday": r["matchday"],
               "team_a": r["team_a"], "team_b": r["team_b"], "outcome": y,
               "model_rps": rps(mp, yi[y]), "model_ll": logloss(mp, yi[y])}
        if pd.notna(r.get("mkt_a")):
            kp = normalize_probs(np.array([[r["mkt_a"], r["mkt_d"], r["mkt_b"]]]))[0]
            row["mkt_rps"] = rps(kp, yi[y]); row["mkt_ll"] = logloss(kp, yi[y])
        if pd.notna(r.get("blend_a")):
            bp = normalize_probs(np.array([[r["blend_a"], r["blend_d"], r["blend_b"]]]))[0]
            row["blend_rps"] = rps(bp, yi[y]); row["blend_ll"] = logloss(bp, yi[y])
        scored.append(row)

    sc = pd.DataFrame(scored)
    OUTD.mkdir(parents=True, exist_ok=True)
    sc.to_csv(OUTD / "prospective_scorecard.csv", index=False)

    print("\n=== PROSPECTIVE LEDGER SCORE (forecasts made pre-kickoff, now finished) ===")
    if sc.empty:
        print("No ledger forecasts have finished yet. Re-run after the next matches play.")
    else:
        n = len(sc)
        print(f"matches scored: {n}  (MD {sc.groupby('matchday').size().to_dict()})")
        print(f"  MODEL  : RPS {sc['model_rps'].mean():.3f}  LogLoss {sc['model_ll'].mean():.3f}")
        if "mkt_rps" in sc:
            mk = sc.dropna(subset=["mkt_rps"])
            print(f"  MARKET : RPS {mk['mkt_rps'].mean():.3f}  LogLoss {mk['mkt_ll'].mean():.3f}  (n={len(mk)})")
        if "blend_rps" in sc:
            bl = sc.dropna(subset=["blend_rps"])
            print(f"  BLEND  : RPS {bl['blend_rps'].mean():.3f}  LogLoss {bl['blend_ll'].mean():.3f}  "
                  f"(validated market+Elo headline)")
            if "mkt_rps" in sc:
                print(f"  -> blend {'BEATS' if bl['blend_rps'].mean() < mk['mkt_rps'].mean() else 'TRAILS'} "
                      f"market on RPS so far")
        print(sc.to_string(index=False))
    print("\n(Backward model/Elo/prior view over all finished matches: scripts/prequential_2026.py)")
    print("wrote:", OUTD / "prospective_scorecard.csv")


if __name__ == "__main__":
    main()
