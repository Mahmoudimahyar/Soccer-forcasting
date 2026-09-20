"""International Event Lake — content-addressed, fail-closed StatsBomb open-data event store.

This is the shared library behind init / restore / audit / retention / sentinel scripts.
The PERSISTENT lake lives OUTSIDE every git worktree. Raw event JSON is stored ONLY in the lake,
content-addressed by sha256, written atomically, recorded in an immutable append-only manifest.

Fail-closed: the sentinel FAILS on manifest-says-present-but-absent, hash mismatch, empty file,
HTML/error body, invalid JSON, non-event-list, ambiguous id, or an object under an unregistered root.

EXTERNAL retrieval (download) = OFFICIAL StatsBomb Open Data ONLY. No API-Football / Odds / paid /
scrape / mirror / browser / 360 / video. Strict EXACT international bridge only. research_only.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

SOURCE_SCHEMA_VERSION = "statsbomb_open_event_v1"

# Worktree root: src/wcdrawlab/research/international_event_lake.py -> parents[3]
_WORKTREE = Path(__file__).resolve().parents[3]
_ROOTS_CFG = _WORKTREE / "configs" / "international_event_lake_roots.yaml"
_CONTRACT_CFG = _WORKTREE / "configs" / "international_event_lake_contract.yaml"


class LakeError(RuntimeError):
    """Any violation of the lake contract (forbidden root, illegal mutation, invalid input)."""


# --------------------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------------------
def load_roots() -> dict[str, Any]:
    return yaml.safe_load(_ROOTS_CFG.read_text(encoding="utf-8"))


def load_contract() -> dict[str, Any]:
    return yaml.safe_load(_CONTRACT_CFG.read_text(encoding="utf-8"))


def _resolve(path_str: str) -> Path:
    p = Path(path_str)
    if not p.is_absolute():
        p = _WORKTREE / p
    return p


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass
class Lake:
    """Resolved view of the persistent lake (paths only — never resolves into a worktree)."""

    root: Path
    objects: Path
    indexes: Path
    manifests: Path
    quarantine: Path
    integrity: Path
    logs: Path
    index_json: Path
    index_jsonl: Path
    manifest_jsonl: Path
    cfg: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def resolve(cls) -> "Lake":
        cfg = load_roots()
        root = Path(cfg["lake_root"])
        # Fail closed: the lake must NOT live inside any git worktree / the active collector.
        forbidden = cfg.get("forbidden_roots", [])
        norm = str(root).replace("\\", "/")
        for f in forbidden:
            if str(f).replace("\\", "/") in norm:
                raise LakeError(f"lake_root resolves under forbidden root {f!r}")
        if "worldcup-international-event-lake" in norm or "worldcup_draw_model_lab_FINAL" in norm:
            raise LakeError(f"lake_root {root} must live OUTSIDE every git worktree")
        sd = cfg["subdirs"]
        return cls(
            root=root,
            objects=root / sd["objects"],
            indexes=root / sd["indexes"],
            manifests=root / sd["manifests"],
            quarantine=root / sd["quarantine"],
            integrity=root / sd["integrity"],
            logs=root / sd["logs"],
            index_json=root / sd["indexes"] / cfg["index_json"],
            index_jsonl=root / sd["indexes"] / cfg["index_jsonl"],
            manifest_jsonl=root / sd["manifests"] / cfg["manifest_jsonl"],
            cfg=cfg,
        )

    def object_path(self, sha256: str) -> Path:
        prefix = sha256[: int(load_contract()["content_addressing"]["shard_prefix_len"])]
        return self.objects / prefix / f"{sha256}.json"

    def rel(self, p: Path) -> str:
        return str(p.relative_to(self.root)).replace("\\", "/")


# --------------------------------------------------------------------------------------
# Exact international bridge
# --------------------------------------------------------------------------------------
def load_exact_bridge() -> dict[int, dict[str, str]]:
    """sb_match_id -> bridge row, EXACT international rows only. Raises on ambiguous duplicate ids."""
    cfg = load_roots()
    path = _resolve(cfg["exact_bridge_csv"])
    allowed = set(cfg.get("allowed_competitions", []))
    out: dict[int, dict[str, str]] = {}
    ambiguous: set[int] = set()
    with path.open("r", encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            if row.get("bridge_confidence") != "exact":
                continue
            if row.get("comp_type") != "international":
                continue
            # competition gate: label starts with an allowed senior men's international competition
            label = (row.get("competition_label") or "")
            if not any(label.startswith(a) for a in allowed):
                continue
            try:
                sb_id = int(row["sb_match_id"])
            except (KeyError, ValueError):
                continue
            if sb_id in out:
                ambiguous.add(sb_id)
            out[sb_id] = row
    for sb_id in ambiguous:
        out.pop(sb_id, None)  # ambiguous never enters evaluation
    return out


def bridge_competitions(bridge: dict[int, dict[str, str]]) -> dict[str, int]:
    from collections import Counter
    return dict(Counter(r.get("competition_label", "?") for r in bridge.values()))


# --------------------------------------------------------------------------------------
# Payload validation (fail-closed primitives)
# --------------------------------------------------------------------------------------
@dataclass
class ValidationResult:
    ok: bool
    reason: str
    event_count: int = 0
    xg_available: bool = False
    possession_available: bool = False
    location_available: bool = False


def validate_event_bytes(raw: bytes) -> ValidationResult:
    """Apply the contract's validity rules to raw event bytes. Pure; no I/O."""
    if not raw:
        return ValidationResult(False, "empty_file")
    stripped = raw.lstrip()
    if stripped[:1] in (b"<",):
        return ValidationResult(False, "html_or_error_body")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return ValidationResult(False, "invalid_json")
    low = text[:200].lower()
    if low.lstrip().startswith("<") or '"message":"not found"' in low.replace(" ", "") or low.strip() in ("404: not found",):
        return ValidationResult(False, "html_or_error_body")
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return ValidationResult(False, "invalid_json")
    if not isinstance(data, list) or len(data) == 0:
        return ValidationResult(False, "not_event_list")
    # each element must look like a StatsBomb event
    req = set(load_contract()["validity"]["event_object_required_keys"])
    for e in data[: min(5, len(data))]:
        if not isinstance(e, dict) or not req.issubset(e.keys()):
            return ValidationResult(False, "not_event_list")
    xg = any(
        isinstance(e, dict)
        and isinstance(e.get("shot"), dict)
        and ("statsbomb_xg" in e["shot"])
        for e in data
    )
    poss = any(isinstance(e, dict) and ("possession" in e) for e in data)
    loc = any(isinstance(e, dict) and ("location" in e) for e in data)
    return ValidationResult(True, "valid", len(data), xg, poss, loc)


