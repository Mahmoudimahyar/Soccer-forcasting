"""Append-only, immutable raw snapshot storage + provenance envelope construction.

Guarantees:
  - Raw snapshots are content-addressed (filename = sha256 of canonical payload) and IMMUTABLE:
    an existing snapshot is never overwritten; re-ingesting identical bytes is idempotent.
  - Every snapshot carries the full raw_provenance_envelope (schemas/live_data_contracts.yaml).
  - Normalized records retain raw_payload_hash, linking back to the immutable raw row.
No network, no secrets. Pure local filesystem.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0"
QUALITY_VALUES = {"ok", "partial", "suspect", "conflict"}
RECON_VALUES = {"single_source", "reconciled", "unresolved", "superseded"}


class RawStoreError(RuntimeError):
    """Raised on any attempt to mutate an immutable raw snapshot or on invalid input."""


def payload_sha256(payload: Any) -> str:
    """Deterministic sha256 of a JSON-serializable payload (canonical, sorted keys)."""
    data = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def make_envelope(
    *,
    source_name: str,
    provider_endpoint: str,
    match_id: str,
    raw_payload: Any,
    retrieval_timestamp_utc: str,
    source_url_or_endpoint: str,
    ingestion_run_id: str,
    event_timestamp_utc: str | None = None,
    published_timestamp_utc: str | None = None,
    provider_match_id: str | None = None,
    provider_event_id: str | None = None,
    quality_status: str = "ok",
    reconciliation_status: str = "single_source",
    schema_version: str = SCHEMA_VERSION,
) -> dict[str, Any]:
    if quality_status not in QUALITY_VALUES:
        raise RawStoreError(f"quality_status must be one of {sorted(QUALITY_VALUES)}")
    if reconciliation_status not in RECON_VALUES:
        raise RawStoreError(f"reconciliation_status must be one of {sorted(RECON_VALUES)}")
    return {
        "source_name": source_name,
        "provider_endpoint": provider_endpoint,
        "retrieval_timestamp_utc": retrieval_timestamp_utc,
        "event_timestamp_utc": event_timestamp_utc,
        "published_timestamp_utc": published_timestamp_utc,
        "match_id": match_id,
        "provider_match_id": provider_match_id,
        "provider_event_id": provider_event_id,
        "source_url_or_endpoint": source_url_or_endpoint,
        "raw_payload_hash": payload_sha256(raw_payload),
        "schema_version": schema_version,
        "ingestion_run_id": ingestion_run_id,
        "quality_status": quality_status,
        "reconciliation_status": reconciliation_status,
    }


def _safe_seg(s: str) -> str:
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in str(s)) or "unknown"


def append_raw_snapshot(envelope: dict[str, Any], raw_payload: Any, output_dir: str | Path) -> dict[str, Any]:
    """Write one immutable, content-addressed raw snapshot. Idempotent for identical bytes.

    Returns {"path", "raw_payload_hash", "wrote": bool}. Raises RawStoreError if an existing file at
    the content-addressed path somehow differs (would indicate corruption / illegal mutation).
    """
    h = payload_sha256(raw_payload)
    if envelope.get("raw_payload_hash") != h:
        raise RawStoreError("envelope.raw_payload_hash does not match the payload (refusing to store).")
    out = Path(output_dir)
    folder = out / _safe_seg(envelope["source_name"]) / _safe_seg(envelope["match_id"])
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{h}.json"
    record = {"envelope": envelope, "payload": raw_payload}

    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
        if payload_sha256(existing.get("payload")) != h:
            raise RawStoreError(f"immutable snapshot mismatch at {path} (content-addressed file changed).")
        return {"path": str(path), "raw_payload_hash": h, "wrote": False}  # idempotent

    path.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
    # append-only audit index
    index = out / "index.jsonl"
    line = json.dumps({k: envelope.get(k) for k in
                       ("ingestion_run_id", "source_name", "match_id", "provider_endpoint",
                        "retrieval_timestamp_utc", "raw_payload_hash", "quality_status",
                        "reconciliation_status")}, ensure_ascii=False)
    with index.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")
    return {"path": str(path), "raw_payload_hash": h, "wrote": True}
