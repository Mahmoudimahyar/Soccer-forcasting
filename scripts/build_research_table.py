"""Build the leakage-safe research modeling table.

Outputs:
  data/processed/research_modeling_table.csv   -> played WC group matches 1998-2026 (for the fixed evaluator)
  data/processed/forecast_targets_2026.csv     -> upcoming 2026 group fixtures (for live forecasting)
  data/processed/elo_history.csv               -> time-safe team Elo trajectory (audit)
  data/processed/groups_2026.csv               -> reconstructed 2026 group assignment (audit)

Design / leakage controls:
  * One Elo built walk-forward over ALL martj42 international results (1872->).
    elo_before(team, date) returns the team's Elo from its last match STRICTLY BEFORE
    `date` (default 1500). The match being predicted is never in that history -> no leakage.
  * Group/matchday labels: jfjelstul (1998-2022, official), reconstruction for 2026.
  * Group-state features come from features.build_pre_match_group_state (pre-match only).
  * Result columns (goals_a/goals_b/outcome/is_draw) are kept but are stripped by the
    fixed evaluator's leakage guard; every modeling feature satisfies available_at <= kickoff.
"""
from __future__ import annotations

import sys
from bisect import bisect_left
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from wcdrawlab.ingest import canonical_team_name  # noqa: E402
from wcdrawlab.elo import goal_difference_multiplier  # noqa: E402
from wcdrawlab.ratings import elo_expected_score, standardize_fifa_release  # noqa: E402
from wcdrawlab.data import asof_join_team_rating  # noqa: E402
from wcdrawlab.features import (  # noqa: E402
    add_basic_outcome_columns,
    add_strength_deltas,
    build_pre_match_group_state,
    add_schedule_adjusted_state,
    add_low_block_risk,
    add_travel_fatigue,
)

RAW = ROOT / "data" / "raw"
PROC = ROOT / "data" / "processed"
SEED = ROOT / "data" / "seed"
FD_RESULTS = PROC / "results_2026_footballdata.csv"  # authoritative 2026 source (if fetched)
FIFA_RANKINGS = PROC / "fifa_rankings.csv"           # release-dated FIFA points (if fetched)

YEARS = [1998, 2002, 2006, 2010, 2014, 2018, 2022, 2026]
HOSTS = {
    1998: {"France"},
    2002: {"Korea Republic", "Japan"},
    2006: {"Germany"},
    2010: {"South Africa"},
    2014: {"Brazil"},
    2018: {"Russia"},
    2022: {"Qatar"},
    2026: {"United States", "Canada", "Mexico"},
}

# Extra aliases to reconcile jfjelstul <-> martj42 spellings after canonical_team_name.
EXTRA_ALIASES = {
    "IR Iran": "Iran",
    "Korea DPR": "Korea DPR",
    "China PR": "China",
    "United States of America": "United States",
    "Côte d'Ivoire": "Ivory Coast",
    "Cote d'Ivoire": "Ivory Coast",
    "Czech Republic": "Czechia",
    "Republic of Ireland": "Ireland",
    "Serbia and Montenegro": "Serbia",  # martj42 labels the 2006 team "Serbia"
}

ELO_K = 40.0
ELO_SCALE = 400.0
HOME_ADV = 65.0
INIT_ELO = 1500.0

CONFED = {
    # UEFA
    **{t: "UEFA" for t in [
        "Spain", "France", "Germany", "England", "Portugal", "Netherlands", "Belgium",
        "Croatia", "Italy", "Switzerland", "Denmark", "Poland", "Serbia", "Wales",
        "Sweden", "Norway", "Austria", "Czechia", "Scotland", "Ukraine", "Russia",
        "Turkey", "Bosnia", "Slovenia", "Slovakia", "Ireland", "Romania", "Bulgaria",
        "Greece", "Hungary", "Iceland", "Albania", "North Macedonia", "Finland",
        "Northern Ireland", "Georgia", "Montenegro", "Serbia and Montenegro",
        "FR Yugoslavia", "Yugoslavia",
    ]},
    # CONMEBOL
    **{t: "CONMEBOL" for t in [
        "Brazil", "Argentina", "Uruguay", "Colombia", "Chile", "Peru", "Ecuador",
        "Paraguay", "Bolivia", "Venezuela",
    ]},
    # CONCACAF
    **{t: "CONCACAF" for t in [
        "United States", "Mexico", "Canada", "Costa Rica", "Honduras", "Panama",
        "Jamaica", "Haiti", "Trinidad and Tobago", "El Salvador", "Curacao", "Cuba",
    ]},
    # CAF
    **{t: "CAF" for t in [
        "Senegal", "Morocco", "Nigeria", "Cameroon", "Ghana", "Egypt", "Algeria",
        "Tunisia", "Ivory Coast", "South Africa", "Congo DR", "Cape Verde", "Mali",
        "Burkina Faso", "Angola", "Togo",
    ]},
    # AFC
    **{t: "AFC" for t in [
        "Japan", "Korea Republic", "Iran", "Saudi Arabia", "Australia", "Qatar",
        "Iraq", "Uzbekistan", "United Arab Emirates", "China", "Jordan", "Bahrain",
        "Korea DPR", "North Korea",
    ]},
    # OFC
    **{t: "OFC" for t in ["New Zealand"]},
}


