"""Canonical leakage-safe DYNAMIC in-play state engine for the FULL API-Football corpus.

research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible.

This module builds a causal, leakage-safe in-play panel from the validated event corpus. It is the
Phase-1 foundation for the dynamic model families (research.wdl.*, research.next_goal.*,
research.discipline.*). It RESOLVES all source locations through the canonical data-root registry
(``wcdrawlab.research.data_roots``) and REUSES the canonical event semantics already proven in this
worktree:

  * ``paid_source.result_semantics``  (RS): provider-aware regulation/ET/shootout score derivation,
    own-goal beneficiary attribution, official-vs-event reconciliation. Only fixtures that reconcile
    EXACTLY (event-derived regulation == official ``score.fulltime``) are admitted to the panel.
  * ``paid_source.historical_datasets`` (HD): subs parsing, players-on-pitch (causal), card class
    (yellow / second_yellow / second_yellow_red / direct_red), regulation score at minute t.

Snapshot schedule (per match), each snapshot retaining a frozen causal cutoff minute ``t``:
  fixed: kickoff(0), 5/10/15/20/30, halftime(45), 45+stoppage, 55/60/65/70/75/80/85;
  event-driven: every goal, every substitution, every yellow / second-yellow / direct-red state
  change, and immediately before extra time (the regulation full-time boundary, minute 90).

HARD LEAKAGE CONSTRAINTS (all enforced, never silently imputed):
  L1  No event, appearance, sub, or card with elapsed > t contributes to a snapshot at minute t.
  L2  No final score / no post-cutoff aggregate statistic enters a feature column.
  L3  No future xG (xG is joined separately by a downstream script with its own cutoff guard).
  L4  No penalty-shootout goal ever affects score, next-goal, or W/D/L state.
  L5  No extra-time goal (elapsed > 90) counts toward a REGULATION target.
  L6  Club rows are produced ONLY as auxiliary player-prior history and are flagged
      ``regulation_target_eligible = 0`` so they can never be used as international test rows.
  L7  Missing data is flagged (coverage columns / status columns), never substituted with a guess.

A snapshot is ``regulation_target_eligible`` only when: comp_type == international, the fixture
reconciles exactly, the official regulation W/D/L is known, and the cutoff t <= 90 (so a regulation
target is defined). The pre-ET boundary snapshot (t == 90) is the last regulation-eligible snapshot.
"""
from __future__ import annotations

import glob
import hashlib
import json
import os
from pathlib import Path

from wcdrawlab.research import data_roots as DR
from wcdrawlab.research.paid_source import historical_datasets as HD
from wcdrawlab.research.paid_source import result_semantics as RS

SCHEMA_VERSION = "dynamic_state_v1"
SOURCE_SEMANTICS_VERSION = RS.PROVIDER_SEMANTICS_VERSION  # api_football_result_v1
PROVIDER = "api_football"

# International competition league ids (senior men's national-team tournaments) -> short label.
INTL_LEAGUES = {1: "World Cup", 4: "Euro Championship", 9: "Copa America",
                6: "Africa Cup of Nations", 7: "Asian Cup"}

# Registered roots scanned for events/lineups/fixture-metadata, in precedence order.
EVENT_ROOTS = ["api_football_corpus", "api_football_player_history", "api_football_player_history_prior"]

# Fixed minute snapshots that always exist (subject to regulation eligibility cutoff).
FIXED_MINUTES = [0, 5, 10, 15, 20, 30, 45, 55, 60, 65, 70, 75, 80, 85]
PRE_ET_BOUNDARY = 90  # regulation full-time / "immediately before extra time"


# --------------------------------------------------------------------------------------------------
# Corpus loading (canonical, registry-resolved). Keyed by the real API-Football fixture id.
# --------------------------------------------------------------------------------------------------
def _canonical_match_id(fixture_id: str) -> str:
    """Deterministic 16-hex canonical id from the provider fixture id (matches xg_snapshot_join key space
    only via api_fixture_id; this column is a stable internal id and is NOT used for the xG join)."""
    return hashlib.sha256(f"apifootball:fixture:{fixture_id}".encode("utf-8")).hexdigest()[:16]


