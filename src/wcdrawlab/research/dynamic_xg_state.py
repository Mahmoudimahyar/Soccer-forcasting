"""Component 3 -- DYNAMIC xG STATE (Phase 3).

Leakage-safe, source-aware dynamic in-play xG-state feature engine for senior men's INTERNATIONAL
fixtures, built ONLY from exact API<->StatsBomb bridge matches and StatsBomb open-data events whose
match-clock minute is <= each decision snapshot. research_only / experimental / not_runtime_approved /
not_trade_eligible / not_live_eligible.

This EXTENDS data/processed/xg_snapshot_join_v1.csv (the JOB5 base join, 4386 rows) by re-deriving the
full per-shot record per match so that higher-order dynamics (per-minute rate, acceleration, momentum,
time-since events, prior-match xG quality) can be computed with the SAME causal guarantee the base join
already enforces. We re-derive from events (rather than from the base CSV's aggregate columns) precisely
because acceleration / momentum need per-shot granularity the aggregate columns do not carry; the base
join's per-snapshot cumulative columns are reproduced bit-for-bit as a cross-check (see audit).

CAUSAL / LEAKAGE RULES (enforced in code, verified by the deterministic self-test):
  * xG at decision minute t uses ONLY shots with match-clock minute <= t (no future xG).
  * Per-match extraction only -> NO cross-match leakage (a row's features come from one sb_match_id).
  * Regulation grid only: period<=2 and t<=90; extra-time / shootout shots are EXCLUDED from features
    (only flagged as `extra_time_events_present`).
  * StatsBomb event minutes are MATCH-CLOCK, never publication time.
  * Prior-match xG quality uses ONLY strictly-earlier matches (by kickoff date, tie-broken by sb_match_id)
    for the SAME api_fixture orientation team set -> it never sees the current or any future match.

SOURCE-AWARE MISSINGNESS (do NOT treat missing xG as zero; do NOT impute into non-StatsBomb matches):
  * Every feature row carries `xg_source` = 'statsbomb_open' and a `has_xg_model` flag. Rows are emitted
    ONLY for exact-bridge StatsBomb matches; non-StatsBomb fixtures are never given a fabricated xG row.
  * Per-shot, `statsbomb_xg is None` is tracked separately (xg_completeness) and such shots contribute to
    shot COUNTS but contribute 0.0 to xG SUMS with an explicit completeness flag -- they are NOT imputed.
  * `xg_state_available` is 1 only when at least the xG-model coverage is present for the match.

BIG-CHANCE PROXY: StatsBomb open data has no Opta-style 'big chance' tag. We expose an explicit xG-threshold
proxy (`big_chance_xg_threshold` = 0.30) and label every such column *_proxy. This is a proxy, NOT a vendor
big-chance flag, and the data card says so.
"""
from __future__ import annotations

import glob
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from wcdrawlab.ingest import canonical_team_name

# ---- fixed, pre-registered constants (frozen before any evaluation) --------------------------------
GRID = list(range(10, 91, 5))          # regulation decision minutes 10,15,...,90 (matches JOB5 base join)
MAJOR_XG = 0.30                         # 'major chance' xG threshold (== JOB5)
BIG_CHANCE_XG = 0.30                    # big-chance PROXY threshold (xG-based; not an Opta tag)
CAP_MIN = 95.0                          # cap for time-since-* features (never exceed end of regulation+ET buffer)
ON_TARGET = {"Goal", "Saved", "Saved To Post", "Saved to Post"}
FEATURE_BUILDER_VERSION = "dynamic_xg_state_v1"
XG_SOURCE = "statsbomb_open"


@dataclass
class ShotRecord:
    """One regulation (period<=2) shot, in match-clock minutes."""
    minute: float
    side: str           # 'H' or 'A'
    xg: float           # 0.0 when statsbomb_xg is missing (NOT imputed; tracked via has_xg)
    is_goal: int
    on_target: int
    has_xg: int         # 1 if statsbomb_xg present on this shot, else 0
    index: Optional[int]


