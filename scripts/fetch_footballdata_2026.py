"""Fetch authoritative 2026 World Cup group structure + freshest results from
football-data.org (free tier). Saves raw snapshot + a normalized results CSV, and
cross-checks the group assignment against the seed-based reconstruction.

Outputs:
  data/raw/footballdata_wc_2026.json
  data/processed/results_2026_footballdata.csv  (group, matchday, team_a, team_b,
                                                 goals_a, goals_b, kickoff_utc, status)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from _live_env import load_keys  # noqa: E402
load_keys(verbose=False)
import os  # noqa: E402
from wcdrawlab.ingest import canonical_team_name  # noqa: E402

RAW = ROOT / "data" / "raw"
PROC = ROOT / "data" / "processed"

EXTRA = {
    "Bosnia-Herzegovina": "Bosnia", "Bosnia and Herzegovina": "Bosnia",
    "Czech Republic": "Czechia", "South Korea": "Korea Republic",
    "Curaçao": "Curacao", "DR Congo": "Congo DR", "USA": "United States",
    "Cape Verde Islands": "Cape Verde", "Côte d'Ivoire": "Ivory Coast",
}


def canon(n: str) -> str:
    return EXTRA.get(str(n).strip(), canonical_team_name(n))


def main():
    key = os.environ.get("FOOTBALL_DATA_KEY")
    if not key:
        raise SystemExit("FOOTBALL_DATA_KEY missing")
    r = requests.get("https://api.football-data.org/v4/competitions/WC/matches",
                     headers={"X-Auth-Token": key}, timeout=30)
    r.raise_for_status()
    payload = r.json()
    (RAW / "footballdata_wc_2026.json").write_text(json.dumps(payload, indent=2))

    rows = []
    for m in payload["matches"]:
        if m.get("stage") != "GROUP_STAGE":
            continue
        ft = m.get("score", {}).get("fullTime", {})
        rows.append({
            "group": str(m.get("group", "")).replace("GROUP_", "").strip(),
            "matchday": m.get("matchday"),
            "team_a": canon(m["homeTeam"]["name"]),
            "team_b": canon(m["awayTeam"]["name"]),
            "goals_a": ft.get("home"),
            "goals_b": ft.get("away"),
            "kickoff_utc": m.get("utcDate"),
            "status": m.get("status"),
        })
    df = pd.DataFrame(rows)
    df["kickoff_utc"] = pd.to_datetime(df["kickoff_utc"], utc=True)
    df = df.sort_values(["group", "matchday", "kickoff_utc"]).reset_index(drop=True)
    df.to_csv(PROC / "results_2026_footballdata.csv", index=False)

    finished = df[df["status"] == "FINISHED"]
    print(f"group-stage matches: {len(df)} | finished: {len(finished)} | groups: {df['group'].nunique()}")
    print("finished by matchday:", finished.groupby("matchday").size().to_dict())

    # cross-check groups vs reconstruction
    recon_path = PROC / "groups_2026.csv"
    if recon_path.exists():
        fd_groups = {g: sorted(set(sub["team_a"]) | set(sub["team_b"]))
                     for g, sub in df.groupby("group")}
        recon = pd.read_csv(recon_path)
        import ast
        mismatches = 0
        for _, r2 in recon.iterrows():
            rec_teams = sorted(ast.literal_eval(r2["teams"]))
            fd_teams = fd_groups.get(r2["group"], [])
            if rec_teams != fd_teams:
                mismatches += 1
                print(f"  GROUP {r2['group']} differs:\n    recon={rec_teams}\n    fdorg={fd_teams}")
        print(f"group cross-check: {len(recon)-mismatches}/{len(recon)} groups identical to reconstruction")

    # team-name coverage check vs martj42 Elo source
    intl = pd.read_csv(RAW / "international_results.csv")
    known = set(intl["home_team"].map(canonical_team_name)) | set(intl["away_team"].map(canonical_team_name))
    unknown = sorted(set(df["team_a"]) | set(df["team_b"]) - known)
    unknown = [t for t in (set(df["team_a"]) | set(df["team_b"])) if t not in known]
    if unknown:
        print("teams not directly in martj42 (Elo will default/alias):", sorted(unknown))
    print("wrote:", PROC / "results_2026_footballdata.csv")


if __name__ == "__main__":
    main()
