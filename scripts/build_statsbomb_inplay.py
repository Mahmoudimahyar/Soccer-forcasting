"""Phase 4: download StatsBomb events+lineups (cache/resume) for the 6 modern men's international
tournaments + a bounded club-auxiliary sample, and build leakage-safe in-play state + target tables.
Raw files cached under data/raw/statsbomb (gitignored). Data provided by StatsBomb (non-commercial).
"""
import argparse
import json
import sys
import time
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from wcdrawlab.research.statsbomb_inplay import extract_events, starting_xi, build_match, events_sha256  # noqa: E402
from wcdrawlab.research.inplay_dataset import _elo_lookup_from_history, _resolve_elo  # noqa: E402
from wcdrawlab.ingest import canonical_team_name  # noqa: E402
from wcdrawlab.research.inplay_models.models import pregame_lambdas, update_inplay_probabilities, InPlayState  # noqa: E402

BASE = "https://raw.githubusercontent.com/statsbomb/open-data/master/data"
EV = ROOT / "data/raw/statsbomb/events"; EV.mkdir(parents=True, exist_ok=True)
LU = ROOT / "data/raw/statsbomb/lineups"; LU.mkdir(parents=True, exist_ok=True)
MA = ROOT / "data/raw/statsbomb/matches"

INTERNATIONAL = [  # (comp, season, tag, confed, has_360)
    (43, 3, "WC2018", "FIFA", False), (55, 43, "EURO2020", "UEFA", True),
    (43, 106, "WC2022", "FIFA", True), (1267, 107, "AFCON2023", "CAF", True),
    (223, 282, "COPA2024", "CONMEBOL", False), (55, 282, "EURO2024", "UEFA", True),
]
CLUB = [(11, 27, "LALIGA_2015_2016", "UEFA", False)]


def get_json(url, cache):
    if cache.exists():
        return json.loads(cache.read_text(encoding="utf-8")), cache.read_text(encoding="utf-8")
    r = requests.get(url, timeout=60); cache.write_text(r.text, encoding="utf-8"); time.sleep(0.1)
    return r.json(), r.text


def pre_match_probs(delta):
    lh, la = pregame_lambdas(delta)
    p = update_inplay_probabilities(lh, la, InPlayState(minute=0.0, goals_a=0, goals_b=0,
                                                        red_cards_a=0, red_cards_b=0))
    return (p.p_a_win, p.p_draw, p.p_b_win)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--club-cap", type=int, default=60, help="max club matches (bounded auxiliary sample)")
    a = ap.parse_args()
    elo = pd.read_csv(ROOT / "data/processed/elo_history.csv")
    lut = _elo_lookup_from_history(elo)

    domains = {"international": INTERNATIONAL, "club": CLUB}
    state = {"international": [], "club": []}
    ng, ct, st_, mt, cov = [], [], [], [], []
    for domain, comps in domains.items():
        for (cid, sid, tag, confed, d360) in comps:
            mlist, _ = get_json(f"{BASE}/matches/{cid}/{sid}.json", MA / f"{cid}_{sid}.json")
            if domain == "club":
                mlist = mlist[:a.club_cap]
            n_elo = 0
            for mobj in mlist:
                mid = mobj["match_id"]
                home = mobj["home_team"]["home_team_name"]; away = mobj["away_team"]["away_team_name"]
                date = mobj["match_date"]
                try:
                    ev, raw = get_json(f"{BASE}/events/{mid}.json", EV / f"{mid}.json")
                    lu, _ = get_json(f"{BASE}/lineups/{mid}.json", LU / f"{mid}.json")
                except Exception as e:
                    print(f"  WARN {mid}: {e}"); continue
                pair = frozenset((canonical_team_name(home), canonical_team_name(away)))
                res = _resolve_elo(lut, date, pair, tol_days=3)
                if res:
                    listed_a, ea, eb = res
                    delta = (ea - eb) if listed_a == canonical_team_name(home) else (eb - ea)
                    n_elo += 1
                else:
                    delta = float("nan")
                p_elo = pre_match_probs(delta if delta == delta else 0.0)
                xi = starting_xi(lu)
                coverage = {"lineup": bool(xi) and all(len(v) >= 7 for v in xi.values() if v) and len(xi) >= 2,
                            "xg": True, "player_ids": bool(xi), "d360": d360, "events_ok": len(ev) > 100}
                ex = extract_events(ev)
                s, g, c, su, m_ = build_match(
                    ex, home, away, sb_match_id=mid, match_date=date, competition_id=tag,
                    competition_type=domain, confederation=confed, elo_delta_home=delta, p_elo=p_elo,
                    coverage=coverage, src_sha=events_sha256(raw))
                state[domain].extend(s); ng.extend(g); ct.extend(c); st_.extend(su); mt.append(m_)
                cov.append({"sb_match_id": mid, "competition_id": tag, "competition_type": domain,
                            "n_xi_home": len(next(iter(xi.values()), [])) if xi else 0,
                            "n_teams_xi": len(xi), "has_player_ids": bool(xi), "has_360": d360,
                            "n_subs": len(ex["subs"]), "n_cards": len(ex["cards"])})
            print(f"  {tag}: {len(mlist)} matches, elo-resolved {n_elo}")

    P = ROOT / "data/processed"
    pd.DataFrame(state["international"]).to_parquet(P / "inplay_state_sb_international.parquet", index=False)
    pd.DataFrame(state["club"]).to_parquet(P / "inplay_state_sb_club.parquet", index=False)
    pd.DataFrame(ng).to_parquet(P / "sb_next_goal_targets.parquet", index=False)
    pd.DataFrame(ct).to_parquet(P / "sb_card_targets.parquet", index=False)
    pd.DataFrame(st_).to_parquet(P / "sb_sub_targets.parquet", index=False)
    pd.DataFrame(mt).to_parquet(P / "sb_match_targets.parquet", index=False)
    pd.DataFrame(cov).to_parquet(P / "sb_player_state_coverage.parquet", index=False)
    print(f"\nINTL state rows {len(state['international'])} ({pd.DataFrame(state['international']).sb_match_id.nunique() if state['international'] else 0} matches)")
    print(f"CLUB state rows {len(state['club'])} | match_targets {len(mt)} | coverage {len(cov)}")
    print("STATSBOMB INPLAY BUILD DONE")


if __name__ == "__main__":
    main()