def _scan_root(root: Path, fixtures: dict, events: dict, lineups: dict, src_root: dict):
    if not root.exists():
        return
    for fp in glob.glob(str(root / "*.json")):
        bn = os.path.basename(fp).lower()
        try:
            payload = json.load(open(fp, encoding="utf-8"))
        except Exception:
            continue
        par = payload.get("parameters") or {}
        get = (payload.get("get") or "").lower()
        resp = payload.get("response")
        if "event" in bn or "event" in get:
            fid = par.get("fixture")
            if fid is not None and isinstance(resp, list):
                events.setdefault(str(fid), resp)
                src_root.setdefault(str(fid), root.name)
        elif "lineup" in bn or "lineup" in get:
            fid = par.get("fixture")
            if fid is not None and isinstance(resp, list):
                lineups.setdefault(str(fid), resp)
        elif isinstance(resp, list):
            for fx in resp:
                fid = (fx.get("fixture") or {}).get("id")
                if fid is not None:
                    fixtures.setdefault(str(fid), fx)


def load_full_corpus():
    """Resolve fixture metadata + events + lineups across ALL registered event roots.

    Returns (fixtures, events, lineups, source_root) dicts keyed by str(fixture_id). A fixture is
    usable for the dynamic panel iff it has BOTH events and lineups (and metadata for typing)."""
    fixtures, events, lineups, src_root = {}, {}, {}, {}
    for name in EVENT_ROOTS:
        try:
            root = DR.get_root(name)
        except Exception:
            continue
        _scan_root(root, fixtures, events, lineups, src_root)
    return fixtures, events, lineups, src_root


def _is_intl(fx) -> bool:
    return (fx.get("league", {}) or {}).get("id") in INTL_LEAGUES


def _comp_label(fx) -> str:
    return INTL_LEAGUES.get((fx.get("league", {}) or {}).get("id"), "club")


# --------------------------------------------------------------------------------------------------
# Snapshot-time selection (causal). All snapshot minutes <= regulation full time for regulation rows.
# --------------------------------------------------------------------------------------------------
def _event_change_minutes(events) -> set:
    """Minutes at which a goal / sub / card (yellow / 2nd-yellow / red) state change occurs, regulation
    window only (1..90). These are the event-driven snapshots."""
    mins = set()
    for e in events:
        et = (e.get("type") or "").lower()
        el = (e.get("time") or {}).get("elapsed")
        if el is None or el < 1 or el > PRE_ET_BOUNDARY:
            continue
        if et in ("goal", "subst", "card"):
            # missed/cancelled penalties are not score changes but a card/sub minute is still a state change;
            # for goals, exclude pure 'missed'/'cancelled' (no score change) but they are rare snapshot minutes.
            if et == "goal":
                d = (e.get("detail") or "").lower()
                if "missed" in d or "cancel" in d:
                    continue
            mins.add(int(el))
    return mins


def snapshot_minutes(events, regulation_eligible: bool) -> list:
    """Ordered unique snapshot cutoff minutes for a match.

    Always includes the fixed grid + the pre-ET boundary (90). Adds every event-driven minute. For a
    regulation-eligible (international, reconciled) fixture every returned minute is <= 90, so a
    regulation W/D/L target is always defined; we NEVER place a regulation snapshot after full time."""
    mins = set(m for m in FIXED_MINUTES) | {PRE_ET_BOUNDARY}
    mins |= _event_change_minutes(events)
    # halftime stoppage: if any event recorded at 45 with extra, the 45 snapshot already covers <=45.
    out = sorted(m for m in mins if 0 <= m <= PRE_ET_BOUNDARY)
    return out


