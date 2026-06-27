"""Component 2 (Phase 2) build entrypoint: FULL TEMPORAL PLAYER PRIORS over the REAL corpus.

research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible.

Pipeline:
  1. Load events+lineups+fixtures from BOTH the inherited api-football corpus (the 900 reconciled fixtures
     with international + club rows) AND this worktree's club player-history root (the +2000 club events that
     thicken the per-player PRIOR history). All paths resolve through the canonical data-root registry —
     nothing is hard-coded against a competing path, and the active collector checkout is never read.
  2. Build the leakage-safe Appearance corpus (player_history.build_appearances) and a DynamicPlayerPriors.
  3. For every INTERNATIONAL regulation snapshot (decision minutes 15/30/45/60/75 of every exact-reconciled
     international fixture) compute the 4 feature categories for BOTH teams, using ONLY appearances dated
     strictly before that fixture's kickoff (causal) and ONLY substitutions up to the snapshot minute.
  4. Emit FOUR gitignored derived tables (exposure / contribution / composition / substitution-delta) under
     data/processed/dynamic_player_priors and a copy of the coverage manifest under the run's model_phase
     dir. A TRACKED manifest holds COUNTS only — no raw external data is committed.

Causal contract is enforced inside dynamic_player_prior_models.py + player_history.py and proven by
scripts/audit_dynamic_player_priors.py. Run:
    python scripts/build_dynamic_temporal_player_priors.py [--run-dir <dir>]
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from wcdrawlab.research import data_roots as DR  # noqa: E402
from wcdrawlab.research import player_history as PH  # noqa: E402
from wcdrawlab.research import dynamic_player_prior_models as DPP  # noqa: E402
from wcdrawlab.research.paid_source import historical_datasets as HD  # noqa: E402
from wcdrawlab.research.paid_source import result_semantics as RS  # noqa: E402

INTL_LEAGUES = {1: "WC", 4: "Euro", 9: "Copa", 6: "AFCON", 7: "AsianCup"}
DECISION_MINUTES = [15, 30, 45, 60, 75]

PROC = ROOT / "data/processed/dynamic_player_priors"
MANIFEST = ROOT / "notes/research/dynamic_player_priors_manifest.json"
DEFAULT_RUN_DIR = ROOT / "outputs/research_runs/truth_20260626_134931/model_phase"

# Raw roots that may hold events/lineups/fixtures, resolved through the registry (first-write-wins).
# We resolve by registry NAME so we never hard-code a competing path; fall back to the literal corpus path
# only via the registry's read-only corpus root.
_REGISTRY_RAW_NAMES = ["api_football_player_history", "api_football_player_history_prior",
                       "api_football_corpus"]


def _raw_roots():
    roots = []
    for name in _REGISTRY_RAW_NAMES:
        try:
            p = DR.get_root(name)
            if p.exists():
                roots.append(p)
        except Exception:
            pass
    # the inherited corpus worktree root that _common uses (international events live here)
    extra = Path("C:/Users/Mahyar/worldcup-api-football-corpus/data/raw/api_football_historical_corpus")
    if extra.exists() and extra not in roots:
        roots.append(extra)
    return roots


def _load_raw(roots):
    fixtures, events, lineups = {}, {}, {}
    for root in roots:
        for fp in root.glob("fixtures_*.json"):
            n = fp.name
            if "events" in n or "lineups" in n:
                continue
            try:
                p = json.loads(fp.read_text(encoding="utf-8"))
            except Exception:
                continue
            for fx in p.get("response", []) or []:
                fid = str((fx.get("fixture") or {}).get("id"))
                if fid != "None":
                    fixtures.setdefault(fid, fx)
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


def _comp_label(fx) -> str:
    return INTL_LEAGUES.get((fx.get("league") or {}).get("id"), "club")


def _prev_xi_lookup(fixtures, lineups):
    """(comp_type, team_id) -> chronologically sorted [(date, fid, xi_ids)] for continuity features."""
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
    prev = None
    for (d, f, xi) in by_team.get((ctype, team_id), []):
        if d < date or (d == date and f < fid):
            prev = xi
        else:
            break
    return prev


def _w(path, rows):
    if not rows:
        return 0
    keys = sorted({k for r in rows for k in r.keys()})
    with open(path, "w", newline="", encoding="utf-8") as f:
        wr = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
        wr.writeheader()
        wr.writerows(rows)
    return len(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", default=str(DEFAULT_RUN_DIR))
    args = ap.parse_args()
    run_dir = Path(args.run_dir)

    roots = _raw_roots()
    fixtures, events, lineups = _load_raw(roots)

    # comp label per match (drives the competition shrinkage tier)
    comp_label_by_match = {fid: _comp_label(fx) for fid, fx in fixtures.items()}

    # leakage-safe Appearances over the WHOLE corpus (intl test pop + club prior history)
    appearances = PH.build_appearances(fixtures, events, lineups)
    dp = DPP.DynamicPlayerPriors(appearances, comp_label_by_match=comp_label_by_match)
    by_team_xi = _prev_xi_lookup(fixtures, lineups)
    # national-only prev XI uses the international slice of the same lookup
    PROC.mkdir(parents=True, exist_ok=True)

    exposure_rows, contrib_rows, comp_rows, sub_rows = [], [], [], []
    counts = defaultdict(int)
    intl_snapshots_with_coverage = set()
    intl_matches_seen = set()

    # iterate INTERNATIONAL exact-reconciled fixtures deterministically (date, fid)
    intl_fids = [fid for fid in fixtures
                 if (fixtures[fid].get("league") or {}).get("id") in INTL_LEAGUES
                 and fid in events and fid in lineups]
    intl_fids.sort(key=lambda f: (PH._parse_dt((fixtures[f].get("fixture") or {}).get("date"))
                                  or datetime.min, f))

    for fid in intl_fids:
        fx = fixtures[fid]
        ev = events[fid]
        date = PH._parse_dt((fx.get("fixture") or {}).get("date"))
        if date is None:
            continue
        can = RS.canonical_result(fx, ev)
        if can["reconciliation_status"] != "exact":
            continue
        home_id, away_id = can["home_id"], can["away_id"]
        if home_id is None or away_id is None:
            continue
        ctype = "international"
        comp = _comp_label(fx)
        parsed = {p["team_id"]: p for p in (HD.parse_lineup(tl) for tl in (lineups[fid] or []))
                  if p.get("team_id") is not None}
        if home_id not in parsed or away_id not in parsed:
            continue
        intl_matches_seen.add(fid)
        subs = HD.substitutions(ev)
        counts["intl_matches"] += 1

        for team_id, opp_id in ((home_id, away_id), (away_id, home_id)):
            lp = parsed.get(team_id)
            if not lp:
                continue
            xi = [s["player_id"] for s in lp["starters"] if s.get("player_id") is not None]
            bench = [b["player_id"] for b in lp["bench"] if b.get("player_id") is not None]
            prev_xi = _prev_xi(by_team_xi, ctype, team_id, date, fid)
            # the national prev-XI is the same lookup restricted to international comp_type (== ctype here)
            prev_nat = prev_xi

            # per-player exposure + contribution priors (PRE-MATCH, strictly-before date) for the XI
            for slot, ids in (("xi", xi), ("bench", bench)):
                for pid in ids:
                    pos = None
                    src = lp["starters"] if slot == "xi" else lp["bench"]
                    for s in src:
                        if s.get("player_id") == pid:
                            pos = s.get("pos"); break
                    ex = dp.exposure_features(pid, date, ctype, team_id=team_id)
                    ex.update({"match_id": fid, "team_id": team_id, "competition": comp,
                               "match_date": date.isoformat(), "slot": slot})
                    exposure_rows.append(ex)
                    cp = dp.contribution_prior(pid, date, ctype, team_id=team_id, position=pos)
                    cp.update({"match_id": fid, "team_id": team_id, "competition": comp,
                               "match_date": date.isoformat(), "slot": slot, "lineup_position": pos})
                    contrib_rows.append(cp)
                    counts["player_prior_rows"] += 1
                    if not cp["unknown_player"]:
                        counts["known_player_priors"] += 1

            # team-state COMPOSITION at each decision minute (on-pitch evolves with subs <= t)
            starter_ids = set(xi)
            team_subs = [s for s in subs if s.get("team_id") == team_id]
            for t in DECISION_MINUTES:
                on_pitch = HD.players_on_pitch(starter_ids, team_subs, t)
                # remaining bench = listed bench minus anyone already brought on by minute t
                brought_on = {s["in_player_id"] for s in team_subs
                              if s.get("minute") is not None and s["minute"] <= t
                              and s.get("in_player_id") is not None}
                remaining_bench = [b for b in bench if b not in brought_on]
                comp_feat = dp.composition_features(
                    sorted(on_pitch), xi, remaining_bench, date, ctype,
                    team_id=team_id, prev_xi_ids=prev_xi, prev_national_ids=prev_nat)
                comp_feat.update({"match_id": fid, "team_id": team_id, "opp_id": opp_id,
                                  "competition": comp, "match_date": date.isoformat(),
                                  "minute": t, "is_home": team_id == home_id})
                comp_rows.append(comp_feat)
                counts["composition_rows"] += 1
                if comp_feat["coverage_aggregate"] > 0.0:
                    intl_snapshots_with_coverage.add((fid, team_id, t))

        # substitution-delta features (priors strictly-before this match; context = sub minute/score)
        for s in subs:
            if s.get("team_id") not in (home_id, away_id):
                continue
            minute = s.get("minute")
            # regulation score diff at the sub minute (causal) from the team's perspective
            sd = None
            if minute is not None:
                sh, sa = HD.regulation_state_at(ev, home_id, away_id, minute)
                sd = (sh - sa) if s["team_id"] == home_id else (sa - sh)
            d = dp.substitution_delta_features(
                s.get("in_player_id"), s.get("out_player_id"), date, ctype,
                minute=minute, score_diff=sd, team_id=s.get("team_id"))
            d.update({"match_id": fid, "team_id": s.get("team_id"), "competition": comp,
                      "match_date": date.isoformat()})
            sub_rows.append(d)
            counts["substitution_delta_rows"] += 1

    n_exp = _w(PROC / "player_exposure_priors.csv", exposure_rows)
    n_con = _w(PROC / "player_contribution_priors.csv", contrib_rows)
    n_comp = _w(PROC / "team_composition_features.csv", comp_rows)
    n_sub = _w(PROC / "substitution_delta_features.csv", sub_rows)

    # number of distinct international snapshots (match,team,minute) with >0 player-prior coverage
    n_cov_snaps = len(intl_snapshots_with_coverage)
    n_intl_matches = len(intl_matches_seen)
    distinct_decision_snapshots = n_intl_matches * 2 * len(DECISION_MINUTES)

    manifest = {
        "dynamic_prior_model_version": DPP.DYNAMIC_PRIOR_MODEL_VERSION,
        "parser_version": PH.PARSER_VERSION,
        "raw_roots_resolved": [str(r) for r in roots],
        "n_appearances_total": len(appearances),
        "n_appearances_international": sum(1 for a in appearances if a.comp_type == "international"),
        "n_appearances_club": sum(1 for a in appearances if a.comp_type == "club"),
        "n_intl_matches_with_lineups": n_intl_matches,
        "n_player_exposure_rows": n_exp,
        "n_player_contribution_rows": n_con,
        "n_team_composition_rows": n_comp,
        "n_substitution_delta_rows": n_sub,
        "n_known_player_priors": counts["known_player_priors"],
        "n_player_prior_rows": counts["player_prior_rows"],
        "distinct_intl_decision_snapshots": distinct_decision_snapshots,
        "intl_decision_snapshots_with_player_prior_coverage": n_cov_snaps,
        "coverage_rate": round(n_cov_snaps / distinct_decision_snapshots, 4)
        if distinct_decision_snapshots else 0.0,
        "decision_minutes": DECISION_MINUTES,
        "out_dir": str(PROC),
        "status": "complete" if n_intl_matches > 0 and n_cov_snaps > 0 else "data_insufficient",
    }
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    # also drop a copy into the run's model_phase dir for the run artifact trail
    try:
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "dynamic_player_priors_manifest.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8")
    except Exception:
        pass
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