@dataclass
class MatchEvents:
    sb_match_id: str
    home: str
    away: str
    shots: list = field(default_factory=list)         # list[ShotRecord], regulation only, time-sorted
    extra_time_count: int = 0
    event_order_ok: int = 1                            # 1 if raw event index sequence is non-decreasing
    sha256: str = ""


def _minute_of(e: dict) -> Optional[float]:
    m = e.get("minute")
    if m is None:
        return None
    return float(m) + float(e.get("second") or 0) / 60.0


def parse_match_events(raw_bytes: bytes, home_canon: str, away_canon: str, sb_match_id: str) -> MatchEvents:
    """Parse one StatsBomb event file into a regulation-only, time-sorted shot record set.

    Deterministic and causal-by-construction: every shot keeps its true match-clock minute; nothing here
    looks at the decision grid, so no future information can enter a single shot record."""
    sha = hashlib.sha256(raw_bytes).hexdigest()
    events = json.loads(raw_bytes.decode("utf-8"))
    me = MatchEvents(sb_match_id=str(sb_match_id), home=home_canon, away=away_canon, sha256=sha)
    raw_indices = []
    for e in events:
        if not isinstance(e, dict):
            continue
        idx = e.get("index")
        if idx is not None:
            raw_indices.append(idx)
        t = (e.get("type") or {}).get("name")
        per = e.get("period")
        mf = _minute_of(e)
        if mf is None:
            continue
        team = canonical_team_name((e.get("team") or {}).get("name"))
        side = "H" if team == home_canon else ("A" if team == away_canon else None)
        if per is not None and per > 2:                      # extra-time / shootout -> excluded from features
            if t in ("Shot", "Own Goal For"):
                me.extra_time_count += 1
            continue
        if t == "Shot" and side is not None:
            sh = e.get("shot") or {}
            xg_raw = sh.get("statsbomb_xg")
            has_xg = xg_raw is not None
            outcome = (sh.get("outcome") or {}).get("name")
            me.shots.append(ShotRecord(
                minute=mf, side=side,
                xg=float(xg_raw) if has_xg else 0.0,
                is_goal=int(outcome == "Goal"),
                on_target=int(outcome in ON_TARGET),
                has_xg=int(has_xg),
                index=idx,
            ))
    me.event_order_ok = int(raw_indices == sorted(raw_indices))
    me.shots.sort(key=lambda s: (s.minute, s.index if s.index is not None else 0))
    return me


def _side_sum(shots, side, attr):
    return sum(getattr(s, attr) for s in shots if s.side == side)


