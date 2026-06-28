"""Phase 1 -- Cross-domain event-process INVENTORY (international lake + club auxiliary corpus).

research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible.

Builds a per-(competition, season, match) inventory of event-process completeness across BOTH domains
used by the hierarchical cross-domain transfer study:

  * INTERNATIONAL  -- the persistent international event lake (258 hash-verified official StatsBomb
                      international event objects). Read leakage-safely THROUGH the canonical event
                      engine (snapshot_features), so every completeness field is computed from the REAL
                      events, never imputed. This is the PRIMARY test population for transfer eval.
  * CLUB           -- the event-process auxiliary corpus (669 club matches) declared in
                      data/reference/event_process_auxiliary_manifest.json. Club rows are AUXILIARY
                      training only; they are NEVER international test rows. When the raw club event
                      objects are materialized under the statsbomb_raw aux root, their event-level
                      completeness is computed identically; when they are absent in this worktree, the
                      row is inventoried at the manifest level and its event-level completeness fields
                      are honestly flagged `raw_absent` (NEVER fabricated).

Outputs (data/reference/):
  domain_event_process_inventory.csv
  domain_event_process_inventory.json
And a human report:
  notes/research/domain_event_process_inventory_report.md

ISOLATION / SAFETY:
  * Sources resolved ONLY via the international event lake config and data_roots (no hard-coded raw
    path into the active collector checkout; data_roots fails closed on it).
  * No network / API / Odds / paid / scrape / credentials. Pure local read of verified objects.
  * Raw event JSON stays in the lake / gitignored roots; only derived completeness counts are written.
"""
from __future__ import annotations

import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

COLLECTOR_FORBIDDEN = "worldcup_draw_model_lab_FINAL"
if COLLECTOR_FORBIDDEN in str(ROOT).replace("\\", "/"):
    raise PermissionError("inventory build must not run inside the active collector checkout")

from wcdrawlab.research import data_roots as DR  # noqa: E402
from wcdrawlab.research import international_event_lake as LAKE  # noqa: E402
from wcdrawlab.research.event_process import snapshot_features as SF  # noqa: E402

REF = ROOT / "data" / "reference"
NOTES = ROOT / "notes" / "research"
AUX_MANIFEST = REF / "event_process_auxiliary_manifest.json"
COHORT_MANIFEST = REF / "international_event_lake_cohort_manifest.csv"

INVENTORY_SCHEMA = "domain_event_process_inventory_v1"

# Capabilities we summarize at the match level (subset of contracts.CAPABILITIES that the snapshot
# engine's source_quality_report populates). Kept explicit so an absent capability is auditable.
CAP_KEYS = (
    "possession_structure", "territory_thirds", "box_entries", "field_tilt",
    "attack_phase", "pressure", "recoveries", "turnovers", "blocks_clearances",
    "shot_events", "shot_xg", "shot_location", "shot_freeze_frame", "cards",
)


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _season_from_label(label: str) -> str:
    """Extract a 4-digit season/edition year from an international competition label, else ''."""
    if not label:
        return ""
    for tok in label.replace("/", " ").split():
        if tok.isdigit() and len(tok) == 4:
            return tok
    return ""


def _quality_grade(*, regulation_clock_ok: bool, starting_xi_ok: bool,
                   xg_coverage: str, n_events: int, snapshot_count: int) -> str:
    """A coarse, transparent per-match quality grade. Deterministic; never tuned to outcomes.

      A : full regulation clock + Starting XI + verified xG + rich event stream + snapshots.
      B : full regulation clock + Starting XI but xG only partial OR thinner event stream.
      C : structurally usable but missing one of {regulation clock, Starting XI} or very thin.
      D : event-level completeness not derivable here (raw absent) -> manifest-only inventory.
    """
    if n_events <= 0:
        return "D"
    if not (regulation_clock_ok and starting_xi_ok):
        return "C"
    if xg_coverage == "available_verified" and n_events >= 1500 and snapshot_count >= 10:
        return "A"
    if xg_coverage in ("available_verified", "available_partial") and n_events >= 800:
        return "B"
    return "C"


