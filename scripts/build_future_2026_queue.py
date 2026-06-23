"""Phase 4: build the future-2026 prospective queue from authoritative API-Football fixtures (read-only).
Only NOT-STARTED matches with a resolvable Elo anchor are 'eligible' (the clean prospective pool);
finished/in-progress matches are excluded with an explicit reason. Pre-match Elo anchors are precomputed
so the collector needs no live call for pre-match windows.
"""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from wcdrawlab.operations.api_football_adapter import ApiFootballReadOnly  # noqa: E402
from wcdrawlab.ingest import canonical_team_name  # noqa: E402
from wcdrawlab.research.inplay_models.models import pregame_lambdas, update_inplay_probabilities, InPlayState  # noqa: E402

WINDOWS = "T-90;T-15;m0;m15;m30;HT;m60;m75;m85"

# Local name aliases: API-Football fixture names -> elo_history names (do not touch shared ingest).
ALIASES = {"Bosnia & Herzegovina": "Bosnia", "Cape Verde Islands": "Cape Verde"}


def _canon(name):
    return canonical_team_name(ALIASES.get(name, name))


def latest_elo_by_team(elo):
    """Each team's MOST RECENT Elo rating (future fixtures have no head-to-head history to look up)."""
    e = elo.copy()
    e["ts"] = pd.to_datetime(e["date"], errors="coerce", utc=True)
    rows = []
    for r in e.itertuples():
        rows.append((canonical_team_name(r.team_a), r.ts, float(r.elo_a_pre)))
        rows.append((canonical_team_name(r.team_b), r.ts, float(r.elo_b_pre)))
    d = pd.DataFrame(rows, columns=["team", "ts", "elo"]).dropna(subset=["ts"])
    return d.sort_values("ts").groupby("team").elo.last().to_dict()


def elo_anchor(delta):
    lh, la = pregame_lambdas(delta)
    p = update_inplay_probabilities(lh, la, InPlayState(minute=0.0, goals_a=0, goals_b=0,
                                                        red_cards_a=0, red_cards_b=0))
    return p.p_a_win, p.p_draw, p.p_b_win


def main():
    try:
        from dotenv import load_dotenv; load_dotenv(ROOT / ".env")
    except Exception:
        pass
    api = ApiFootballReadOnly(daily_budget=50, reserve=10, min_interval_s=0.0,
                              raw_dir=ROOT / "data/raw/operations")
    res = api.get("/fixtures", {"league": 1, "season": 2026})
    fixtures = res["response"]
    elo = pd.read_csv(ROOT / "data/processed/elo_history.csv")
    latest = latest_elo_by_team(elo)

    rows = []
    for f in fixtures:
        fx = f["fixture"]; mid = fx["id"]; status = fx["status"]["short"]
        home = f["teams"]["home"]["name"]; away = f["teams"]["away"]["name"]
        rnd = (f.get("league") or {}).get("round", "")
        stage = "group" if "group" in rnd.lower() else "knockout"
        delta = float("nan"); anchor = (None, None, None)
        if status == "NS":
            eh, ea_ = latest.get(_canon(home)), latest.get(_canon(away))
            if eh is not None and ea_ is not None:
                delta = eh - ea_
                anchor = elo_anchor(delta)
                state, reason = "eligible", ""
            else:
                miss = [t for t, v in [(home, eh), (away, ea_)] if v is None]
                state, reason = "blocked", f"no_elo_rating_for:{';'.join(miss)}"
        elif status in ("FT", "AET", "PEN"):
            state, reason = "skipped", "completed_not_clean_prospective"
        else:
            state, reason = "skipped", f"in_progress_or_other_status:{status}"
        rows.append({
            "match_id": mid, "home": home, "away": away, "kickoff_utc": fx["date"],
            "stage": stage, "round": rnd, "status": status, "state": state, "reason": reason,
            "elo_delta_home": delta, "anchor_p_home": anchor[0], "anchor_p_draw": anchor[1],
            "anchor_p_away": anchor[2], "scheduled_windows": WINDOWS,
            "source_dependencies": "pre_match:elo_history(deterministic);in_play:api_football_events",
            "frozen_model_version": "m2_frozen@v2", "ledger_path": "data/processed/prospective/ledger.jsonl",
            "scoring_status": "pending",
        })
    df = pd.DataFrame(rows).sort_values("kickoff_utc")
    outp = ROOT / "data/reference/future_2026_prospective_queue.csv"
    df.to_csv(outp, index=False)
    n = df.state.value_counts().to_dict()
    print(f"queue: {len(df)} fixtures -> {dict(n)}")
    print(f"  eligible (clean prospective pool): {(df.state=='eligible').sum()}")
    print(f"wrote {outp}")


if __name__ == "__main__":
    main()