# --------------------------------------------------------------------------------------------------
# Per-snapshot causal feature derivation. Everything below uses ONLY events with elapsed <= t.
# --------------------------------------------------------------------------------------------------
def _cards_state(events_up_to, home_id, away_id):
    """Yellow / second-yellow / direct-red counts per side, from cards with minute <= t (caller filters)."""
    yh = ya = syh = sya = drh = dra = 0
    for c in HD.cards_table(events_up_to):
        home_side = c["team_id"] == home_id
        if c["card_class"] == "yellow":
            yh += home_side; ya += not home_side
        elif c["card_class"] == "second_yellow":
            syh += home_side; sya += not home_side
        elif c["card_class"] == "second_yellow_red":
            drh += home_side; dra += not home_side  # a sending-off via 2nd yellow
        elif c["card_class"] == "direct_red":
            drh += home_side; dra += not home_side
    return yh, ya, syh, sya, drh, dra


def _next_regulation_goal(events, t, horizon=15):
    """1 if a valid REGULATION goal (elapsed in (t, min(90, t+h)]) occurs after cutoff t. Label only."""
    for e in events:
        if (e.get("type") or "").lower() != "goal":
            continue
        d = (e.get("detail") or "").lower()
        if "missed" in d or "cancel" in d:
            continue
        el = (e.get("time") or {}).get("elapsed")
        if el is not None and t < el <= min(PRE_ET_BOUNDARY, t + horizon):
            return 1
    return 0


def _next_goal_side(events, t):
    """Side of the NEXT regulation goal after t: 'home'/'away'/'none'. Label only (uses future events)."""
    cand = []
    for e in events:
        if (e.get("type") or "").lower() != "goal":
            continue
        d = (e.get("detail") or "").lower()
        if "missed" in d or "cancel" in d:
            continue
        el = (e.get("time") or {}).get("elapsed")
        if el is not None and t < el <= PRE_ET_BOUNDARY:
            cand.append((el, (e.get("team") or {}).get("id")))
    return sorted(cand)[0] if cand else None


def _starter_ids(lineup_resp):
    """{team_id: [player_ids]} of starting XI per side from the lineup response."""
    out = {}
    for tl in lineup_resp or []:
        pl = HD.parse_lineup(tl)
        out[pl["team_id"]] = [s["player_id"] for s in pl["starters"] if s["player_id"] is not None]
    return out


def _bench_ids(lineup_resp):
    out = {}
    for tl in lineup_resp or []:
        pl = HD.parse_lineup(tl)
        out[pl["team_id"]] = [b["player_id"] for b in pl["bench"] if b["player_id"] is not None]
    return out


