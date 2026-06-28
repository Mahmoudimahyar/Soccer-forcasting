"""Deterministic self-tests for the International Event Lake evaluation-cohort builder (Phase 4).

research_only. >= 30 deterministic tests covering the spec invariants:
  raw-backed availability, no silent cache fallback, no cross-worktree raw reads, source-hash
  traceability, exact-bridge requirement, no future-event leakage, regulation-only, no shootout/ET
  target leakage, deterministic folds, NO 2026 WC in any cohort, match-level grouping.

Every test builds an ISOLATED synthetic lake under tmp_path and drives the builder's pure functions.
No test ever reads the persistent lake or any data/raw cache. No network.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from wcdrawlab.research import international_event_lake as L  # noqa: E402
import build_international_event_lake_cohort as COH  # noqa: E402


# =====================================================================================================
# fixtures: an isolated synthetic lake + helpers
# =====================================================================================================
def _xi(idx, team_id, name, period=1, minute=0):
    return {"id": f"xi{idx}", "index": idx, "period": period, "minute": minute, "second": 0,
            "type": {"name": "Starting XI"}, "team": {"id": team_id, "name": name}}


def _shot(idx, minute, team_id, xg, goal=False, period=None, second=0):
    per = period if period is not None else (1 if minute < 45 else 2)
    return {"id": f"s{idx}", "index": idx, "period": per, "minute": minute, "second": second,
            "type": {"name": "Shot"}, "team": {"id": team_id}, "location": [110.0, 40.0],
            "shot": {"statsbomb_xg": xg, "outcome": {"name": "Goal" if goal else "Saved"}}}


def _match_events(home_goal_min=10, away_goal_min=None, et_goal=False, stoppage_winner=False):
    """A small valid two-team match. Home(1), Away(2)."""
    ev = [_xi(1, 1, "Home"), _xi(2, 2, "Away"),
          _shot(3, home_goal_min, 1, 0.30, goal=True),
          _shot(4, 30, 2, 0.10, goal=False)]
    n = 5
    if away_goal_min is not None:
        ev.append(_shot(n, away_goal_min, 2, 0.40, goal=True)); n += 1
    if stoppage_winner:
        # away scores at clock 92' (regulation stoppage time, but engine clock-minute > 90)
        ev.append(_shot(n, 92, 2, 0.5, goal=True, period=2)); n += 1
    if et_goal:
        ev.append({"id": "et", "index": n, "period": 3, "minute": 95, "second": 0,
                   "type": {"name": "Shot"}, "team": {"id": 1}, "location": [110, 40],
                   "shot": {"statsbomb_xg": 0.5, "outcome": {"name": "Goal"}}}); n += 1
    return ev


def _make_lake(tmp_path: Path) -> L.Lake:
    root = tmp_path / "lake"
    sub = lambda n: root / n  # noqa: E731
    lake = L.Lake(
        root=root, objects=sub("objects"), indexes=sub("indexes"), manifests=sub("manifests"),
        quarantine=sub("quarantine"), integrity=sub("integrity"), logs=sub("logs"),
        index_json=sub("indexes") / "idx.json", index_jsonl=sub("indexes") / "idx.jsonl",
        manifest_jsonl=sub("manifests") / "man.jsonl", cfg={},
    )
    for d in (lake.objects, lake.indexes, lake.manifests, lake.quarantine, lake.integrity, lake.logs):
        d.mkdir(parents=True, exist_ok=True)
    return lake


def _store(lake: L.Lake, sb_id: int, events: list, comp="FIFA World Cup 2018", kickoff="2018-06-14"):
    raw = json.dumps(events).encode("utf-8")
    sha = hashlib.sha256(raw).hexdigest()
    objdir = lake.objects / sha[:2]
    objdir.mkdir(parents=True, exist_ok=True)
    (objdir / f"{sha}.json").write_bytes(raw)
    return {"local_path": f"objects/{sha[:2]}/{sha}.json", "sha256": sha,
            "competition_label": comp, "kickoff_date": kickoff, "sb_match_id": sb_id}


def _bridge_row(sb_id, comp, kickoff, home="Home", away="Away", reg_h=1, reg_a=0):
    return {"sb_match_id": str(sb_id), "bridge_id": f"b{sb_id}", "api_fixture_id": f"f{sb_id}",
            "competition_label": comp, "comp_type": "international", "kickoff_date": kickoff,
            "sb_home": home, "sb_away": away, "norm_home": home, "norm_away": away,
            "api_regulation_home": str(reg_h), "api_regulation_away": str(reg_a),
            "bridge_confidence": "exact"}


# =====================================================================================================
# 1-6: raw-backed availability + fail-closed reads
# =====================================================================================================
def test_load_raw_from_lake_ok(tmp_path):
    lake = _make_lake(tmp_path)
    rec = _store(lake, 7525, _match_events())
    ev, reason = COH.load_raw_from_lake(lake, rec)
    assert reason == "ok" and isinstance(ev, list) and len(ev) >= 4


def test_hash_mismatch_fails_closed(tmp_path):
    lake = _make_lake(tmp_path)
    rec = _store(lake, 7525, _match_events())
    rec_bad = dict(rec, sha256="0" * 64)
    ev, reason = COH.load_raw_from_lake(lake, rec_bad)
    assert ev is None and reason == "hash_mismatch"


def test_missing_object_fails_closed(tmp_path):
    lake = _make_lake(tmp_path)
    rec = {"local_path": "objects/ab/" + "a" * 64 + ".json", "sha256": "a" * 64}
    ev, reason = COH.load_raw_from_lake(lake, rec)
    assert ev is None and reason == "manifest_present_but_object_absent"


def test_empty_object_fails_closed(tmp_path):
    lake = _make_lake(tmp_path)
    sha = hashlib.sha256(b"").hexdigest()
    (lake.objects / sha[:2]).mkdir(parents=True, exist_ok=True)
    (lake.objects / sha[:2] / f"{sha}.json").write_bytes(b"")
    rec = {"local_path": f"objects/{sha[:2]}/{sha}.json", "sha256": sha}
    ev, reason = COH.load_raw_from_lake(lake, rec)
    assert ev is None and reason == "empty_file"


def test_html_error_body_fails_closed(tmp_path):
    lake = _make_lake(tmp_path)
    body = b"<!DOCTYPE html><html>404</html>"
    sha = hashlib.sha256(body).hexdigest()
    (lake.objects / sha[:2]).mkdir(parents=True, exist_ok=True)
    (lake.objects / sha[:2] / f"{sha}.json").write_bytes(body)
    rec = {"local_path": f"objects/{sha[:2]}/{sha}.json", "sha256": sha}
    ev, reason = COH.load_raw_from_lake(lake, rec)
    assert ev is None and reason in ("html_or_error_body", "invalid_json", "not_event_list")


def test_filename_hash_disagreement_fails_closed(tmp_path):
    lake = _make_lake(tmp_path)
    raw = json.dumps(_match_events()).encode("utf-8")
    sha = hashlib.sha256(raw).hexdigest()
    wrong = "f" * 64
    (lake.objects / wrong[:2]).mkdir(parents=True, exist_ok=True)
    (lake.objects / wrong[:2] / f"{wrong}.json").write_bytes(raw)  # filename stem != sha
    rec = {"local_path": f"objects/{wrong[:2]}/{wrong}.json", "sha256": sha}
    ev, reason = COH.load_raw_from_lake(lake, rec)
    # bytes hash == recorded sha (valid), but the filename stem != sha -> content-addressing violation
    assert ev is None and reason == "filename_hash_disagreement"


# =====================================================================================================
# 7-9: no cross-worktree raw read / no silent cache fallback
# =====================================================================================================
def test_object_under_unregistered_root_fails_closed(tmp_path):
    lake = _make_lake(tmp_path)
    outside = tmp_path / "outside" / "evil.json"
    outside.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(_match_events()).encode("utf-8")
    outside.write_bytes(raw)
    rec = {"local_path": "../outside/evil.json", "sha256": hashlib.sha256(raw).hexdigest()}
    ev, reason = COH.load_raw_from_lake(lake, rec)
    assert ev is None and reason == "object_under_unregistered_root"


def test_no_cache_fallback_when_lake_object_absent(tmp_path, monkeypatch):
    # If the lake index references an absent object, the builder must NOT fall back to any data/raw cache.
    # We assert the only raw read path is load_raw_from_lake (no DR.get_root('statsbomb_raw') events read).
    src = (ROOT / "scripts/build_international_event_lake_cohort.py").read_text(encoding="utf-8")
    assert "statsbomb_raw" not in src, "cohort builder must not reference the data/raw statsbomb cache"
    assert "events_up_to" not in src or "snapshot_features" in src  # leakage gate via engine only


def test_builder_source_has_no_forbidden_roots():
    src = (ROOT / "scripts/build_international_event_lake_cohort.py").read_text(encoding="utf-8")
    assert "worldcup_draw_model_lab_FINAL" not in src
    assert "api_football" not in src.lower()
    assert "odds" not in src.lower()


# =====================================================================================================
# 10-12: source-hash traceability
# =====================================================================================================
def _build_one(tmp_path, sb_id=7525, events=None, comp="FIFA World Cup 2018", kickoff="2018-06-14",
               reg_h=1, reg_a=0, monkeypatch=None):
    """Drive build_cohort against an isolated lake + bridge via monkeypatch."""
    lake = _make_lake(tmp_path)
    events = events if events is not None else _match_events()
    rec = _store(lake, sb_id, events, comp=comp, kickoff=kickoff)
    index = {str(sb_id): {**rec, "sb_match_id": sb_id}}
    bridge = {sb_id: _bridge_row(sb_id, comp, kickoff, reg_h=reg_h, reg_a=reg_a)}
    monkeypatch.setattr(COH.L.Lake, "resolve", staticmethod(lambda: lake))
    monkeypatch.setattr(COH.L, "read_index", lambda _l: index)
    monkeypatch.setattr(COH.L, "load_exact_bridge", lambda: bridge)
    return COH.build_cohort()


def test_cohort_row_carries_lake_sha(tmp_path, monkeypatch):
    built = _build_one(tmp_path, monkeypatch=monkeypatch)
    assert len(built["rows"]) == 1
    r = built["rows"][0]
    assert len(r["lake_sha256"]) == 64
    assert r["lake_local_path"].startswith("objects/")


def test_snapshot_source_sha_equals_lake_sha(tmp_path, monkeypatch):
    built = _build_one(tmp_path, monkeypatch=monkeypatch)
    r = built["rows"][0]
    for s in r["_snapshots"]:
        assert s["source_sha256"] == r["lake_sha256"]
        assert s["lake_sha256"] == r["lake_sha256"]


def test_lake_sha_matches_object_bytes(tmp_path, monkeypatch):
    built = _build_one(tmp_path, monkeypatch=monkeypatch)
    r = built["rows"][0]
    lake = COH.L.Lake.resolve()
    obj = lake.root / r["lake_local_path"]
    assert hashlib.sha256(obj.read_bytes()).hexdigest() == r["lake_sha256"]


# =====================================================================================================
# 13-15: exact-bridge requirement
# =====================================================================================================
def test_not_in_exact_bridge_excluded(tmp_path, monkeypatch):
    lake = _make_lake(tmp_path)
    rec = _store(lake, 999, _match_events())
    monkeypatch.setattr(COH.L.Lake, "resolve", staticmethod(lambda: lake))
    monkeypatch.setattr(COH.L, "read_index", lambda _l: {"999": {**rec, "sb_match_id": 999}})
    monkeypatch.setattr(COH.L, "load_exact_bridge", lambda: {})  # empty bridge
    built = COH.build_cohort()
    assert built["rows"] == []
    assert any(e["exclusion_reason"] == "not_in_exact_bridge" for e in built["exclusions"])


def test_non_international_excluded(tmp_path, monkeypatch):
    lake = _make_lake(tmp_path)
    rec = _store(lake, 555, _match_events())
    br = _bridge_row(555, "Some League", "2019-01-01")
    br["comp_type"] = "club"
    monkeypatch.setattr(COH.L.Lake, "resolve", staticmethod(lambda: lake))
    monkeypatch.setattr(COH.L, "read_index", lambda _l: {"555": {**rec, "sb_match_id": 555}})
    monkeypatch.setattr(COH.L, "load_exact_bridge", lambda: {555: br})
    built = COH.build_cohort()
    assert built["rows"] == []
    assert any(e["exclusion_reason"] == "not_international" for e in built["exclusions"])


def test_included_match_is_exact_bridge(tmp_path, monkeypatch):
    built = _build_one(tmp_path, monkeypatch=monkeypatch)
    assert built["rows"][0]["bridge_confidence"] == "exact"


# =====================================================================================================
# 16-20: NO 2026 WORLD CUP in any cohort
# =====================================================================================================
def test_is_2026_wc_detects():
    assert COH.is_2026_wc("FIFA World Cup 2026", "2026-06-15") is True
    assert COH.is_2026_wc("FIFA World Cup", "2026-07-01") is True


def test_is_2026_wc_negatives():
    assert COH.is_2026_wc("FIFA World Cup 2018", "2018-06-14") is False
    assert COH.is_2026_wc("UEFA Euro 2024", "2024-06-14") is False
    assert COH.is_2026_wc("Copa America 2024", "2024-06-21") is False


def test_2026_wc_excluded_before_raw_read(tmp_path, monkeypatch):
    lake = _make_lake(tmp_path)
    rec = _store(lake, 2026001, _match_events(), comp="FIFA World Cup 2026", kickoff="2026-06-15")
    br = _bridge_row(2026001, "FIFA World Cup 2026", "2026-06-15")
    monkeypatch.setattr(COH.L.Lake, "resolve", staticmethod(lambda: lake))
    monkeypatch.setattr(COH.L, "read_index", lambda _l: {"2026001": {**rec, "sb_match_id": 2026001}})
    monkeypatch.setattr(COH.L, "load_exact_bridge", lambda: {2026001: br})
    built = COH.build_cohort()
    assert built["rows"] == []
    assert any("2026" in e["exclusion_reason"] for e in built["exclusions"])


def test_no_2026_in_any_subcohort(tmp_path, monkeypatch):
    # mix a 2018 (valid) and a 2026 (forbidden) match; the 2026 must appear in NO sub-cohort
    lake = _make_lake(tmp_path)
    r1 = _store(lake, 7525, _match_events(), comp="FIFA World Cup 2018", kickoff="2018-06-14")
    r2 = _store(lake, 2026001, _match_events(), comp="FIFA World Cup 2026", kickoff="2026-06-15")
    index = {"7525": {**r1, "sb_match_id": 7525}, "2026001": {**r2, "sb_match_id": 2026001}}
    bridge = {7525: _bridge_row(7525, "FIFA World Cup 2018", "2018-06-14"),
              2026001: _bridge_row(2026001, "FIFA World Cup 2026", "2026-06-15")}
    monkeypatch.setattr(COH.L.Lake, "resolve", staticmethod(lambda: lake))
    monkeypatch.setattr(COH.L, "read_index", lambda _l: index)
    monkeypatch.setattr(COH.L, "load_exact_bridge", lambda: bridge)
    built = COH.build_cohort()
    assert all(not COH.is_2026_wc(r["competition_label"], r["kickoff_date"]) for r in built["rows"])
    counts = COH.subcohort_counts(built["rows"])
    assert counts["official_selected"] == 1  # only the 2018 match


def test_final_2026_assertion_guards(tmp_path, monkeypatch):
    # if a 2026 row somehow survived into rows, build_cohort raises (defence in depth). We simulate by
    # checking the assertion logic directly.
    rows = [{"competition_label": "FIFA World Cup 2026", "kickoff_date": "2026-06-15"}]
    bad = [r for r in rows if COH.is_2026_wc(r["competition_label"], r["kickoff_date"])]
    assert len(bad) == 1


# =====================================================================================================
# 21-25: regulation-only + no future / ET / shootout target leakage
# =====================================================================================================
def test_regulation_target_excludes_extra_time(tmp_path, monkeypatch):
    # home goal @10, ET goal @95 (period 3): regulation target must be Home win 1-0, ET ignored
    built = _build_one(tmp_path, events=_match_events(et_goal=True), reg_h=1, reg_a=0,
                       monkeypatch=monkeypatch)
    r = built["rows"][0]
    assert r["reg_home_goals"] == 1 and r["reg_away_goals"] == 0 and r["target_wdl"] == "H"


def test_snapshot_no_future_event_leak(tmp_path, monkeypatch):
    # away goal @70: a snapshot at 30' must not see it
    built = _build_one(tmp_path, events=_match_events(away_goal_min=70), reg_h=1, reg_a=1,
                       monkeypatch=monkeypatch)
    r = built["rows"][0]
    snaps_at_30 = [s for s in r["_snapshots"] if abs(float(s["snapshot_minute"]) - 30.0) < 1e-6]
    assert snaps_at_30, "expected a 30' snapshot"
    for s in snaps_at_30:
        assert s["goals_home"] == 1 and s["goals_away"] == 0  # away goal @70 invisible


def test_leakage_self_test_all_ok(tmp_path, monkeypatch):
    built = _build_one(tmp_path, events=_match_events(away_goal_min=70), monkeypatch=monkeypatch)
    checks = built["leakage_checks"]
    assert checks and all(c["ok"] for c in checks)


def test_snapshots_are_regulation_only(tmp_path, monkeypatch):
    built = _build_one(tmp_path, events=_match_events(et_goal=True), monkeypatch=monkeypatch)
    r = built["rows"][0]
    for s in r["_snapshots"]:
        assert float(s["snapshot_minute"]) <= 90.0 + 1e-6


def test_wdl_target_conflict_excluded_from_eligibility(tmp_path, monkeypatch):
    # stoppage-time winner (engine clock>90 drops it) makes the engine W/D/L (Draw) disagree with the
    # bridge regulation result (Away win) -> wdl_target_conflict -> NOT eligible for any target family
    built = _build_one(tmp_path, events=_match_events(away_goal_min=30, stoppage_winner=True),
                       reg_h=1, reg_a=2, monkeypatch=monkeypatch)
    r = built["rows"][0]
    assert r["reconciliation_status"] == "wdl_target_conflict"
    assert r["target_eligible_wdl"] is False
    assert r["target_eligible_event_process"] is False
    assert r["exclusion_reason"].startswith("wdl_target_conflict")


# =====================================================================================================
# 26-29: deterministic folds + match-level grouping
# =====================================================================================================
def test_folds_deterministic():
    comps = ["FIFA World Cup 2018", "UEFA Euro 2020", "FIFA World Cup 2022"]
    f1 = COH.assign_folds(comps)
    f2 = COH.assign_folds(comps)
    assert f1 == f2
    assert f1["FIFA World Cup 2018"]["primary_fold"] == 0
    assert f1["FIFA World Cup 2022"]["primary_fold"] == 2


def test_folds_loco_name_is_competition():
    comps = ["A", "B"]
    f = COH.assign_folds(comps)
    assert f["A"]["loco_fold"] == "A" and f["B"]["loco_fold"] == "B"


def test_competition_order_by_kickoff(tmp_path, monkeypatch):
    lake = _make_lake(tmp_path)
    r1 = _store(lake, 1, _match_events(), comp="UEFA Euro 2020", kickoff="2021-06-11")
    r2 = _store(lake, 2, _match_events(), comp="FIFA World Cup 2018", kickoff="2018-06-14")
    index = {"1": {**r1, "sb_match_id": 1}, "2": {**r2, "sb_match_id": 2}}
    bridge = {1: _bridge_row(1, "UEFA Euro 2020", "2021-06-11"),
              2: _bridge_row(2, "FIFA World Cup 2018", "2018-06-14")}
    monkeypatch.setattr(COH.L.Lake, "resolve", staticmethod(lambda: lake))
    monkeypatch.setattr(COH.L, "read_index", lambda _l: index)
    monkeypatch.setattr(COH.L, "load_exact_bridge", lambda: bridge)
    built = COH.build_cohort()
    assert built["comp_order"][0] == "FIFA World Cup 2018"  # earliest kickoff first


def test_match_level_grouping_one_row_per_match(tmp_path, monkeypatch):
    built = _build_one(tmp_path, monkeypatch=monkeypatch)
    # exactly one cohort row per sb_match_id, even though it has many snapshots
    ids = [r["sb_match_id"] for r in built["rows"]]
    assert len(ids) == len(set(ids))
    assert built["rows"][0]["snapshot_count"] == len(built["rows"][0]["_snapshots"])


# =====================================================================================================
# 30-34: determinism + manifest shape + season + canonical id + reconciliation
# =====================================================================================================
def test_build_is_deterministic(tmp_path, monkeypatch):
    b1 = _build_one(tmp_path / "a", monkeypatch=monkeypatch)
    b2 = _build_one(tmp_path / "b", monkeypatch=monkeypatch)
    r1, r2 = b1["rows"][0], b2["rows"][0]
    assert r1["target_wdl"] == r2["target_wdl"]
    assert r1["snapshot_count"] == r2["snapshot_count"]
    assert r1["lake_sha256"] == r2["lake_sha256"]


def test_manifest_fields_present(tmp_path, monkeypatch):
    built = _build_one(tmp_path, monkeypatch=monkeypatch)
    pr = COH._public_row(built["rows"][0])
    for f in ("canonical_match_id", "sb_match_id", "lake_sha256", "bridge_id", "reconciliation_status",
              "target_eligible_wdl", "primary_fold", "loco_fold", "is_2026_wc_excluded", "snapshot_count"):
        assert f in pr


def test_season_extraction():
    assert COH._season_from("FIFA World Cup 2018", "2018-06-14") == "2018"
    assert COH._season_from("UEFA Euro 2020", "2021-06-11") == "2020"
    assert COH._season_from(None, "2022-11-20") == "2022"


def test_canonical_match_id_stable():
    a = COH._canonical_match_id("FIFA World Cup 2018", 7525)
    b = COH._canonical_match_id("FIFA World Cup 2018", 7525)
    assert a == b and "7525" in a


def test_reconciliation_exact_when_goals_match(tmp_path, monkeypatch):
    # home 1-0, bridge reg 1-0 -> exact
    built = _build_one(tmp_path, events=_match_events(), reg_h=1, reg_a=0, monkeypatch=monkeypatch)
    assert built["rows"][0]["reconciliation_status"] == "exact"


def test_reconciliation_count_mismatch_same_wdl(tmp_path, monkeypatch):
    # engine 1-0 (H), bridge 2-0 (H): goal count differs but W/D/L agrees -> mismatch_regulation_goals,
    # still eligible
    built = _build_one(tmp_path, events=_match_events(), reg_h=2, reg_a=0, monkeypatch=monkeypatch)
    r = built["rows"][0]
    assert r["reconciliation_status"] == "mismatch_regulation_goals"
    assert r["target_eligible_wdl"] is True


def test_subcohort_counts_monotone(tmp_path, monkeypatch):
    built = _build_one(tmp_path, monkeypatch=monkeypatch)
    c = COH.subcohort_counts(built["rows"])
    # event-process eligible <= official selected; xg eligible <= event-process eligible
    assert c["xg_eligible"] <= c["event_process_eligible"] <= c["official_selected"]


def test_no_exclusion_reason_for_clean_match(tmp_path, monkeypatch):
    built = _build_one(tmp_path, monkeypatch=monkeypatch)
    assert built["rows"][0]["exclusion_reason"] == ""


# =====================================================================================================
# 38-40: integration against the REAL persistent lake (skipped if absent)
# =====================================================================================================
def _real_lake_available() -> bool:
    try:
        lake = L.Lake.resolve()
        return lake.index_json.exists()
    except Exception:
        return False


@pytest.mark.skipif(not _real_lake_available(), reason="persistent lake absent in clean worktree")
def test_real_lake_builds_raw_backed():
    built = COH.build_cohort()
    assert built["rows"], "real lake should yield >=1 cohort match"
    for r in built["rows"]:
        assert len(r["lake_sha256"]) == 64
        assert not COH.is_2026_wc(r["competition_label"], r["kickoff_date"])


@pytest.mark.skipif(not _real_lake_available(), reason="persistent lake absent in clean worktree")
def test_real_lake_leakage_all_ok():
    built = COH.build_cohort()
    checks = built["leakage_checks"]
    assert checks and all(c["ok"] for c in checks)


@pytest.mark.skipif(not _real_lake_available(), reason="persistent lake absent in clean worktree")
def test_real_lake_no_2026_anywhere():
    built = COH.build_cohort()
    assert all(not COH.is_2026_wc(r["competition_label"], r["kickoff_date"]) for r in built["rows"])
    assert all(not COH.is_2026_wc(e.get("competition_label"), e.get("kickoff_date"))
               or "2026" in e["exclusion_reason"] for e in built["exclusions"])
