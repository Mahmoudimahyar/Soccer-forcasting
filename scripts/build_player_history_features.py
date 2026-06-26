"""Phase 2: build the causal rolling player-impact feature tables from the corpus raw.

Reads events+lineups from BOTH the player-history corpus (this worktree, gitignored) and the inherited
api_football historical corpus (corpus worktree + this worktree), derives leakage-safe Appearances, builds
a PlayerHistory, then emits THREE gitignored derived tables — per-player pre-match priors, per-team XI/bench
aggregates, and per-substitution deltas — each carrying source_hash + prior_model_version provenance. A
TRACKED manifest holds COUNTS only (no raw external data committed). research_only / not_runtime_approved.

Every prior is strictly-before the match date (see player_history.py for the causal contract). Run:
    python scripts/build_player_history_features.py
"""
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from wcdrawlab.research import player_history as PH  # noqa: E402
from wcdrawlab.research.paid_source import historical_datasets as HD  # noqa: E402

# raw roots that may hold events/lineups (first-write-wins; corpus worktree has the inherited 900+)
RAW_ROOTS = [
    ROOT / "data/raw/player_history_corpus",
    ROOT / "data/raw/api_football_historical_corpus",
    Path("C:/Users/Mahyar/worldcup-api-football-corpus/data/raw/api_football_historical_corpus"),
]
PROC = ROOT / "data/processed/player_history"
MANIFEST = ROOT / "notes/research/player_history_feature_manifest.json"


def _load_raw():
    fixtures, events, lineups = {}, {}, {}
    for root in RAW_ROOTS:
        if not root.exists():
            continue
        for fp in root.glob("fixtures_*.json"):
            if "events" in fp.name or "lineups" in fp.name:
                continue
            try:
                p = json.loads(fp.read_text(encoding="utf-8"))
            except Exception:
                continue
            for fx in p.get("response", []) or []:
                fixtures.setdefault(str((fx.get("fixture") or {}).get("id")), fx)
        for fp in root.glob("fixtures_events_*.json"):
            try:
                p = json.loads(fp.read_text(encoding="utf-8"))
            except Exception:
                continue
            fid = (p.get("parameters") or {}).get("fixture")
            if fid is not None:
                events.setdefault(str(fid), p.get("response", []) or [])
        for fp in root.glob("fixtures_lineups_*.json"):
            try:
                p = json.loads(fp.read_text(encoding="utf-8"))
            except Exception:
                continue
            fid = (p.get("parameters") or {}).get("fixture")
            if fid is not None:
                lineups.setdefault(str(fid), p.get("response", []) or [])
    return fixtures, events, lineups


def _prev_xi_lookup(fixtures, lineups):
    """team_id -> chronologically sorted [(date, fixture_id, [xi_ids])] for continuity-with-prior-XI."""
    by_team = defaultdict(list)
    for fid, ln in lineups.items():
        fx = fixtures.get(fid)
        if not fx:
            continue
        date = PH._parse_dt((fx.get("fixture") or {}).get("date"))
        if date is None:
            continue
        ctype = PH._comp_type_for_fixture(fx)
        for tl in ln:
            p = HD.parse_lineup(tl)
            if p.get("team_id") is None:
                continue
            xi = [s["player_id"] for s in p["starters"] if s.get("player_id") is not None]
            by_team[(ctype, p["team_id"])].append((date, fid, xi))
    for k in by_team:
        by_team[k].sort(key=lambda x: (x[0], x[1]))
    return by_team


def _prev_xi(by_team, ctype, team_id, date, fid):
    """The team's immediately-earlier XI (strictly before this match), or None."""
    seq = by_team.get((ctype, team_id), [])
    prev = None
    for (d, f, xi) in seq:
        if d < date or (d == date and f < fid):
            prev = xi
        else:
            break
    return prev


def main():
    fixtures, events, lineups = _load_raw()
    appearances = PH.build_appearances(fixtures, events, lineups)
    hist = PH.PlayerHistory(appearances)
    by_team_xi = _prev_xi_lookup(fixtures, lineups)
    PROC.mkdir(parents=True, exist_ok=True)

    prior_rows, agg_rows, sub_rows = [], [], []
    counts = defaultdict(lambda: defaultdict(int))

    # iterate matches deterministically (date, fid)
    ordered = sorted(
        [fid for fid in fixtures if fid in events and fid in lineups],
        key=lambda f: (PH._parse_dt((fixtures[f].get("fixture") or {}).get("date")) or PH.datetime.min, f),
    )
    for fid in ordered:
        fx = fixtures[fid]
        date = PH._parse_dt((fx.get("fixture") or {}).get("date"))
        if date is None:
            continue
        ctype = PH._comp_type_for_fixture(fx)
        teams = fx.get("teams") or {}
        home_id = (teams.get("home") or {}).get("id")
        away_id = (teams.get("away") or {}).get("id")
        parsed = {p["team_id"]: p for p in (HD.parse_lineup(tl) for tl in (lineups[fid] or [])) if p.get("team_id") is not None}
        counts[ctype]["matches"] += 1
        for team_id in (home_id, away_id):
            lp = parsed.get(team_id)
            if not lp:
                continue
            xi = [s["player_id"] for s in lp["starters"] if s.get("player_id") is not None]
            bench = [b["player_id"] for b in lp["bench"] if b.get("player_id") is not None]
            prev_xi = _prev_xi(by_team_xi, ctype, team_id, date, fid)
            agg = PH.lineup_aggregate(xi, bench, date, ctype, hist, prev_xi_ids=prev_xi)
            agg.update({"match_id": fid, "team_id": team_id, "match_date": date.isoformat(),
                        "is_home": team_id == home_id})
            agg_rows.append(agg)
            counts[ctype]["team_rows"] += 1
            counts[ctype]["unknown_players_in_xi"] += agg["n_unknown_players"]
            # per-player priors
            for pid in xi:
                pr = hist.prior(pid, date, ctype)
                pr.update({"match_id": fid, "team_id": team_id, "match_date": date.isoformat(), "slot": "xi"})
                prior_rows.append(pr)
                counts[ctype]["xi_player_priors"] += 1
                if pr["unknown_player"]:
                    counts[ctype]["unknown_priors"] += 1
        # substitution deltas (incoming - outgoing), priors strictly-before this match
        for s in HD.substitutions(events[fid]):
            d = PH.substitution_delta(s.get("in_player_id"), s.get("out_player_id"), date, ctype, hist)
            d.update({"match_id": fid, "team_id": s.get("team_id"), "minute": s.get("minute")})
            sub_rows.append(d)
            counts[ctype]["substitution_deltas"] += 1

    def _w(name, rows):
        if not rows:
            return
        # union of keys for stable header
        keys = list({k for r in rows for k in r.keys()})
        keys.sort()
        with open(PROC / name, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
            w.writeheader()
            w.writerows(rows)

    _w("player_priors.csv", prior_rows)
    _w("lineup_aggregates.csv", agg_rows)
    _w("substitution_deltas.csv", sub_rows)

    manifest = {
        "prior_model_version": PH.PRIOR_MODEL_VERSION,
        "parser_version": PH.PARSER_VERSION,
        "n_appearances": len(appearances),
        "n_player_prior_rows": len(prior_rows),
        "n_lineup_aggregate_rows": len(agg_rows),
        "n_substitution_delta_rows": len(sub_rows),
        "by_comp_type": {ct: dict(counts[ct]) for ct in counts},
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