def canon(name: str) -> str:
    n = canonical_team_name(name)
    return EXTRA_ALIASES.get(str(name).strip(), EXTRA_ALIASES.get(n, n))


# --------------------------------------------------------------------------------------
# 1. Time-safe Elo over all international results
# --------------------------------------------------------------------------------------
def build_elo_history() -> dict[str, tuple[list, list]]:
    intl = pd.read_csv(RAW / "international_results.csv")
    intl["date"] = pd.to_datetime(intl["date"], errors="coerce", utc=True)
    intl = intl.dropna(subset=["date"]).sort_values("date", kind="stable").reset_index(drop=True)
    intl["team_a"] = intl["home_team"].map(canon)
    intl["team_b"] = intl["away_team"].map(canon)

    # Keep Elo current: append football-data.org finished 2026 results that martj42 lags on
    # (deduped by date + team pair). Hosts (USA/Canada/Mexico) are non-neutral; rest neutral.
    if FD_RESULTS.exists():
        fd = pd.read_csv(FD_RESULTS, parse_dates=["kickoff_utc"])
        fd = fd[fd["status"] == "FINISHED"].copy()
        fd["team_a"] = fd["team_a"].map(canon)
        fd["team_b"] = fd["team_b"].map(canon)
        # Dedup by team PAIR among martj42's already-FINISHED 2026 matches (each 2026 group
        # pairing is unique), so we only add results martj42 still lacks — no double counting
        # despite UTC-vs-date day shifts.
        m26_played = ((intl["date"].dt.year == 2026)
                      & intl["home_score"].notna() & intl["away_score"].notna())
        existing_pairs = {frozenset((a, b))
                          for a, b in zip(intl.loc[m26_played, "team_a"], intl.loc[m26_played, "team_b"])}
        add = []
        hosts2026 = HOSTS[2026]
        for r in fd.itertuples(index=False):
            if frozenset((r.team_a, r.team_b)) in existing_pairs or pd.isna(r.goals_a) or pd.isna(r.goals_b):
                continue
            add.append({"date": r.kickoff_utc, "home_team": r.team_a, "away_team": r.team_b,
                        "home_score": r.goals_a, "away_score": r.goals_b,
                        "neutral": r.team_a not in hosts2026, "team_a": r.team_a, "team_b": r.team_b})
        if add:
            intl = pd.concat([intl, pd.DataFrame(add)], ignore_index=True)
            intl = intl.sort_values("date", kind="stable").reset_index(drop=True)
            print(f"[elo] supplemented with {len(add)} fresher football-data 2026 results")

    elo: dict[str, float] = {}
    hist: dict[str, tuple[list, list]] = {}  # team -> (dates[], elo_after[])
    audit = []

    for r in intl.itertuples(index=False):
        a, b = r.team_a, r.team_b
        ea = elo.get(a, INIT_ELO)
        eb = elo.get(b, INIT_ELO)
        ha = 0.0 if bool(r.neutral) else HOME_ADV
        if pd.notna(r.home_score) and pd.notna(r.away_score):
            ga, gb = int(r.home_score), int(r.away_score)
            exp_a = float(elo_expected_score(np.array([(ea + ha) - eb]), ELO_SCALE)[0])
            score_a = 1.0 if ga > gb else 0.5 if ga == gb else 0.0
            mult = goal_difference_multiplier(abs(ga - gb))
            delta = ELO_K * mult * (score_a - exp_a)
            ea_new, eb_new = ea + delta, eb - delta
            elo[a], elo[b] = ea_new, eb_new
            for t, e_after in ((a, ea_new), (b, eb_new)):
                d, vals = hist.setdefault(t, ([], []))
                d.append(r.date)
                vals.append(e_after)
            audit.append((r.date, a, b, ea, eb, ea_new, eb_new))

    pd.DataFrame(audit, columns=["date", "team_a", "team_b", "elo_a_pre", "elo_b_pre",
                                 "elo_a_post", "elo_b_post"]).to_csv(PROC / "elo_history.csv", index=False)
    print(f"[elo] built history for {len(hist)} teams from {len(intl)} matches; "
          f"final-Elo top: {sorted(elo.items(), key=lambda kv: -kv[1])[:5]}")
    return hist


