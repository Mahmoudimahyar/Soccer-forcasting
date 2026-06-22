"""Rebuild the 2022 WC group-stage event replay with the corrected provider-aware semantics and run
the 48-match reconciliation release gate. Read-only over cached data; raw files untouched.
Writes data/processed/event_replay_2022_quality.csv.
"""
import glob
import hashlib
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from wcdrawlab.research.event_semantics import score_from_events  # noqa: E402

C = ROOT / "data/raw/api_football_2022_worldcup"
fx = {f["fixture"]["id"]: f for f in json.loads((C / "fixtures.json").read_text(encoding="utf-8"))["response"]}
grp = {i: f for i, f in fx.items() if "group" in str(f.get("league", {}).get("round", "")).lower()}

rows = []
for fp in sorted(glob.glob(str(C / "events_*.json"))):
    fid = int(Path(fp).stem.split("_")[1])
    f = grp.get(fid)
    if not f:
        continue
    raw = Path(fp).read_bytes()
    ev = json.loads(raw)["response"]
    home, away = f["teams"]["home"]["name"], f["teams"]["away"]["name"]
    off_h, off_a = f["goals"]["home"], f["goals"]["away"]
    s = score_from_events(ev, home, away, "api_football")
    own_goal = any(e.get("type") == "Goal" and str(e.get("detail")) == "Own Goal" for e in ev)
    var = any(e.get("type") == "Var" for e in ev)
    missing_minute = any(e.get("type") == "Goal" and (e.get("time") or {}).get("elapsed") is None for e in ev)
    exact = (s["home"], s["away"]) == (off_h, off_a)
    rows.append({
        "fixture_id": fid, "home": home, "away": away,
        "official_score": f"{off_h}-{off_a}", "replay_score": f"{s['home']}-{s['away']}",
        "exact_reconcile": exact,
        "goals_by_team_reconcile": (s["home"] == off_h and s["away"] == off_a),
        "own_goal_present": own_goal, "var_present": var, "missing_minute": missing_minute,
        "provider": "api_football", "quality_status": s["quality_status"],
        "raw_payload_sha256_16": hashlib.sha256(raw).hexdigest()[:16],
        "classification": "exact" if exact else "DISCREPANCY",
    })

q = pd.DataFrame(rows).sort_values("fixture_id")
q.to_csv(ROOT / "data/processed/event_replay_2022_quality.csv", index=False)
n = len(q); ok = int(q.exact_reconcile.sum())
print(f"2022 group-stage replay reconciliation: {ok}/{n} exact")
print(f"  own-goal matches: {int(q.own_goal_present.sum())} | VAR matches: {int(q.var_present.sum())} | "
      f"missing-minute matches: {int(q.missing_minute.sum())} | degraded quality: {int((q.quality_status!='ok').sum())}")
if ok != n:
    print("  REMAINING DISCREPANCIES:")
    print(q[~q.exact_reconcile][["fixture_id", "home", "away", "official_score", "replay_score", "own_goal_present", "var_present"]].to_string(index=False))
else:
    print("  RELEASE GATE: PASS (48/48 exact)")
# show own-goal matches specifically (the remediation target)
print("\n  own-goal matches (post-fix):")
print(q[q.own_goal_present][["fixture_id", "home", "away", "official_score", "replay_score", "exact_reconcile"]].to_string(index=False))