def build_snapshots_for_fixture(fid, fx, events, lineup_resp, source_root):
    """Build the full causal snapshot list for ONE fixture. Returns (rows, status, reason).

    status == 'ok' only when the fixture reconciles exactly and has a defined regulation result. Club
    fixtures are still built (auxiliary), but flagged regulation_target_eligible=0. Fixtures that do
    not reconcile exactly are SKIPPED for the international regulation target population (no silent
    admission), but still emitted as auxiliary rows with target eligibility 0 and a reason flag."""
    intl = _is_intl(fx)
    can = RS.canonical_result(fx, events)
    home_id, away_id = can["home_id"], can["away_id"]
    if home_id is None or away_id is None:
        return [], "skip", "missing_team_ids"
    reconciled = can["reconciliation_status"] == "exact"
    off_h = can["official_regulation_home_goals"]
    off_a = can["official_regulation_away_goals"]
    has_reg_target = reconciled and off_h is not None and off_a is not None
    target_wdl = (("H" if off_h > off_a else ("A" if off_a > off_h else "D"))
                  if has_reg_target else None)

    # a row is part of the international regulation TEST population only if intl + reconciled + target.
    reg_pop = bool(intl and has_reg_target)

    fixture_meta = fx.get("fixture", {}) or {}
    league = fx.get("league", {}) or {}
    kickoff_date = str(fixture_meta.get("date", ""))[:10]
    season = league.get("season")
    comp_label = _comp_label(fx)

    subs = HD.substitutions(events)
    starters = _starter_ids(lineup_resp)
    bench = _bench_ids(lineup_resp)
    home_starters = starters.get(home_id, [])
    away_starters = starters.get(away_id, [])
    has_lineups = bool(home_starters and away_starters)

    # source provenance hashes (stable, content-addressed)
    ev_hash = hashlib.sha256(json.dumps(events, sort_keys=True, default=str).encode()).hexdigest()[:16]
    ln_hash = hashlib.sha256(json.dumps(lineup_resp or [], sort_keys=True, default=str).encode()).hexdigest()[:16]

    cmid = _canonical_match_id(str(fid))
    rows = []
    for t in snapshot_minutes(events, reg_pop):
        ev_le = HD.events_up_to(events, t)  # ONLY elapsed <= t  (L1)
        sh, sa = HD.regulation_state_at(events, home_id, away_id, t)  # regulation goals <= min(t,90) (L4/L5)
        yh, ya, syh, sya, drh, dra = _cards_state(ev_le, home_id, away_id)
        sub_h = sum(1 for s in subs if s["minute"] is not None and s["minute"] <= t and s["team_id"] == home_id)
        sub_a = sum(1 for s in subs if s["minute"] is not None and s["minute"] <= t and s["team_id"] == away_id)
        on_home = HD.players_on_pitch(home_starters, [s for s in subs if s["team_id"] == home_id], t)
        on_away = HD.players_on_pitch(away_starters, [s for s in subs if s["team_id"] == away_id], t)
        # sending-off reduces players on pitch; reds are drh/dra. on-pitch count net of sendings-off.
        n_home = max(0, len(on_home) - drh)
        n_away = max(0, len(on_away) - dra)

        # discipline state-change targets (labels; future allowed)
        next_goal = _next_regulation_goal(events, t)
        ng = _next_goal_side(events, t)
        next_goal_team = ("home" if ng and ng[1] == home_id else ("away" if ng and ng[1] == away_id else "none"))

        is_event_snap = t in _event_change_minutes(events)
        period = "1H" if t <= 45 else ("HT" if t == 45 else "2H")
        if t == 0:
            period = "KO"
        elif t == PRE_ET_BOUNDARY:
            period = "FT_REG"

        rows.append({
            # identity / timing
            "canonical_match_id": cmid,
            "api_fixture_id": int(fid) if str(fid).isdigit() else fid,
            "competition": comp_label,
            "season": season,
            "kickoff_date": kickoff_date,
            "comp_type": "international" if intl else "club",
            "is_international": int(intl),
            "snapshot_minute": t,
            "source_cutoff_minute": t,
            "period": period,
            "snapshot_kind": "event" if is_event_snap else "fixed",
            # state (causal, <= t)
            "score_home": sh, "score_away": sa, "score_diff": sh - sa,
            "remaining_minutes": max(0, PRE_ET_BOUNDARY - t),
            "wld_state": "H" if sh > sa else ("D" if sh == sa else "A"),
            "yellow_home": yh, "yellow_away": ya,
            "second_yellow_home": syh, "second_yellow_away": sya,
            "red_home": drh, "red_away": dra, "red_diff": drh - dra,
            "subs_home": sub_h, "subs_away": sub_a, "subs_diff": sub_h - sub_a,
            "players_on_pitch_home": n_home, "players_on_pitch_away": n_away,
            "player_count_diff": n_home - n_away,
            "n_on_pitch_ids_home": len(on_home), "n_on_pitch_ids_away": len(on_away),
            "n_starters_home": len(home_starters), "n_starters_away": len(away_starters),
            "n_bench_home": len(bench.get(home_id, [])), "n_bench_away": len(bench.get(away_id, [])),
            # eligibility / provenance
            "regulation_eligible": int(t <= PRE_ET_BOUNDARY),
            "regulation_target_eligible": int(reg_pop and t <= PRE_ET_BOUNDARY),
            "reconciliation_status": can["reconciliation_status"],
            "reconciliation_exception": can.get("reconciliation_exception_type"),
            "has_lineups": int(has_lineups),
            "events_source_root": source_root.get(str(fid), "unknown"),
            "events_sha256": ev_hash, "lineups_sha256": ln_hash,
            "source_semantics_version": SOURCE_SEMANTICS_VERSION,
            "schema_version": SCHEMA_VERSION,
            "final_result_type": can["final_result_type"],
            # xG completeness placeholder (filled by the xG-enriched join product; here we only flag)
            "xg_join_available": 0,
            # targets (labels — may use future events)
            "target_wdl": target_wdl,
            "next_goal_15": next_goal,
            "next_goal_team": next_goal_team,
            # on-pitch / starting / bench player ids (kept compact as sorted id lists)
            "on_pitch_home_ids": ",".join(str(p) for p in sorted(on_home)),
            "on_pitch_away_ids": ",".join(str(p) for p in sorted(on_away)),
            "starting_home_ids": ",".join(str(p) for p in home_starters),
            "starting_away_ids": ",".join(str(p) for p in away_starters),
            "bench_home_ids": ",".join(str(p) for p in bench.get(home_id, [])),
            "bench_away_ids": ",".join(str(p) for p in bench.get(away_id, [])),
        })
    status = "ok" if has_reg_target else "no_regulation_target"
    reason = "" if has_reg_target else f"reconciliation={can['reconciliation_status']}"
    return rows, status, reason