def elo_before(hist: dict[str, tuple[list, list]], team: str, date: pd.Timestamp) -> float:
    """Team Elo carried into `date`: elo_after of last match STRICTLY before date."""
    if team not in hist:
        return INIT_ELO
    dates, vals = hist[team]
    i = bisect_left(dates, date)  # first index with dates[i] >= date
    return vals[i - 1] if i > 0 else INIT_ELO


# --------------------------------------------------------------------------------------
# 2. Historical WC group matches (1998-2022) from jfjelstul
# --------------------------------------------------------------------------------------
def load_historical_groups() -> pd.DataFrame:
    jf = pd.read_csv(RAW / "jf_worldcup_matches.csv")
    jf = jf[(jf["group_stage"] == 1) & (jf["tournament_name"].str.contains("Men's", na=False))].copy()
    jf["kickoff_utc"] = pd.to_datetime(jf["match_date"], errors="coerce", utc=True)
    jf["year"] = jf["kickoff_utc"].dt.year
    jf = jf[jf["year"].isin([y for y in YEARS if y != 2026])].copy()
    jf["team_a"] = jf["home_team_name"].map(canon)
    jf["team_b"] = jf["away_team_name"].map(canon)
    jf["group"] = jf["group_name"].str.replace("Group ", "", regex=False).str.strip()
    out = pd.DataFrame({
        "kickoff_utc": jf["kickoff_utc"],
        "year": jf["year"].astype(int),
        "tournament": jf["tournament_name"],
        "stage": "group",
        "group": jf["group"],
        "team_a": jf["team_a"],
        "team_b": jf["team_b"],
        "goals_a": pd.to_numeric(jf["home_team_score"], errors="coerce"),
        "goals_b": pd.to_numeric(jf["away_team_score"], errors="coerce"),
        "source": "jfjelstul",
    })
    return out


