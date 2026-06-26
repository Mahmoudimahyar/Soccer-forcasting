"""Deterministic SYNTHETIC tests for the causal rolling player-impact system. No real data, no network.

Covers (one or more tests each):
  1. no future player-appearance leakage          7. position-specific aggregation
  2. no future national-team-appearance leakage    8. deterministic rebuild
  3. no post-match use in a pre-match prior         9. club / international separation
  4. exact-ID linking only                         10. source-hash traceability
  5. substitution-delta direction
  6. unknown-player behavior
"""
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from wcdrawlab.research import player_history as PH  # noqa: E402

# ---- synthetic builders -------------------------------------------------------------------------
H, A = 10, 20  # team ids


def _dt(s):
    return datetime.fromisoformat(s + "T18:00:00+00:00")


def _goal(el, team, detail="Normal Goal"):
    return {"time": {"elapsed": el}, "type": "Goal", "detail": detail, "team": {"id": team}, "player": {"id": 1}}


def _sub(el, team, pin, pout):
    return {"time": {"elapsed": el}, "type": "subst", "team": {"id": team},
            "player": {"id": pin}, "assist": {"id": pout}}


def _xi(team, ids, formation="4-3-3", positions=None):
    positions = positions or {}
    return {"team": {"id": team}, "formation": formation,
            "startXI": [{"player": {"id": pid, "pos": positions.get(pid, "M"), "number": i + 1}}
                        for i, pid in enumerate(ids)],
            "substitutes": []}


def _norm_date(date):
    """Normalize a bare 'YYYY-MM-DD' to a tz-aware kickoff ISO string (provider dates are tz-aware)."""
    return date if "T" in str(date) else f"{date}T18:00:00+00:00"


def _fixture(fid, date, league_id, gh, ga, et_h=None, et_a=None, pen_h=None, pen_a=None):
    score = {"fulltime": {"home": gh, "away": ga},
             "extratime": {"home": et_h, "away": et_a},
             "penalty": {"home": pen_h, "away": pen_a}}
    return {"fixture": {"id": fid, "date": _norm_date(date)},
            "teams": {"home": {"id": H}, "away": {"id": A}},
            "league": {"id": league_id, "season": 2021},
            "score": score, "goals": {"home": gh, "away": ga}}


def _make_match(fid, date, league_id, home_xi, away_xi, goals, subs=None,
                gh=None, ga=None, positions=None, et=None, pen=None):
    """Build (fixture, events, lineups) with regulation score matching the goal events (so it reconciles)."""
    events = list(goals) + list(subs or [])
    rgh = sum(1 for g in goals if g["team"]["id"] == H and (g.get("detail") != "Own Goal_skip"))
    # compute regulation score from goal events using beneficiary credit (team field)
    rgh = sum(1 for g in goals if g["team"]["id"] == H and 0 < g["time"]["elapsed"] <= 90)
    rga = sum(1 for g in goals if g["team"]["id"] == A and 0 < g["time"]["elapsed"] <= 90)
    gh = rgh if gh is None else gh
    ga = rga if ga is None else ga
    et_h, et_a = (et or (None, None))
    pen_h, pen_a = (pen or (None, None))
    fx = _fixture(fid, date, league_id, gh, ga, et_h, et_a, pen_h, pen_a)
    lineups = [_xi(H, home_xi, positions=positions), _xi(A, away_xi, positions=positions)]
    return fx, events, lineups


def _hist_from(matches):
    """matches: list of (fid, date, league_id, home_xi, away_xi, goals, subs). -> PlayerHistory + index."""
    fixtures, events, lineups = {}, {}, {}
    for m in matches:
        fx, ev, ln = _make_match(*m)
        fid = str(m[0])
        fixtures[fid] = fx
        events[fid] = ev
        lineups[fid] = ln
    return PH.build_player_history(fixtures, events, lineups), fixtures, events, lineups


CLUB = 39          # EPL -> club
INTL = 1           # World Cup -> international


# ============================ 1. no future player-appearance leakage ============================
def test_no_future_player_appearance_leakage_club():
    # P1 plays a great match M2 (team wins big) AFTER the target M_target on the same date boundary.
    # Prior at M1 (earliest) must be unknown; prior at M2 must reflect ONLY M1, never M2/M3.
    P1 = 101
    home1 = [P1, 102, 103]
    matches = [
        (1, "2021-01-01", CLUB, home1, [201, 202, 203], [_goal(10, H), _goal(20, H)]),  # H wins 2-0
        (2, "2021-02-01", CLUB, home1, [201, 202, 203], [_goal(10, A)]),                # H loses 0-1
        (3, "2021-03-01", CLUB, home1, [201, 202, 203], [_goal(5, H), _goal(8, H), _goal(9, H)]),  # future blowout
    ]
    hist, fx, _, _ = _hist_from(matches)
    d1 = PH._parse_dt(fx["1"]["fixture"]["date"])
    d2 = PH._parse_dt(fx["2"]["fixture"]["date"])
    p_at_1 = hist.prior(P1, d1, "club")
    p_at_2 = hist.prior(P1, d2, "club")
    assert p_at_1["unknown_player"] is True and p_at_1["prior_appearances"] == 0
    # at M2 only M1 (a 2-0 win) is known: gd should be positive; M3 blowout must NOT inflate it
    assert p_at_2["prior_appearances"] == 1
    assert p_at_2["gd_contribution_per90"] > 0
    # re-querying at M3 includes M1+M2 only (2 apps), never M3 itself
    d3 = PH._parse_dt(fx["3"]["fixture"]["date"])
    p_at_3 = hist.prior(P1, d3, "club")
    assert p_at_3["prior_appearances"] == 2


