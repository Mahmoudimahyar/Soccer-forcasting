"""Phase 3 (xG bridge): build CAUSAL in-play xG event-state features for EXACT-bridged international games.

For ONLY the games in the exact API<->StatsBomb bridge whose StatsBomb event JSON has been acquired, derive
leakage-safe in-play features on a fixed decision grid. At each decision minute t, a feature uses ONLY events
with match-clock minute <= t (strictly causal — no future shot/xG/goal can enter the state at t).

Per (match, team, t) and as home/away differences:
  - cumulative xG for / against (sum of shot statsbomb_xg up to t)
  - xG difference (for - against)
  - rolling 5-min and 10-min xG difference (xG in (t-5, t] and (t-10, t])
  - shot-count difference (shots for - shots against, up to t)
  - time-since-last-shot (minutes since the most recent shot by EITHER team, up to t; capped)
  - time-since-last-major-chance (minutes since the most recent shot with xG >= MAJOR_CHANCE_XG, up to t)
  - event-order index of the last event used (StatsBomb `index`) + completeness flags

CAUSAL / SEMANTIC RULES (enforced + tested):
  - features at minute t use ONLY events with minute <= t (see _events_up_to). No look-ahead.
  - StatsBomb event timestamps are MATCH-CLOCK minutes, NOT live publication times. They are used purely
    as in-match elapsed time; never interpreted as a real-world publication/decision wall-clock.
  - own goals contribute to the goal/score view via the beneficiary ("Own Goal For") but carry no xG.
  - shootout is never part of in-play state; extra time (period > 2 / minute > 90) is flagged separately and
    excluded from the regulation grid by default.

Output (derived only; raw stays gitignored): data/processed/xg_event_state_features_v1.csv
research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible.
"""
from __future__ import annotations

import csv
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from wcdrawlab.ingest import canonical_team_name  # noqa: E402

RAW_SB = ROOT / "data/raw/statsbomb_open"
BRIDGE_CSV = ROOT / "data/processed/api_statsbomb_match_bridge_v1.csv"
OUT_CSV = ROOT / "data/processed/xg_event_state_features_v1.csv"

FEATURE_BUILDER_VERSION = "xg_event_state_v1"
DECISION_GRID = list(range(10, 91, 5))   # regulation decision minutes 10..90 (step 5)
MAJOR_CHANCE_XG = 0.30                     # shot xG threshold for a "major chance"
CAP_SINCE = 95.0                           # cap for time-since-* when no prior event exists


def _sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _shot_minute(e) -> float:
    """Continuous match-clock minute of an event (minute + second/60)."""
    m = e.get("minute")
    s = e.get("second") or 0
    if m is None:
        return None
    return float(m) + float(s) / 60.0


def extract_shots_goals(events: list, home_canon: str, away_canon: str):
    """Return (shots, goals) where shots = [(minute_float, side, xg, is_goal, index)] for periods 1-2 (regulation).

    side in {'H','A'}; minute_float is continuous; is_goal True if outcome name == 'Goal'.
    Own goals are returned in `goals` only (beneficiary side) and carry no xG.
    Extra-time events (period > 2) are returned separately as `et_shots` for the flag, excluded from grid.
    """
    shots, goals, et_count = [], [], 0
    for e in events:
        t = (e.get("type") or {}).get("name")
        team = canonical_team_name((e.get("team") or {}).get("name"))
        period = e.get("period")
        mf = _shot_minute(e)
        if mf is None:
            continue
        side = "H" if team == home_canon else ("A" if team == away_canon else None)
        if period is not None and period > 2:  # extra time / shootout periods
            if t in ("Shot", "Own Goal For"):
                et_count += 1
            continue
        if t == "Shot":
            sh = e.get("shot") or {}
            xg = sh.get("statsbomb_xg")
            xg = float(xg) if xg is not None else 0.0
            is_goal = (sh.get("outcome") or {}).get("name") == "Goal"
            if side is not None:
                shots.append((mf, side, xg, int(is_goal), e.get("index")))
                if is_goal:
                    goals.append((mf, side, "shot"))
        elif t == "Own Goal For":
            if side is not None:
                goals.append((mf, side, "own_goal"))  # beneficiary side; no xG
    return shots, goals, et_count


def _events_up_to(shots, t):
    """CAUSAL filter: only shots at continuous match-clock minute <= t."""
    return [s for s in shots if s[0] <= t]


