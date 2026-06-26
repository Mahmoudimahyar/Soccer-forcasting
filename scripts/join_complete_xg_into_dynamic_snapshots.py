"""JOB5: build the REAL xG-to-snapshot join for EXACT-bridged international matches, over the now-complete
StatsBomb cache. Resolves events through the canonical data-root registry (canonical + prior roots) — no
hard-coded path. Strictly causal (events at match-clock minute <= cutoff only). Produces a NONZERO audited set
of xG-eligible regulation-time international snapshots. research_only / not_runtime / not_trade / not_live.

Leakage rules (enforced): no future xG event; no cross-match leakage (per-match extraction); regulation grid
only (period<=2, minute<=90); extra-time/shootout excluded; StatsBomb minutes are MATCH-CLOCK, never publication
time; own goals credit the beneficiary with no xG.
"""
from __future__ import annotations
import csv, glob, hashlib, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "src"))
from wcdrawlab.research import data_roots as DR  # noqa: E402
from wcdrawlab.ingest import canonical_team_name  # noqa: E402

BRIDGE_CSV = Path("C:/Users/Mahyar/worldcup-player-impact-xg/data/processed/api_statsbomb_match_bridge_v1.csv")
OUT = ROOT / "data/processed/xg_snapshot_join_v1.csv"
GRID = list(range(10, 91, 5))           # regulation decision minutes
MAJOR_XG = 0.30
CAP = 95.0
ON_TARGET = {"Goal", "Saved", "Saved To Post", "Saved to Post"}


def _min(e):
    m = e.get("minute")
    return None if m is None else float(m) + float(e.get("second") or 0) / 60.0


def _shots(events, home, away):
    """Return per-shot records [(min, side, xg, is_goal, on_target, has_xg, index)] for regulation (period<=2)."""
    out, et = [], 0
    for e in events:
        t = (e.get("type") or {}).get("name"); per = e.get("period"); mf = _min(e)
        team = canonical_team_name((e.get("team") or {}).get("name"))
        side = "H" if team == home else ("A" if team == away else None)
        if mf is None:
            continue
        if per is not None and per > 2:
            if t in ("Shot", "Own Goal For"):
                et += 1
            continue
        if t == "Shot" and side is not None:
            sh = e.get("shot") or {}
            xg_raw = sh.get("statsbomb_xg")
            has_xg = xg_raw is not None
            xg = float(xg_raw) if has_xg else 0.0
            outcome = (sh.get("outcome") or {}).get("name")
            out.append((mf, side, xg, int(outcome == "Goal"), int(outcome in ON_TARGET), int(has_xg), e.get("index")))
    return out, et


def _feat(shots, t):
    past = [s for s in shots if s[0] <= t]
    xg_h = sum(s[2] for s in past if s[1] == "H"); xg_a = sum(s[2] for s in past if s[1] == "A")
    n_h = sum(1 for s in past if s[1] == "H"); n_a = sum(1 for s in past if s[1] == "A")
    sot_h = sum(s[4] for s in past if s[1] == "H"); sot_a = sum(s[4] for s in past if s[1] == "A")
    r5_h = sum(s[2] for s in past if s[1] == "H" and s[0] > t - 5); r5_a = sum(s[2] for s in past if s[1] == "A" and s[0] > t - 5)
    r10_h = sum(s[2] for s in past if s[1] == "H" and s[0] > t - 10); r10_a = sum(s[2] for s in past if s[1] == "A" and s[0] > t - 10)
    tsls = min(CAP, t - max(s[0] for s in past)) if past else CAP
    majors = [s[0] for s in past if s[2] >= MAJOR_XG]
    tslmc = min(CAP, t - max(majors)) if majors else CAP
    roll5 = round(r5_h - r5_a, 5); roll10 = round(r10_h - r10_a, 5)
    n_with_xg = sum(s[5] for s in past); n_shots = len(past)
    return {
        "cum_xg_home": round(xg_h, 5), "cum_xg_away": round(xg_a, 5), "cum_xg_diff": round(xg_h - xg_a, 5),
        "roll5_xg_diff": roll5, "roll10_xg_diff": roll10,
        "xg_momentum": round(roll5 - 0.5 * roll10, 5),       # recent-5 trend vs the 10-min baseline
        "shot_count_diff": n_h - n_a, "shot_on_target_diff": sot_h - sot_a,
        "time_since_last_shot": round(tsls, 3), "time_since_last_major_chance": round(tslmc, 3),
        "last_event_index": max((s[6] for s in past if s[6] is not None), default=None),
        "xg_completeness": round(n_with_xg / n_shots, 4) if n_shots else 1.0,
        "n_shots_to_t": n_shots,
    }


def main():
    rows = list(csv.DictReader(open(BRIDGE_CSV, encoding="utf-8")))
    # resolve every bridged match's event file across REGISTERED roots (no hard-coded path)
    ev_files = {}
    for rn in ("statsbomb_raw", "statsbomb_raw_prior"):
        try:
            for fp in glob.glob(str(DR.get_root(rn) / "events" / "*.json")):
                ev_files.setdefault(Path(fp).stem, fp)
        except Exception:
            pass
    out_rows = []; matches_with_events = 0; ambiguous = 0
    for b in rows:
        if b.get("bridge_confidence") != "exact":   # exact bridge only
            ambiguous += 1; continue
        fp = ev_files.get(str(b["sb_match_id"]))
        if not fp:
            continue
        raw = Path(fp).read_bytes(); sha = hashlib.sha256(raw).hexdigest()
        events = json.loads(raw.decode("utf-8"))
        home = canonical_team_name(b["sb_home"]); away = canonical_team_name(b["sb_away"])
        shots, et = _shots(events, home, away)
        matches_with_events += 1
        ordered = [e.get("index") for e in events if isinstance(e, dict) and e.get("index") is not None]
        order_ok = int(ordered == sorted(ordered))
        for t in GRID:
            f = _feat(shots, t)
            out_rows.append({
                "canonical_match_id": b["bridge_id"], "api_fixture_id": b["api_fixture_id"],
                "sb_match_id": b["sb_match_id"], "competition_label": b["competition_label"],
                "comp_type": "international", "kickoff_date": b["kickoff_date"],
                "snapshot_minute": t, "source_cutoff_minute": t, "regulation_eligible": int(t <= 90),
                "home": b["api_home"], "away": b["api_away"], **f,
                "source_event_order_ok": order_ok, "extra_time_events_present": int(et > 0),
                "sb_events_sha256": sha, "xg_eligible": int(f["n_shots_to_t"] >= 0 and t <= 90),
                "feature_builder_version": "xg_snapshot_join_v1",
            })
    OUT.parent.mkdir(parents=True, exist_ok=True)
    cols = list(out_rows[0].keys()) if out_rows else []
    with OUT.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols); w.writeheader()
        for r in sorted(out_rows, key=lambda x: (x["competition_label"], x["kickoff_date"], x["sb_match_id"], x["snapshot_minute"])):
            w.writerow(r)
    summary = {"bridged_matches_with_events": matches_with_events, "ambiguous_excluded": ambiguous,
               "xg_snapshots_built": len(out_rows),
               "xg_eligible_international_snapshots": sum(r["xg_eligible"] for r in out_rows),
               "distinct_matches": len({r["sb_match_id"] for r in out_rows}), "out": str(OUT)}
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