# ============================ 2. no future national-team-appearance leakage ============================
def test_no_future_national_team_appearance_leakage():
    P1 = 301
    matches = [
        (1, "2021-06-01", INTL, [P1, 302, 303], [401, 402, 403], [_goal(30, H)]),   # win
        (2, "2021-07-01", INTL, [P1, 302, 303], [401, 402, 403], [_goal(30, H), _goal(40, H)]),
    ]
    hist, fx, _, _ = _hist_from(matches)
    d1 = PH._parse_dt(fx["1"]["fixture"]["date"])
    # first national-team match: no prior international history -> unknown
    assert hist.prior(P1, d1, "international")["unknown_player"] is True
    # the SECOND match (future) must not leak into the prior at the first match
    d2 = PH._parse_dt(fx["2"]["fixture"]["date"])
    assert hist.prior(P1, d2, "international")["prior_appearances"] == 1


# ============================ 3. no post-match use in a pre-match prior ============================
def test_no_postmatch_score_in_prematch_prior():
    # Same-DATE later fixture id must NOT be counted (strict-before by date; equal date excluded).
    P1 = 501
    matches = [
        (1, "2021-01-10", CLUB, [P1, 502], [601, 602], [_goal(10, H)]),
        (2, "2021-01-10", CLUB, [P1, 502], [601, 602], [_goal(10, A)]),  # SAME DATE
    ]
    hist, fx, _, _ = _hist_from(matches)
    d = PH._parse_dt(fx["1"]["fixture"]["date"])
    # at the first match's date, NO appearance is strictly-before -> unknown (the same-date M1 is excluded)
    assert hist.prior(P1, d, "club")["unknown_player"] is True


def test_no_postmatch_aggregate_only_uses_on_pitch_window():
    # A player subbed OFF at 60 must not be charged with a goal conceded at 80.
    P_off = 701
    subs = [_sub(60, H, 999, P_off)]
    fx, ev, ln = _make_match(1, "2021-01-01", CLUB, [P_off, 702, 703], [801, 802], [_goal(80, A)], subs)
    apps = PH.appearances_from_fixture(fx, ev, ln, "club")
    p_off_app = [a for a in apps if a.player_id == P_off][0]
    # P_off was on the pitch 0..60 only; the conceded goal at 80 is OUTSIDE the on-pitch window ->
    # the RAW on-pitch goals-against attribution must be 0 (no post-leave leakage). minutes_on == 60.
    assert p_off_app.minutes_on == 60.0
    assert p_off_app.goals_against_on == 0
    assert p_off_app.gd_on == 0
    # the incoming player (999) WAS on at 80 and is charged the conceded goal
    p_in_app = [a for a in apps if a.player_id == 999][0]
    assert p_in_app.goals_against_on == 1


# ============================ 4. exact-ID linking only ============================
def test_exact_id_linking_only_no_name_fuzz():
    # Two DIFFERENT ids that would fuzzy-match by similar slot must remain distinct priors.
    P_a, P_b = 111, 112
    matches = [
        (1, "2021-01-01", CLUB, [P_a, 113, 114], [211, 212], [_goal(10, H), _goal(20, H)]),  # P_a in a win
        (2, "2021-02-01", CLUB, [P_b, 113, 114], [211, 212], [_goal(10, A)]),               # P_b in a loss
    ]
    hist, _, _, _ = _hist_from(matches)
    d = PH._parse_dt("2021-06-06T18:00:00+00:00")
    pa = hist.prior(P_a, d, "club")
    pb = hist.prior(P_b, d, "club")
    # distinct ids -> distinct histories; the win player's gd > the loss player's gd
    assert pa["prior_appearances"] == 1 and pb["prior_appearances"] == 1
    assert pa["gd_contribution_per90"] > pb["gd_contribution_per90"]
    # a never-seen id is its own unknown category, not merged into any existing player
    assert hist.prior(99999, d, "club")["unknown_player"] is True


