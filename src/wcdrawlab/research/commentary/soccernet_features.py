"""Phase 4: parse SoccerNet action labels + SoccerNet-Echoes commentary into half-relative event/segment
series for alignment. Echoes start_time (s from start of half) and label position (ms from start of half)
are BOTH half-relative -> directly comparable per (match, half). Raw text stays in memory only (gitignored
source); nothing here writes raw text to tracked files. research_only / historical_weak_supervision_only.
"""
from __future__ import annotations

import json
from pathlib import Path

from . import soccernet_mapping as M
from . import normalization as N


def _match_id_from_dir(p: Path, root: Path) -> str:
    return str(p.parent.relative_to(root)).replace("\\", "/")


def load_label_events(labels_root) -> dict:
    """match_id -> [ {half:int, t_s:float, canonical:str, source_label:str, team:str, visibility:str} ]"""
    root = Path(labels_root)
    out = {}
    for fp in root.rglob("Labels-v2.json"):
        mid = _match_id_from_dir(fp, root)
        d = json.loads(fp.read_text(encoding="utf-8"))
        evs = []
        for a in d.get("annotations", []):
            gt = a.get("gameTime", "")
            try:
                half = int(gt.split(" - ")[0])
            except Exception:
                half = 0
            try:
                t_s = float(a.get("position", 0)) / 1000.0
            except Exception:
                t_s = 0.0
            canonical, support, conf = M.map_to_canonical_event(a.get("label", ""))
            evs.append({"half": half, "t_s": t_s, "canonical": canonical, "support": support,
                        "source_label": a.get("label"), "team": a.get("team"),
                        "visibility": a.get("visibility")})
        out[mid] = sorted(evs, key=lambda e: (e["half"], e["t_s"]))
    return out


def echoes_match_id(g: str) -> str:
    parts = str(g).replace("\\", "/").rstrip("/").split("/")
    if parts and parts[-1].isdigit():
        return "/".join(parts[:-1])
    return "/".join(parts)


def echoes_half(g: str) -> int:
    parts = str(g).replace("\\", "/").rstrip("/").split("/")
    return int(parts[-1]) if parts and parts[-1].isdigit() else 0


def load_echoes_segments(arrow_path, keep_match_ids=None) -> dict:
    """match_id -> [ {half:int, t_s:float, text:str, norm:str, content_hash:str} ] (raw text in-memory only)."""
    import pyarrow as pa
    keep = set(keep_match_ids) if keep_match_ids is not None else None
    try:
        tbl = pa.ipc.open_file(pa.memory_map(str(arrow_path), "r")).read_all()
    except Exception:
        with pa.OSFile(str(arrow_path), "rb") as f:
            tbl = pa.ipc.open_stream(f).read_all()
    g = tbl.column("game").to_pylist()
    st = tbl.column("start_time").to_pylist()
    tx = tbl.column("text").to_pylist()
    out = {}
    for i in range(len(g)):
        mid = echoes_match_id(g[i])
        if keep is not None and mid not in keep:
            continue
        norm = N.normalize_text(tx[i] or "")
        out.setdefault(mid, []).append({"half": echoes_half(g[i]), "t_s": float(st[i] or 0.0),
                                        "text": tx[i] or "", "norm": norm,
                                        "content_hash": N.content_hash(tx[i] or "")})
    for mid in out:
        out[mid].sort(key=lambda s: (s["half"], s["t_s"]))
    return out
