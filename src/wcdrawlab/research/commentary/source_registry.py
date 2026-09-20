"""Load + query the commentary source rights registry (Phase 2 schema). research_only."""
from __future__ import annotations
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[4]
RIGHTS = ROOT / "schemas/commentary_source_rights_v1.yaml"


def load_rights(path=RIGHTS) -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def classification(source_id, rights=None) -> str:
    rights = rights or load_rights()
    return (rights.get("sources", {}).get(source_id) or {}).get("classification", "unavailable_or_unverified")


def is_use_permitted(source_id, use_type, rights=None) -> bool:
    rights = rights or load_rights()
    return bool((rights.get("sources", {}).get(source_id) or {}).get("matrix", {}).get(use_type, False))


def rights_ok_for_research(source_id, rights=None) -> bool:
    """Research download/derived-label use permitted (a prerequisite, not sufficient, for live use)."""
    return is_use_permitted(source_id, "store_derived_event_labels", rights) or \
        is_use_permitted(source_id, "train_model_on_text", rights)