# --------------------------------------------------------------------------------------
# Index / manifest I/O
# --------------------------------------------------------------------------------------
def read_index(lake: Lake) -> dict[str, dict[str, Any]]:
    if not lake.index_json.exists():
        return {}
    doc = json.loads(lake.index_json.read_text(encoding="utf-8"))
    return doc.get("objects", {})


def write_index(lake: Lake, objects: dict[str, dict[str, Any]]) -> None:
    doc = {
        "schema_version": "international_event_lake_manifest_v1",
        "lake_root": str(lake.root),
        "updated_ts": _utc_now(),
        "object_count": len(objects),
        "objects": objects,
    }
    _atomic_write_text(lake.index_json, json.dumps(doc, indent=2, ensure_ascii=False))
    # mirror as JSONL (one record per line)
    lines = [json.dumps(rec, ensure_ascii=False, sort_keys=True) for rec in objects.values()]
    _atomic_write_text(lake.index_jsonl, ("\n".join(lines) + ("\n" if lines else "")))


def append_manifest(lake: Lake, record: dict[str, Any]) -> None:
    lake.manifest_jsonl.parent.mkdir(parents=True, exist_ok=True)
    with lake.manifest_jsonl.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def _atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


# --------------------------------------------------------------------------------------
# Store one object (atomic, content-addressed, immutable, first-write-wins)
# --------------------------------------------------------------------------------------
def store_object(
    lake: Lake,
    *,
    sb_match_id: int,
    raw: bytes,
    source_url: str,
    ingestion_mode: str,
    ingestion_run_id: str,
    bridge_row: dict[str, str] | None,
    retrieval_ts: str | None = None,
    copied_from: str | None = None,
) -> dict[str, Any]:
    """Validate, hash, atomically write, and record one event object. Returns the index record.

    Raises LakeError on validation failure (caller should quarantine instead of storing).
    Idempotent: identical bytes already present are not rewritten.
    """
    vr = validate_event_bytes(raw)
    if not vr.ok:
        raise LakeError(f"refusing to store sb_match_id={sb_match_id}: {vr.reason}")
    sha = sha256_bytes(raw)
    obj = lake.object_path(sha)
    if not obj.exists():
        _atomic_write_bytes(obj, raw)  # tmp -> atomic rename
    else:
        # immutability check: existing bytes must hash to the same sha
        if sha256_bytes(obj.read_bytes()) != sha:
            raise LakeError(f"immutable object at {obj} changed on disk")
    record = {
        "sb_match_id": sb_match_id,
        "local_path": lake.rel(obj),
        "sha256": sha,
        "event_count": vr.event_count,
        "xg_available": vr.xg_available,
        "possession_available": vr.possession_available,
        "location_available": vr.location_available,
        "source_url": source_url,
        "retrieval_ts": retrieval_ts or _utc_now(),
        "validation_status": "valid",
        "source_schema_version": SOURCE_SCHEMA_VERSION,
        # provenance
        "bridge_id": (bridge_row or {}).get("bridge_id"),
        "competition_label": (bridge_row or {}).get("competition_label"),
        "kickoff_date": (bridge_row or {}).get("kickoff_date"),
        "norm_home": (bridge_row or {}).get("norm_home"),
        "norm_away": (bridge_row or {}).get("norm_away"),
        "ingestion_mode": ingestion_mode,
        "ingestion_run_id": ingestion_run_id,
        "copied_from": copied_from,
    }
    append_manifest(lake, record)
    return record


