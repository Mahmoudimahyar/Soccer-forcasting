"""Extract a combined international shot table from already-cached StatsBomb events (no re-download).
Feeds the pre-registered xG feature families in Phase 5."""
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from wcdrawlab.research.statsbomb_inplay import extract_events  # noqa: E402

EV = ROOT / "data/raw/statsbomb/events"


def main():
    st = pd.read_parquet(ROOT / "data/processed/inplay_state_sb_international.parquet")
    meta = st.drop_duplicates("sb_match_id")[["sb_match_id", "home_team", "away_team"]]
    rows = []
    for r in meta.itertuples():
        fp = EV / f"{r.sb_match_id}.json"
        if not fp.exists():
            continue
        ev = json.loads(fp.read_text(encoding="utf-8"))
        for (minute, team, xg, is_goal) in extract_events(ev)["shots"]:
            rows.append({"sb_match_id": r.sb_match_id, "minute": minute, "team": team, "xg": xg,
                         "is_goal": is_goal, "home_team": r.home_team, "away_team": r.away_team})
    df = pd.DataFrame(rows)
    outp = ROOT / "data/processed/statsbomb_shots_international.parquet"
    df.to_parquet(outp, index=False)
    print(f"wrote {len(df)} shots ({df.sb_match_id.nunique()} matches) -> {outp.name}")


if __name__ == "__main__":
    main()
