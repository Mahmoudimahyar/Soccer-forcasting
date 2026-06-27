"""Causal event-process SNAPSHOT dataset builder.

research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible.

Builds, from StatsBomb open-data event files ONLY (no network, no API-Football, no Odds API), the
leakage-safe event-process snapshot datasets and their target/quality side-tables:

  (1) intl_event_process_snapshots.csv   -- exact-bridge INTERNATIONAL event-process snapshots
  (2) club_event_process_snapshots.csv   -- AUXILIARY club snapshots (from whatever aux files exist now)
  (3) intl_targets_wdl.csv               -- intl regulation W/D/L targets (per match)
  (4) intl_targets_next_goal.csv         -- intl next-goal targets (per snapshot)
  (5) intl_targets_scoring_horizon.csv   -- intl next-5/10/15min scoring targets (per snapshot)
  (6) competition_source_quality.csv     -- per-competition source-quality roll-up
  (7) match_completeness.csv             -- per-match structural completeness (intl + club)
  + build_manifest.json                  -- counts, leakage self-test result, provenance

LEAKAGE / ISOLATION RULES (enforced):
  * Every snapshot feature at minute t is computed from events with match-clock minute <= t only
    (snapshot_features.events_up_to). A self-test re-verifies this on real produced rows.
  * Regulation only (period 1/2, minute <= 90); no extra-time, no shootout; no FT snapshot for
    regulation targets. A pre-extra-time boundary snapshot is allowed only when ET exists.
  * CLUB rows are tagged comp_type='club' and written to a SEPARATE file; they are NEVER emitted into
    the international snapshot/target files (which carry comp_type='international').
  * No final score / totals / future events leak into a snapshot. Targets live in separate tables.
  * Missing source fields are FLAGGED (available_verified/available_partial/unavailable/unknown),
    never imputed as 0.
  * Raw stays gitignored; outputs go to data/processed and outputs/research_runs/<run_id>/.
  * The active collector checkout is NEVER read (data_roots fails closed on it).

Sources are resolved ONLY via wcdrawlab.research.data_roots. International StatsBomb event files are
taken from statsbomb_raw/events and statsbomb_raw_prior/events (whatever is present now — no waiting,
no polling, no downloading). The api<->statsbomb international bridge (258 exact rows) selects the
international population. Auxiliary club event files are read from
statsbomb_raw/event_process_auxiliary/ (whatever is present now).
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from wcdrawlab.research import data_roots as DR  # noqa: E402
from wcdrawlab.research.event_process import snapshot_features as SF  # noqa: E402
from wcdrawlab.research.event_process import contracts as C  # noqa: E402

BRIDGE_CSV = Path("C:/Users/Mahyar/worldcup-player-impact-xg/data/processed/api_statsbomb_match_bridge_v1.csv")
SCORING_HORIZONS = [5, 10, 15]


# =================================================================================================
# IO helpers
# =================================================================================================
def _load_events(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _find_intl_event_file(sb_match_id: str):
    """Resolve a StatsBomb event JSON for an international match from the canonical events dir or the
    read-only prior cache. Returns (path, root_name) or (None, None). Never downloads."""
    for root_name in ("statsbomb_raw", "statsbomb_raw_prior"):
        try:
            base = DR.get_root(root_name) / "events"
        except Exception:
            continue
        p = base / f"{sb_match_id}.json"
        if p.exists():
            return p, root_name
    return None, None


def _resolve_home_away(events, bridge_row):
    """Map the bridge's home/away team NAMES to StatsBomb team ids using the two Starting XI events.
    Falls back to documented Starting XI order (first == home) if names cannot be matched."""
    xi = []
    for ev in events:
        t = ev.get("type") or {}
        if t.get("name") == "Starting XI":
            tm = ev.get("team") or {}
            if tm.get("id") is not None:
                xi.append((tm.get("id"), (tm.get("name") or "").strip().lower()))
    if len(xi) < 2:
        return None, None
    sb_home = (bridge_row.get("sb_home") or "").strip().lower()
    sb_away = (bridge_row.get("sb_away") or "").strip().lower()
    by_name = {n: i for i, n in xi}
    h_id = by_name.get(sb_home)
    a_id = by_name.get(sb_away)
    if h_id is not None and a_id is not None and h_id != a_id:
        return h_id, a_id
    # fallback: documented order
    return xi[0][0], xi[1][0]


def _writer(path: Path, fieldnames):
    path.parent.mkdir(parents=True, exist_ok=True)
    f = path.open("w", newline="", encoding="utf-8")
    w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
    w.writeheader()
    return f, w


# =================================================================================================
# international snapshot build (exact bridge)
# =================================================================================================
def build_international(out_dir: Path, limit_matches: int | None):
    if not BRIDGE_CSV.exists():
        return {"status": "data_insufficient", "reason": f"bridge missing at {BRIDGE_CSV}"}
    bridge = list(csv.DictReader(BRIDGE_CSV.open(encoding="utf-8")))
    bridge = [r for r in bridge if r.get("bridge_confidence") == "exact"
              and r.get("comp_type") == "international"]

    snap_rows, wdl_rows, ng_rows, sc_rows, comp_quality, completeness = [], [], [], [], {}, []
    n_match_with_events = 0
    n_match_no_events = 0
    leakage_checks = []

    for bi, row in enumerate(bridge):
        if limit_matches is not None and n_match_with_events >= limit_matches:
            break
        sb_id = row["sb_match_id"]
        path, root_name = _find_intl_event_file(sb_id)
        if path is None:
            n_match_no_events += 1
            continue
        events = _load_events(path)
        if not events:
            n_match_no_events += 1
            continue
        n_match_with_events += 1
        comp_label = row.get("competition_label")
        h_id, a_id = _resolve_home_away(events, row)
        ctx = SF.prepare_match(events, sb_id, home_team_id=h_id, away_team_id=a_id)
        if ctx.home_team_id is None or ctx.away_team_id is None:
            continue
        sha = _sha256(path)

        # targets (per match) ---------------------------------------------------------------------
        fin = SF.regulation_final(events, ctx)
        if fin is not None:
            wdl_rows.append({
                "source_match_id": sb_id, "bridge_id": row.get("bridge_id"),
                "api_fixture_id": row.get("api_fixture_id"), "competition_label": comp_label,
                "comp_type": "international", "kickoff_date": row.get("kickoff_date"),
                "home_team_id": ctx.home_team_id, "away_team_id": ctx.away_team_id,
                **fin,
                # cross-check vs bridge-reported regulation goals (provenance, not a feature)
                "bridge_reg_home": row.get("api_regulation_home"),
                "bridge_reg_away": row.get("api_regulation_away"),
            })

        # snapshots (per snapshot) ----------------------------------------------------------------
        sched = SF.snapshot_schedule(events, ctx)
        for s in sched:
            t = s["minute"]
            feats = SF.snapshot_features(events, ctx, t, reason=s["reason"])
            base = {
                "source_match_id": sb_id, "bridge_id": row.get("bridge_id"),
                "api_fixture_id": row.get("api_fixture_id"),
                "competition_label": comp_label, "comp_type": "international",
                "kickoff_date": row.get("kickoff_date"),
                "home_team_id": ctx.home_team_id, "away_team_id": ctx.away_team_id,
                "snapshot_kind": s["kind"], "source_root": root_name,
                "source_sha256": sha, "engine_version": SF.ENGINE_VERSION,
            }
            base.update(feats)
            snap_rows.append(base)

            # next-goal target (per snapshot)
            ng = SF.next_goal_after(events, ctx, t)
            ng_rows.append({
                "source_match_id": sb_id, "competition_label": comp_label,
                "comp_type": "international", "snapshot_minute": feats["snapshot_minute"],
                "snapshot_reason": s["reason"], **ng,
            })
            # near-term scoring targets (per snapshot, per horizon)
            sc_row = {
                "source_match_id": sb_id, "competition_label": comp_label,
                "comp_type": "international", "snapshot_minute": feats["snapshot_minute"],
                "snapshot_reason": s["reason"],
            }
            for h in SCORING_HORIZONS:
                sc_row.update(SF.scoring_in_window(events, ctx, t, h))
            sc_rows.append(sc_row)

        # source-quality roll-up (per competition) ------------------------------------------------
        rep = SF.source_quality_report(events, ctx)
        comp_quality.setdefault(comp_label, {"n_matches": 0, "caps": {}})
        cq = comp_quality[comp_label]
        cq["n_matches"] += 1
        for cap, info in rep.capabilities.items():
            cq["caps"].setdefault(cap, {f: 0 for f in C.QUALITY_FLAGS})
            cq["caps"][cap][info["quality"]] += 1

        # completeness (per match) ----------------------------------------------------------------
        mc = SF.match_completeness(events, ctx)
        mc["comp_type"] = "international"
        mc["competition_label"] = comp_label
        completeness.append(mc)

        # leakage self-test on a real produced row (sampled): snapshot at t sees no event > t
        if len(leakage_checks) < 50 and len(sched) > 3:
            t_chk = sched[len(sched) // 2]["minute"]
            sliced = SF.events_up_to(events, t_chk)
            mx = max((SF.event_clock(e) for e in sliced), default=0.0)
            leakage_checks.append({"match": sb_id, "t": t_chk, "max_clock_in_slice": round(mx, 3),
                                   "ok": mx <= t_chk + 1e-6})

    return {
        "snap_rows": snap_rows, "wdl_rows": wdl_rows, "ng_rows": ng_rows, "sc_rows": sc_rows,
        "comp_quality": comp_quality, "completeness": completeness,
        "n_match_with_events": n_match_with_events, "n_match_no_events": n_match_no_events,
        "n_bridge_exact": len(bridge), "leakage_checks": leakage_checks,
    }


# =================================================================================================
# auxiliary club snapshot build (whatever exists now)
# =================================================================================================
def build_club(out_dir: Path, limit_matches: int | None):
    try:
        aux_dir = DR.get_root("statsbomb_raw") / "event_process_auxiliary"
    except Exception as e:
        return {"status": "data_insufficient", "reason": f"aux root unresolved: {e}"}
    if not aux_dir.exists():
        return {"snap_rows": [], "completeness": [], "n_match_with_events": 0, "reason": "aux dir absent"}
    files = sorted(aux_dir.glob("*.json"), key=lambda p: p.name)
    snap_rows, completeness = [], []
    n_ok = 0
    for path in files:
        if limit_matches is not None and n_ok >= limit_matches:
            break
        events = _load_events(path)
        if not events:
            continue
        sb_id = path.stem
        ctx = SF.prepare_match(events, sb_id)  # club home/away from documented Starting XI order
        if ctx.home_team_id is None or ctx.away_team_id is None:
            continue
        n_ok += 1
        sha = _sha256(path)
        sched = SF.snapshot_schedule(events, ctx)
        for s in sched:
            t = s["minute"]
            feats = SF.snapshot_features(events, ctx, t, reason=s["reason"])
            base = {
                "source_match_id": sb_id, "comp_type": "club",
                "home_team_id": ctx.home_team_id, "away_team_id": ctx.away_team_id,
                "home_team_name": ctx.home_team_name, "away_team_name": ctx.away_team_name,
                "snapshot_kind": s["kind"], "source_sha256": sha,
                "engine_version": SF.ENGINE_VERSION,
            }
            base.update(feats)
            snap_rows.append(base)
        mc = SF.match_completeness(events, ctx)
        mc["comp_type"] = "club"
        mc["competition_label"] = "club_auxiliary"
        completeness.append(mc)
    return {"snap_rows": snap_rows, "completeness": completeness, "n_match_with_events": n_ok,
            "n_aux_files": len(files)}


# =================================================================================================
# write-out
# =================================================================================================
def _write_rows(path: Path, rows):
    if not rows:
        return 0
    # union of keys preserving first-seen order, stable across rows
    fieldnames = []
    seen = set()
    for r in rows:
        for k in r.keys():
            if k not in seen:
                seen.add(k)
                fieldnames.append(k)
    f, w = _writer(path, fieldnames)
    for r in rows:
        w.writerow(r)
    f.close()
    return len(rows)


def _flatten_comp_quality(comp_quality):
    rows = []
    for comp, info in sorted(comp_quality.items(), key=lambda kv: str(kv[0])):
        for cap, counts in sorted(info["caps"].items()):
            row = {"competition_label": comp, "n_matches": info["n_matches"], "capability": cap}
            row.update(counts)
            # dominant flag = the modal quality for this capability across matches
            row["dominant_quality"] = max(counts.items(), key=lambda kv: kv[1])[0]
            rows.append(row)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", default=None, help="research run id (else outputs/research_runs/active_run_id.txt)")
    ap.add_argument("--limit-intl", type=int, default=None, help="cap intl matches (debug)")
    ap.add_argument("--limit-club", type=int, default=None, help="cap club matches (debug)")
    ap.add_argument("--self-test", action="store_true", help="run a tiny in-memory leakage self-test and exit")
    args = ap.parse_args()

    if args.self_test:
        _self_test()
        return

    run_id = args.run_id
    if run_id is None:
        rid = ROOT / "outputs/research_runs/active_run_id.txt"
        run_id = rid.read_text(encoding="utf-8").strip() if rid.exists() else \
            datetime.now(timezone.utc).strftime("ep_%Y%m%d_%H%M%S")

    processed = ROOT / "data/processed/event_process_snapshots"
    run_out = ROOT / "outputs/research_runs" / run_id / "event_process_snapshots"
    processed.mkdir(parents=True, exist_ok=True)
    run_out.mkdir(parents=True, exist_ok=True)

    intl = build_international(processed, args.limit_intl)
    club = build_club(processed, args.limit_club)

    manifest = {
        "engine_version": SF.ENGINE_VERSION,
        "schema_version": C.SCHEMA_VERSION,
        "built_utc": datetime.now(timezone.utc).isoformat(),
        "run_id": run_id,
        "labels": "research_only/experimental/not_runtime_approved/not_trade_eligible/not_live_eligible",
        "international": {}, "club": {}, "leakage_self_test": {},
    }

    if "snap_rows" in intl:
        n_snap = _write_rows(processed / "intl_event_process_snapshots.csv", intl["snap_rows"])
        _write_rows(processed / "intl_targets_wdl.csv", intl["wdl_rows"])
        _write_rows(processed / "intl_targets_next_goal.csv", intl["ng_rows"])
        _write_rows(processed / "intl_targets_scoring_horizon.csv", intl["sc_rows"])
        cq_rows = _flatten_comp_quality(intl["comp_quality"])
        _write_rows(processed / "competition_source_quality.csv", cq_rows)
        all_completeness = list(intl["completeness"]) + list(club.get("completeness", []))
        _write_rows(processed / "match_completeness.csv", all_completeness)
        manifest["international"] = {
            "n_bridge_exact": intl["n_bridge_exact"],
            "n_matches_with_events": intl["n_match_with_events"],
            "n_matches_no_events_present": intl["n_match_no_events"],
            "n_snapshots": n_snap,
            "n_wdl_targets": len(intl["wdl_rows"]),
            "n_next_goal_targets": len(intl["ng_rows"]),
            "n_scoring_horizon_targets": len(intl["sc_rows"]),
            "n_competitions_quality": len(intl["comp_quality"]),
            "n_completeness_rows": len(all_completeness),
        }
        # leakage self-test verdict from real rows
        checks = intl.get("leakage_checks", [])
        manifest["leakage_self_test"] = {
            "n_sampled": len(checks),
            "all_ok": all(c["ok"] for c in checks) if checks else None,
            "violations": [c for c in checks if not c["ok"]],
        }
    else:
        manifest["international"] = {"status": intl.get("status"), "reason": intl.get("reason")}

    if "snap_rows" in club:
        n_club = _write_rows(processed / "club_event_process_snapshots.csv", club["snap_rows"])
        manifest["club"] = {
            "n_aux_files_present": club.get("n_aux_files"),
            "n_matches_with_events": club["n_match_with_events"],
            "n_snapshots": n_club,
        }
    else:
        manifest["club"] = {"status": club.get("status"), "reason": club.get("reason")}

    (processed / "build_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (run_out / "build_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    # mirror the small side tables into the run dir for the supervisor ledger
    for name in ("competition_source_quality.csv", "match_completeness.csv", "intl_targets_wdl.csv"):
        src = processed / name
        if src.exists():
            (run_out / name).write_bytes(src.read_bytes())

    print(json.dumps({"status": "ok", **manifest["international"], "club": manifest["club"],
                      "leakage": manifest["leakage_self_test"], "out": str(processed)}))


# =================================================================================================
# self-test (deterministic, in-memory; no files needed)
# =================================================================================================
def _synthetic_match():
    """A tiny deterministic StatsBomb-shaped match: home(1) leads via an early goal; away(2) shoots
    late. Used to prove (a) the leakage gate and (b) that a snapshot at t excludes events after t."""
    def shot(idx, minute, second, team_id, xg, goal=False):
        return {"index": idx, "period": 1 if minute < 45 else 2, "minute": minute, "second": second,
                "type": {"name": "Shot"}, "team": {"id": team_id},
                "location": [110.0, 40.0],
                "shot": {"statsbomb_xg": xg, "outcome": {"name": "Goal" if goal else "Saved"}}}
    return [
        {"index": 1, "period": 1, "minute": 0, "second": 0, "type": {"name": "Starting XI"}, "team": {"id": 1, "name": "Home"}},
        {"index": 2, "period": 1, "minute": 0, "second": 0, "type": {"name": "Starting XI"}, "team": {"id": 2, "name": "Away"}},
        shot(10, 10, 0, 1, 0.30, goal=True),     # home goal @10'
        shot(20, 30, 0, 2, 0.10),                # away shot @30'
        shot(30, 70, 0, 2, 0.40, goal=True),     # away goal @70' (must NOT appear in @30 snapshot)
        {"index": 40, "period": 3, "minute": 95, "second": 0, "type": {"name": "Shot"},  # ET shot: excluded
         "team": {"id": 1}, "location": [110, 40], "shot": {"statsbomb_xg": 0.5, "outcome": {"name": "Goal"}}},
    ]


def _self_test():
    ev = _synthetic_match()
    ctx = SF.prepare_match(ev, "synthetic")
    assert ctx.home_team_id == 1 and ctx.away_team_id == 2, "home/away resolution"
    # snapshot at t=30: home 1, away 0; away goal @70 and ET shot @95 must be invisible
    snap = SF.snapshot_features(ev, ctx, 30.0, "clock")
    assert snap["goals_home"] == 1 and snap["goals_away"] == 0, f"leak: {snap['goals_home']}-{snap['goals_away']}"
    assert snap["shots_home"] == 1 and snap["shots_away"] == 1, "shot count @30"
    sliced = SF.events_up_to(ev, 30.0)
    assert all(SF.event_clock(e) <= 30.0 + 1e-9 for e in sliced), "events_up_to gate"
    assert all(e.get("period") in (1, 2) for e in sliced), "regulation only (no ET)"
    # regulation final must include away goal @70 -> draw 1-1 (ET shot excluded)
    fin = SF.regulation_final(ev, ctx)
    assert fin["reg_home_goals"] == 1 and fin["reg_away_goals"] == 1 and fin["target_wdl"] == "D", fin
    # next-goal after t=30 is away
    ng = SF.next_goal_after(ev, ctx, 30.0)
    assert ng["next_goal_side"] == "away", ng
    # scoring window: away scores in next 45m after t=30 (goal @70)
    sw = SF.scoring_in_window(ev, ctx, 30.0, 45)
    assert sw["away_scores_next45m"] == 1 and sw["home_scores_next45m"] == 0, sw
    print(json.dumps({"self_test": "pass", "snap@30": {"H": snap["goals_home"], "A": snap["goals_away"]},
                      "reg_final": fin, "next_goal": ng}))


if __name__ == "__main__":
    main()
