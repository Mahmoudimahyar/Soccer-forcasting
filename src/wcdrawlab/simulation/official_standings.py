"""Official 2026 FIFA World Cup standings + tiebreak engine (Article 13 ordering).

This is the PRODUCTION 2026 simulator. The legacy `standings.py` / `group_simulator.py`
(simplified order: overall GD before head-to-head) are retained only as a baseline and must NOT
be used for 2026 forecasts.

Within-group order when teams are tied on points (official 2026, head-to-head BEFORE overall GD;
drawing of lots removed):
  1. points (group key)
  2. head-to-head points (among the tied teams only)
  3. head-to-head goal difference (among the tied teams only)
  4. head-to-head goals scored (among the tied teams only)
  5. overall goal difference
  6. overall goals scored
  7. team conduct score (fewer cards is better)
  8. FIFA World Ranking
FIFA re-applies the head-to-head steps to any subset that remains tied after a partial
separation (handled here by recursion).

Best third-placed teams (across groups, no head-to-head): points, GD, goals, conduct, FIFA rank.
Source: notes/research / data/reference/tiebreak_rules_2026.yaml.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from wcdrawlab.evaluation import normalize_probs
from wcdrawlab.simulation.group_simulator import outcome_to_score


@dataclass
class OfficialGroupTable:
    group: str
    matches: list = field(default_factory=list)            # (a, b, ga, gb)
    fifa_rank: dict = field(default_factory=dict)           # team -> int (lower better)
    conduct: dict = field(default_factory=dict)             # team -> score (higher better = fewer cards)
    _teams: set = field(default_factory=set)

    def ensure(self, team: str, fifa_rank: int = 999):
        self._teams.add(team)
        self.fifa_rank.setdefault(team, fifa_rank)
        self.conduct.setdefault(team, 0)

    def add_result(self, a: str, b: str, ga: int, gb: int):
        self.ensure(a); self.ensure(b)
        self.matches.append((a, b, int(ga), int(gb)))

    def set_conduct(self, team: str, score: float):
        self.ensure(team); self.conduct[team] = score

    # ---- aggregate stats ----
    def _overall(self) -> dict:
        s = {t: {"points": 0, "gf": 0, "ga": 0} for t in self._teams}
        for a, b, ga, gb in self.matches:
            s[a]["gf"] += ga; s[a]["ga"] += gb
            s[b]["gf"] += gb; s[b]["ga"] += ga
            if ga > gb:
                s[a]["points"] += 3
            elif ga == gb:
                s[a]["points"] += 1; s[b]["points"] += 1
            else:
                s[b]["points"] += 3
        for t in s:
            s[t]["gd"] = s[t]["gf"] - s[t]["ga"]
            s[t]["conduct"] = self.conduct.get(t, 0)
            s[t]["fifa_rank"] = self.fifa_rank.get(t, 999)
        return s

    def _h2h(self, subset: list) -> dict:
        sub = set(subset)
        h = {t: {"points": 0, "gf": 0, "ga": 0} for t in subset}
        for a, b, ga, gb in self.matches:
            if a in sub and b in sub:
                h[a]["gf"] += ga; h[a]["ga"] += gb
                h[b]["gf"] += gb; h[b]["ga"] += ga
                if ga > gb:
                    h[a]["points"] += 3
                elif ga == gb:
                    h[a]["points"] += 1; h[b]["points"] += 1
                else:
                    h[b]["points"] += 3
        for t in h:
            h[t]["gd"] = h[t]["gf"] - h[t]["ga"]
        return h

    def _order_tied(self, teams: list, overall: dict) -> list:
        """Order teams that are equal on points, per the official recursive H2H procedure."""
        if len(teams) == 1:
            return teams
        h = self._h2h(teams)
        ordered = sorted(teams, key=lambda t: (-h[t]["points"], -h[t]["gd"], -h[t]["gf"]))
        # partition into blocks equal on (h2h points, gd, gf)
        blocks, cur = [], [ordered[0]]
        for t in ordered[1:]:
            p = cur[-1]
            same = (h[t]["points"], h[t]["gd"], h[t]["gf"]) == (h[p]["points"], h[p]["gd"], h[p]["gf"])
            if same:
                cur.append(t)
            else:
                blocks.append(cur); cur = [t]
        blocks.append(cur)
        if len(blocks) == 1:
            # head-to-head separated nobody -> overall criteria for the whole tied set
            return sorted(teams, key=lambda t: (-overall[t]["gd"], -overall[t]["gf"],
                                                -overall[t]["conduct"], overall[t]["fifa_rank"], t))
        # partial separation -> re-apply procedure to each still-tied block
        out = []
        for block in blocks:
            out.extend(self._order_tied(block, overall) if len(block) > 1 else block)
        return out

    def ranked(self) -> list:
        """Return team names ordered 1st..last per official 2026 rules."""
        overall = self._overall()
        teams = sorted(self._teams, key=lambda t: -overall[t]["points"])
        out, cur = [], [teams[0]] if teams else []
        for t in teams[1:]:
            if overall[t]["points"] == overall[cur[-1]]["points"]:
                cur.append(t)
            else:
                out.extend(self._order_tied(cur, overall)); cur = [t]
        if cur:
            out.extend(self._order_tied(cur, overall))
        return out

    def standings_frame(self) -> pd.DataFrame:
        overall = self._overall()
        order = self.ranked()
        return pd.DataFrame([{"group": self.group, "rank": i + 1, "team": t, **overall[t]}
                             for i, t in enumerate(order)])


def rank_third_place_official(third_rows: pd.DataFrame) -> pd.DataFrame:
    """Rank third-placed teams across groups (no head-to-head): points, GD, goals, conduct, FIFA rank."""
    if third_rows.empty:
        return third_rows
    df = third_rows.copy()
    if "conduct" not in df:
        df["conduct"] = 0
    if "fifa_rank" not in df:
        df["fifa_rank"] = 999
    return df.sort_values(["points", "gd", "gf", "conduct", "fifa_rank", "team"],
                          ascending=[False, False, False, False, True, True]).reset_index(drop=True)


def simulate_group_stage_official(fixtures: pd.DataFrame, probs: np.ndarray, n_sims: int = 10000,
                                  third_place_slots: int = 8, seed: int = 42) -> pd.DataFrame:
    """Monte-Carlo group stage with the OFFICIAL 2026 tiebreak engine. Drop-in for the legacy
    simulate_group_stage: returns [team, p_advance, p_first, p_second, p_third_advance].
    Played fixtures (non-NaN goals) are used as-is -> deterministic when all played."""
    rng = np.random.default_rng(seed)
    fixtures = fixtures.reset_index(drop=True).copy()
    probs = normalize_probs(probs)
    teams = sorted(set(fixtures["team_a"]) | set(fixtures["team_b"]))
    adv = {t: 0 for t in teams}; first = {t: 0 for t in teams}
    second = {t: 0 for t in teams}; third_adv = {t: 0 for t in teams}
    groups = sorted(fixtures["group"].dropna().unique())

    for _ in range(n_sims):
        tables = {g: OfficialGroupTable(g) for g in groups}
        for i, r in fixtures.iterrows():
            tbl = tables[r["group"]]
            a, b = r["team_a"], r["team_b"]
            fra = int(r.get("fifa_rank_a", 999)) if pd.notna(r.get("fifa_rank_a", 999)) else 999
            frb = int(r.get("fifa_rank_b", 999)) if pd.notna(r.get("fifa_rank_b", 999)) else 999
            tbl.ensure(a, fra); tbl.ensure(b, frb)
            if pd.notna(r.get("goals_a", np.nan)) and pd.notna(r.get("goals_b", np.nan)):
                ga, gb = int(r["goals_a"]), int(r["goals_b"])
            else:
                ga, gb = outcome_to_score(rng.choice(["A", "D", "B"], p=probs[i]), rng)
            tbl.add_result(a, b, ga, gb)

        third_rows = []
        for g, tbl in tables.items():
            order = tbl.ranked()
            overall = tbl._overall()
            if len(order) >= 1:
                first[order[0]] += 1; adv[order[0]] += 1
            if len(order) >= 2:
                second[order[1]] += 1; adv[order[1]] += 1
            if len(order) >= 3:
                t3 = order[2]
                third_rows.append({"group": g, "team": t3, "points": overall[t3]["points"],
                                   "gd": overall[t3]["gd"], "gf": overall[t3]["gf"],
                                   "conduct": overall[t3]["conduct"], "fifa_rank": overall[t3]["fifa_rank"]})
        ranked_thirds = rank_third_place_official(pd.DataFrame(third_rows))
        for _, row in ranked_thirds.head(third_place_slots).iterrows():
            third_adv[row["team"]] += 1; adv[row["team"]] += 1

    out = pd.DataFrame({"team": teams})
    out["p_advance"] = out["team"].map(adv) / n_sims
    out["p_first"] = out["team"].map(first) / n_sims
    out["p_second"] = out["team"].map(second) / n_sims
    out["p_third_advance"] = out["team"].map(third_adv) / n_sims
    return out.sort_values("p_advance", ascending=False).reset_index(drop=True)


def force_match_outcome_official(fixtures: pd.DataFrame, match_id, outcome: str) -> pd.DataFrame:
    """Set one match to A/D/B with a representative scoreline (1-0 / 1-1 / 0-1)."""
    out = fixtures.copy()
    idx = out.index[out["match_id"] == match_id]
    if len(idx) != 1:
        raise ValueError(f"match_id {match_id} not found uniquely")
    ga, gb = {"A": (1, 0), "D": (1, 1), "B": (0, 1)}[outcome]
    out.loc[idx, "goals_a"] = ga
    out.loc[idx, "goals_b"] = gb
    return out


def match_advance_utilities_official(fixtures, probs, match_id, team_a, team_b,
                                     n_sims=5000, third_place_slots=8, seed=42) -> dict:
    """Tier-3 draw-utility / must-win-pressure features, computed from the OFFICIAL engine.
    Replaces wcdrawlab.simulation.utility.match_advance_utilities (legacy, simplified tiebreak)."""
    res = {}
    for outcome in ["A", "D", "B"]:
        forced = force_match_outcome_official(fixtures, match_id, outcome)
        sim = simulate_group_stage_official(forced, probs, n_sims=n_sims,
                                            third_place_slots=third_place_slots, seed=seed)
        mp = dict(zip(sim["team"], sim["p_advance"]))
        res[outcome] = {team_a: mp.get(team_a, 0.0), team_b: mp.get(team_b, 0.0)}
    a_win, a_draw, a_loss = res["A"][team_a], res["D"][team_a], res["B"][team_a]
    b_win, b_draw, b_loss = res["B"][team_b], res["D"][team_b], res["A"][team_b]
    du_a, du_b = a_draw - a_loss, b_draw - b_loss
    return {
        "p_adv_a_if_win": a_win, "p_adv_a_if_draw": a_draw, "p_adv_a_if_loss": a_loss,
        "p_adv_b_if_win": b_win, "p_adv_b_if_draw": b_draw, "p_adv_b_if_loss": b_loss,
        "draw_utility_a": du_a, "draw_utility_b": du_b, "mutual_draw_utility": min(du_a, du_b),
        "must_win_pressure_a": a_win - a_draw, "must_win_pressure_b": b_win - b_draw,
        "must_win_pressure_max": max(a_win - a_draw, b_win - b_draw),
    }
