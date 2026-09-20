"""Daily quota-window resume: dynamic collector-aware reserve (NOT static 25%). Probes /status; if
remaining > dynamic reserve, resumes the canonical backfill from the first unfinished fixture; else exits
harmlessly. No concurrent backfills. API-Football only; key read-only/never printed. research_only."""
import sys, json, subprocess
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT/"src"))
from wcdrawlab.research import quota_policy as QP
from wcdrawlab.research.paid_source import safe_config
from wcdrawlab.operations.api_football_adapter import ApiFootballReadOnly
def main():
    st = safe_config.load_paid_keys()
    if st["API_FOOTBALL_KEY"] != "SET": print(json.dumps({"state":"PREFLIGHT_FAILED"})); return
    af = ApiFootballReadOnly(daily_budget=2, reserve=0, min_interval_s=0.5)
    try:
        s = af.get("/status"); req = ((s.get("response") or {}).get("requests") or {}) if s.get("ok") else {}
        remaining = int(req.get("limit_day") or 0) - int(req.get("current") or 0)
    except Exception:
        print(json.dumps({"state":"WAITING_FOR_API_QUOTA","reason":"probe failed"})); return
    budget, reserve = QP.research_budget(remaining, 5000)
    if budget < 2:
        print(json.dumps({"state":"WAITING_FOR_API_QUOTA","remaining":remaining,"reserve":reserve,
                          "research_budget":budget,"action":"exit harmlessly; retry next window"})); return
    p = subprocess.run([sys.executable, str(ROOT/"scripts/complete_full_player_history_backfill.py"),
                        "--max-requests", str(budget)], capture_output=True, text=True, cwd=str(ROOT))
    print((p.stdout or "").strip().splitlines()[-1] if p.stdout else json.dumps({"state":"RUNNING"}))
if __name__ == "__main__": main()
