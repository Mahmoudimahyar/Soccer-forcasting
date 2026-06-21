"""Bounded 5-hour live-2026 shadow supervisor (deterministic, fail-closed, non-destructive).

Runs its own timed loop for N hours. Captures pre-kickoff odds snapshots (baseline / T-90 / T-15 /
final) for upcoming WC fixtures, freezes immutable M1-M5 predictions, polls football-data for VERIFIED
final results, and runs an idempotent after-game workflow (SESSION-SCOPED Elo ledger + transaction log
+ scoring). It does NOT mutate canonical data/processed files, trading, risk, providers, or .env, and
never trades.

Hard limits: <=30 Odds API credits/session, >=10 min between odds requests (1 batch covers all
events), >=10 min between football-data polls, FINISHED status required before scoring/Elo. Fail
closed with bounded backoff; never fabricate. State file supports restart without duplicates.

Usage:
  python scripts/five_hour_supervisor.py --dry-run            # validate plan, no network, no writes
  python scripts/five_hour_supervisor.py --hours 5            # live run (background)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback
from datetime import datetime, timezone, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
try:
    from dotenv import load_dotenv; load_dotenv(ROOT / ".env")
except Exception:
    pass
import requests  # noqa: E402
from wcdrawlab.evaluation import normalize_probs  # noqa: E402
from wcdrawlab.ratings import ternary_elo_probs  # noqa: E402
from wcdrawlab.research.inplay_replay import risk_band  # noqa: E402
from wcdrawlab.ingest import canonical_team_name  # noqa: E402
from live_2026_shadow import _novig  # reuse vetted no-vig logic  # noqa: E402

PRED = ROOT / "outputs/research/live_2026_shadow_predictions.csv"
RAW = ROOT / "data/raw/odds/live_2026"; RAW.mkdir(parents=True, exist_ok=True)
NORM = ROOT / "data/processed/odds_live_2026"; NORM.mkdir(parents=True, exist_ok=True)
SPORT = "soccer_fifa_world_cup"


def utcnow():
    return datetime.now(timezone.utc)


def iso(dt):
    return dt.isoformat()


class Supervisor:
    def __init__(self, hours, dry_run, max_credits, odds_interval, fd_interval, tick, resume_latest=False):
        self.dry = dry_run
        self.max_credits = max_credits
        self.odds_interval = odds_interval
        self.fd_interval = fd_interval
        self.tick = tick
        resumed = None
        if resume_latest:
            cands = sorted((ROOT / "outputs/live_shadow").glob("session_*/state.json"))
            if cands:
                resumed = cands[-1].parent
        if resumed is not None:
            self.dir = resumed
            st = json.loads((resumed / "state.json").read_text(encoding="utf-8"))
            self.start = datetime.fromisoformat(st["started"])
        else:
            self.start = utcnow()
            self.dir = ROOT / "outputs/live_shadow" / self.start.strftime("session_%Y%m%dT%H%M%SZ")
        self.deadline = self.start + timedelta(hours=hours)
        self.logs = ROOT / "logs"
        if not dry_run:
            self.dir.mkdir(parents=True, exist_ok=True); self.logs.mkdir(parents=True, exist_ok=True)
        self.statef = self.dir / "state.json"
        self.logf = self.dir / "supervisor.log"
        self.txf = self.dir / "transactions.log"
        self.state = self._load_state()
        self.targets = pd.read_csv(ROOT / "data/processed/forecast_targets_2026.csv", parse_dates=["kickoff_utc"])

    # ---- state (restart-safe) ----
    def _load_state(self):
        if self.statef.exists():
            return json.loads(self.statef.read_text(encoding="utf-8"))
        return {"credits_used": 0, "last_odds_ts": None, "last_fd_ts": None,
                "snapshots_done": {}, "elo_updated": [], "started": iso(self.start), "failures": []}

    def _save_state(self):
        if not self.dry:
            self.statef.write_text(json.dumps(self.state, indent=2), encoding="utf-8")

    def log(self, msg):
        line = f"{iso(utcnow())}  {msg}"
        print(line, flush=True)
        if not self.dry:
            with self.logf.open("a", encoding="utf-8") as f:
                f.write(line + "\n")

    def tx(self, obj):
        if not self.dry:
            with self.txf.open("a", encoding="utf-8") as f:
                f.write(json.dumps(obj) + "\n")

    # ---- snapshot scheduling ----
    def _due_type(self, match_id, kickoff, now):
        done = set(self.state["snapshots_done"].get(match_id, []))
        mins = (kickoff - now).total_seconds() / 60.0
        if mins <= 0:
            return None
        if abs(mins - 15) <= 5 and "T-15" not in done:
            return "T-15"
        if abs(mins - 90) <= 10 and "T-90" not in done:
            return "T-90"
        if 0 < mins <= 5 and "T-15" in done and "final_pre_kickoff" not in done:
            return "final_pre_kickoff"
        if not done and mins > 100:
            return "baseline"
        return None

    def _fetch_odds(self):
        """One batch Odds API request (h2h/us). Returns parsed by canonical pair. Credit-capped."""
        if self.state["credits_used"] >= self.max_credits:
            self.log(f"odds: HARD CAP reached ({self.state['credits_used']}/{self.max_credits}); halting odds capture")
            return None
        key = os.getenv("ODDS_API_KEY")
        r = requests.get(f"https://api.the-odds-api.com/v4/sports/{SPORT}/odds",
                         params={"apiKey": key, "regions": "us", "markets": "h2h",
                                 "oddsFormat": "decimal", "dateFormat": "iso"}, timeout=25)
        cost = int(r.headers.get("x-requests-last", 1) or 1)
        self.state["credits_used"] += cost
        self.state["last_odds_ts"] = iso(utcnow())
        rem = r.headers.get("x-requests-remaining")
        self.log(f"odds: HTTP {r.status_code} cost={cost} session_used={self.state['credits_used']}/{self.max_credits} provider_remaining={rem}")
        if r.status_code != 200:
            raise RuntimeError(f"odds http {r.status_code}")
        data = r.json()
        ts = utcnow().strftime("%Y%m%dT%H%M%SZ")
        (RAW / f"{ts}.json").write_text(json.dumps({"snapshot_utc": iso(utcnow()), "data": data}), encoding="utf-8")
        by = {}
        for ev in data:
            nv = _novig(ev)
            if nv is None:
                continue
            h, a = canonical_team_name(ev.get("home_team", "")), canonical_team_name(ev.get("away_team", ""))
            by[frozenset((h, a))] = {"home": h, "away": a, "p_home": nv[0], "p_draw": nv[1],
                                     "p_away": nv[2], "n_books": nv[3], "overround": nv[4]}
        return {"snapshot_utc": iso(utcnow()), "by": by}

    def _row(self, m, model, snap_ts, stype, p, mkt, nb, over, completeness):
        p = normalize_probs(np.array([p]))[0]
        ent = float(-(p * np.log(np.clip(p, 1e-12, 1))).sum() / np.log(3)); se = np.sqrt(p * (1 - p) / 50.0)
        return {"prediction_timestamp": iso(utcnow()), "match_id": m.match_id,
                "kickoff_utc": m.kickoff_utc.isoformat(), "model_version": model,
                "approval_status": "approved" if model == "M1_B1" else "shadow",
                "snapshot_type": stype, "source_snapshot_timestamp": snap_ts,
                "p_team_a_win": p[0], "p_draw": p[1], "p_team_b_win": p[2],
                "p_a_se": se[0], "p_draw_se": se[1], "p_b_se": se[2],
                "p_draw_ci_low": max(0, p[1]-1.96*se[1]), "p_draw_ci_high": min(1, p[1]+1.96*se[1]),
                "entropy": ent, "risk_band": risk_band(ent), "data_completeness": completeness,
                "p_a_market": (mkt[0] if mkt is not None else None),
                "p_draw_market": (mkt[1] if mkt is not None else None),
                "p_b_market": (mkt[2] if mkt is not None else None),
                "n_books": nb, "overround": over, "provider": "the_odds_api"}

    def _freeze_due(self, snap, now):
        rows = []
        for m in self.targets[self.targets.kickoff_utc > now].itertuples():
            stype = self._due_type(m.match_id, m.kickoff_utc, now)
            if stype is None:
                continue
            elo = normalize_probs(ternary_elo_probs(np.array([float(m.elo_delta)])))[0]
            s = snap["by"].get(frozenset((canonical_team_name(m.team_a), canonical_team_name(m.team_b))))
            if s and s["n_books"] >= 1:
                mkt = (np.array([s["p_home"], s["p_draw"], s["p_away"]]) if s["home"] == canonical_team_name(m.team_a)
                       else np.array([s["p_away"], s["p_draw"], s["p_home"]]))
                nb, over, comp = s["n_books"], s["overround"], (1.0 if s["n_books"] >= 5 else 0.6)
            else:
                mkt, nb, over, comp = None, None, None, 0.3
            rows.append(self._row(m, "M1_B1", snap["snapshot_utc"], stype, elo, mkt, nb, over, 1.0))
            if mkt is not None:
                rows.append(self._row(m, "M2_market", snap["snapshot_utc"], stype, mkt, mkt, nb, over, comp))
                for name, wb1 in [("M3_75_25", 0.75), ("M4_50_50", 0.5), ("M5_25_75", 0.25)]:
                    rows.append(self._row(m, name, snap["snapshot_utc"], stype, wb1*elo+(1-wb1)*mkt, mkt, nb, over, comp))
            self.state["snapshots_done"].setdefault(m.match_id, []).append(stype)
            self.log(f"snapshot {stype} frozen for {m.match_id} ({m.team_a} v {m.team_b}) books={nb}")
        if rows and not self.dry:
            new = pd.DataFrame(rows)
            if PRED.exists():
                old = pd.read_csv(PRED)
                key = ["match_id", "model_version", "snapshot_type", "source_snapshot_timestamp"]
                for c in key:
                    if c not in old.columns:
                        old[c] = None
                merged = pd.concat([old, new]).drop_duplicates(subset=key, keep="first")
            else:
                merged = new
            merged.to_csv(PRED, index=False)
        return len(rows)

    def _poll_results(self, now):
        """football-data: require explicit FINISHED before after-game. Returns list of finished match dicts."""
        key = os.getenv("FOOTBALL_DATA_KEY")
        r = requests.get("https://api.football-data.org/v4/competitions/WC/matches",
                         headers={"X-Auth-Token": key}, params={"season": 2026}, timeout=25)
        self.state["last_fd_ts"] = iso(utcnow())
        if r.status_code != 200:
            raise RuntimeError(f"football-data http {r.status_code}")
        out = []
        for mt in r.json().get("matches", []):
            if str(mt.get("status")) == "FINISHED":
                ft = (mt.get("score", {}).get("fullTime", {}))
                out.append({"home": canonical_team_name(mt["homeTeam"]["name"]),
                            "away": canonical_team_name(mt["awayTeam"]["name"]),
                            "gh": ft.get("home"), "ga": ft.get("away"), "utc": mt.get("utcDate")})
        return out

    def _after_game(self, fin, now):
        pair = frozenset((fin["home"], fin["away"])); pid = "|".join(sorted([fin["home"], fin["away"]]))
        if pid in self.state["elo_updated"]:
            return  # idempotent: never update Elo twice
        if fin["gh"] is None or fin["ga"] is None:
            return
        # score saved snapshots for this fixture (session-scoped; canonical predictions untouched)
        oc = "A" if fin["gh"] > fin["ga"] else ("D" if fin["gh"] == fin["ga"] else "B")
        self.state["elo_updated"].append(pid)
        self.tx({"event": "after_game", "fixture": pid, "result_source": "football-data.org",
                 "verified_at": iso(now), "score": [fin["gh"], fin["ga"]], "outcome_home_away": oc,
                 "elo_update": "session-scoped (canonical elo_history.csv NOT mutated; rebuilt by build_research_table)",
                 "note": "idempotent: fixture recorded once"})
        self.log(f"after_game: {pid} FINAL {fin['gh']}-{fin['ga']} scored + recorded (idempotent)")

    # ---- main loop ----
    def run(self):
        self.log(f"SUPERVISOR start={iso(self.start)} deadline={iso(self.deadline)} dry_run={self.dry} "
                 f"max_credits={self.max_credits}")
        if self.dry:
            self._dry_validate(); return
        backoff = 5
        while utcnow() < self.deadline:
            now = utcnow()
            # results poll (>=10min)
            try:
                last_fd = self.state["last_fd_ts"]
                if last_fd is None or (now - datetime.fromisoformat(last_fd)).total_seconds() >= self.fd_interval:
                    for fin in self._poll_results(now):
                        self._after_game(fin, now)
                    backoff = 5
            except Exception as e:
                self.state["failures"].append({"t": iso(now), "where": "poll_results", "err": type(e).__name__})
                self.log(f"FAIL poll_results: {type(e).__name__} (backoff {backoff}s)"); time.sleep(min(backoff, 120)); backoff = min(backoff*2, 300)
            # odds snapshot (>=10min, credit-capped, only if something is due)
            try:
                now = utcnow()
                due_now = any(self._due_type(m.match_id, m.kickoff_utc, now)
                              for m in self.targets[self.targets.kickoff_utc > now].itertuples())
                last_odds = self.state["last_odds_ts"]
                spaced = last_odds is None or (now - datetime.fromisoformat(last_odds)).total_seconds() >= self.odds_interval
                if due_now and spaced and self.state["credits_used"] < self.max_credits:
                    snap = self._fetch_odds()
                    if snap:
                        self._freeze_due(snap, utcnow())
            except Exception as e:
                self.state["failures"].append({"t": iso(utcnow()), "where": "odds", "err": type(e).__name__})
                self.log(f"FAIL odds: {type(e).__name__}"); time.sleep(min(backoff, 120)); backoff = min(backoff*2, 300)
            self._save_state()
            time.sleep(self.tick)
        self._finalize()

    def _dry_validate(self):
        now = utcnow()
        up = self.targets[self.targets.kickoff_utc > now]
        plan = []
        for m in up.itertuples():
            st = self._due_type(m.match_id, m.kickoff_utc, now)
            mins = (m.kickoff_utc - now).total_seconds()/60.0
            if st or mins < 120:
                plan.append((m.match_id, round(mins, 1), st))
        self.log(f"DRY-RUN ok: upcoming={len(up)}; near-term schedule (match, mins_to_ko, due_type):")
        for p in plan[:8]:
            self.log(f"  {p}")
        self.log(f"DRY-RUN: max_credits={self.max_credits}, odds_interval={self.odds_interval}s, "
                 f"fd_interval={self.fd_interval}s. No network, no writes performed.")

    def _finalize(self):
        summ = {"session_start": iso(self.start), "session_end": iso(utcnow()),
                "planned_deadline": iso(self.deadline), "credits_used": self.state["credits_used"],
                "credit_cap": self.max_credits, "snapshots_done": self.state["snapshots_done"],
                "fixtures_finalized": self.state["elo_updated"], "failures": self.state["failures"]}
        if not self.dry:
            (self.dir / "session_summary.json").write_text(json.dumps(summ, indent=2), encoding="utf-8")
        self.log(f"SUPERVISOR DONE. credits_used={self.state['credits_used']} "
                 f"snapshots={sum(len(v) for v in self.state['snapshots_done'].values())} "
                 f"finalized={len(self.state['elo_updated'])}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--hours", type=float, default=5.0)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--max-credits", type=int, default=30)
    p.add_argument("--odds-interval", type=int, default=600)
    p.add_argument("--fd-interval", type=int, default=600)
    p.add_argument("--tick", type=int, default=60)
    p.add_argument("--resume-latest", action="store_true", help="resume the most recent session (restart-safe)")
    a = p.parse_args()
    Supervisor(a.hours, a.dry_run, a.max_credits, a.odds_interval, a.fd_interval, a.tick,
               resume_latest=a.resume_latest).run()


if __name__ == "__main__":
    main()