# ============================ 5. substitution-delta direction ============================
def test_substitution_delta_direction():
    # Build a strong incoming player (P_strong: prior wins) and a weak outgoing player (P_weak: prior losses).
    P_strong, P_weak = 1201, 1202
    matches = [
        (1, "2021-01-01", CLUB, [P_strong, 1, 2], [9, 8], [_goal(10, H), _goal(20, H), _goal(30, H)]),  # big win
        (2, "2021-01-15", CLUB, [P_weak, 3, 4], [9, 8], [_goal(10, A), _goal(20, A), _goal(30, A)]),     # big loss
    ]
    hist, _, _, _ = _hist_from(matches)
    d = PH._parse_dt("2021-06-06T18:00:00+00:00")
    delta = PH.substitution_delta(P_strong, P_weak, d, "club", hist)
    # incoming(strong) - outgoing(weak): strong has higher gd prior -> positive delta
    assert delta["gd_delta_per90"] > 0
    assert delta["in_player_id"] == P_strong and delta["out_player_id"] == P_weak
    # swapping direction flips the sign
    rev = PH.substitution_delta(P_weak, P_strong, d, "club", hist)
    assert abs(rev["gd_delta_per90"] + delta["gd_delta_per90"]) < 1e-9


# ============================ 6. unknown-player behavior ============================
def test_unknown_player_returns_shrinkage_prior_not_future():
    hist, _, _, _ = _hist_from([
        (1, "2021-01-01", CLUB, [1, 2, 3], [4, 5, 6], [_goal(10, H)]),
    ])
    d = PH._parse_dt("2021-06-06T18:00:00+00:00")
    pr = hist.prior(424242, d, "club")  # id never appears
    assert pr["unknown_player"] is True and pr["insufficient_history"] is True
    assert pr["prior_appearances"] == 0 and pr["prior_minutes"] == 0.0
    assert pr["exposure"] == 0.0 and pr["uncertainty"] == 1.0
    assert pr["position_state"] == "unknown"


def test_unknown_player_in_aggregate_lowers_completeness():
    hist, _, _, _ = _hist_from([
        (1, "2021-01-01", CLUB, [1, 2, 3], [4, 5, 6], [_goal(10, H)]),
        (2, "2021-02-01", CLUB, [1, 2, 3], [4, 5, 6], [_goal(10, H)]),
    ])
    d = PH._parse_dt("2021-03-01T18:00:00+00:00")
    # XI = two known (1,2) + one unknown (777)
    agg = PH.lineup_aggregate([1, 2, 777], [], d, "club", hist)
    assert agg["n_unknown_players"] == 1
    assert abs(agg["history_completeness"] - (2 / 3)) < 1e-6  # rounded to 6 dp in the aggregate


# ============================ 7. position-specific aggregation ============================
def test_position_specific_aggregation_and_state():
    # A player who always starts as defender 'D' should get position_state 'D'.
    P_def = 1501
    pos = {P_def: "D"}
    matches = [
        (1, "2021-01-01", CLUB, [P_def, 1, 2], [4, 5, 6], [_goal(10, H)], None, None, None, pos),
        (2, "2021-02-01", CLUB, [P_def, 1, 2], [4, 5, 6], [_goal(10, H)], None, None, None, pos),
    ]
    hist, _, _, _ = _hist_from(matches)
    d = PH._parse_dt("2021-03-01T18:00:00+00:00")
    assert hist.prior(P_def, d, "club")["position_state"] == "D"
    # aggregate exposes offensive/defensive balance separately
    agg = PH.lineup_aggregate([P_def, 1, 2], [], d, "club", hist)
    assert "xi_off_balance_per90" in agg and "xi_def_balance_per90" in agg
    assert agg["xi_size"] == 3


def test_top3_aggregation_uses_strongest():
    # 4 XI players with different priors; top3 mean must exceed the full-XI mean if one is weak.
    strong = [2001, 2002, 2003]
    weak = 2004
    matches = []
    fid = 1
    # give the 3 strong players a winning history, the weak player a losing history
    for d_i, pid_group, goals in [("2021-01-01", strong, [_goal(10, H), _goal(20, H)]),
                                  ("2021-01-05", [weak], [_goal(10, A), _goal(20, A)])]:
        matches.append((fid, d_i, CLUB, pid_group + [9001, 9002, 9003][:3 - len(pid_group) + 3][:0] + [9001, 9002],
                        [8001, 8002, 8003], goals))
        fid += 1
    hist, _, _, _ = _hist_from(matches)
    d = PH._parse_dt("2021-06-06T18:00:00+00:00")
    agg = PH.lineup_aggregate([2001, 2002, 2003, weak], [], d, "club", hist)
    assert agg["xi_top3_prior_gd90"] >= agg["xi_mean_prior_gd90"]