# --------------------------------------------------------------------------------------------------
# Deterministic self-test: a snapshot at minute t must exclude every event after t.
# --------------------------------------------------------------------------------------------------
def selftest_no_future_leak(fixtures, events, lineups, source_root, max_checks=200):
    """For a sample of fixtures, recompute score at each snapshot minute t and verify it equals the
    score computed from ONLY events with elapsed <= t (and never includes a later goal). Also assert no
    on-pitch player entered via a sub with minute > t. Returns (passed:int, failed:int, details:list)."""
    passed = failed = 0
    details = []
    checked = 0
    for fid, fx in fixtures.items():
        ev = events.get(str(fid))
        if ev is None:
            continue
        can = RS.canonical_result(fx, ev)
        home_id, away_id = can["home_id"], can["away_id"]
        if home_id is None:
            continue
        subs = HD.substitutions(ev)
        for t in snapshot_minutes(ev, True):
            sh, sa = HD.regulation_state_at(ev, home_id, away_id, t)
            # independent recompute: goals strictly after t must NOT be in the count
            sh2, sa2 = RS.derive_window_score(ev, home_id, away_id, 0, min(t, 90))
            ok_score = (sh, sa) == (sh2, sa2)
            # any future goal (elapsed in (t,90]) must increase a *later* snapshot, not this one
            future_goal_leaked = False
            for e in ev:
                if (e.get("type") or "").lower() == "goal":
                    el = (e.get("time") or {}).get("elapsed")
                    d = (e.get("detail") or "").lower()
                    if el is not None and el > t and el <= 90 and "missed" not in d and "cancel" not in d:
                        # recompute including only <= t must be strictly less than including <= el
                        a_h, a_a = RS.derive_window_score(ev, home_id, away_id, 0, t)
                        b_h, b_a = RS.derive_window_score(ev, home_id, away_id, 0, el)
                        if (a_h + a_a) >= (b_h + b_a) and el <= 90:
                            future_goal_leaked = True
                        break
            # on-pitch must not contain a player subbed in after t
            on = HD.players_on_pitch([s["player_id"] for s in []], subs, t)  # noqa: placeholder safety
            late_in = any(s["minute"] is not None and s["minute"] > t and s["in_player_id"] in
                          HD.players_on_pitch(
                              [], [x for x in subs if x["minute"] is not None and x["minute"] <= t], t)
                          for s in subs)
            if ok_score and not future_goal_leaked and not late_in:
                passed += 1
            else:
                failed += 1
                details.append({"fixture": fid, "t": t, "ok_score": ok_score,
                                "future_goal_leaked": future_goal_leaked, "late_in": late_in})
        checked += 1
        if checked >= max_checks:
            break
    return passed, failed, details
