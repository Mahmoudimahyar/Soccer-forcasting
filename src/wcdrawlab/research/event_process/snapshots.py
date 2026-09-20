"""Leakage-safe causal event-process snapshots.

research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible.

A snapshot at decision minute t summarizes the match-process state using ONLY events with match-clock
minute <= t (regulation, period in {1,2}, minute <= 90). It composes possession / territory / transition
/ attack / set-piece / pressure / chance-quality layers into a flat, model-ready feature row keyed by
(match_id, minute), and carries the per-match SourceQualityReport so downstream models can gate on
field availability. No final score / totals / later substitutions enter a snapshot. Club matches are
extracted identically but are tagged comp_type='club' so the eval layer never uses them as international
test rows.

`elapsed_minute <= t` is the single truncation rule. We use the regulation `minute` (not raw seconds)
to match the prior in-play harness convention (decision minutes 15/30/45/60/75)."""
from __future__ import annotations

from . import canonical_events as CE
from . import contracts as C
from . import possession as POSS
from . import territory as TERR
from . import transitions as TRN
from . import attacks as ATT
from . import set_pieces as SP
from . import pressure as PR
from . import chance_quality as CQ
from . import quality as QA

DECISION_MINUTES = [15, 30, 45, 60, 75]


def _truncate(canon: list, t_minute: int) -> list:
    """Leakage gate: regulation events with minute <= t. ET/shootout (period>2) and minute>90 dropped."""
    return [e for e in canon if e.period in (1, 2) and e.minute <= 90 and e.minute <= t_minute]


def _score_at(canon_at_t: list, home_id, away_id) -> tuple[int, int]:
    """Regulation score from goals up to t. Counts shot outcomes == Goal (credited to shooter's team),
    own goals to the beneficiary, and penalties (already shots). No final-score leak."""
    h = a = 0
    for e in canon_at_t:
        if e.kind == CE.KIND_SHOT:
            if ((e.raw.get("shot") or {}).get("outcome") or {}).get("name") == "Goal":
                if e.team_id == home_id:
                    h += 1
                elif e.team_id == away_id:
                    a += 1
        elif e.kind == CE.KIND_OWN_GOAL_AGAINST:
            # own goal against the acting team's own net -> benefits the opponent
            if e.team_id == home_id:
                a += 1
            elif e.team_id == away_id:
                h += 1
    return h, a


def _cards_at(canon_at_t: list, home_id, away_id) -> dict:
    yh = ya = rh = ra = 0
    for e in canon_at_t:
        card = ((e.raw.get("foul_committed") or {}).get("card") or
                (e.raw.get("bad_behaviour") or {}).get("card") or {})
        name = (card or {}).get("name")
        if not name:
            continue
        home = e.team_id == home_id
        if name == "Yellow Card":
            yh += home; ya += (not home)
        elif name in ("Red Card", "Second Yellow"):
            rh += home; ra += (not home)
    return {"yellow_home": yh, "yellow_away": ya, "red_home": rh, "red_away": ra}


def _team_block(canon_at_t, poss_at_t, shots_at_t, team_id, direction, prefix) -> dict:
    terr = TERR.territory_for_team(canon_at_t, team_id, direction)
    trn = TRN.transition_counts(canon_at_t, team_id, direction)
    fast = TRN.fast_transitions(poss_at_t, team_id)
    att = ATT.attack_chains_for_team(canon_at_t, poss_at_t, team_id)
    sp = SP.set_piece_counts(canon_at_t, poss_at_t, team_id)
    pr = PR.pressure_counts(canon_at_t, team_id)
    cq = CQ.team_chance_summary(shots_at_t, team_id)
    row = {}
    for src in (terr, trn, fast, att, sp, pr, cq):
        for k, v in src.items():
            if k in ("team_id", "phase_counts", "phase_shots", "_direction_known"):
                continue
            row[f"{prefix}_{k}"] = v
    row[f"{prefix}_direction_known"] = direction is not None
    return row


def build_snapshots(canon: list, trace: C.SourceTrace, home_id, away_id,
                    decision_minutes=None) -> list:
    """Return a list of snapshot feature-dicts for one match (one per decision minute).

    Each row includes leakage-verified=True only if the truncation passed the leakage check."""
    decision_minutes = decision_minutes or DECISION_MINUTES
    dir_home = CE.attacking_direction(canon, home_id) if home_id is not None else None
    dir_away = CE.attacking_direction(canon, away_id) if away_id is not None else None
    directions = {home_id: dir_home, away_id: dir_away}
    qrep = QA.assess_match(canon, trace, directions)

    rows = []
    for t in decision_minutes:
        ct = _truncate(canon, t)
        lk = QA.leakage_check(ct, t)
        poss_t = POSS.extract_possessions(ct, directions)
        shots_t = CQ.shots_for_match(ct, directions)
        sh, sa = _score_at(ct, home_id, away_id)
        cards = _cards_at(ct, home_id, away_id)
        tilt = TERR.field_tilt(ct, home_id, away_id, dir_home, dir_away)

        row = {
            "match_id": trace.source_match_id,
            "provider": trace.provider,
            "competition_label": trace.competition_label,
            "comp_type": trace.comp_type,
            "bridge_id": trace.bridge_id,
            "api_fixture_id": trace.api_fixture_id,
            "minute": t,
            "remaining": max(0, 90 - t),
            "n_events_le_t": len(ct),
            "score_home": sh, "score_away": sa, "score_diff": sh - sa,
            "home_field_tilt": tilt["home_field_tilt"],
            "leakage_verified": lk["all_ok"],
            "direction_home_known": dir_home is not None,
            "direction_away_known": dir_away is not None,
        }
        row.update(cards)
        if home_id is not None:
            row.update(_team_block(ct, poss_t, shots_t, home_id, dir_home, "home"))
        if away_id is not None:
            row.update(_team_block(ct, poss_t, shots_t, away_id, dir_away, "away"))
        # source-quality flags inline (compact), so a consumer can gate per row
        row["_source_quality"] = {k: v["quality"] for k, v in qrep.capabilities.items()}
        row["source_sha256"] = trace.source_sha256
        rows.append(row)
    return rows