def quarantine_payload(lake: Lake, *, sb_match_id: int | str, raw: bytes, reason: str, source: str) -> Path:
    """Write a rejected payload into quarantine with a reason. Never enters the index/evaluation."""
    lake.quarantine.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    stem = f"{sb_match_id}_{reason}_{ts}"
    safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in stem)
    p = lake.quarantine / f"{safe}.quarantine"
    _atomic_write_bytes(p, raw if raw else b"")
    meta = lake.quarantine / f"{safe}.meta.json"
    _atomic_write_text(meta, json.dumps(
        {"sb_match_id": sb_match_id, "reason": reason, "source": source, "ts": _utc_now()},
        indent=2, ensure_ascii=False))
    return p


# --------------------------------------------------------------------------------------
# Integrity sentinel — FAIL CLOSED
# --------------------------------------------------------------------------------------
@dataclass
class SentinelReport:
    ok: bool
    checked: int
    failures: list[dict[str, Any]]
    ts: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "all_ok": self.ok,
            "checked": self.checked,
            "failure_count": len(self.failures),
            "failures": self.failures,
            "ts": self.ts,
        }


def run_sentinel(lake: Lake, *, bridge: dict[int, dict[str, str]] | None = None,
                 write_report: bool = True) -> SentinelReport:
    """Verify EVERY indexed object against the fail-closed contract. Returns ok only if all pass.

    Fails on: manifest-present-but-absent, hash mismatch (bytes vs recorded sha and vs filename),
    empty file, HTML/error body, invalid JSON, non-event-list, ambiguous id, object outside the
    registered objects/ root, or a duplicate sb_match_id in the index.
    """
    failures: list[dict[str, Any]] = []
    index = read_index(lake)
    objects_root = lake.objects.resolve()

    if bridge is None:
        try:
            bridge = load_exact_bridge()
        except Exception:  # bridge unavailable -> do not silently pass id checks
            bridge = {}

    # detect ambiguous ids in the index itself
    seen_ids: set[int] = set()

    for sb_id_str, rec in index.items():
        try:
            sb_id = int(sb_id_str)
        except (TypeError, ValueError):
            failures.append({"sb_match_id": sb_id_str, "reason": "non_integer_match_id"})
            continue
        if sb_id in seen_ids:
            failures.append({"sb_match_id": sb_id, "reason": "ambiguous_match_id_duplicate_index_key"})
            continue
        seen_ids.add(sb_id)

        recorded_sha = rec.get("sha256")
        local_path = rec.get("local_path")
        if not local_path:
            failures.append({"sb_match_id": sb_id, "reason": "missing_local_path"})
            continue
        obj = (lake.root / local_path).resolve()

        # object must live under the registered objects/ tree
        try:
            obj.relative_to(objects_root)
        except ValueError:
            failures.append({"sb_match_id": sb_id, "reason": "object_under_unregistered_root",
                             "path": str(obj)})
            continue

        if not obj.exists():
            failures.append({"sb_match_id": sb_id, "reason": "manifest_present_but_object_absent",
                             "path": str(obj)})
            continue

        raw = obj.read_bytes()
        if not raw:
            failures.append({"sb_match_id": sb_id, "reason": "empty_file", "path": str(obj)})
            continue

        actual_sha = sha256_bytes(raw)
        if actual_sha != recorded_sha:
            failures.append({"sb_match_id": sb_id, "reason": "hash_mismatch",
                             "recorded": recorded_sha, "actual": actual_sha})
            continue
        # content-addressing: filename stem must equal the sha
        if obj.stem != actual_sha:
            failures.append({"sb_match_id": sb_id, "reason": "filename_hash_disagreement",
                             "filename": obj.name, "actual": actual_sha})
            continue

        vr = validate_event_bytes(raw)
        if not vr.ok:
            failures.append({"sb_match_id": sb_id, "reason": vr.reason, "path": str(obj)})
            continue

        # id must resolve unambiguously to exactly one exact bridge row
        if bridge and sb_id not in bridge:
            failures.append({"sb_match_id": sb_id, "reason": "not_in_exact_bridge"})
            continue

    # Orphan / unregistered-root scan: every object file on disk must (a) sit at the
    # canonical sharded path objects/<sha[:2]>/<sha>.json and (b) be referenced by the index.
    shard_len = int(load_contract()["content_addressing"]["shard_prefix_len"])
    indexed_paths = {str((lake.root / rec["local_path"]).resolve())
                     for rec in index.values() if rec.get("local_path")}
    if lake.objects.exists():
        for obj in lake.objects.rglob("*.json"):
            ro = obj.resolve()
            stem = obj.stem
            canonical = (lake.objects / stem[:shard_len] / f"{stem}.json").resolve()
            if ro != canonical:
                failures.append({"reason": "object_under_unregistered_root", "path": lake.rel(ro)})
                continue
            if str(ro) not in indexed_paths:
                failures.append({"reason": "orphan_object_not_in_index", "path": lake.rel(ro)})

    rep = SentinelReport(ok=len(failures) == 0, checked=len(index), failures=failures, ts=_utc_now())
    if write_report:
        lake.integrity.mkdir(parents=True, exist_ok=True)
        out = lake.integrity / "sentinel_report.json"
        _atomic_write_text(out, json.dumps(rep.to_dict(), indent=2, ensure_ascii=False))
    return rep


def log_run(lake: Lake, name: str, payload: dict[str, Any]) -> Path:
    lake.logs.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    p = lake.logs / f"{name}_{ts}.json"
    _atomic_write_text(p, json.dumps({"ts": _utc_now(), **payload}, indent=2, ensure_ascii=False))
    return p
