"""Canonical data-root resolver. Every research job resolves source/output locations through here — no
hard-coded raw paths. Fails closed on unknown/forbidden roots. research_only."""
from __future__ import annotations
from pathlib import Path
import yaml
_CFG = Path(__file__).resolve().parents[3] / "configs/research_data_roots.yaml"
COLLECTOR = "worldcup_draw_model_lab_FINAL"
def _load():
    return yaml.safe_load(_CFG.read_text(encoding="utf-8"))
def get_root(name: str) -> Path:
    cfg = _load(); r = cfg["roots"].get(name)
    if r is None:
        raise KeyError(f"unknown data root '{name}' (not in research_data_roots.yaml)")
    p = Path(r["path"])
    # fail closed: never resolve into the active collector checkout
    if COLLECTOR in str(p).replace("\\", "/") and "worktree" not in str(p):
        raise PermissionError(f"root '{name}' resolves into the active collector checkout -> forbidden")
    return p
def manifest(name: str) -> Path:
    return Path(_load()["manifests"][name])
def forbidden_roots():
    return _load().get("forbidden_roots", [])
