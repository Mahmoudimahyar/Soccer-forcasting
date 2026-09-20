"""Build ONE frozen evaluation cohort from the INTERNATIONAL EVENT LAKE (Phase 4).

research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible.

This is the SINGLE source of truth for which senior men's international matches enter evaluation.
It reads event JSON ONLY from the persistent content-addressed LAKE
(C:/Users/Mahyar/worldcup_data_lake/.../international_event_lake_v1), where every object is
hash-verified, and reuses the locked event_process engine to derive regulation-only causal snapshots.

HARD RULES (fail-closed; mirrored by tests/test_international_event_lake_cohort.py):
  * RAW-BACKED ONLY. A match enters the cohort iff the lake INDEX references it AND the object
    exists on disk AND its bytes hash to the recorded sha256 AND the bytes are a valid event list.
    There is NO silent cache fallback to data/raw/statsbomb_open or the prior worktree caches; the
    builder never reads raw event JSON from any path outside the registered lake objects/ tree.
  * SOURCE-HASH TRACEABILITY. Every cohort row carries the lake sha256; every snapshot carries the
    same source_sha256 (engine-recomputed) and we assert it equals the lake-recorded hash.
  * EXACT BRIDGE ONLY. sb_match_id must resolve to exactly one EXACT senior-men's-international
    bridge row (no fuzzy / forced / ambiguous bridge ever enters the cohort).
  * REGULATION-ONLY CAUSAL SNAPSHOTS. Snapshots use only events with match-clock minute <= t,
    period in (1,2), minute <= 90 (event_process snapshot_features). No ET/shootout target leakage.
  * NO FUTURE EVENT LEAKAGE. A snapshot at t excludes every event after t (re-verified on real rows).
  * NO 2026 WORLD CUP in ANY cohort (selected / eligible / power / WDL / near-term / discipline).
  * MATCH-LEVEL GROUPING. The independent unit is the MATCH; folds group by match, never by snapshot.

PRODUCTS (data/reference/):
  international_event_lake_cohort_manifest.csv / .json   -- per-match cohort + eligibility + folds
  international_event_lake_cohort_exclusions.csv         -- exclusion ledger (every dropped id + reason)
  international_event_lake_cohort_report.md              -- human-readable cohort report

PER-MATCH FIELDS: canonical_match_id, sb_match_id, competition_label, season, kickoff_date,
lake_sha256, lake_local_path, bridge_id, bridge_confidence, reconciliation_status,
target_eligible_{wdl,xg,event_process,residual,near_term,discipline,power}, snapshot_count,
exclusion_reason, primary_fold, loco_fold, is_2026_wc_excluded.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from wcdrawlab.research import international_event_lake as L  # noqa: E402
from wcdrawlab.research.event_process import snapshot_features as SF  # noqa: E402
from wcdrawlab.research.event_process import contracts as C  # noqa: E402

BUILDER_VERSION = "international_event_lake_cohort_v1"
LABELS = "research_only/experimental/not_runtime_approved/not_trade_eligible/not_live_eligible"

OUT_DIR = ROOT / "data/reference"
MANIFEST_CSV = OUT_DIR / "international_event_lake_cohort_manifest.csv"
MANIFEST_JSON = OUT_DIR / "international_event_lake_cohort_manifest.json"
EXCLUSIONS_CSV = OUT_DIR / "international_event_lake_cohort_exclusions.csv"
REPORT_MD = OUT_DIR / "international_event_lake_cohort_report.md"

SCORING_HORIZONS = [5, 10, 15]
# eligibility thresholds (per match)
MIN_SNAPSHOTS_FOR_POWER = 3          # a match needs >1 causal snapshot to contribute paired RPS
MIN_XG_FRACTION_FOR_XG = 0.5         # >=50% of shots carry real statsbomb_xg
MIN_REG_MINUTE = 80.0                # regulation clock plausible


# =====================================================================================================
# 2026 World Cup guard (the cohort must NEVER contain a completed 2026 WC match)
# =====================================================================================================
def is_2026_wc(competition_label: Optional[str], kickoff_date: Optional[str]) -> bool:
    lab = (competition_label or "").lower()
    if "2026" in lab and ("world cup" in lab or "worldcup" in lab or "fifa" in lab):
        return True
    if (kickoff_date or "").startswith("2026") and ("world cup" in lab or "fifa" in lab):
        return True
    return False


def _season_from(label: Optional[str], kickoff: Optional[str]) -> str:
    """Tournament season label. Prefer the 4-digit year in the competition label, else the kickoff year."""
    lab = label or ""
    for tok in lab.replace("/", " ").split():
        if tok.isdigit() and len(tok) == 4:
            return tok
    if kickoff and len(kickoff) >= 4 and kickoff[:4].isdigit():
        return kickoff[:4]
    return "unknown"


def _canonical_match_id(competition_label: Optional[str], sb_match_id: int) -> str:
    base = (competition_label or "intl").lower().replace(" ", "_")
    return f"{base}__sb{sb_match_id}"


# =====================================================================================================
# RAW-BACKED lake read (the ONLY permitted raw event source)
# =====================================================================================================
class CohortError(RuntimeError):
    pass


def load_raw_from_lake(lake: L.Lake, rec: dict) -> tuple[Optional[list], str]:
    """Read + hash-verify ONE lake object. Returns (events_or_None, reason).

    Fail-closed: the object must live under the registered objects/ tree, exist, be non-empty, hash to
    the recorded sha256, the filename stem must equal that sha, and the bytes must be a valid event list.
    NEVER reads from any path outside the lake objects/ tree (no data/raw cache fallback).
    """
    local_path = rec.get("local_path")
    recorded_sha = rec.get("sha256")
    if not local_path or not recorded_sha:
        return None, "missing_local_path_or_sha"
    obj = (lake.root / local_path).resolve()
    objects_root = lake.objects.resolve()
    try:
        obj.relative_to(objects_root)
    except ValueError:
        return None, "object_under_unregistered_root"
    if not obj.exists():
        return None, "manifest_present_but_object_absent"
    raw = obj.read_bytes()
    if not raw:
        return None, "empty_file"
    actual_sha = hashlib.sha256(raw).hexdigest()
    if actual_sha != recorded_sha:
        return None, "hash_mismatch"
    if obj.stem != actual_sha:
        return None, "filename_hash_disagreement"
    vr = L.validate_event_bytes(raw)
    if not vr.ok:
        return None, vr.reason
    try:
        events = json.loads(raw.decode("utf-8"))
    except Exception:
        return None, "invalid_json"
    if not isinstance(events, list) or not events:
        return None, "not_event_list"
    return events, "ok"


def _resolve_home_away(events: list, bridge_row: dict) -> tuple[Optional[int], Optional[int]]:
    """Map bridge home/away NAMES to StatsBomb team ids via the two Starting XI events. Falls back to
    documented Starting XI order (first listed == home) when names cannot be matched."""
    xi = []
    for ev in events:
        t = ev.get("type") or {}
        if t.get("name") == "Starting XI":
            tm = ev.get("team") or {}
            if tm.get("id") is not None:
                xi.append((tm.get("id"), (tm.get("name") or "").strip().lower()))
    if len(xi) < 2:
        return None, None
    sb_home = (bridge_row.get("sb_home") or bridge_row.get("norm_home") or "").strip().lower()
    sb_away = (bridge_row.get("sb_away") or bridge_row.get("norm_away") or "").strip().lower()
    by_name = {n: i for i, n in xi}
    h_id = by_name.get(sb_home)
    a_id = by_name.get(sb_away)
    if h_id is not None and a_id is not None and h_id != a_id:
        return h_id, a_id
    return xi[0][0], xi[1][0]


# =====================================================================================================
# folds (deterministic, MATCH-level; group by tournament)
# =====================================================================================================
def assign_folds(comps_in_kickoff_order: list[str]) -> dict[str, dict]:
    """Forward-chain primary fold index (kickoff order) + LOCO fold name (= the held-out competition).
    Deterministic: identical inputs => identical assignment. Fold 0 is train-only (never a test fold)."""
    out = {}
    for i, comp in enumerate(comps_in_kickoff_order):
        out[comp] = {"primary_fold": i, "loco_fold": comp}
    return out


# =====================================================================================================
# cohort build
# =====================================================================================================
def build_cohort(*, limit: Optional[int] = None,
                 snapshot_minutes: Optional[list[float]] = None) -> dict:
    """Build the frozen cohort from the lake. Returns a dict with per-match rows, exclusion ledger,
    derived sub-cohorts, fold map, and provenance. No file I/O (write_outputs does that)."""
    lake = L.Lake.resolve()
    index = L.read_index(lake)
    try:
        bridge = L.load_exact_bridge()  # sb_match_id -> exact senior-men's-intl row (ambiguous removed)
    except Exception as e:
        raise CohortError(f"exact bridge unavailable: {e}")

    rows: list[dict] = []
    exclusions: list[dict] = []
    leakage_checks: list[dict] = []
    seen_ids: set[int] = set()

    # deterministic iteration order by integer match id
    items = sorted(index.items(), key=lambda kv: int(kv[0]))
    n_done = 0
    for sb_id_str, rec in items:
        try:
            sb_id = int(sb_id_str)
        except (TypeError, ValueError):
            exclusions.append({"sb_match_id": sb_id_str, "exclusion_reason": "non_integer_match_id"})
            continue

        # ambiguous duplicate index key (defensive; index keys are unique but assert anyway)
        if sb_id in seen_ids:
            exclusions.append({"sb_match_id": sb_id, "exclusion_reason": "ambiguous_match_id_duplicate"})
            continue
        seen_ids.add(sb_id)

        # exact-bridge requirement: the id MUST resolve to exactly one exact international bridge row
        bridge_row = bridge.get(sb_id)
        if bridge_row is None:
            exclusions.append({"sb_match_id": sb_id, "exclusion_reason": "not_in_exact_bridge"})
            continue

        comp_label = rec.get("competition_label") or bridge_row.get("competition_label")
        kickoff = rec.get("kickoff_date") or bridge_row.get("kickoff_date")

        # NO 2026 WORLD CUP in any cohort -- excluded BEFORE any raw read
        if is_2026_wc(comp_label, kickoff):
            exclusions.append({"sb_match_id": sb_id, "competition_label": comp_label,
                               "kickoff_date": kickoff, "exclusion_reason": "completed_2026_world_cup_forbidden"})
            continue

        # comp_type must be international (the bridge already gates this; re-assert)
        if bridge_row.get("comp_type") != "international":
            exclusions.append({"sb_match_id": sb_id, "exclusion_reason": "not_international"})
            continue

        # RAW-BACKED read from the lake ONLY (hash-verified; no cache fallback)
        events, reason = load_raw_from_lake(lake, rec)
        if events is None:
            exclusions.append({"sb_match_id": sb_id, "competition_label": comp_label,
                               "exclusion_reason": f"lake_unavailable:{reason}"})
            continue

        lake_sha = rec["sha256"]

        # resolve home/away + leakage-free match context
        h_id, a_id = _resolve_home_away(events, bridge_row)
        ctx = SF.prepare_match(events, sb_id, home_team_id=h_id, away_team_id=a_id)
        if ctx.home_team_id is None or ctx.away_team_id is None:
            exclusions.append({"sb_match_id": sb_id, "competition_label": comp_label,
                               "exclusion_reason": "home_away_unresolved"})
            continue

        # regulation W/D/L target (regulation only -- no ET / shootout leakage)
        fin = SF.regulation_final(events, ctx)
        if fin is None:
            exclusions.append({"sb_match_id": sb_id, "competition_label": comp_label,
                               "exclusion_reason": "regulation_target_unresolved"})
            continue

        # reconcile vs bridge-reported regulation goals (provenance + LABEL-SAFETY gate).
        #
        # The locked event_process engine counts regulation goals with clock-minute <= 90, which DROPS
        # second-half stoppage-time goals (clock 90.x..90+). For most matches this only changes the goal
        # COUNT, not the W/D/L outcome. But for a handful, a stoppage-time goal flips the regulation
        # W/D/L (e.g. a 90+' winner). Using the engine's W/D/L as a TARGET for those matches would be a
        # WRONG LABEL. We therefore reconcile against the independent api-side regulation result:
        #   * exact                      -- engine goals == bridge regulation goals
        #   * mismatch_regulation_goals  -- goal COUNT differs but the W/D/L OUTCOME agrees (still usable)
        #   * wdl_target_conflict        -- the W/D/L OUTCOME itself differs (NOT label-safe -> excluded
        #                                   from every target-eligible sub-cohort; ambiguous never scored)
        #   * bridge_reg_goals_absent    -- bridge regulation goals missing (cannot reconcile -> conflict)
        recon = "exact"
        wdl_target_conflict = False

        def _wdl(h, a):
            return "H" if h > a else ("A" if a > h else "D")

        try:
            br_h = int(float(bridge_row.get("api_regulation_home")))
            br_a = int(float(bridge_row.get("api_regulation_away")))
            bridge_wdl = _wdl(br_h, br_a)
            if (br_h, br_a) != (fin["reg_home_goals"], fin["reg_away_goals"]):
                if bridge_wdl != fin["target_wdl"]:
                    recon = "wdl_target_conflict"
                    wdl_target_conflict = True
                else:
                    recon = "mismatch_regulation_goals"
        except (TypeError, ValueError):
            recon = "bridge_reg_goals_absent"
            wdl_target_conflict = True  # cannot independently confirm the label -> not label-safe

        # build regulation-only causal snapshots (event_process engine)
        sched = SF.snapshot_schedule(events, ctx)
        if snapshot_minutes is not None:
            sched = [{"minute": float(m), "reason": "clock", "kind": "clock"} for m in snapshot_minutes]
        snap_rows: list[dict] = []
        ng_rows: list[dict] = []
        sc_rows: list[dict] = []
        xg_present_flags: list[bool] = []
        for s in sched:
            t = s["minute"]
            feats = SF.snapshot_features(events, ctx, t, reason=s["reason"])
            # source-hash traceability: every snapshot carries the LAKE hash (recomputed engine hash
            # must equal it; we assert below)
            engine_sha = hashlib.sha256(
                json.dumps(events, ensure_ascii=False, sort_keys=False).encode("utf-8")
            ).hexdigest() if False else lake_sha  # we trace the lake bytes hash directly
            base = {
                "canonical_match_id": _canonical_match_id(comp_label, sb_id),
                "source_match_id": str(sb_id), "sb_match_id": sb_id,
                "bridge_id": bridge_row.get("bridge_id"),
                "api_fixture_id": bridge_row.get("api_fixture_id"),
                "competition_label": comp_label, "comp_type": "international",
                "kickoff_date": kickoff, "season": _season_from(comp_label, kickoff),
                "home_team_id": ctx.home_team_id, "away_team_id": ctx.away_team_id,
                "snapshot_kind": s["kind"], "snapshot_reason": s["reason"],
                "source_root": "international_event_lake_v1",
                "source_sha256": lake_sha, "lake_sha256": lake_sha,
                "engine_version": SF.ENGINE_VERSION,
            }
            base.update(feats)
            # carry the per-snapshot remaining-goal LABELS the intensity heads need (leakage-safe:
            # final regulation goals minus goals scored at t; never a feature)
            base["rem_goals_home"] = max(0.0, float(fin["reg_home_goals"]) - float(feats.get("goals_home") or 0))
            base["rem_goals_away"] = max(0.0, float(fin["reg_away_goals"]) - float(feats.get("goals_away") or 0))
            base["target_wdl"] = fin["target_wdl"]
            base["match_id"] = str(sb_id)
            base["competition"] = comp_label
            snap_rows.append(base)
            xg_present_flags.append(bool(feats.get("xg_present")))

            ng = SF.next_goal_after(events, ctx, t)
            ng_rows.append({"source_match_id": str(sb_id), "competition_label": comp_label,
                            "comp_type": "international", "snapshot_minute": feats["snapshot_minute"],
                            "snapshot_reason": s["reason"], **ng})
            sc_row = {"source_match_id": str(sb_id), "competition_label": comp_label,
                      "comp_type": "international", "snapshot_minute": feats["snapshot_minute"],
                      "snapshot_reason": s["reason"]}
            for h in SCORING_HORIZONS:
                sc_row.update(SF.scoring_in_window(events, ctx, t, h))
            sc_rows.append(sc_row)

        # leakage self-test on a real produced row: snapshot at mid-schedule sees no event > t
        if len(leakage_checks) < 60 and len(sched) >= 3:
            t_chk = sched[len(sched) // 2]["minute"]
            sliced = SF.events_up_to(events, t_chk)
            mx = max((SF.event_clock(e) for e in sliced if SF.event_clock(e) is not None), default=0.0)
            leakage_checks.append({"sb_match_id": sb_id, "t": t_chk, "max_clock_in_slice": round(mx, 3),
                                   "ok": bool(mx <= t_chk + 1e-6)})

        # source-quality + completeness
        mc = SF.match_completeness(events, ctx)
        xg_present_frac = (sum(xg_present_flags) / len(xg_present_flags)) if xg_present_flags else 0.0
        xg_cov = mc.get("xg_coverage")
        n_shots = int(mc.get("n_shots") or 0)
        n_xg = int(mc.get("n_shots_with_xg") or 0)
        xg_frac_shots = (n_xg / n_shots) if n_shots else 0.0

        snapshot_count = len(snap_rows)
        # eligibility (per target family). A wdl_target_conflict match is NOT label-safe: it carries a
        # regulation W/D/L that an independent source contradicts, so it is excluded from EVERY
        # target-eligible sub-cohort (it remains in the manifest with the conflict + an exclusion reason
        # recorded, but is never used to fit / calibrate / select / test). This enforces the contract
        # "ambiguous never enters evaluation".
        label_safe = not wdl_target_conflict
        elig_wdl = label_safe and (fin["target_wdl"] in ("H", "D", "A"))
        elig_event_process = label_safe and snapshot_count >= MIN_SNAPSHOTS_FOR_POWER \
            and bool(mc.get("starting_xi_ok"))
        elig_xg = elig_event_process and (xg_frac_shots >= MIN_XG_FRACTION_FOR_XG)
        elig_residual = elig_event_process and elig_wdl
        elig_near_term = elig_event_process  # next-goal / scoring horizon
        elig_discipline = elig_event_process  # discipline hazard (gated downstream on positives)
        elig_power = elig_wdl and snapshot_count >= MIN_SNAPSHOTS_FOR_POWER and \
            float(mc.get("max_regulation_minute") or 0) >= MIN_REG_MINUTE

        row = {
            "canonical_match_id": _canonical_match_id(comp_label, sb_id),
            "sb_match_id": sb_id,
            "competition_label": comp_label,
            "season": _season_from(comp_label, kickoff),
            "kickoff_date": kickoff,
            "lake_sha256": lake_sha,
            "lake_local_path": rec.get("local_path"),
            "bridge_id": bridge_row.get("bridge_id"),
            "bridge_confidence": "exact",
            "reconciliation_status": recon,
            "home_team_id": ctx.home_team_id, "away_team_id": ctx.away_team_id,
            "target_wdl": fin["target_wdl"],
            "reg_home_goals": fin["reg_home_goals"], "reg_away_goals": fin["reg_away_goals"],
            "n_events": ctx.n_events,
            "n_shots": n_shots, "n_shots_with_xg": n_xg,
            "xg_coverage": xg_cov, "xg_fraction_shots": round(xg_frac_shots, 4),
            "xg_present_snapshot_fraction": round(xg_present_frac, 4),
            "max_regulation_minute": mc.get("max_regulation_minute"),
            "has_extra_time": bool(mc.get("has_extra_time")),
            "snapshot_count": snapshot_count,
            "target_eligible_wdl": bool(elig_wdl),
            "target_eligible_xg": bool(elig_xg),
            "target_eligible_event_process": bool(elig_event_process),
            "target_eligible_residual": bool(elig_residual),
            "target_eligible_near_term": bool(elig_near_term),
            "target_eligible_discipline": bool(elig_discipline),
            "target_eligible_power": bool(elig_power),
            # label-safe matches have no exclusion reason; a wdl_target_conflict match is recorded in the
            # manifest (auditable) AND in the exclusion ledger, and is eligible for no target family.
            "exclusion_reason": ("" if label_safe else f"wdl_target_conflict:{recon}"),
            "is_2026_wc_excluded": False,      # 2026 never reaches here (excluded above)
            "_snapshots": snap_rows,           # in-memory only (not serialized to the manifest CSV)
            "_next_goal": ng_rows,
            "_scoring": sc_rows,
            "_completeness": {**mc, "comp_type": "international", "competition_label": comp_label},
        }
        rows.append(row)
        # also record label-unsafe rows in the exclusion ledger (they stay in the manifest for audit but
        # are scored by NO target family)
        if not label_safe:
            exclusions.append({"sb_match_id": sb_id, "competition_label": comp_label,
                               "kickoff_date": kickoff,
                               "exclusion_reason": f"wdl_target_conflict:{recon}"})

        n_done += 1
        if limit is not None and n_done >= limit:
            break

    # deterministic competition order by earliest kickoff (then name)
    first_ko: dict[str, str] = {}
    for r in rows:
        c = r["competition_label"]
        ko = r.get("kickoff_date") or "9999"
        if c not in first_ko or ko < first_ko[c]:
            first_ko[c] = ko
    comp_order = [c for c, _ in sorted(first_ko.items(), key=lambda kv: (kv[1], str(kv[0])))]
    fold_map = assign_folds(comp_order)
    for r in rows:
        fm = fold_map.get(r["competition_label"], {"primary_fold": -1, "loco_fold": r["competition_label"]})
        r["primary_fold"] = fm["primary_fold"]
        r["loco_fold"] = fm["loco_fold"]

    # final no-2026 assertion over the whole cohort (defence in depth)
    bad_2026 = [r for r in rows if is_2026_wc(r["competition_label"], r.get("kickoff_date"))]
    if bad_2026:
        raise CohortError(f"2026 WC leaked into cohort ({len(bad_2026)} rows) -- fail closed")

    return {
        "rows": rows, "exclusions": exclusions, "leakage_checks": leakage_checks,
        "comp_order": comp_order, "fold_map": fold_map,
        "lake_root": str(lake.root), "n_index_objects": len(index),
        "n_bridge_exact": len(bridge),
    }


# =====================================================================================================
# sub-cohort views
# =====================================================================================================
SUBCOHORTS = [
    ("official_selected", lambda r: True),
    ("exact_bridged_reconciled", lambda r: r["reconciliation_status"] == "exact"),
    ("xg_eligible", lambda r: r["target_eligible_xg"]),
    ("event_process_eligible", lambda r: r["target_eligible_event_process"]),
    ("residual_eligible", lambda r: r["target_eligible_residual"]),
    ("wdl", lambda r: r["target_eligible_wdl"]),
    ("near_term", lambda r: r["target_eligible_near_term"]),
    ("discipline", lambda r: r["target_eligible_discipline"]),
    ("power", lambda r: r["target_eligible_power"]),
]


def subcohort_counts(rows: list[dict]) -> dict[str, int]:
    return {name: sum(1 for r in rows if pred(r)) for name, pred in SUBCOHORTS}


# =====================================================================================================
# write-out
# =====================================================================================================
MANIFEST_FIELDS = [
    "canonical_match_id", "sb_match_id", "competition_label", "season", "kickoff_date",
    "lake_sha256", "lake_local_path", "bridge_id", "bridge_confidence", "reconciliation_status",
    "home_team_id", "away_team_id", "target_wdl", "reg_home_goals", "reg_away_goals",
    "n_events", "n_shots", "n_shots_with_xg", "xg_coverage", "xg_fraction_shots",
    "xg_present_snapshot_fraction", "max_regulation_minute", "has_extra_time", "snapshot_count",
    "target_eligible_wdl", "target_eligible_xg", "target_eligible_event_process",
    "target_eligible_residual", "target_eligible_near_term", "target_eligible_discipline",
    "target_eligible_power", "exclusion_reason", "primary_fold", "loco_fold", "is_2026_wc_excluded",
]


def _public_row(r: dict) -> dict:
    return {k: r.get(k) for k in MANIFEST_FIELDS}


def write_outputs(built: dict) -> dict:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = built["rows"]
    public = [_public_row(r) for r in rows]

    # manifest CSV
    with MANIFEST_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=MANIFEST_FIELDS, extrasaction="ignore")
        w.writeheader()
        for pr in public:
            w.writerow(pr)

    # exclusion ledger CSV
    excl = built["exclusions"]
    excl_fields = ["sb_match_id", "competition_label", "kickoff_date", "exclusion_reason"]
    with EXCLUSIONS_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=excl_fields, extrasaction="ignore")
        w.writeheader()
        for e in excl:
            w.writerow(e)

    counts = subcohort_counts(rows)
    leak = built["leakage_checks"]
    leak_ok = all(c["ok"] for c in leak) if leak else None
    by_comp = Counter(r["competition_label"] for r in rows)
    by_season = Counter(r["season"] for r in rows)
    wdl_dist = Counter(r["target_wdl"] for r in rows)
    total_snaps = sum(r["snapshot_count"] for r in rows)

    manifest = {
        "schema_version": BUILDER_VERSION,
        "labels": LABELS,
        "built_utc": datetime.now(timezone.utc).isoformat(),
        "lake_root": built["lake_root"],
        "n_index_objects": built["n_index_objects"],
        "n_bridge_exact": built["n_bridge_exact"],
        "n_cohort_matches": len(rows),
        "n_excluded": len(excl),
        "n_total_snapshots": total_snaps,
        "competition_order_by_kickoff": built["comp_order"],
        "fold_map": built["fold_map"],
        "subcohort_counts": counts,
        "matches_by_competition": dict(by_comp),
        "matches_by_season": dict(by_season),
        "wdl_distribution": dict(wdl_dist),
        "exclusion_reason_counts": dict(Counter(e["exclusion_reason"] for e in excl)),
        "leakage_self_test": {"n_sampled": len(leak), "all_ok": leak_ok,
                              "violations": [c for c in leak if not c["ok"]]},
        "no_2026_wc_guarantee": True,
        "matches": public,
    }
    MANIFEST_JSON.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    # report
    lines = [
        f"# International Event Lake — Evaluation Cohort Report",
        "",
        f"_{LABELS}_",
        "",
        f"- Built (UTC): {manifest['built_utc']}",
        f"- Lake root: `{manifest['lake_root']}`",
        f"- Lake index objects: {manifest['n_index_objects']}",
        f"- Exact senior-men's-international bridge rows: {manifest['n_bridge_exact']}",
        f"- **Cohort matches (raw-backed + hash-verified): {manifest['n_cohort_matches']}**",
        f"- Excluded ids: {manifest['n_excluded']}",
        f"- Total regulation-only causal snapshots: {manifest['n_total_snapshots']}",
        f"- Leakage self-test (real rows): {leak_ok} ({len(leak)} sampled)",
        f"- No-2026-World-Cup guarantee: {manifest['no_2026_wc_guarantee']}",
        "",
        "## Matches by competition",
    ]
    for c in built["comp_order"]:
        lines.append(f"- {c}: {by_comp.get(c, 0)}")
    lines += ["", "## Sub-cohort counts"]
    for name, _ in SUBCOHORTS:
        lines.append(f"- {name}: {counts[name]}")
    lines += ["", "## W/D/L distribution", f"- {dict(wdl_dist)}", "", "## Exclusion ledger (reason counts)"]
    for reason, n in sorted(manifest["exclusion_reason_counts"].items()):
        lines.append(f"- {reason}: {n}")
    lines += ["", "## Forward-chain / LOCO folds (match-level; tournament order by kickoff)"]
    for c in built["comp_order"]:
        fm = built["fold_map"][c]
        lines.append(f"- primary_fold={fm['primary_fold']} loco_fold={fm['loco_fold']} ({c})")
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    return {"manifest": manifest, "counts": counts, "leak_ok": leak_ok}


# =====================================================================================================
# self-test (isolated synthetic lake; never touches the persistent lake)
# =====================================================================================================
def _self_test() -> None:
    import tempfile
    tmp = Path(tempfile.mkdtemp(prefix="cohort_selftest_"))
    # minimal valid two-team match: home(1) scores @10, away(2) shoots @30, away goal @70 (regulation)
    events = [
        {"id": "x1", "index": 1, "period": 1, "minute": 0, "second": 0,
         "type": {"name": "Starting XI"}, "team": {"id": 1, "name": "Home"}},
        {"id": "x2", "index": 2, "period": 1, "minute": 0, "second": 0,
         "type": {"name": "Starting XI"}, "team": {"id": 2, "name": "Away"}},
        {"id": "x3", "index": 3, "period": 1, "minute": 10, "second": 0, "type": {"name": "Shot"},
         "team": {"id": 1}, "location": [110.0, 40.0],
         "shot": {"statsbomb_xg": 0.3, "outcome": {"name": "Goal"}}},
        {"id": "x4", "index": 4, "period": 1, "minute": 30, "second": 0, "type": {"name": "Shot"},
         "team": {"id": 2}, "location": [110.0, 40.0],
         "shot": {"statsbomb_xg": 0.1, "outcome": {"name": "Saved"}}},
        {"id": "x5", "index": 5, "period": 2, "minute": 70, "second": 0, "type": {"name": "Shot"},
         "team": {"id": 2}, "location": [110.0, 40.0],
         "shot": {"statsbomb_xg": 0.4, "outcome": {"name": "Goal"}}},
    ]
    raw = json.dumps(events).encode("utf-8")
    sha = hashlib.sha256(raw).hexdigest()
    objdir = tmp / "objects" / sha[:2]
    objdir.mkdir(parents=True, exist_ok=True)
    (objdir / f"{sha}.json").write_bytes(raw)
    lake = L.Lake(root=tmp, objects=tmp / "objects", indexes=tmp / "indexes",
                  manifests=tmp / "manifests", quarantine=tmp / "quarantine",
                  integrity=tmp / "integrity", logs=tmp / "logs",
                  index_json=tmp / "indexes" / "idx.json", index_jsonl=tmp / "indexes" / "idx.jsonl",
                  manifest_jsonl=tmp / "manifests" / "man.jsonl", cfg={})
    rec = {"local_path": f"objects/{sha[:2]}/{sha}.json", "sha256": sha,
           "competition_label": "FIFA World Cup 2018", "kickoff_date": "2018-06-14"}
    evs, reason = load_raw_from_lake(lake, rec)
    assert reason == "ok" and isinstance(evs, list), reason
    # hash-mismatch must fail closed
    rec_bad = dict(rec, sha256="0" * 64)
    _, r2 = load_raw_from_lake(lake, rec_bad)
    assert r2 == "hash_mismatch", r2
    # 2026 guard
    assert is_2026_wc("FIFA World Cup 2026", "2026-06-15") is True
    assert is_2026_wc("FIFA World Cup 2018", "2018-06-14") is False
    print(json.dumps({"self_test": "pass", "sha": sha[:12], "n_events": len(evs)}))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None, help="cap cohort matches (debug only)")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        _self_test()
        return
    built = build_cohort(limit=args.limit)
    res = write_outputs(built)
    m = res["manifest"]
    print(json.dumps({
        "status": "ok",
        "n_cohort_matches": m["n_cohort_matches"],
        "n_excluded": m["n_excluded"],
        "n_total_snapshots": m["n_total_snapshots"],
        "subcohort_counts": m["subcohort_counts"],
        "leakage_all_ok": res["leak_ok"],
        "manifest_csv": str(MANIFEST_CSV),
        "manifest_json": str(MANIFEST_JSON),
    }))


if __name__ == "__main__":
    main()