# =================================================================================================
# INTERNATIONAL domain -- read every lake object through the engine (REAL completeness)
# =================================================================================================
def _load_cohort_index() -> dict[int, dict]:
    """sb_match_id -> cohort manifest row (provides competition/season/date/targets/folds)."""
    out: dict[int, dict] = {}
    if not COHORT_MANIFEST.exists():
        return out
    with COHORT_MANIFEST.open("r", encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            try:
                out[int(row["sb_match_id"])] = row
            except (KeyError, ValueError):
                continue
    return out


def inventory_international() -> tuple[list[dict], dict]:
    lake = LAKE.Lake.resolve()
    index = LAKE.read_index(lake)
    cohort = _load_cohort_index()
    rows: list[dict] = []
    n_read = n_missing = 0
    for sb_id_str, rec in index.items():
        try:
            sb_id = int(sb_id_str)
        except (TypeError, ValueError):
            continue
        obj = (lake.root / rec["local_path"]) if rec.get("local_path") else None
        comp_label = rec.get("competition_label") or ""
        cm = cohort.get(sb_id, {})
        if obj is None or not obj.exists():
            n_missing += 1
            rows.append(_intl_row_absent(sb_id, comp_label, rec, cm, reason="lake_object_absent"))
            continue
        try:
            events = json.loads(obj.read_text(encoding="utf-8"))
        except Exception as exc:  # pragma: no cover - defensive
            n_missing += 1
            rows.append(_intl_row_absent(sb_id, comp_label, rec, cm, reason=f"unreadable:{type(exc).__name__}"))
            continue
        ctx = SF.prepare_match(events, str(sb_id))
        mc = SF.match_completeness(events, ctx)
        sched = SF.snapshot_schedule(events, ctx)
        sqr = SF.source_quality_report(events, ctx)
        caps = {k: (sqr.capabilities.get(k) or {}).get("quality") for k in CAP_KEYS}
        n_yellow = sum(1 for e in events if SF._card_name(e) == SF.CARD_YELLOW)
        n_red = sum(1 for e in events if SF._card_name(e) in SF.SENDING_OFF)
        n_sub = sum(1 for e in events if SF._type_name(e) == SF.T_SUB)
        n_pressure = sum(1 for e in events if SF._type_name(e) == SF.T_PRESSURE)
        n_setpiece = sum(1 for e in events if SF._type_name(e) == SF.T_PASS
                         and ((e.get("pass") or {}).get("type") or {}).get("name") in ("Corner", "Free Kick"))
        has_loc = any(isinstance(e.get("location"), (list, tuple)) for e in events)
        grade = _quality_grade(
            regulation_clock_ok=mc["regulation_clock_ok"], starting_xi_ok=mc["starting_xi_ok"],
            xg_coverage=mc["xg_coverage"], n_events=mc["n_events"], snapshot_count=len(sched),
        )
        n_read += 1
        rows.append({
            "domain": "international",
            "competition": comp_label,
            "season": cm.get("season") or _season_from_label(comp_label),
            "match_id": str(sb_id),
            "sb_match_id": sb_id,
            "match_date": rec.get("kickoff_date") or cm.get("kickoff_date") or "",
            "home": rec.get("norm_home") or "",
            "away": rec.get("norm_away") or "",
            "source_sha256": rec.get("sha256") or "",
            "source_present": True,
            "source_reason": "lake_object_read",
            # structural completeness (REAL)
            "n_events": mc["n_events"],
            "starting_xi_ok": bool(mc["starting_xi_ok"]),
            "max_regulation_minute": mc["max_regulation_minute"],
            "has_extra_time": bool(mc["has_extra_time"]),
            "regulation_clock_ok": bool(mc["regulation_clock_ok"]),
            "n_half_start_events": mc["n_half_start_events"],
            "n_half_end_events": mc["n_half_end_events"],
            "n_shots": mc["n_shots"],
            "n_shots_with_xg": mc["n_shots_with_xg"],
            "xg_coverage": mc["xg_coverage"],
            "xg_available": bool(mc["n_shots_with_xg"] > 0),
            "possession_available": caps.get("possession_structure") == "available_verified",
            "location_available": bool(has_loc),
            "pressure_available": bool(n_pressure > 0),
            "n_pressure_events": n_pressure,
            "n_set_piece_deliveries": n_setpiece,
            "set_piece_available": bool(n_setpiece > 0),
            "n_yellow_cards": n_yellow,
            "n_red_cards": n_red,
            "cards_available": caps.get("cards") in ("available_verified", "available_partial"),
            "n_substitutions": n_sub,
            "sub_available": bool(n_sub > 0),
            "snapshot_count": len(sched),
            # eligibility (regulation-grade for the transfer test population)
            "regulation_eligible": bool(mc["regulation_clock_ok"] and mc["starting_xi_ok"]),
            "target_eligible_wdl": _cm_bool(cm, "target_eligible_wdl", default=mc["starting_xi_ok"]),
            "target_eligible_event_process": _cm_bool(cm, "target_eligible_event_process", default=True),
            "is_2026_wc_excluded": _cm_bool(cm, "is_2026_wc_excluded", default=False),
            "primary_fold": cm.get("primary_fold", ""),
            "loco_fold": cm.get("loco_fold", comp_label),
            "quality_grade": grade,
            **{f"cap_{k}": caps.get(k) for k in CAP_KEYS},
        })
    summary = {
        "domain": "international",
        "objects_indexed": len(index),
        "objects_read": n_read,
        "objects_absent_or_unreadable": n_missing,
        "lake_root": str(lake.root),
    }
    return rows, summary


def _cm_bool(cm: dict, key: str, default: bool) -> bool:
    v = cm.get(key)
    if v is None or v == "":
        return bool(default)
    return str(v).strip().lower() in ("true", "1", "yes")


def _intl_row_absent(sb_id, comp_label, rec, cm, reason) -> dict:
    base = {f"cap_{k}": "raw_absent" for k in CAP_KEYS}
    return {
        "domain": "international",
        "competition": comp_label,
        "season": cm.get("season") or _season_from_label(comp_label),
        "match_id": str(sb_id),
        "sb_match_id": sb_id,
        "match_date": rec.get("kickoff_date") or "",
        "home": rec.get("norm_home") or "",
        "away": rec.get("norm_away") or "",
        "source_sha256": rec.get("sha256") or "",
        "source_present": False,
        "source_reason": reason,
        "n_events": 0, "starting_xi_ok": False, "max_regulation_minute": None,
        "has_extra_time": None, "regulation_clock_ok": False,
        "n_half_start_events": None, "n_half_end_events": None,
        "n_shots": None, "n_shots_with_xg": None, "xg_coverage": "raw_absent",
        "xg_available": None, "possession_available": None, "location_available": None,
        "pressure_available": None, "n_pressure_events": None,
        "n_set_piece_deliveries": None, "set_piece_available": None,
        "n_yellow_cards": None, "n_red_cards": None, "cards_available": None,
        "n_substitutions": None, "sub_available": None, "snapshot_count": None,
        "regulation_eligible": False,
        "target_eligible_wdl": _cm_bool(cm, "target_eligible_wdl", default=False),
        "target_eligible_event_process": _cm_bool(cm, "target_eligible_event_process", default=False),
        "is_2026_wc_excluded": _cm_bool(cm, "is_2026_wc_excluded", default=False),
        "primary_fold": cm.get("primary_fold", ""),
        "loco_fold": cm.get("loco_fold", comp_label),
        "quality_grade": "D",
        **base,
    }


# =================================================================================================
# CLUB domain -- auxiliary corpus. Event-level completeness only when raw objects are materialized.
# =================================================================================================
def _find_club_event_file(match_id: str) -> Path | None:
    """Resolve a club event JSON from the aux roots IF materialized. Never downloads. Returns None
    when the corpus is not present in this worktree (the honest, common case)."""
    candidates: list[Path] = []
    for root_name in ("statsbomb_raw", "statsbomb_raw_prior"):
        try:
            base = DR.get_root(root_name)
        except Exception:
            continue
        candidates.append(base / "event_process_auxiliary" / f"{match_id}.json")
        candidates.append(base / "event_process_auxiliary" / "events" / f"{match_id}.json")
        candidates.append(base / "events" / f"{match_id}.json")
    for p in candidates:
        try:
            if p.exists():
                return p
        except Exception:
            continue
    return None


def inventory_club() -> tuple[list[dict], dict]:
    if not AUX_MANIFEST.exists():
        return [], {"domain": "club", "fixtures_declared": 0, "events_materialized": 0,
                    "reason": "aux_manifest_absent"}
    doc = json.loads(AUX_MANIFEST.read_text(encoding="utf-8"))
    fixtures = doc.get("fixtures", [])
    rows: list[dict] = []
    n_mat = 0
    for fx in fixtures:
        match_id = str(fx.get("match_id"))
        comp = fx.get("competition") or ""
        season = fx.get("season") or ""
        path = _find_club_event_file(match_id)
        if path is not None:
            try:
                events = json.loads(path.read_text(encoding="utf-8"))
                rows.append(_club_row_present(fx, events, path))
                n_mat += 1
                continue
            except Exception:
                pass
        rows.append(_club_row_absent(fx))
    summary = {
        "domain": "club",
        "fixtures_declared": len(fixtures),
        "events_materialized": n_mat,
        "events_absent": len(fixtures) - n_mat,
        "aux_roots_checked": ["statsbomb_raw/event_process_auxiliary", "statsbomb_raw_prior/event_process_auxiliary"],
        "note": ("club raw event objects are NOT materialized in this worktree; event-level "
                 "completeness flagged raw_absent (manifest-level inventory only)") if n_mat == 0 else
                f"{n_mat}/{len(fixtures)} club event objects materialized",
    }
    return rows, summary


def _club_row_present(fx: dict, events: list, path: Path) -> dict:
    match_id = str(fx.get("match_id"))
    ctx = SF.prepare_match(events, match_id)
    mc = SF.match_completeness(events, ctx)
    sched = SF.snapshot_schedule(events, ctx)
    sqr = SF.source_quality_report(events, ctx)
    caps = {k: (sqr.capabilities.get(k) or {}).get("quality") for k in CAP_KEYS}
    n_yellow = sum(1 for e in events if SF._card_name(e) == SF.CARD_YELLOW)
    n_red = sum(1 for e in events if SF._card_name(e) in SF.SENDING_OFF)
    n_sub = sum(1 for e in events if SF._type_name(e) == SF.T_SUB)
    n_pressure = sum(1 for e in events if SF._type_name(e) == SF.T_PRESSURE)
    n_setpiece = sum(1 for e in events if SF._type_name(e) == SF.T_PASS
                     and ((e.get("pass") or {}).get("type") or {}).get("name") in ("Corner", "Free Kick"))
    has_loc = any(isinstance(e.get("location"), (list, tuple)) for e in events)
    grade = _quality_grade(
        regulation_clock_ok=mc["regulation_clock_ok"], starting_xi_ok=mc["starting_xi_ok"],
        xg_coverage=mc["xg_coverage"], n_events=mc["n_events"], snapshot_count=len(sched),
    )
    return {
        "domain": "club",
        "competition": fx.get("competition") or "",
        "season": fx.get("season") or "",
        "match_id": match_id,
        "sb_match_id": None,
        "match_date": fx.get("match_date") or "",
        "home": fx.get("home") or "",
        "away": fx.get("away") or "",
        "source_sha256": "",
        "source_present": True,
        "source_reason": "aux_event_object_read",
        "n_events": mc["n_events"],
        "starting_xi_ok": bool(mc["starting_xi_ok"]),
        "max_regulation_minute": mc["max_regulation_minute"],
        "has_extra_time": bool(mc["has_extra_time"]),
        "regulation_clock_ok": bool(mc["regulation_clock_ok"]),
        "n_half_start_events": mc["n_half_start_events"],
        "n_half_end_events": mc["n_half_end_events"],
        "n_shots": mc["n_shots"],
        "n_shots_with_xg": mc["n_shots_with_xg"],
        "xg_coverage": mc["xg_coverage"],
        "xg_available": bool(mc["n_shots_with_xg"] > 0),
        "possession_available": caps.get("possession_structure") == "available_verified",
        "location_available": bool(has_loc),
        "pressure_available": bool(n_pressure > 0),
        "n_pressure_events": n_pressure,
        "n_set_piece_deliveries": n_setpiece,
        "set_piece_available": bool(n_setpiece > 0),
        "n_yellow_cards": n_yellow,
        "n_red_cards": n_red,
        "cards_available": caps.get("cards") in ("available_verified", "available_partial"),
        "n_substitutions": n_sub,
        "sub_available": bool(n_sub > 0),
        "snapshot_count": len(sched),
        # CLUB rows are auxiliary-only: NEVER eligible as an international test row.
        "regulation_eligible": bool(mc["regulation_clock_ok"] and mc["starting_xi_ok"]),
        "target_eligible_wdl": False,
        "target_eligible_event_process": False,
        "is_2026_wc_excluded": False,
        "primary_fold": "",
        "loco_fold": fx.get("competition") or "",
        "quality_grade": grade,
        **{f"cap_{k}": caps.get(k) for k in CAP_KEYS},
    }


def _club_row_absent(fx: dict) -> dict:
    base = {f"cap_{k}": "raw_absent" for k in CAP_KEYS}
    return {
        "domain": "club",
        "competition": fx.get("competition") or "",
        "season": fx.get("season") or "",
        "match_id": str(fx.get("match_id")),
        "sb_match_id": None,
        "match_date": fx.get("match_date") or "",
        "home": fx.get("home") or "",
        "away": fx.get("away") or "",
        "source_sha256": "",
        "source_present": False,
        "source_reason": "club_raw_absent_in_worktree",
        "n_events": 0, "starting_xi_ok": None, "max_regulation_minute": None,
        "has_extra_time": None, "regulation_clock_ok": None,
        "n_half_start_events": None, "n_half_end_events": None,
        "n_shots": None, "n_shots_with_xg": None, "xg_coverage": "raw_absent",
        "xg_available": None, "possession_available": None, "location_available": None,
        "pressure_available": None, "n_pressure_events": None,
        "n_set_piece_deliveries": None, "set_piece_available": None,
        "n_yellow_cards": None, "n_red_cards": None, "cards_available": None,
        "n_substitutions": None, "sub_available": None, "snapshot_count": None,
        "regulation_eligible": None,
        "target_eligible_wdl": False,
        "target_eligible_event_process": False,
        "is_2026_wc_excluded": False,
        "primary_fold": "",
        "loco_fold": fx.get("competition") or "",
        "quality_grade": "D",
        **base,
    }


# =================================================================================================
# roll-ups + writers
# =================================================================================================
def _per_group_rollup(rows: list[dict]) -> list[dict]:
    """(domain, competition, season) roll-up: counts + completeness coverage."""
    from collections import defaultdict
    agg: dict[tuple, dict] = defaultdict(lambda: {
        "n_matches": 0, "n_source_present": 0, "n_regulation_eligible": 0,
        "n_xg_verified": 0, "n_xg_partial": 0, "n_possession": 0, "n_pressure": 0,
        "n_set_piece": 0, "n_cards": 0, "n_subs": 0,
        "grade_A": 0, "grade_B": 0, "grade_C": 0, "grade_D": 0, "snapshots_total": 0,
    })
    for r in rows:
        key = (r["domain"], r["competition"], r["season"])
        a = agg[key]
        a["n_matches"] += 1
        a["n_source_present"] += 1 if r.get("source_present") else 0
        a["n_regulation_eligible"] += 1 if r.get("regulation_eligible") else 0
        if r.get("xg_coverage") == "available_verified":
            a["n_xg_verified"] += 1
        elif r.get("xg_coverage") == "available_partial":
            a["n_xg_partial"] += 1
        a["n_possession"] += 1 if r.get("possession_available") else 0
        a["n_pressure"] += 1 if r.get("pressure_available") else 0
        a["n_set_piece"] += 1 if r.get("set_piece_available") else 0
        a["n_cards"] += 1 if r.get("cards_available") else 0
        a["n_subs"] += 1 if r.get("sub_available") else 0
        a[f"grade_{r.get('quality_grade', 'D')}"] += 1
        a["snapshots_total"] += int(r.get("snapshot_count") or 0)
    out = []
    for (domain, comp, season), a in sorted(agg.items()):
        out.append({"domain": domain, "competition": comp, "season": season, **a})
    return out


def main() -> int:
    REF.mkdir(parents=True, exist_ok=True)
    NOTES.mkdir(parents=True, exist_ok=True)

    intl_rows, intl_summary = inventory_international()
    club_rows, club_summary = inventory_club()
    rows = intl_rows + club_rows
    groups = _per_group_rollup(rows)

    # CSV
    fieldnames = list(rows[0].keys()) if rows else []
    csv_path = REF / "domain_event_process_inventory.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)

    # JSON
    payload = {
        "schema_version": INVENTORY_SCHEMA,
        "generated_ts": _utc(),
        "labels": ["research_only", "experimental", "not_runtime_approved",
                   "not_trade_eligible", "not_live_eligible"],
        "domains": {"international": intl_summary, "club": club_summary},
        "totals": {
            "n_rows": len(rows),
            "international_matches": len(intl_rows),
            "club_matches": len(club_rows),
            "international_source_present": sum(1 for r in intl_rows if r.get("source_present")),
            "club_source_present": sum(1 for r in club_rows if r.get("source_present")),
        },
        "per_group_rollup": groups,
        "rows": rows,
    }
    json_path = REF / "domain_event_process_inventory.json"
    json_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    _write_report(payload, intl_summary, club_summary, groups, intl_rows, club_rows)
    print(json.dumps({
        "status": "complete",
        "csv": str(csv_path),
        "json": str(json_path),
        "international_read": intl_summary.get("objects_read"),
        "club_declared": club_summary.get("fixtures_declared"),
        "club_materialized": club_summary.get("events_materialized"),
    }))
    return 0


def _write_report(payload, intl_summary, club_summary, groups, intl_rows, club_rows) -> None:
    from collections import Counter
    lines: list[str] = []
    A = lines.append
    A("# Domain Event-Process Inventory Report (Phase 1)")
    A("")
    A("_research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible_")
    A("")
    A(f"Generated: {payload['generated_ts']}")
    A("")
    A("## Scope")
    A("")
    A("Inventory of event-process completeness across the two domains of the hierarchical "
      "cross-domain transfer study. INTERNATIONAL is the PRIMARY (and only) test population; CLUB is "
      "AUXILIARY training only and is never used as an international test row.")
    A("")
    A("## Domain summaries")
    A("")
    A("### International (persistent event lake)")
    A("")
    A(f"- lake root: `{intl_summary.get('lake_root')}`")
    A(f"- objects indexed: **{intl_summary.get('objects_indexed')}**")
    A(f"- objects read through the engine (REAL completeness): **{intl_summary.get('objects_read')}**")
    A(f"- objects absent/unreadable: {intl_summary.get('objects_absent_or_unreadable')}")
    A("")
    # competition breakdown
    comp_counts = Counter(r["competition"] for r in intl_rows)
    A("Per-competition (international):")
    A("")
    A("| competition | matches | regulation-eligible | xG verified | possession | pressure | snapshots |")
    A("|---|---:|---:|---:|---:|---:|---:|")
    for g in groups:
        if g["domain"] != "international":
            continue
        A(f"| {g['competition']} {g['season']} | {g['n_matches']} | {g['n_regulation_eligible']} | "
          f"{g['n_xg_verified']} | {g['n_possession']} | {g['n_pressure']} | {g['snapshots_total']} |")
    A("")
    A("### Club (event-process auxiliary corpus)")
    A("")
    A(f"- fixtures declared in aux manifest: **{club_summary.get('fixtures_declared')}**")
    A(f"- club event objects materialized in this worktree: **{club_summary.get('events_materialized')}**")
    A(f"- note: {club_summary.get('note')}")
    A("")
    club_comp = Counter(r["competition"] for r in club_rows)
    A("Per-competition (club, manifest-level):")
    A("")
    A("| competition | matches | seasons | event objects present |")
    A("|---|---:|---:|---:|")
    # group by competition aggregating seasons
    from collections import defaultdict
    cc = defaultdict(lambda: {"matches": 0, "seasons": set(), "present": 0})
    for r in club_rows:
        d = cc[r["competition"]]
        d["matches"] += 1
        d["seasons"].add(r["season"])
        d["present"] += 1 if r.get("source_present") else 0
    for comp, d in sorted(cc.items(), key=lambda kv: -kv[1]["matches"]):
        A(f"| {comp} | {d['matches']} | {len(d['seasons'])} | {d['present']} |")
    A("")
    A("## Quality-grade distribution")
    A("")
    grade_intl = Counter(r["quality_grade"] for r in intl_rows)
    grade_club = Counter(r["quality_grade"] for r in club_rows)
    A("| grade | international | club | meaning |")
    A("|---|---:|---:|---|")
    meanings = {
        "A": "full clock + XI + verified xG + rich stream + snapshots",
        "B": "full clock + XI, partial xG or thinner stream",
        "C": "usable but missing clock/XI or very thin",
        "D": "event-level completeness not derivable here (raw absent)",
    }
    for gr in ("A", "B", "C", "D"):
        A(f"| {gr} | {grade_intl.get(gr, 0)} | {grade_club.get(gr, 0)} | {meanings[gr]} |")
    A("")
    A("## Stable-completeness headline (international)")
    A("")
    present = [r for r in intl_rows if r.get("source_present")]
    n = len(present) or 1
    A(f"- matches with verified xG coverage: {sum(1 for r in present if r['xg_coverage'] == 'available_verified')}/{len(present)}")
    A(f"- matches with possession structure: {sum(1 for r in present if r.get('possession_available'))}/{len(present)}")
    A(f"- matches with pressure events: {sum(1 for r in present if r.get('pressure_available'))}/{len(present)}")
    A(f"- matches with set-piece deliveries: {sum(1 for r in present if r.get('set_piece_available'))}/{len(present)}")
    A(f"- matches regulation-eligible: {sum(1 for r in present if r.get('regulation_eligible'))}/{len(present)}")
    A("")
    A("## Honesty / leakage notes")
    A("")
    A("- International completeness is computed from the REAL lake event objects through the canonical "
      "snapshot engine (no imputation; absent fields flagged, never zeroed).")
    A("- The club raw corpus is not materialized in this worktree; its event-level completeness is "
      "honestly flagged `raw_absent`. This is recorded so Phase 2 can declare cross-domain feature "
      "overlap `data_insufficient` rather than fabricate club distributions.")
    A("- Club rows carry `target_eligible_wdl=False` and are never international test rows.")
    A("")
    (NOTES / "domain_event_process_inventory_report.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