# ============================ 8. deterministic rebuild ============================
def test_deterministic_rebuild_identical_priors_and_hashes():
    spec = [
        (1, "2021-01-01", CLUB, [1, 2, 3], [4, 5, 6], [_goal(10, H)]),
        (2, "2021-02-01", CLUB, [1, 2, 3], [4, 5, 6], [_goal(10, H), _goal(20, A)]),
    ]
    h1, _, _, _ = _hist_from(spec)
    h2, _, _, _ = _hist_from(spec)
    d = PH._parse_dt("2021-03-01T18:00:00+00:00")
    a = h1.prior(1, d, "club")
    b = h2.prior(1, d, "club")
    assert a == b  # full dict equality incl. source_hashes and rounded floats


# ============================ 9. club / international separation ============================
def test_club_and_international_never_pooled():
    P1 = 3001
    matches = [
        (1, "2021-01-01", CLUB, [P1, 2, 3], [4, 5, 6], [_goal(10, H), _goal(20, H)]),   # club win
        (2, "2021-02-01", INTL, [P1, 2, 3], [4, 5, 6], [_goal(10, A), _goal(20, A)]),    # intl loss
    ]
    hist, _, _, _ = _hist_from(matches)
    d = PH._parse_dt("2021-06-06T18:00:00+00:00")
    club_p = hist.prior(P1, d, "club")
    intl_p = hist.prior(P1, d, "international")
    # each plane sees ONLY its own appearance
    assert club_p["prior_appearances"] == 1 and intl_p["prior_appearances"] == 1
    # club is a win (gd>0), international is a loss (gd<0) -> they must differ and not be pooled
    assert club_p["gd_contribution_per90"] > 0 > intl_p["gd_contribution_per90"]


def test_intl_prior_unaffected_by_club_history():
    P1 = 3101
    matches = [
        (1, "2021-01-01", CLUB, [P1, 2, 3], [4, 5, 6], [_goal(10, H), _goal(20, H), _goal(30, H)]),  # club blowout win
    ]
    hist, _, _, _ = _hist_from(matches)
    d = PH._parse_dt("2021-06-06T18:00:00+00:00")
    # P1 has NO international history -> unknown on the international plane despite a club blowout
    assert hist.prior(P1, d, "international")["unknown_player"] is True


# ============================ 10. source-hash traceability ============================
def test_source_hash_present_and_traces_contributing_appearances():
    matches = [
        (1, "2021-01-01", CLUB, [1, 2, 3], [4, 5, 6], [_goal(10, H)]),
        (2, "2021-02-01", CLUB, [1, 2, 3], [4, 5, 6], [_goal(10, H)]),
    ]
    hist, fx, ev, ln = _hist_from(matches)
    d = PH._parse_dt("2021-03-01T18:00:00+00:00")
    pr = hist.prior(1, d, "club")
    # one hash per contributing (distinct) appearance source; both earlier matches contribute
    assert len(pr["source_hashes"]) == 2
    # every hash recomputes deterministically from the same raw events+lineups
    for fid in ("1", "2"):
        recomputed = PH.source_hash({"fid": fid, "events": ev[fid], "lineups": ln[fid]})
        assert recomputed in pr["source_hashes"]
    assert pr["prior_model_version"] == PH.PRIOR_MODEL_VERSION


def test_appearance_carries_parser_version_and_hash():
    fx, ev, ln = _make_match(1, "2021-01-01", CLUB, [1, 2, 3], [4, 5, 6], [_goal(10, H)])
    apps = PH.appearances_from_fixture(fx, ev, ln, "club")
    assert apps, "expected appearances from a reconciling fixture"
    for ap in apps:
        assert ap.parser_version == PH.PARSER_VERSION
        assert ap.source_hash and isinstance(ap.source_hash, str)


# ============================ extra: regulation/ET separation + reconciliation gating ===========
def test_extra_time_goal_excluded_from_contribution():
    # ET goal (elapsed 105) must not enter the player's on-pitch gd; official ft score = regulation only.
    P1 = 4001
    fx, ev, ln = _make_match(
        1, "2021-01-01", CLUB, [P1, 2, 3], [4, 5, 6],
        [_goal(40, H), _goal(105, H)], gh=1, ga=0, et=(2, 0))
    apps = PH.appearances_from_fixture(fx, ev, ln, "club")
    p1_app = [a for a in apps if a.player_id == P1][0]
    assert p1_app.goals_for_on == 1  # only the 40' regulation goal, not the 105' ET goal


def test_unreconciled_fixture_yields_no_appearances():
    # official ft says 5-0 but events show 1-0 -> mismatch -> excluded (no trust in attribution)
    fx, ev, ln = _make_match(1, "2021-01-01", CLUB, [1, 2, 3], [4, 5, 6], [_goal(10, H)], gh=5, ga=0)
    assert PH.appearances_from_fixture(fx, ev, ln, "club") == []