def dynamic_features_at(me: MatchEvents, t: float, prior_quality: Optional[dict] = None) -> dict:
    """Compute the full dynamic xG-state feature vector at decision minute t.

    CAUSAL GUARANTEE: only shots with minute <= t enter `past`; nothing after t is referenced. The 'rate'
    and 'acceleration' families compare two strictly-past windows, so they too are leakage-safe."""
    past = [s for s in me.shots if s.minute <= t]

    cum_xg_h = _side_sum(past, "H", "xg"); cum_xg_a = _side_sum(past, "A", "xg")
    n_h = sum(1 for s in past if s.side == "H"); n_a = sum(1 for s in past if s.side == "A")
    sot_h = _side_sum(past, "H", "on_target"); sot_a = _side_sum(past, "A", "on_target")

    # rolling windows (recent-5 / recent-10 min, both strictly within the past)
    w5 = [s for s in past if s.minute > t - 5]
    w10 = [s for s in past if s.minute > t - 10]
    r5_h = _side_sum(w5, "H", "xg"); r5_a = _side_sum(w5, "A", "xg")
    r10_h = _side_sum(w10, "H", "xg"); r10_a = _side_sum(w10, "A", "xg")
    roll5 = r5_h - r5_a
    roll10 = r10_h - r10_a

    # earlier 5-min window [t-10, t-5) -> used for acceleration (change in rate), all in the past
    w_prev5 = [s for s in past if t - 10 < s.minute <= t - 5]
    prev5 = _side_sum(w_prev5, "H", "xg") - _side_sum(w_prev5, "A", "xg")

    cum_xg_diff = cum_xg_h - cum_xg_a
    # per elapsed minute (t>=10 on the grid, so elapsed is always > 0)
    elapsed = max(t, 1.0)
    xg_per_min_h = cum_xg_h / elapsed
    xg_per_min_a = cum_xg_a / elapsed
    xg_per_min_diff = cum_xg_diff / elapsed

    # momentum = recent-5 trend net of the 10-min baseline (== JOB5 definition);
    # acceleration = change in the 5-min xG-diff *rate* between the two adjacent past windows.
    xg_momentum = roll5 - 0.5 * roll10
    xg_acceleration = (roll5 / 5.0) - (prev5 / 5.0)

    # time-since events (capped); when nothing has happened yet, the cap stands in (NOT zero).
    tsls = min(CAP_MIN, t - max((s.minute for s in past), default=t - CAP_MIN)) if past else CAP_MIN
    majors = [s.minute for s in past if s.xg >= MAJOR_XG]
    tslmc = min(CAP_MIN, t - max(majors)) if majors else CAP_MIN

    # big-chance PROXY (xG-threshold), per side and diff
    bc_h = sum(1 for s in past if s.side == "H" and s.xg >= BIG_CHANCE_XG)
    bc_a = sum(1 for s in past if s.side == "A" and s.xg >= BIG_CHANCE_XG)

    # source-aware completeness: fraction of past shots that actually carry an xG model value
    n_with_xg = sum(s.has_xg for s in past)
    n_shots = len(past)

    feats = {
        # cumulative state
        "cum_xg_home": round(cum_xg_h, 6), "cum_xg_away": round(cum_xg_a, 6),
        "cum_xg_diff": round(cum_xg_diff, 6),
        # per-minute rate
        "xg_per_min_home": round(xg_per_min_h, 6), "xg_per_min_away": round(xg_per_min_a, 6),
        "xg_per_min_diff": round(xg_per_min_diff, 6),
        # rolling windows
        "roll5_xg_diff": round(roll5, 6), "roll10_xg_diff": round(roll10, 6),
        "xg_momentum": round(xg_momentum, 6),
        "xg_acceleration": round(xg_acceleration, 6),
        # shot-volume diffs
        "shot_count_diff": n_h - n_a, "shot_on_target_diff": sot_h - sot_a,
        # big-chance PROXY (xG-threshold, NOT an Opta tag)
        "big_chance_proxy_home": bc_h, "big_chance_proxy_away": bc_a,
        "big_chance_proxy_diff": bc_h - bc_a,
        # time-since events
        "time_since_last_shot": round(tsls, 4), "time_since_last_major_chance": round(tslmc, 4),
        # completeness / provenance
        "n_shots_to_t": n_shots, "n_shots_with_xg_to_t": n_with_xg,
        "xg_completeness": round(n_with_xg / n_shots, 5) if n_shots else 1.0,
        "last_event_index": max((s.index for s in past if s.index is not None), default=None),
    }
    # prior xG quality (strictly earlier matches) -- injected by the builder, never future-derived
    if prior_quality is not None:
        feats["prior_xg_quality_home"] = prior_quality.get("home")
        feats["prior_xg_quality_away"] = prior_quality.get("away")
        feats["prior_xg_n_matches_home"] = prior_quality.get("n_home")
        feats["prior_xg_n_matches_away"] = prior_quality.get("n_away")
    else:
        feats["prior_xg_quality_home"] = None
        feats["prior_xg_quality_away"] = None
        feats["prior_xg_n_matches_home"] = 0
        feats["prior_xg_n_matches_away"] = 0
    return feats


def resolve_event_files() -> dict:
    """Resolve every StatsBomb event file across REGISTERED roots (canonical first, then prior). No
    hard-coded path -- all roots come from the canonical data-root registry."""
    from wcdrawlab.research import data_roots as DR
    files = {}
    for rn in ("statsbomb_raw", "statsbomb_raw_prior"):
        try:
            root = DR.get_root(rn)
        except Exception:
            continue
        for fp in glob.glob(str(root / "events" / "*.json")):
            files.setdefault(Path(fp).stem, fp)   # canonical wins ties
    return files
