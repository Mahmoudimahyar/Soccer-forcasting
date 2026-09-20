"""Canonical model identity + legacy-alias resolution (Offline Hardening Phase 0).

Resolves namespace-colliding legacy labels (e.g. prematch 'M2' = market no-vig vs inplay 'M2' =
remaining-time Poisson) to durable canonical IDs WITHOUT mutating any historical row. Annotation only
ADDS canonical columns; it never overwrites existing values.
"""
from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
IDENTITY = ROOT / "schemas/model_identity_v1.yaml"
ALIASES = ROOT / "configs/model_alias_registry.yaml"
IDENTITY_FIELDS = ["model_namespace", "model_family", "canonical_model_id", "canonical_model_version",
                   "approval_status", "research_status", "runtime_eligible", "trade_eligible"]


def load_identity(path=IDENTITY) -> dict:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return {m["canonical_model_id"]: m for m in data["models"]}


def load_aliases(path=ALIASES) -> dict:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    out = {}
    for a in data["aliases"]:
        key = (a["context"], a["legacy_alias"])
        if key in out and out[key] != a["canonical_model_id"]:
            raise ValueError(f"alias registry conflict for {key}: {out[key]} vs {a['canonical_model_id']}")
        out[key] = a["canonical_model_id"]
    return out


def resolve(legacy_alias: str, context: str, aliases: dict | None = None) -> str:
    aliases = aliases if aliases is not None else load_aliases()
    key = (context, legacy_alias)
    if key not in aliases:
        raise KeyError(f"unresolvable legacy alias {legacy_alias!r} in context {context!r}")
    return aliases[key]


def model_info(canonical_id: str, identity: dict | None = None) -> dict:
    identity = identity if identity is not None else load_identity()
    if canonical_id not in identity:
        raise KeyError(f"unknown canonical_model_id {canonical_id!r}")
    return identity[canonical_id]


def check_invariants(identity: dict | None = None) -> list:
    identity = identity if identity is not None else load_identity()
    v = []
    runtime = [cid for cid, m in identity.items() if m.get("runtime_eligible")]
    if runtime != ["prematch.b1_elo"]:
        v.append(f"runtime_eligible set must be exactly ['prematch.b1_elo'], got {runtime}")
    trade = [cid for cid, m in identity.items() if m.get("trade_eligible")]
    if trade:
        v.append(f"no model may be trade_eligible (paper-only), got {trade}")
    for cid, m in identity.items():
        if m.get("research_status") == "research_only" and m.get("runtime_eligible"):
            v.append(f"research_only model {cid} must not be runtime_eligible")
    return v


def annotate(df, context: str, alias_col: str = "model", identity=None, aliases=None):
    """Return a COPY of df with canonical identity columns ADDED (legacy columns untouched)."""
    identity = identity if identity is not None else load_identity()
    aliases = aliases if aliases is not None else load_aliases()
    out = df.copy()
    canon = []
    for a in out[alias_col].astype(str):
        try:
            canon.append(resolve(a, context, aliases))
        except KeyError:
            canon.append(None)
    out["legacy_model_alias"] = out[alias_col]
    out["canonical_model_id"] = canon
    for f in ["model_namespace", "model_family", "approval_status", "research_status",
              "runtime_eligible", "trade_eligible", "canonical_model_version"]:
        out[f] = [identity.get(c, {}).get(f) if c else None for c in canon]
    return out
