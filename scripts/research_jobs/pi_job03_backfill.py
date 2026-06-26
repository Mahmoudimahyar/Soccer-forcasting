"""JOB3: player-history backfill (events+lineups) by invoking the inherited bounded, resumable,
append-only scripts/player_history_backfill.py. API-Football ONLY (no Odds API). The backfill honors
>=1s/request, <=2 retries, first-write-wins, and a per-fixture manifest; it stops on quota/auth. This
wrapper passes the remaining supervisor API budget as --max-requests and reports requests spent so the
controller can debit the whole-run cap. Skips (not fails) if the API key is missing or budget is zero.
research_only / experimental / not_runtime_approved."""
import sys, json, subprocess, re
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent)); import _job
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT / "src"))
BACKFILL = ROOT / "scripts/player_history_backfill.py"
RAW = ROOT / "data/raw/player_history_corpus"; PROG = RAW / "progress.json"


def _done_count():
    if PROG.exists():
        try:
            return len(json.loads(PROG.read_text(encoding="utf-8")).get("done", []))
        except Exception:
            return 0
    return 0


def main():
    _job.run_dir()
    budget = _job.api_budget()
    if budget < 4:
        _job.emit("skipped", reason=f"insufficient API budget for backfill (remaining={budget})"); return
    try:
        from wcdrawlab.research.paid_source import safe_config
        if safe_config.load_paid_keys().get("API_FOOTBALL_KEY") != "SET":
            _job.emit("skipped", reason="API_FOOTBALL_KEY missing -> backfill skipped (no network)"); return
    except Exception as e:
        _job.emit("skipped", reason=f"safe_config unavailable: {e}"); return
    before = _done_count()
    # cap this job's spend at the supervisor's remaining budget (2 requests per fixture)
    max_requests = max(0, min(budget, 4200))
    p = subprocess.run([sys.executable, str(BACKFILL), "--max-requests", str(max_requests)],
                       capture_output=True, text=True, cwd=str(ROOT))
    after = _done_count()
    out = (p.stdout or "") + (p.stderr or "")
    m = re.search(r"reqs=(\d+)", out)
    reqs = int(m.group(1)) if m else 0
    auth = "auth=True" in out
    pulled = after - before
    status = "failed" if auth else "complete"
    _job.emit(status,
              reason=(f"backfill auth-blocked after {pulled} fixtures (reqs={reqs})" if auth
                      else f"backfill pulled {pulled} fixtures (done_total={after}, reqs={reqs})"),
              api_requests=reqs,
              state_updates={"player_history_done": after, "player_history_pulled_this_run": pulled})


main()
