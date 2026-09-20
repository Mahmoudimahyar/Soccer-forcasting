"""Tiny job helper: arg parsing + JSON result emission + shared-state access. research_only."""
import argparse, json, os
def run_dir():
    ap = argparse.ArgumentParser(); ap.add_argument("--run-dir", required=True)
    return ap.parse_args().run_dir
def shared():
    try: return json.loads(os.environ.get("DEEP_RESEARCH_SHARED", "{}"))
    except Exception: return {}
def api_budget():
    try: return int(os.environ.get("DEEP_RESEARCH_API_BUDGET", "0"))
    except Exception: return 0
def emit(status, reason="", api_requests=0, state_updates=None, **extra):
    print(json.dumps({"status": status, "reason": reason, "api_requests": api_requests,
                      "state_updates": state_updates or {}, **extra}))
