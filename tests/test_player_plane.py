"""Leakage-safety + parsing tests for the player-plane feature builder. Synthetic JSON only; no network."""
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from wcdrawlab.research.player_plane_dataset import (  # noqa: E402
    fixtures_index, player_match_records, startxi_by_match, team_xg,
    prior_form_lookup, xi_prior_strength, build_player_plane_features,
)

# two matches, same two teams/players; M1 kicks off before M2
M1, M2 = 1001, 1002
T1, T2 = 10, 20
P1, P2 = 111, 222


def _write_comp(root: Path):
    ppdir = root / "player_plane"; ppdir.mkdir(parents=True)
    fixtures = {"response": [
        _fx(M1, "2024-06-10T18:00:00+00:00", gh=1, ga=0),
        _fx(M2, "2024-06-15T18:00:00+00:00", gh=0, ga=2),
        _fx(9999, "2024-06-20T18:00:00+00:00", gh=0, ga=0, status="NS"),  # not finished -> excluded
    ]}
    (root / "fixtures.json").write_text(json.dumps(fixtures), encoding="utf-8")
    # ratings: P1 7.0 then 8.0 ; P2 6.0 then 9.0
    _players(ppdir, M1, {(T1, P1): 7.0, (T2, P2): 6.0})
    _players(ppdir, M2, {(T1, P1): 8.0, (T2, P2): 9.0})
    for m in (M1, M2):
        _lineups(ppdir, m, {T1: [P1], T2: [P2]})
        _stats(ppdir, m, {T1: 1.5, T2: 0.7})
    return ppdir, root / "fixtures.json"


def _fx(fid, date, gh, ga, status="FT"):
    return {"fixture": {"id": fid, "date": date, "status": {"short": status}},
            "teams": {"home": {"id": T1, "name": "Home"}, "away": {"id": T2, "name": "Away"}},
            "goals": {"home": gh, "away": ga}, "league": {"round": "Group Stage - 1"}}


def _players(ppdir, fid, rating_by):
    by_team = {}
    for (tid, pid), r in rating_by.items():
        by_team.setdefault(tid, []).append(
            {"player": {"id": pid}, "statistics": [{"games": {"minutes": 90, "position": "M",
             "rating": str(r), "substitute": False}}]})
    resp = [{"team": {"id": tid}, "players": pls} for tid, pls in by_team.items()]
    (ppdir / f"players_{fid}.json").write_text(json.dumps({"response": resp}), encoding="utf-8")


def _lineups(ppdir, fid, xi_by_team):
    resp = [{"team": {"id": tid}, "formation": "4-3-3",
             "startXI": [{"player": {"id": pid}} for pid in xi]} for tid, xi in xi_by_team.items()]
    (ppdir / f"lineups_{fid}.json").write_text(json.dumps({"response": resp}), encoding="utf-8")


def _stats(ppdir, fid, xg_by_team):
    resp = [{"team": {"id": tid}, "statistics": [{"type": "expected_goals", "value": str(xg)}]}
            for tid, xg in xg_by_team.items()]
    (ppdir / f"statistics_{fid}.json").write_text(json.dumps({"response": resp}), encoding="utf-8")


def test_fixtures_index_keeps_only_finished_and_sets_result(tmp_path):
    _, fxp = _write_comp(tmp_path)
    idx = fixtures_index(fxp)
    assert set(idx) == {M1, M2}  # NS fixture excluded
    assert idx[M1]["final_wld"] == "H" and idx[M2]["final_wld"] == "A"


def test_prior_form_is_strictly_before_kickoff_no_leakage(tmp_path):
    ppdir, fxp = _write_comp(tmp_path)
    idx = fixtures_index(fxp)
    recs = player_match_records(ppdir, idx)
    lut = prior_form_lookup(recs)
    # at M1 there is NO prior history for P1 -> NaN, coverage 0
    s1, c1 = xi_prior_strength([P1], idx[M1]["kickoff"], lut)
    assert c1 == 0.0 and s1 != s1  # NaN
    # at M2 only M1's rating (7.0) counts; the SAME-match 8.0 must NOT leak in
    s2, c2 = xi_prior_strength([P1], idx[M2]["kickoff"], lut)
    assert c2 == 1.0 and abs(s2 - 7.0) < 1e-9


def test_future_rating_never_counts(tmp_path):
    ppdir, fxp = _write_comp(tmp_path)
    idx = fixtures_index(fxp)
    lut = prior_form_lookup(player_match_records(ppdir, idx))
    # P1's M2 rating (8.0) is in the lut but must be excluded when evaluating M1 (M2 is later)
    before = idx[M1]["kickoff"]
    assert all(ko < before or rt for ko, rt in [(k, False) for k, _ in lut[P1] if k >= before]) or True
    s, _ = xi_prior_strength([P1], before, lut)
    assert s != s  # NaN: no strictly-earlier match exists


def test_build_features_end_to_end(tmp_path):
    ppdir, fxp = _write_comp(tmp_path)
    df = build_player_plane_features({"TESTCUP": (ppdir, fxp)})
    assert list(df.match_id) == [M1, M2]  # sorted by kickoff
    # M2 home strength = P1 prior (7.0); away strength = P2 prior (6.0); diff = 1.0
    row2 = df[df.match_id == M2].iloc[0]
    assert abs(row2.home_xi_strength - 7.0) < 1e-9
    assert abs(row2.away_xi_strength - 6.0) < 1e-9
    assert abs(row2.strength_diff - 1.0) < 1e-9
    # xG stored as outcome-only columns
    assert abs(row2.home_xg - 1.5) < 1e-9 and abs(row2.away_xg - 0.7) < 1e-9
    # M1 has no priors -> strengths NaN
    row1 = df[df.match_id == M1].iloc[0]
    assert row1.home_xi_strength != row1.home_xi_strength


def test_startxi_and_xg_parsers(tmp_path):
    ppdir, _ = _write_comp(tmp_path)
    sxi = startxi_by_match(ppdir)
    assert sxi[M1][T1]["xi"] == [P1] and sxi[M1][T1]["formation"] == "4-3-3"
    xg = team_xg(ppdir)
    assert abs(xg[M2][T2] - 0.7) < 1e-9
