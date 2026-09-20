"""Phase 2: causal ROLLING PLAYER-IMPACT feature system.

research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible.

Turns API-Football events + lineups into leakage-safe PRE-MATCH player priors and starting-XI / bench
lineup aggregates, plus per-substitution deltas. The ONLY player information that can enter a prior for
match M is information knowable strictly BEFORE M's kickoff:

  * a player's prior priors are built ONLY from appearances dated strictly BEFORE the current match date
    (appearance = the player was on the pitch in a fixture that has reconciled-exact regulation truth).
  * per-appearance the player accrues: minutes-on-pitch (causal, from lineups + subs), the team-adjusted
    regulation goal-difference WHILE the player was on the pitch, and a Win/Draw/Loss contribution.
  * priors are REGULARIZED (shrinkage to a global prior mean with a pseudo-count) so thin histories do
    not produce extreme values; exposure / uncertainty are exposed explicitly.
  * a player with NO prior appearances is flagged unknown / insufficient-history and contributes the
    shrinkage prior only (never a future value).

Hard causal rules (enforced + tested in tests/test_player_history.py):
  - prior(player, M) uses ONLY appearances with appearance_date < M.date  (STRICT before).
  - NO post-match aggregate (rating, final score, later subs) is ever read into a pre-match prior.
  - regulation targets exclude extra-time (90<elapsed<=120) and shootout (official score only).
  - EXACT integer player.id linkage ONLY; never fuzzy name matching; unmatched/unknown is its own category.
  - club and international appearances are separated by comp_type and never pooled into the same prior.

Transparent models only: regularized means / shrinkage. NO neural nets, no opaque learned embeddings.

Pure functions + a build entrypoint; NO network here (fetching lives in scripts/player_history_backfill.py;
the build wrapper lives in scripts/build_player_history_features.py).
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterable, Optional

# Reuse the inherited, already-tested semantics. Never re-implement own-goal / regulation logic.
from .paid_source import result_semantics as RS
from .paid_source import historical_datasets as HD

PRIOR_MODEL_VERSION = "player_history_prior_v1"
PARSER_VERSION = "player_history_parser_v1"

# Shrinkage pseudo-counts (regularization strength toward the global prior mean). Larger -> stronger
# shrinkage of thin-history players toward the population mean. Fixed constants -> deterministic rebuild.
SHRINK_MINUTES = 270.0          # ~3 full matches of exposure before a player's own signal dominates
SHRINK_APPEARANCES = 3.0        # pseudo-appearances for WDL / per-appearance rates
REGULATION_MAX_MINUTE = 90      # regulation only; ET (90<el<=120) and shootout excluded

# Offensive / defensive split: while a player is on the pitch we accrue the team's regulation goals FOR
# (offensive exposure) and AGAINST (defensive exposure), per-90-on-pitch, shrunk to global means.


# --------------------------------------------------------------------------------------------------
# Appearance extraction (one row per player-appearance in one fixture) — fully causal within a match.
# --------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Appearance:
    """One player's leakage-safe appearance summary for a single fixture.

    `match_date` is the fixture kickoff (UTC). All cross-match priors filter on match_date < target.date.
    All within-match quantities (minutes, gd_on, wdl) are derived only from events of THIS fixture and are
    final-after-the-fact facts about a PAST match — they only ever feed priors for strictly-LATER matches.
    """
    player_id: int
    team_id: int
    match_id: str
    match_date: datetime
    comp_type: str            # "club" | "international"
    position: Optional[str]   # provider pos of the start slot (G/D/M/F) or None if came off bench
    started: bool
    minutes_on: float         # causal minutes on the pitch in regulation (0..90)
    goals_for_on: int         # regulation team goals scored while this player was on the pitch
    goals_against_on: int     # regulation team goals conceded while this player was on the pitch
    gd_on: int                # goals_for_on - goals_against_on (team-adjusted, on-pitch only)
    team_result: str          # "W" | "D" | "L" for the player's team (regulation result)
    source_hash: str          # hash of the raw events+lineups that produced this appearance
    parser_version: str = PARSER_VERSION


def _parse_dt(s) -> Optional[datetime]:
    if s in (None, ""):
        return None
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except Exception:
        return None


def source_hash(*objs) -> str:
    """Stable content hash for provenance traceability of a derived row (deterministic across rebuilds)."""
    h = hashlib.sha256()
    for o in objs:
        h.update(json.dumps(o, sort_keys=True, default=str, ensure_ascii=True).encode("utf-8"))
    return h.hexdigest()[:16]


def _on_pitch_interval(starter_ids, subs, player_id):
    """Return (on_from, off_at) regulation minutes for a player, or None if never on the pitch.

    Uses ONLY substitution minutes (causal within the match). A starter is on from minute 0; a substitute
    is on from their entry minute; a player subbed off goes off at that minute. Minutes clamped to [0,90]
    (regulation). This is a within-match derivation of a PAST fixture; it does not leak across matches.
    """
    on_from = None
    off_at = REGULATION_MAX_MINUTE
    if player_id in starter_ids:
        on_from = 0
    # apply subs in minute order
    for s in sorted([x for x in subs if x.get("minute") is not None], key=lambda x: x["minute"]):
        m = max(0, min(REGULATION_MAX_MINUTE, s["minute"]))
        if s.get("in_player_id") == player_id and on_from is None:
            on_from = m
        if s.get("out_player_id") == player_id and on_from is not None and off_at == REGULATION_MAX_MINUTE:
            off_at = m
    if on_from is None:
        return None
    return (on_from, max(on_from, off_at))


def _regulation_goals(events, home_id, away_id):
    """Sorted list of (minute, scoring_team_id) for regulation goals (0<el<=90), beneficiary-credited.

    Delegates own-goal/missed/cancelled semantics to result_semantics via per-minute windowing so the
    inherited beneficiary rule is the single source of truth.
    """
    out = []
    for e in events:
        if (e.get("type") or "").lower() != "goal":
            continue
        d = (e.get("detail") or "").lower()
        if "missed" in d or "cancel" in d:
            continue
        el = (e.get("time") or {}).get("elapsed")
        if el is None or not (0 < el <= REGULATION_MAX_MINUTE):
            continue
        # Use the inherited credit rule (own goal => beneficiary = event team).
        dh, da = RS.derive_window_score([e], home_id, away_id, el - 1, el)
        if dh:
            out.append((el, home_id))
        elif da:
            out.append((el, away_id))
    out.sort(key=lambda x: x[0])
    return out


def appearances_from_fixture(fixture: dict, events: list, lineups: list, comp_type: str) -> list:
    """Derive leakage-safe Appearance rows for one fixture. Returns [] unless regulation reconciles EXACT.

    Only fixtures whose event-derived regulation matches the official regulation score are used, so the
    on-pitch goal-difference attribution is trustworthy. comp_type partitions club vs international.
    """
    can = RS.canonical_result(fixture, events)
    if can["reconciliation_status"] != "exact":
        return []
    home_id, away_id = can["home_id"], can["away_id"]
    if home_id is None or away_id is None:
        return []
    fid = str((fixture.get("fixture") or {}).get("id"))
    match_date = _parse_dt((fixture.get("fixture") or {}).get("date"))
    if match_date is None:
        return []
    fh = can["official_regulation_home_goals"]
    fa = can["official_regulation_away_goals"]
    if fh is None or fa is None:
        return []

    subs = HD.substitutions(events)
    goals = _regulation_goals(events, home_id, away_id)
    shash = source_hash({"fid": fid, "events": events, "lineups": lineups})

    # index lineups per team
    parsed = [HD.parse_lineup(tl) for tl in (lineups or [])]
    by_team = {p["team_id"]: p for p in parsed if p.get("team_id") is not None}

    rows = []
    for team_id, opp_id in ((home_id, away_id), (away_id, home_id)):
        lp = by_team.get(team_id)
        if not lp:
            continue
        starters = {s["player_id"]: s for s in lp["starters"] if s.get("player_id") is not None}
        bench = {b["player_id"]: b for b in lp["bench"] if b.get("player_id") is not None}
        team_subs = [s for s in subs if s.get("team_id") == team_id]
        # team regulation result
        team_for_final = fh if team_id == home_id else fa
        team_against_final = fa if team_id == home_id else fh
        team_result = "W" if team_for_final > team_against_final else ("L" if team_for_final < team_against_final else "D")

        # every player who appeared = starters + any incoming sub
        appeared_ids = set(starters) | {s["in_player_id"] for s in team_subs if s.get("in_player_id") is not None}
        for pid in appeared_ids:
            interval = _on_pitch_interval(set(starters), team_subs, pid)
            if interval is None:
                continue
            on_from, off_at = interval
            minutes_on = float(off_at - on_from)
            gf = sum(1 for (m, scorer) in goals if on_from < m <= off_at and scorer == team_id)
            ga = sum(1 for (m, scorer) in goals if on_from < m <= off_at and scorer == opp_id)
            started = pid in starters
            pos = starters[pid]["pos"] if started else (bench.get(pid, {}) or {}).get("pos")
            rows.append(Appearance(
                player_id=int(pid), team_id=int(team_id), match_id=fid, match_date=match_date,
                comp_type=comp_type, position=pos, started=started, minutes_on=minutes_on,
                goals_for_on=gf, goals_against_on=ga, gd_on=gf - ga, team_result=team_result,
                source_hash=shash,
            ))
    return rows


# --------------------------------------------------------------------------------------------------
# Rolling priors (cross-match) — the ONLY place cross-match information is combined; always date-filtered.
# --------------------------------------------------------------------------------------------------
class PlayerHistory:
    """Holds all Appearances and answers leakage-safe prior queries.

    A prior for (player_id, before_date, comp_type) aggregates ONLY appearances strictly earlier than
    before_date within the SAME comp_type. Global means (for shrinkage) are computed lazily but are also
    date-/comp-filtered per query so a prior never depends on the future or on the other plane.
    """

    def __init__(self, appearances: Iterable[Appearance]):
        # store per (comp_type, player_id) sorted by date for fast strict-before slicing
        self._by_key: dict = {}
        self._all: list = []
        for ap in appearances:
            self._all.append(ap)
            self._by_key.setdefault((ap.comp_type, ap.player_id), []).append(ap)
        for k in self._by_key:
            self._by_key[k].sort(key=lambda a: (a.match_date, a.match_id))
        self._all.sort(key=lambda a: (a.match_date, a.match_id))

    # ---- global shrinkage targets (date + comp filtered) ----
    def _global_means(self, before: datetime, comp_type: str) -> dict:
        gd = []
        wdl = []
        per90_for = []
        per90_against = []
        for ap in self._all:
            if ap.comp_type != comp_type or not (ap.match_date < before):
                continue
            if ap.minutes_on <= 0:
                continue
            gd.append(ap.gd_on / ap.minutes_on * 90.0)
            per90_for.append(ap.goals_for_on / ap.minutes_on * 90.0)
            per90_against.append(ap.goals_against_on / ap.minutes_on * 90.0)
            wdl.append(1.0 if ap.team_result == "W" else (0.5 if ap.team_result == "D" else 0.0))
        return {
            "gd90": _mean(gd, 0.0),
            "off90": _mean(per90_for, 0.0),
            "def90": _mean(per90_against, 0.0),
            "wdl": _mean(wdl, 0.5),
            "n": len(gd),
        }

    def prior(self, player_id: int, before: datetime, comp_type: str) -> dict:
        """Leakage-safe regularized prior for a player as of `before` (STRICT) within `comp_type`.

        Returns a dict matching schemas/player_impact_prior_v1.yaml. A player with no strictly-earlier
        appearance is flagged unknown=True and returns the shrinkage prior (global means) only.
        """
        hist = [a for a in self._by_key.get((comp_type, player_id), []) if a.match_date < before]
        g = self._global_means(before, comp_type)
        prior_appearances = len(hist)
        total_minutes = sum(a.minutes_on for a in hist)
        if prior_appearances == 0 or total_minutes <= 0:
            return {
                "player_id": int(player_id), "comp_type": comp_type,
                "prior_appearances": prior_appearances, "prior_minutes": float(total_minutes),
                "minutes_per_appearance": 0.0,
                "gd_contribution_per90": round(g["gd90"], 6),
                "off_contribution_per90": round(g["off90"], 6),
                "def_contribution_per90": round(g["def90"], 6),
                "wdl_contribution": round(g["wdl"], 6),
                "exposure": 0.0, "uncertainty": 1.0,
                "position_state": "unknown",
                "unknown_player": True, "insufficient_history": True,
                "prior_model_version": PRIOR_MODEL_VERSION,
                "source_hashes": [],
            }
        raw_gd90 = sum(a.gd_on for a in hist) / total_minutes * 90.0
        raw_off90 = sum(a.goals_for_on for a in hist) / total_minutes * 90.0
        raw_def90 = sum(a.goals_against_on for a in hist) / total_minutes * 90.0
        wdl_pts = sum(1.0 if a.team_result == "W" else (0.5 if a.team_result == "D" else 0.0) for a in hist)

        # shrinkage to global mean: weight by exposure (minutes for rates, appearances for WDL)
        gd90 = _shrink(raw_gd90, g["gd90"], total_minutes, SHRINK_MINUTES)
        off90 = _shrink(raw_off90, g["off90"], total_minutes, SHRINK_MINUTES)
        def90 = _shrink(raw_def90, g["def90"], total_minutes, SHRINK_MINUTES)
        wdl = (wdl_pts + SHRINK_APPEARANCES * g["wdl"]) / (prior_appearances + SHRINK_APPEARANCES)

        exposure = total_minutes / (total_minutes + SHRINK_MINUTES)        # 0..1, grows with minutes
        uncertainty = SHRINK_APPEARANCES / (prior_appearances + SHRINK_APPEARANCES)  # 1..0, shrinks w/ apps
        # dominant position over prior appearances (deterministic tie-break by label)
        pos_state = _dominant_position(hist)
        return {
            "player_id": int(player_id), "comp_type": comp_type,
            "prior_appearances": prior_appearances, "prior_minutes": float(total_minutes),
            "minutes_per_appearance": round(total_minutes / prior_appearances, 6),
            "gd_contribution_per90": round(gd90, 6),
            "off_contribution_per90": round(off90, 6),
            "def_contribution_per90": round(def90, 6),
            "wdl_contribution": round(wdl, 6),
            "exposure": round(exposure, 6), "uncertainty": round(uncertainty, 6),
            "position_state": pos_state,
            "unknown_player": False,
            "insufficient_history": prior_appearances < SHRINK_APPEARANCES,
            "prior_model_version": PRIOR_MODEL_VERSION,
            "source_hashes": sorted({a.source_hash for a in hist}),
        }


def _mean(xs, default):
    return (sum(xs) / len(xs)) if xs else default


def _shrink(raw, prior_mean, weight, pseudo):
    """Exposure-weighted shrinkage toward prior_mean: (w*raw + pseudo*prior)/(w+pseudo)."""
    return (weight * raw + pseudo * prior_mean) / (weight + pseudo) if (weight + pseudo) > 0 else prior_mean


def _dominant_position(hist) -> str:
    """Most-common START position over prior appearances; 'sub' if only ever a substitute; else 'unknown'."""
    counts: dict = {}
    for a in hist:
        if a.started and a.position:
            counts[a.position] = counts.get(a.position, 0) + 1
    if counts:
        # deterministic: highest count, tie-break alphabetically
        return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
    return "sub" if any(not a.started for a in hist) else "unknown"


# --------------------------------------------------------------------------------------------------
# Lineup aggregates (starting XI / bench) + continuity + substitution deltas.
# --------------------------------------------------------------------------------------------------
def _w_mean(values, weights, default):
    num = sum(v * w for v, w in zip(values, weights))
    den = sum(weights)
    return (num / den) if den > 0 else default


def lineup_aggregate(xi_player_ids, bench_player_ids, before: datetime, comp_type: str,
                     hist: PlayerHistory, prev_xi_ids=None) -> dict:
    """Starting-XI / bench aggregate features from per-player priors (all strictly-before `before`).

    matches schemas/player_history_state_v1.yaml. Aggregates: mean / exposure-weighted / top-3 prior GD,
    offensive & defensive balance, bench strength, history completeness, continuity-with-prior-XI.
    """
    xi = [pid for pid in (xi_player_ids or []) if pid is not None]
    bench = [pid for pid in (bench_player_ids or []) if pid is not None]
    xi_priors = [hist.prior(pid, before, comp_type) for pid in xi]
    bench_priors = [hist.prior(pid, before, comp_type) for pid in bench]

    known = [p for p in xi_priors if not p["unknown_player"]]
    gd_vals = [p["gd_contribution_per90"] for p in xi_priors]
    weights = [max(p["exposure"], 1e-9) for p in xi_priors]
    off_vals = [p["off_contribution_per90"] for p in xi_priors]
    def_vals = [p["def_contribution_per90"] for p in xi_priors]

    mean_gd = _mean(gd_vals, 0.0)
    weighted_gd = _w_mean(gd_vals, weights, 0.0)
    top3_gd = _mean(sorted(gd_vals, reverse=True)[:3], 0.0)
    bench_gd = _mean([p["gd_contribution_per90"] for p in bench_priors], 0.0)

    completeness = (len(known) / len(xi)) if xi else 0.0
    continuity = _continuity(xi, prev_xi_ids)

    return {
        "comp_type": comp_type,
        "xi_size": len(xi),
        "xi_mean_prior_gd90": round(mean_gd, 6),
        "xi_weighted_prior_gd90": round(weighted_gd, 6),
        "xi_top3_prior_gd90": round(top3_gd, 6),
        "xi_off_balance_per90": round(_mean(off_vals, 0.0), 6),
        "xi_def_balance_per90": round(_mean(def_vals, 0.0), 6),
        "bench_strength_prior_gd90": round(bench_gd, 6),
        "history_completeness": round(completeness, 6),
        "n_unknown_players": sum(1 for p in xi_priors if p["unknown_player"]),
        "continuity_with_prior_xi": round(continuity, 6),
        "mean_exposure": round(_mean([p["exposure"] for p in xi_priors], 0.0), 6),
        "mean_uncertainty": round(_mean([p["uncertainty"] for p in xi_priors], 1.0), 6),
        "prior_model_version": PRIOR_MODEL_VERSION,
        "source_hashes": sorted({h for p in xi_priors for h in p["source_hashes"]}),
    }


def _continuity(xi, prev_xi):
    """Fraction of today's XI that also started the team's immediately-prior XI (0..1; None-prev -> 0)."""
    if not xi or not prev_xi:
        return 0.0
    prev = set(prev_xi)
    return sum(1 for pid in xi if pid in prev) / len(xi)


def substitution_delta(in_player_id, out_player_id, before: datetime, comp_type: str,
                       hist: PlayerHistory) -> dict:
    """incoming prior - outgoing prior (per the contract), both strictly-before `before`.

    matches schemas/player_substitution_delta_v1.yaml. Positive gd_delta => the incoming player has the
    stronger prior on-pitch goal-difference contribution. Both priors are leakage-safe.
    """
    p_in = hist.prior(in_player_id, before, comp_type) if in_player_id is not None else None
    p_out = hist.prior(out_player_id, before, comp_type) if out_player_id is not None else None

    def _v(p, key):
        return p[key] if p is not None else 0.0

    return {
        "in_player_id": int(in_player_id) if in_player_id is not None else None,
        "out_player_id": int(out_player_id) if out_player_id is not None else None,
        "comp_type": comp_type,
        "gd_delta_per90": round(_v(p_in, "gd_contribution_per90") - _v(p_out, "gd_contribution_per90"), 6),
        "off_delta_per90": round(_v(p_in, "off_contribution_per90") - _v(p_out, "off_contribution_per90"), 6),
        "def_delta_per90": round(_v(p_in, "def_contribution_per90") - _v(p_out, "def_contribution_per90"), 6),
        "wdl_delta": round(_v(p_in, "wdl_contribution") - _v(p_out, "wdl_contribution"), 6),
        "exposure_delta": round(_v(p_in, "exposure") - _v(p_out, "exposure"), 6),
        "in_unknown": bool(p_in["unknown_player"]) if p_in is not None else True,
        "out_unknown": bool(p_out["unknown_player"]) if p_out is not None else True,
        "prior_model_version": PRIOR_MODEL_VERSION,
    }


# --------------------------------------------------------------------------------------------------
# Build entrypoint: corpus (fixtures/events/lineups) -> all Appearances -> PlayerHistory.
# --------------------------------------------------------------------------------------------------
INTL_LEAGUES = {1, 4, 9, 6, 7}  # WC, Euro, Copa, AFCON, AsianCup (mirrors research_jobs/_common)


def _comp_type_for_fixture(fixture: dict) -> str:
    lid = (fixture.get("league") or {}).get("id")
    return "international" if lid in INTL_LEAGUES else "club"


def build_appearances(fixtures: dict, events: dict, lineups: dict) -> list:
    """All leakage-safe Appearances across a corpus. fixtures/events/lineups keyed by str fixture id."""
    out = []
    for fid, fx in fixtures.items():
        ev = events.get(fid)
        ln = lineups.get(fid)
        if ev is None or ln is None:
            continue
        out.extend(appearances_from_fixture(fx, ev, ln, _comp_type_for_fixture(fx)))
    return out


def build_player_history(fixtures: dict, events: dict, lineups: dict) -> PlayerHistory:
    return PlayerHistory(build_appearances(fixtures, events, lineups))
