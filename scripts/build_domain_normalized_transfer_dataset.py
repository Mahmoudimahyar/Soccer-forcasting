"""Build the CAUSAL DOMAIN-NORMALIZED TRANSFER DATASET (Phase 3) on REAL local data.

research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible.

Pipeline (no network, no API-Football, no Odds API, no scrape, no credentials):

  1. Resolve INTERNATIONAL event JSON from the PERSISTENT international event lake (258 hash-verified
     StatsBomb objects) via its index + the exact api<->statsbomb bridge -> leakage-safe event-process
     snapshots (reusing the event_process engine) with the side-specific REMAINING-goal LABELS.
  2. Resolve CLUB auxiliary event JSON from the event-process auxiliary corpus (whatever is present now)
     -> club snapshot rows, tagged domain='club' (auxiliary training ONLY; NEVER an intl test row).
  3. Hand the two row-sets to research.transfer.domain_normalized_dataset.build_all_fold_rows which, FOR
     EACH OUTER TEMPORAL FOLD (held-out intl tournament; training strictly before its first kickoff):
       * fits the per-DOMAIN score/time reference-intensity baseline on TRAIN rows only,
       * fits the stable-feature filter on TRAIN rows only,
       * computes the TRANSFER TARGET = event-process residual beyond each domain's own baseline,
       * assembles intl-train + club-train + held-out intl-test rows (match-level grouping preserved).
  4. Write the materialised dataset (CSV) + a build manifest (counts, fold summary, leakage self-test).

All source locations resolve ONLY via wcdrawlab.research.data_roots / the lake roots config; the active
collector checkout is never read. Raw stays in the lake (gitignored). Outputs:
  data/processed/domain_normalized_transfer/transfer_dataset_v1.csv
  data/processed/domain_normalized_transfer/build_manifest.json
  + a mirror under outputs/research_runs/<run_id>/hierarchical_transfer/.

If neither the lake nor the events dirs yield international rows, the script exits with an HONEST
``data_insufficient`` manifest (it never fabricates rows).
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from wcdrawlab.research import data_roots as DR  # noqa: E402
from wcdrawlab.research import international_event_lake as LAKE  # noqa: E402
from wcdrawlab.research.event_process import snapshot_features as SF  # noqa: E402
from wcdrawlab.research.transfer import domain_normalized_dataset as DND  # noqa: E402

OUT_DIR = ROOT / "data/processed/domain_normalized_transfer"
DATASET_CSV = OUT_DIR / "transfer_dataset_v1.csv"
MANIFEST_JSON = OUT_DIR / "build_manifest.json"
AUX_MANIFEST = ROOT / "data/reference/event_process_auxiliary_manifest.csv"


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_events(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


# =================================================================================================
# international rows from the persistent lake
# =================================================================================================
def _snapshot_rows_for_match(events, sb_id, ctx, meta: dict) -> list[dict]:
    """All leakage-safe snapshot rows for one match, carrying side-specific remaining-goal labels."""
    fin = SF.regulation_final(events, ctx)
    if fin is None:
        return []
    reg_h = float(fin["reg_home_goals"])
    reg_a = float(fin["reg_away_goals"])
    rows: list[dict] = []
    for s in SF.snapshot_schedule(events, ctx):
        t = s["minute"]
        feats = SF.snapshot_features(events, ctx, t, reason=s["reason"])
        cur_h = float(feats.get("goals_home") or 0.0)
        cur_a = float(feats.get("goals_away") or 0.0)
        row = dict(feats)
        row.update(meta)
        row["snapshot_kind"] = s["kind"]
        row["source_match_id"] = str(sb_id)
        row["match_id"] = str(sb_id)
        row["target_wdl"] = fin["target_wdl"]
        row["reg_home_goals"] = reg_h
        row["reg_away_goals"] = reg_a
        row["rem_goals_home"] = max(0.0, reg_h - cur_h)
        row["rem_goals_away"] = max(0.0, reg_a - cur_a)
        row["engine_version"] = SF.ENGINE_VERSION
        rows.append(row)
    return rows


def _resolve_home_away(events, bridge_row):
    xi = []
    for ev in events:
        t = ev.get("type") or {}
        if t.get("name") == "Starting XI":
            tm = ev.get("team") or {}
            if tm.get("id") is not None:
                xi.append((tm.get("id"), (tm.get("name") or "").strip().lower()))
    if len(xi) < 2:
        return None, None
    by_name = {n: i for i, n in xi}
    h = by_name.get((bridge_row.get("sb_home") or "").strip().lower())
    a = by_name.get((bridge_row.get("sb_away") or "").strip().lower())
    if h is not None and a is not None and h != a:
        return h, a
    return xi[0][0], xi[1][0]


def build_international_rows(limit_matches: int | None) -> tuple[list[dict], dict]:
    """International snapshot rows resolved from the lake (primary) with an events-dir fallback."""
    try:
        lake = LAKE.Lake.resolve()
        index = LAKE.read_index(lake)
    except Exception as e:
        return [], {"status": "data_insufficient", "reason": f"lake unavailable: {e!r}"}
    try:
        bridge = LAKE.load_exact_bridge()
    except Exception as e:
        return [], {"status": "data_insufficient", "reason": f"exact bridge unavailable: {e!r}"}
    rows: list[dict] = []
    n_match = 0
    n_no_obj = 0
    for sb_id, rec in sorted(index.items(), key=lambda kv: str(kv[0])):
        if limit_matches is not None and n_match >= limit_matches:
            break
        try:
            sb_int = int(sb_id)
        except (TypeError, ValueError):
            continue
        br = bridge.get(sb_int)
        if br is None:
            continue  # only matches that EXACTLY bridge enter the international population
        sha = rec.get("sha256")
        path = lake.object_path(sha) if sha else None
        if path is None or not path.exists():
            n_no_obj += 1
            continue
        events = _load_events(path)
        if not events:
            n_no_obj += 1
            continue
        h, a = _resolve_home_away(events, br)
        ctx = SF.prepare_match(events, str(sb_int), home_team_id=h, away_team_id=a)
        if ctx.home_team_id is None or ctx.away_team_id is None:
            continue
        meta = {
            "competition_label": br.get("competition_label") or rec.get("competition_label"),
            "competition": br.get("competition_label") or rec.get("competition_label"),
            "season": br.get("sb_season_id") or br.get("api_season") or br.get("competition_label"),
            "comp_type": "international", "domain": DND.DOMAIN_INTERNATIONAL,
            "kickoff_date": br.get("kickoff_date") or rec.get("kickoff_date"),
            "bridge_id": br.get("bridge_id"), "api_fixture_id": br.get("api_fixture_id"),
            "home_team_id": ctx.home_team_id, "away_team_id": ctx.away_team_id,
            "orientation": br.get("orientation"),
            "source_root": "international_event_lake_v1", "source_sha256": sha,
        }
        rows.extend(_snapshot_rows_for_match(events, sb_int, ctx, meta))
        n_match += 1
    info = {"status": "ok" if rows else "data_insufficient",
            "n_intl_matches_with_events": n_match, "n_intl_objects_missing": n_no_obj,
            "n_intl_rows": len(rows)}
    if not rows:
        info["reason"] = "no international snapshot rows produced from the lake/bridge"
    return rows, info


# =================================================================================================
# club auxiliary rows (whatever local event JSON exists now; never downloads)
# =================================================================================================
def _find_club_event_file(match_id: str):
    """Resolve a club event JSON from the auxiliary corpus or known StatsBomb event caches. Returns
    (path, root_name) or (None, None). Never downloads."""
    candidates = []
    try:
        candidates.append((DR.get_root("statsbomb_raw_event_process") / "event_process_auxiliary" / f"{match_id}.json", "event_process_aux_root"))
        candidates.append((DR.get_root("statsbomb_raw") / "event_process_auxiliary" / f"{match_id}.json",
                           "event_process_auxiliary"))
        candidates.append((DR.get_root("statsbomb_raw") / "events" / f"{match_id}.json", "statsbomb_raw"))
    except Exception:
        pass
    try:
        candidates.append((DR.get_root("statsbomb_raw_prior") / "events" / f"{match_id}.json",
                           "statsbomb_raw_prior"))
    except Exception:
        pass
    for p, name in candidates:
        if p.exists():
            return p, name
    return None, None


def build_club_rows(limit_matches: int | None) -> tuple[list[dict], dict]:
    """Club auxiliary snapshot rows from whatever local event JSON exists now. Returns ([], info) when
    no club event files are present locally (honest: the 670-match manifest lists matches whose raw
    event JSON has NOT been downloaded into this worktree)."""
    if not AUX_MANIFEST.exists():
        return [], {"status": "no_club_manifest", "n_club_rows": 0,
                    "reason": f"club aux manifest absent at {AUX_MANIFEST}"}
    man = list(csv.DictReader(AUX_MANIFEST.open(encoding="utf-8")))
    rows: list[dict] = []
    n_match = 0
    n_no_file = 0
    for m in man:
        if limit_matches is not None and n_match >= limit_matches:
            break
        mid = str(m.get("match_id") or "").strip()
        if not mid:
            continue
        path, root = _find_club_event_file(mid)
        if path is None:
            n_no_file += 1
            continue
        events = _load_events(path)
        if not events:
            n_no_file += 1
            continue
        ctx = SF.prepare_match(events, mid)  # club: home/away from documented Starting XI order
        if ctx.home_team_id is None or ctx.away_team_id is None:
            continue
        import hashlib
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        meta = {
            "competition_label": m.get("competition"), "competition": m.get("competition"),
            "season": m.get("season"), "comp_type": "club", "domain": DND.DOMAIN_CLUB,
            "kickoff_date": m.get("match_date"), "source_root": root, "source_sha256": sha,
            "orientation": "home",
        }
        rows.extend(_snapshot_rows_for_match(events, mid, ctx, meta))
        n_match += 1
    info = {"status": "ok" if rows else "no_local_club_events",
            "n_club_matches_with_events": n_match, "n_club_matches_no_local_file": n_no_file,
            "n_club_rows": len(rows), "n_club_manifest": len(man)}
    if not rows:
        info["reason"] = ("club auxiliary event JSON is not present locally (manifest lists matches but "
                          "raw events have not been downloaded; no network is permitted) -- "
                          "club-auxiliary training rows = 0 for this build")
    return rows, info


# =================================================================================================
# write
# =================================================================================================
def _write_csv(rows: list[dict], path: Path) -> list[str]:
    path.parent.mkdir(parents=True, exist_ok=True)
    cols: list[str] = []
    for r in rows:
        for k in r:
            if k not in cols:
                cols.append(k)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: ("" if r.get(k) is None else r.get(k)) for k in cols})
    return cols


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit-intl", type=int, default=None, help="cap international matches (debug)")
    ap.add_argument("--limit-club", type=int, default=None, help="cap club matches (debug)")
    ap.add_argument("--run-id", default=None)
    ap.add_argument("--min-present-frac", type=float, default=0.5)
    ap.add_argument("--max-smd", type=float, default=1.0)
    args = ap.parse_args()
    run_id = args.run_id or f"transfer_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"

    intl_rows, intl_info = build_international_rows(args.limit_intl)
    club_rows, club_info = build_club_rows(args.limit_club)

    manifest: dict = {
        "schema_version": DND.DATASET_VERSION, "run_id": run_id, "built_ts": _utc(),
        "labels": list(DND.ELIGIBILITY_LABELS), "reference_model": DND.REFERENCE_MODEL,
        "international": intl_info, "club": club_info,
        "min_present_frac": args.min_present_frac, "max_smd": args.max_smd,
    }

    if not intl_rows:
        manifest["status"] = "data_insufficient"
        manifest["reason"] = intl_info.get("reason", "no international rows")
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        MANIFEST_JSON.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        print(json.dumps({"status": "data_insufficient", "reason": manifest["reason"]}, indent=2))
        return 0

    try:
        built = DND.build_all_fold_rows(intl_rows, club_rows,
                                        min_present_frac=args.min_present_frac, max_smd=args.max_smd)
    except DND.DataInsufficient as e:
        manifest["status"] = "data_insufficient"
        manifest["reason"] = str(e)
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        MANIFEST_JSON.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        print(json.dumps({"status": "data_insufficient", "reason": str(e)}, indent=2))
        return 0

    rows = built["rows"]
    cols = _write_csv(rows, DATASET_CSV)
    manifest["status"] = "ok"
    manifest["summary"] = built["summary"]
    manifest["n_columns"] = len(cols)
    manifest["dataset_csv"] = str(DATASET_CSV)
    MANIFEST_JSON.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    # mirror to the run dir
    run_dir = ROOT / "outputs/research_runs" / run_id / "hierarchical_transfer"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "build_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    s = built["summary"]
    print(json.dumps({
        "status": "ok",
        "n_rows": s["n_rows_total"], "n_folds": s["n_folds"],
        "n_intl_test_matches": s["n_intl_test_matches"],
        "n_club_train_matches": s["n_club_train_matches"],
        "stable_feature_subset_sizes_by_fold": s["stable_feature_subset_sizes_by_fold"],
        "dataset_csv": str(DATASET_CSV),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