# --------------------------------------------------------------------------------------
# 3. Reconstruct 2026 groups from martj42 fixtures, anchored by the seed file
# --------------------------------------------------------------------------------------
def reconstruct_2026() -> pd.DataFrame:
    # Prefer the authoritative football-data.org structure + freshest results when available.
    if FD_RESULTS.exists():
        fd = pd.read_csv(FD_RESULTS, parse_dates=["kickoff_utc"])
        fd["team_a"] = fd["team_a"].map(canon)
        fd["team_b"] = fd["team_b"].map(canon)
        rows = pd.DataFrame({
            "kickoff_utc": fd["kickoff_utc"],
            "year": 2026,
            "tournament": "2026 FIFA World Cup",
            "stage": "group",
            "group": fd["group"].astype(str),
            "matchday": fd["matchday"].astype("Int64"),
            "team_a": fd["team_a"],
            "team_b": fd["team_b"],
            "goals_a": pd.to_numeric(fd["goals_a"], errors="coerce"),
            "goals_b": pd.to_numeric(fd["goals_b"], errors="coerce"),
            "source": "footballdata.org",
        })
        grp_df = pd.DataFrame({"group": sorted(rows["group"].unique())})
        grp_df["teams"] = grp_df["group"].map(
            lambda g: sorted(set(rows.loc[rows.group == g, "team_a"]) | set(rows.loc[rows.group == g, "team_b"])))
        grp_df.to_csv(PROC / "groups_2026.csv", index=False)
        n_fin = int((rows["goals_a"].notna() & rows["goals_b"].notna()).sum())
        print(f"[2026] using football-data.org: {len(rows)} group matches, {n_fin} finished, "
              f"{rows['group'].nunique()} groups")
        assert rows["group"].nunique() == 12
        return rows

    intl = pd.read_csv(RAW / "international_results.csv")
    intl["date"] = pd.to_datetime(intl["date"], errors="coerce", utc=True)
    wc26 = intl[(intl["tournament"] == "FIFA World Cup") & (intl["date"].dt.year == 2026)].copy()
    wc26["team_a"] = wc26["home_team"].map(canon)
    wc26["team_b"] = wc26["away_team"].map(canon)

    # Union-find over team pairings -> connected components (groups of 4).
    parent: dict[str, str] = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x, y):
        parent[find(x)] = find(y)

    for r in wc26.itertuples(index=False):
        union(r.team_a, r.team_b)
    comp: dict[str, list[str]] = {}
    for t in set(wc26["team_a"]).union(wc26["team_b"]):
        comp.setdefault(find(t), []).append(t)
    components = list(comp.values())

    # Membership comes from the fixture graph (authoritative). Letters are anchored to the
    # seed file's group assignments, but the seed has an internal conflict: it labels
    # "Netherlands-Japan" as L even though the fixture graph places Netherlands/Japan in
    # the SAME round-robin component as Sweden/Tunisia (seed group F). We therefore assign
    # letters deterministically by greedy vote, respecting unambiguous anchors and breaking
    # the conflict so every component gets a unique letter (graph membership overrides the
    # bad seed anchor).
    from collections import Counter

    seed = pd.read_csv(SEED / "worldcup_2026_seed_matches.csv")
    team_to_letter: dict[str, str] = {}
    for r in seed.itertuples(index=False):
        for t in (canon(r.team_a), canon(r.team_b)):
            team_to_letter[t] = r.group

    comps = [frozenset(m) for m in components]
    votes = {c: Counter(team_to_letter[t] for t in c if t in team_to_letter) for c in comps}
    # process components most-confident first; deterministic tie-break by sorted members
    order = sorted(comps, key=lambda c: (-(max(votes[c].values()) if votes[c] else 0), sorted(c)))
    available = set("ABCDEFGHIJKL")
    label_map: dict[frozenset, str] = {}
    for c in order:
        pick = None
        for letter, _cnt in sorted(votes[c].items(), key=lambda kv: (-kv[1], kv[0])):
            if letter in available:
                pick = letter
                break
        if pick is None:  # no available voted letter -> take lowest free letter
            pick = min(available)
        available.discard(pick)
        label_map[c] = pick

    def group_of(team):
        for members, letter in label_map.items():
            if team in members:
                return letter
        return "?"

    wc26["group"] = wc26["team_a"].map(group_of)
    wc26 = wc26.sort_values("date", kind="stable")

    rows = pd.DataFrame({
        "kickoff_utc": wc26["date"],
        "year": 2026,
        "tournament": "2026 FIFA World Cup",
        "stage": "group",
        "group": wc26["group"],
        "team_a": wc26["team_a"],
        "team_b": wc26["team_b"],
        "goals_a": pd.to_numeric(wc26["home_score"], errors="coerce"),
        "goals_b": pd.to_numeric(wc26["away_score"], errors="coerce"),
        "source": "martj42+seed_recon",
    })

    # audit: print the 12 reconstructed groups
    audit = (rows.assign(team=rows["team_a"]).groupby("group")["team_a"]
             .apply(lambda s: sorted(set(s) | set(rows.loc[s.index, "team_b"]))))
    grp_df = pd.DataFrame({"group": audit.index, "teams": audit.values})
    grp_df.to_csv(PROC / "groups_2026.csv", index=False)
    print("[2026] reconstructed groups:")
    for _, gr in grp_df.iterrows():
        print(f"   {gr['group']}: {gr['teams']}")
    n_groups = rows["group"].nunique()
    assert len(components) == 12, f"expected 12 fixture components, got {len(components)}"
    assert all(len(m) == 4 for m in components), \
        f"every 2026 group must have 4 teams; sizes={sorted(len(m) for m in components)}"
    assert n_groups == 12, f"expected 12 distinct group letters, got {n_groups}"
    assert (rows["group"] != "?").all(), "some 2026 matches unlabeled"
    return rows


