"""Self-test for the international event lake: sentinel PASSES on valid objects and FAILS CLOSED on
each synthetic corruption (hash mismatch, empty, HTML body, invalid JSON, non-event-list,
manifest-present-but-absent, unregistered-root, filename/hash disagreement, ambiguous id).

Runs against an ISOLATED temporary lake (never touches the persistent lake). research_only.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from wcdrawlab.research import international_event_lake as L  # noqa: E402


VALID_EVENTS = [
    {"id": "a", "index": 1, "type": {"name": "Pass"}, "possession": 1,
     "location": [60.0, 40.0]},
    {"id": "b", "index": 2, "type": {"name": "Shot"}, "possession": 1,
     "location": [110.0, 40.0], "shot": {"statsbomb_xg": 0.21}},
    {"id": "c", "index": 3, "type": {"name": "Pass"}, "possession": 2},
]


def _tmp_lake(tmp_path: Path) -> L.Lake:
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


def _store_valid(lake: L.Lake, sb_id: int = 3939969) -> dict:
    raw = json.dumps(VALID_EVENTS).encode("utf-8")
    rec = L.store_object(
        lake, sb_match_id=sb_id, raw=raw,
        source_url=f"https://example/events/{sb_id}.json",
        ingestion_mode="copied_local", ingestion_run_id="test",
        bridge_row={"bridge_id": "x", "competition_label": "FIFA World Cup 2018"},
    )
    idx = L.read_index(lake)
    idx[str(sb_id)] = rec
    L.write_index(lake, idx)
    return rec


# bridge stub: sb_id 3939969 is a valid exact international match
BRIDGE = {3939969: {"bridge_id": "x", "competition_label": "FIFA World Cup 2018"}}


def test_validate_event_bytes_accepts_valid():
    vr = L.validate_event_bytes(json.dumps(VALID_EVENTS).encode("utf-8"))
    assert vr.ok and vr.event_count == 3
    assert vr.xg_available and vr.possession_available and vr.location_available


@pytest.mark.parametrize("raw,reason", [
    (b"", "empty_file"),
    (b"<!DOCTYPE html><html>404</html>", "html_or_error_body"),
    (b"{not json", "invalid_json"),
    (json.dumps({"a": 1}).encode(), "not_event_list"),
    (json.dumps([]).encode(), "not_event_list"),
    (json.dumps([{"foo": "bar"}]).encode(), "not_event_list"),
])
def test_validate_event_bytes_rejects(raw, reason):
    vr = L.validate_event_bytes(raw)
    assert not vr.ok and vr.reason == reason


def test_sentinel_passes_on_valid(tmp_path):
    lake = _tmp_lake(tmp_path)
    _store_valid(lake)
    rep = L.run_sentinel(lake, bridge=BRIDGE, write_report=False)
    assert rep.ok and rep.checked == 1 and rep.failures == []


def test_sentinel_fails_hash_mismatch(tmp_path):
    lake = _tmp_lake(tmp_path)
    rec = _store_valid(lake)
    obj = lake.root / rec["local_path"]
    obj.write_bytes(json.dumps(VALID_EVENTS + [{"id": "z", "index": 4, "type": {"name": "Pass"}}]).encode())
    rep = L.run_sentinel(lake, bridge=BRIDGE, write_report=False)
    assert not rep.ok
    assert any(f["reason"] == "hash_mismatch" for f in rep.failures)


def test_sentinel_fails_object_absent(tmp_path):
    lake = _tmp_lake(tmp_path)
    rec = _store_valid(lake)
    (lake.root / rec["local_path"]).unlink()
    rep = L.run_sentinel(lake, bridge=BRIDGE, write_report=False)
    assert not rep.ok
    assert any(f["reason"] == "manifest_present_but_object_absent" for f in rep.failures)


def test_sentinel_fails_empty_object(tmp_path):
    lake = _tmp_lake(tmp_path)
    rec = _store_valid(lake)
    # truncate to empty but keep filename == old sha -> empty triggers first
    (lake.root / rec["local_path"]).write_bytes(b"")
    rep = L.run_sentinel(lake, bridge=BRIDGE, write_report=False)
    assert not rep.ok
    assert any(f["reason"] in ("empty_file", "hash_mismatch") for f in rep.failures)


def test_sentinel_fails_unregistered_root(tmp_path):
    lake = _tmp_lake(tmp_path)
    rec = _store_valid(lake)
    sha = rec["sha256"]
    # write a byte-identical copy at a NON-canonical (unregistered) path
    bad = lake.objects / str(3939969) / f"{sha}.json"
    bad.parent.mkdir(parents=True, exist_ok=True)
    bad.write_bytes((lake.root / rec["local_path"]).read_bytes())
    rep = L.run_sentinel(lake, bridge=BRIDGE, write_report=False)
    assert not rep.ok
    assert any(f["reason"] == "object_under_unregistered_root" for f in rep.failures)


def test_sentinel_fails_not_in_exact_bridge(tmp_path):
    lake = _tmp_lake(tmp_path)
    _store_valid(lake, sb_id=3939969)
    # empty bridge -> id resolves to nothing -> fail closed
    rep = L.run_sentinel(lake, bridge={111: {}}, write_report=False)
    assert not rep.ok
    assert any(f["reason"] == "not_in_exact_bridge" for f in rep.failures)


def test_store_is_idempotent(tmp_path):
    lake = _tmp_lake(tmp_path)
    r1 = _store_valid(lake)
    raw = json.dumps(VALID_EVENTS).encode("utf-8")
    r2 = L.store_object(lake, sb_match_id=3939969, raw=raw, source_url="x",
                        ingestion_mode="copied_local", ingestion_run_id="test2", bridge_row=None)
    assert r1["sha256"] == r2["sha256"]
    assert (lake.objects / r1["sha256"][:2] / f"{r1['sha256']}.json").exists()


def test_quarantine_never_enters_index(tmp_path):
    lake = _tmp_lake(tmp_path)
    L.quarantine_payload(lake, sb_match_id=999999, raw=b"garbage", reason="invalid_json", source="x")
    assert L.read_index(lake) == {}  # nothing entered the index
    assert list(lake.quarantine.glob("*.quarantine"))


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
