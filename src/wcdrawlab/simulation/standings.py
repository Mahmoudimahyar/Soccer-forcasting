from __future__ import annotations

from dataclasses import dataclass, field
import pandas as pd


@dataclass
class TeamStanding:
    team: str
    points: int = 0
    gf: int = 0
    ga: int = 0
    fairplay: int = 0
    fifa_rank: int = 999
    # head-to-head details can be layered in if needed.

    @property
    def gd(self) -> int:
        return self.gf - self.ga

    def record(self, gf: int, ga: int):
        self.gf += gf
        self.ga += ga
        if gf > ga:
            self.points += 3
        elif gf == ga:
            self.points += 1


@dataclass
class GroupTable:
    group: str
    teams: dict[str, TeamStanding] = field(default_factory=dict)

    def ensure(self, team: str, fifa_rank: int = 999):
        if team not in self.teams:
            self.teams[team] = TeamStanding(team=team, fifa_rank=fifa_rank)

    def add_result(self, team_a: str, team_b: str, goals_a: int, goals_b: int):
        self.ensure(team_a)
        self.ensure(team_b)
        self.teams[team_a].record(goals_a, goals_b)
        self.teams[team_b].record(goals_b, goals_a)

    def dataframe(self) -> pd.DataFrame:
        rows = []
        for s in self.teams.values():
            rows.append({
                "group": self.group,
                "team": s.team,
                "points": s.points,
                "gd": s.gd,
                "gf": s.gf,
                "ga": s.ga,
                "fairplay": s.fairplay,
                "fifa_rank": s.fifa_rank,
            })
        df = pd.DataFrame(rows)
        if df.empty:
            return df
        # Simplified 2026-style ordering fallback. Real engine should add H2H before overall GD.
        return df.sort_values(["points", "gd", "gf", "fairplay", "fifa_rank"], ascending=[False, False, False, False, True]).reset_index(drop=True)


def rank_third_place_teams(third_rows: pd.DataFrame) -> pd.DataFrame:
    if third_rows.empty:
        return third_rows
    return third_rows.sort_values(["points", "gd", "gf", "fairplay", "fifa_rank"], ascending=[False, False, False, False, True]).reset_index(drop=True)