# --------------------------------------------------------------------------------------
# 4. Assemble, add features, split
# --------------------------------------------------------------------------------------
def _strict_prior_group_aggregates(df: pd.DataFrame) -> pd.DataFrame:
    """Recompute prior_group_{draws,goals,matches,goals_per_match} using strictly-earlier
    kickoff DATE within each (year, group). Same-day matches are treated as simultaneous
    (not available to one another) -> no final-matchday leakage."""
    out = df.copy()
    pgm = pd.Series(0, index=out.index, dtype=int)
    pgd = pd.Series(0, index=out.index, dtype=int)
    pgg = pd.Series(0, index=out.index, dtype=int)
    for _, g in out.groupby("group_uid", sort=False):
        played = g[g["goals_a"].notna() & g["goals_b"].notna()]
        for idx, row in g.iterrows():
            earlier = played[played["kickoff_utc"] < row["kickoff_utc"]]
            n = len(earlier)
            pgm.loc[idx] = n
            pgd.loc[idx] = int((earlier["goals_a"] == earlier["goals_b"]).sum())
            pgg.loc[idx] = int((earlier["goals_a"] + earlier["goals_b"]).sum())
    out["prior_group_matches"] = pgm
    out["prior_group_draws"] = pgd
    out["prior_group_goals"] = pgg
    out["prior_group_goals_per_match"] = (pgg / pgm.replace(0, np.nan)).fillna(0.0)
    return out


