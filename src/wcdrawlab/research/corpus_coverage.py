"""Raw-backed corpus coverage across REGISTERED data roots (canonical + prior). The completion gate must be
measured by ACTUAL events+lineups raw present, NOT by the done-list length (which can over-report). research_only."""
from __future__ import annotations
import glob, json, os
from wcdrawlab.research import data_roots as DR
ROOTS = {"canonical": "api_football_player_history", "prior": "api_football_player_history_prior"}
def _endpoint(get_field, filename):
    g = (str(get_field) + " " + filename).lower()
    if "event" in g: return "events"
    if "lineup" in g: return "lineups"
    return None
def _root_cov(root):
    cov = {}
    if not root.exists(): return cov
    for fp in glob.glob(str(root / "*.json")):
        try:
            p = json.load(open(fp, encoding="utf-8")); par = p.get("parameters") or {}
            fid = par.get("fixture")
            if fid is None: continue
            ep = _endpoint(p.get("get", ""), os.path.basename(fp))
            if ep and isinstance(p.get("response"), list):
                cov.setdefault(str(fid), set()).add(ep)
        except Exception:
            pass
    return cov
def coverage(done_ids):
    done_ids = [str(d) for d in done_ids]
    per_root_full = {}; union = {}
    for label, name in ROOTS.items():
        try: c = _root_cov(DR.get_root(name))
        except Exception: c = {}
        per_root_full[label] = sum(1 for eps in c.values() if {"events", "lineups"} <= eps)
        for f, eps in c.items(): union.setdefault(f, set()).update(eps)
    fully = {f for f, eps in union.items() if {"events", "lineups"} <= eps}
    backed = [d for d in done_ids if d in fully]; missing = [d for d in done_ids if d not in fully]
    return {"per_root_full_events_and_lineups": per_root_full, "done": len(done_ids),
            "raw_backed_across_registered_roots": len(backed), "missing_ids": missing,
            "coverage_rate": round(len(backed) / len(done_ids), 4) if done_ids else 0.0}
