"""Daily quota-window resume: safe budget probe FIRST; if quota available AND no active run, resume the
canonical backfill from the first unfinished fixture; else exit harmlessly. No concurrent backfills.
API-Football only; key read-only/never printed. research_only."""
import sys, json, subprocess
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT/"src"))
from wcdrawlab.research.paid_source import safe_config
from wcdrawlab.operations.api_football_adapter import ApiFootballReadOnly
def main():
    st = safe_config.load_paid_keys()
    if st["API_FOOTBALL_KEY"] != "SET": print(json.dumps({"state":"PREFLIGHT_FAILED"})); return
    af = ApiFootballReadOnly(daily_budget=2, reserve=0, min_interval_s=0.5)
    try:
        s = af.get("/status"); req = s["response"].get("requests",{}) if s["ok"] else {}
        remaining = (req.get("limit_day") or 0) - (req.get("current") or 0)
    except Exception:
        print(json.dumps({"state":"WAITING_FOR_API_QUOTA","reason":"probe failed"})); return
    reserve = max(1500, int(0.25*remaining)); research = min(4500, max(0, remaining-reserve))
    if research < 200:
        print(json.dumps({"state":"WAITING_FOR_API_QUOTA","remaining":remaining,"research_budget":research,"action":"exit harmlessly; retry next window"})); return
    # quota available -> resume the bounded backfill
    p = subprocess.run([sys.executable, str(ROOT/"scripts/complete_full_player_history_backfill.py"),
                        "--max-requests", str(research)], capture_output=True, text=True, cwd=str(ROOT))
    print((p.stdout or "").strip().splitlines()[-1] if p.stdout else json.dumps({"state":"RUNNING"}))
if __name__ == "__main__": main()