def features_at(shots, goals, t):
    """Compute the causal xG state for decision minute t from shots/goals up to t."""
    past = _events_up_to(shots, t)
    # cumulative xG and shot counts per side
    xg_h = sum(s[2] for s in past if s[1] == "H")
    xg_a = sum(s[2] for s in past if s[1] == "A")
    n_h = sum(1 for s in past if s[1] == "H")
    n_a = sum(1 for s in past if s[1] == "A")
    # rolling windows
    roll5_h = sum(s[2] for s in past if s[1] == "H" and s[0] > t - 5)
    roll5_a = sum(s[2] for s in past if s[1] == "A" and s[0] > t - 5)
    roll10_h = sum(s[2] for s in past if s[1] == "H" and s[0] > t - 10)
    roll10_a = sum(s[2] for s in past if s[1] == "A" and s[0] > t - 10)
    # time-since-last-shot (either team)
    if past:
        last_shot_min = max(s[0] for s in past)
        tsls = min(CAP_SINCE, t - last_shot_min)
    else:
        tsls = CAP_SINCE
    # time-since-last-major-chance
    majors = [s[0] for s in past if s[2] >= MAJOR_CHANCE_XG]
    tslmc = min(CAP_SINCE, t - max(majors)) if majors else CAP_SINCE
    # last event-order index used
    last_index = max((s[4] for s in past if s[4] is not None), default=None)
    # goal/score view up to t (includes own goals as beneficiary)
    g_h = sum(1 for g in goals if g[0] <= t and g[1] == "H")
    g_a = sum(1 for g in goals if g[0] <= t and g[1] == "A")
    return {
        "cum_xg_home": round(xg_h, 5), "cum_xg_away": round(xg_a, 5),
        "cum_xg_diff": round(xg_h - xg_a, 5),
        "roll5_xg_diff": round(roll5_h - roll5_a, 5),
        "roll10_xg_diff": round(roll10_h - roll10_a, 5),
        "shot_count_home": n_h, "shot_count_away": n_a, "shot_count_diff": n_h - n_a,
        "time_since_last_shot": round(tsls, 3),
        "time_since_last_major_chance": round(tslmc, 3),
        "last_event_index": last_index,
        "score_home_to_t": g_h, "score_away_to_t": g_a, "score_diff_to_t": g_h - g_a,
    }


def load_bridge():
    if not BRIDGE_CSV.exists():
        raise SystemExit(f"bridge CSV not found: {BRIDGE_CSV} — run build_api_statsbomb_match_bridge.py first")
    with BRIDGE_CSV.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def build():
    rows_out = []
    bridge = load_bridge()
    ev_dir = RAW_SB / "events"
    matched_with_events = 0
    for b in bridge:
        sb_id = b["sb_match_id"]
        fp = ev_dir / f"{sb_id}.json"
        if not fp.exists():
            continue   # event JSON not acquired for this game (bounded sample) -> no features
        matched_with_events += 1
        raw = fp.read_bytes()
        src_sha = _sha256_bytes(raw)
        events = json.loads(raw.decode("utf-8"))
        home_canon = canonical_team_name(b["sb_home"])
        away_canon = canonical_team_name(b["sb_away"])
        shots, goals, et_count = extract_shots_goals(events, home_canon, away_canon)
        n_total_shots = len(shots)
        for t in DECISION_GRID:
            feats = features_at(shots, goals, t)
            rows_out.append({
                "bridge_id": b["bridge_id"], "api_fixture_id": b["api_fixture_id"], "sb_match_id": sb_id,
                "competition_label": b["competition_label"], "comp_type": "international",
                "kickoff_date": b["kickoff_date"], "decision_minute": t,
                "home": b["api_home"], "away": b["api_away"],
                **feats,
                # completeness / provenance flags
                "n_shots_total_regulation": n_total_shots,
                "has_any_shot_event": int(n_total_shots > 0),
                "extra_time_events_present": int(et_count > 0),
                "sb_events_sha256": src_sha,
                "feature_builder_version": FEATURE_BUILDER_VERSION,
            })
    return rows_out, matched_with_events, len(bridge)


def main():
    rows, with_events, n_bridge = build()
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    cols = ["bridge_id", "api_fixture_id", "sb_match_id", "competition_label", "comp_type", "kickoff_date",
            "decision_minute", "home", "away", "cum_xg_home", "cum_xg_away", "cum_xg_diff", "roll5_xg_diff",
            "roll10_xg_diff", "shot_count_home", "shot_count_away", "shot_count_diff", "time_since_last_shot",
            "time_since_last_major_chance", "last_event_index", "score_home_to_t", "score_away_to_t",
            "score_diff_to_t", "n_shots_total_regulation", "has_any_shot_event", "extra_time_events_present",
            "sb_events_sha256", "feature_builder_version"]
    with OUT_CSV.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for r in sorted(rows, key=lambda x: (x["competition_label"], x["kickoff_date"], x["sb_match_id"],
                                             x["decision_minute"])):
            w.writerow(r)
    n_matches = len({r["sb_match_id"] for r in rows})
    print(f"bridge rows           : {n_bridge}")
    print(f"bridged games WITH acquired events (xG-derivable): {with_events}")
    print(f"feature rows written  : {len(rows)} across {n_matches} matches x {len(DECISION_GRID)} minutes")
    print(f"wrote {OUT_CSV}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
