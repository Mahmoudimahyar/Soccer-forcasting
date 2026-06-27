import argparse, json, os, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT/"scripts/research_jobs"))
def run_dir():
    ap=argparse.ArgumentParser(); ap.add_argument("--run-dir", required=True); return ap.parse_args().run_dir
def shared():
    try: return json.loads(os.environ.get("DEEP_RESEARCH_SHARED","{}"))
    except Exception: return {}
def emit(status, reason="", state_updates=None, **x):
    print(json.dumps({"status":status,"reason":reason,"state_updates":state_updates or {}, **x}))
