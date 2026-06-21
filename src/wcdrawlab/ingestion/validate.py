"""Validation against schemas/live_data_contracts.yaml.

Checks (a) the raw provenance envelope and (b) normalized records against their schema's required
fields, primary key, and any declared enum values. Pure functions; returns a list of error strings
(empty = valid). No network, no secrets.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

_CONTRACTS = Path(__file__).resolve().parents[3] / "schemas" / "live_data_contracts.yaml"


@lru_cache(maxsize=1)
def contracts() -> dict[str, Any]:
    return yaml.safe_load(_CONTRACTS.read_text(encoding="utf-8"))


def _required_fields(spec: dict[str, Any]) -> list[str]:
    out = []
    for name, meta in spec.items():
        if isinstance(meta, dict) and meta.get("required"):
            out.append(name)
    return out


def _enum_values(meta: dict[str, Any]) -> list | None:
    if isinstance(meta, dict) and meta.get("type") == "enum":
        return meta.get("values")
    return None


def validate_envelope(env: dict[str, Any]) -> list[str]:
    spec = contracts()["raw_provenance_envelope"]
    errors: list[str] = []
    for field in _required_fields(spec):
        if env.get(field) in (None, ""):
            errors.append(f"missing required envelope field: {field}")
    for field, meta in spec.items():
        vals = _enum_values(meta)
        if vals is not None and env.get(field) is not None and env.get(field) not in vals:
            errors.append(f"envelope.{field}={env.get(field)!r} not in {vals}")
    return errors


def list_schemas() -> list[str]:
    return sorted(contracts()["normalized_schemas"].keys())


def validate_normalized(schema_key: str, row: dict[str, Any]) -> list[str]:
    schemas = contracts()["normalized_schemas"]
    if schema_key not in schemas:
        return [f"unknown schema_key: {schema_key} (known: {list_schemas()})"]
    schema = schemas[schema_key]
    fields = schema.get("fields", {})
    errors: list[str] = []
    # primary key present
    for pk in schema.get("primary_key", []):
        if row.get(pk) in (None, ""):
            errors.append(f"{schema_key}: missing primary-key field {pk}")
    # required fields present
    for field in _required_fields(fields):
        if row.get(field) in (None, ""):
            errors.append(f"{schema_key}: missing required field {field}")
    # enum membership
    for field, meta in fields.items():
        vals = _enum_values(meta)
        if vals is not None and row.get(field) is not None and row.get(field) not in vals:
            errors.append(f"{schema_key}.{field}={row.get(field)!r} not in {vals}")
    return errors