def assign_matchday(df: pd.DataFrame) -> pd.Series:
    md = pd.Series(pd.NA, index=df.index, dtype="Int64")
    for (_, _), g in df.groupby(["year", "group"], sort=False):
        order = g.sort_values(["kickoff_utc", "team_a"]).index
        if len(order) == 6:
            md.loc[order] = [1, 1, 2, 2, 3, 3]
        else:
            md.loc[order] = [i // 2 + 1 for i in range(len(order))]
    return md


def main() -> None:
    PROC.mkdir(parents=True, exist_ok=True)
    hist = build_elo_history()

    hist_df = load_historical_groups()
    wc26_df = reconstruct_2026()
    matches = pd.concat([hist_df, wc26_df], ignore_index=True)

    # unmapped-team diagnostics (Elo + confederation)
    all_teams = set(matches["team_a"]).union(matches["team_b"])
    no_elo = sorted(t for t in all_teams if t not in hist)
    no_conf = sorted(t for t in all_teams if t not in CONFED)
    if no_elo:
        print(f"[warn] {len(no_elo)} teams without Elo history: {no_elo}")
    if no_conf:
        print(f"[warn] {len(no_conf)} teams without confederation: {no_conf}")

    # Use authoritative matchday where a source provided it (football-data.org 2026);
    # compute chronologically for the rest (historical rows).
    auto_md = assign_matchday(matches)
    if "matchday" in matches.columns:
        matches["matchday"] = matches["matchday"].fillna(auto_md).astype("Int64")
    else:
        matches["matchday"] = auto_md
    matches["match_id"] = (
        matches["year"].astype(str) + "_" + matches["group"].astype(str) + "_"
        + matches["kickoff_utc"].dt.strftime("%m%d") + "_"
        + matches["team_a"].str.replace(" ", "").str[:3] + matches["team_b"].str.replace(" ", "").str[:3]
    )
    assert matches["match_id"].is_unique, "match_id collision"

    # Elo (time-safe) + deltas
    matches["elo_a"] = [elo_before(hist, t, d) for t, d in zip(matches["team_a"], matches["kickoff_utc"])]
    matches["elo_b"] = [elo_before(hist, t, d) for t, d in zip(matches["team_b"], matches["kickoff_utc"])]

    # host / neutral context
    matches["venue_host_a"] = [int(t in HOSTS.get(y, set())) for t, y in zip(matches["team_a"], matches["year"])]
    matches["venue_host_b"] = [int(t in HOSTS.get(y, set())) for t, y in zip(matches["team_b"], matches["year"])]
    matches["venue_host_advantage"] = matches["venue_host_a"] - matches["venue_host_b"]
    matches["venue_neutral"] = (matches["venue_host_a"] + matches["venue_host_b"] == 0).astype(int)

    # confederation pair
    ca = matches["team_a"].map(lambda t: CONFED.get(t, "OTHER"))
    cb = matches["team_b"].map(lambda t: CONFED.get(t, "OTHER"))
    matches["confed_same"] = (ca == cb).astype(int)
    matches["confed_intercontinental"] = (ca != cb).astype(int)
    matches["confed_a"] = ca
    matches["confed_b"] = cb

    # market features: no real timestamped odds available yet -> explicit missingness
    for c in ["p_a_market", "p_draw_market", "p_b_market", "market_total_goals"]:
        matches[c] = np.nan
    matches["market_is_missing"] = 1

    # FIFA ranking features (release-normalized, time-safe asof join: release_date <= kickoff).
    # tolerance_days=None so the latest available release is always used (dataset ends 2024-09,
    # so 2026 matches use a stale-but-time-safe release; flagged by fifa_is_stale).
    if FIFA_RANKINGS.exists():
        fifa = pd.read_csv(FIFA_RANKINGS, parse_dates=["release_date"])
        fifa = standardize_fifa_release(fifa)
        for team_col, suffix in [("team_a", "_a"), ("team_b", "_b")]:
            matches = asof_join_team_rating(
                matches, fifa, team_col=team_col, date_col="kickoff_utc",
                rating_team_col="team", rating_date_col="release_date",
                rating_cols=["fifa_points_z", "fifa_rank_percentile"],
                tolerance_days=None, suffix=suffix)
        # days between the FIFA release used and kickoff (staleness audit on team_a side)
        rd = pd.to_datetime(matches.get("release_date_a"), utc=True, errors="coerce")
        matches["fifa_age_days"] = (matches["kickoff_utc"] - rd).dt.days
        matches["fifa_is_stale"] = (matches["fifa_age_days"] > 120).astype("Int64")
    else:
        for c in ["fifa_points_z_a", "fifa_points_z_b", "fifa_rank_percentile_a", "fifa_rank_percentile_b"]:
            matches[c] = np.nan

    # feature builders (all pre-match / leakage-safe)
    matches = add_strength_deltas(matches)               # elo_delta, abs_elo_delta

    # Group-state must be scoped to a SINGLE tournament: the group letter "A".."L" is
    # reused every year, so we key group-state on year+letter to avoid accumulating
    # standings across tournaments. The display `group` column stays the letter.
    matches["group_uid"] = matches["year"].astype(str) + "_" + matches["group"].astype(str)
    state_input = matches.copy()
    state_input["group"] = matches["group_uid"]
    state_out = build_pre_match_group_state(state_input)  # points/gd/draws pre (per tournament)
    new_state_cols = [c for c in state_out.columns if c not in matches.columns]
    matches = matches.merge(state_out[["match_id", *new_state_cols]], on="match_id", how="left")

    # Strict-before fix for GROUP-LEVEL aggregates: the two final-matchday matches in a
    # group kick off simultaneously, and with date-only sources same-day matches are not
    # available to each other. build_pre_match_group_state uses processing order for ties,
    # which would let a simultaneous match leak into prior_group_* aggregates. Recompute
    # those aggregates using strictly-earlier kickoff DATE only (conservative, leak-free).
    # Per-team state (points_*_pre, gd_*_pre, ...) is unaffected: teams play once per date.
    matches = _strict_prior_group_aggregates(matches)
    matches = add_schedule_adjusted_state(matches)       # ppg, state deltas
    matches = add_low_block_risk(matches)                # low_block_risk (needs market_total -> default)
    matches = add_travel_fatigue(matches)                # travel_fatigue (defaults)
    matches = add_basic_outcome_columns(matches)         # outcome, is_draw (LABELS, last)

    matches = matches.sort_values(["kickoff_utc", "match_id"]).reset_index(drop=True)
    matches["feature_provenance"] = (
        "elo=martj42_walkforward(<kickoff); group=" + matches["source"]
        + "; market=MISSING; available_at<=kickoff"
    )

    played = matches[matches["goals_a"].notna() & matches["goals_b"].notna()].copy()
    upcoming = matches[matches["goals_a"].isna() | matches["goals_b"].isna()].copy()

    played.to_csv(PROC / "research_modeling_table.csv", index=False)
    upcoming.to_csv(PROC / "forecast_targets_2026.csv", index=False)

    print("\n=== SUMMARY ===")
    print("played rows:", len(played), " upcoming rows:", len(upcoming))
    print("played by year:\n", played.groupby("year").size().to_string())
    print("played by year x outcome (draw rate):")
    dr = played.assign(is_draw=(played["outcome"] == "D").astype(int)).groupby("year")["is_draw"].mean()
    print(dr.round(3).to_string())
    print("2026 played by matchday:\n",
          played[played.year == 2026].groupby("matchday").size().to_string())
    print("upcoming 2026 by matchday:\n", upcoming.groupby("matchday").size().to_string())
    print("columns:", len(played.columns))
    print("wrote:", PROC / "research_modeling_table.csv")


if __name__ == "__main__":
    main()
