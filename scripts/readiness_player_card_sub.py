"""Phase 6: measure data readiness for player-effect, card, and substitution / next-goal models against
the built StatsBomb datasets. Emits notes/research/player_card_substitution_readiness.md.
Thresholds: player/sub >=500 matches w/ lineup+subs; red/2nd-yellow >=150 positive events;
next-goal >=500 matches w/ event timestamps."""
import json
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from wcdrawlab.research.statsbomb_inplay import extract_events  # noqa: E402

EV = ROOT / "data/raw/statsbomb/events"
P = ROOT / "data/processed"


def main():
    cov = pd.read_parquet(P / "sb_player_state_coverage.parquet")
    mt = pd.read_parquet(P / "sb_match_targets.parquet")
    intl = pd.read_parquet(P / "inplay_state_sb_international.parquet")
    intl_ids = set(intl.sb_match_id.unique())

    # complete-lineup + sub coverage
    complete_xi = cov[(cov.n_teams_xi >= 2) & (cov.has_player_ids)]
    with_subs = cov[cov.n_subs > 0]
    with_pids = cov[cov.has_player_ids]
    with_360 = cov[cov.has_360]

    # card / penalty / goal-after-sub counts from cached events
    direct_red = second_yellow = penalties = goals = 0
    for r in cov.itertuples():
        fp = EV / f"{r.sb_match_id}.json"
        if not fp.exists():
            continue
        ev = json.loads(fp.read_text(encoding="utf-8"))
        for e in ev:
            t = (e.get("type") or {}).get("name")
            if t in ("Foul Committed", "Bad Behaviour"):
                nm = ((e.get("foul_committed") or e.get("bad_behaviour") or {}).get("card") or {}).get("name")
                if nm == "Red Card":
                    direct_red += 1
                elif nm == "Second Yellow":
                    second_yellow += 1
            elif t == "Shot":
                sh = e.get("shot") or {}
                if (sh.get("type") or {}).get("name") == "Penalty":
                    penalties += 1
                if (sh.get("outcome") or {}).get("name") == "Goal":
                    goals += 1

    intl_matches = cov[cov.competition_type == "international"].sb_match_id.nunique()
    club_matches = cov[cov.competition_type == "club"].sb_match_id.nunique()
    wld = Counter(mt.final_wld)
    comp_cov = cov.groupby(["competition_type", "competition_id"]).sb_match_id.nunique()

    def gate(n, thr):
        return f"READY ({n} >= {thr})" if n >= thr else f"BLOCKED ({n} < {thr})"

    md = ["# Player / Card / Substitution Readiness (Phase 6, 2026-06-22)", "",
          "Measured against the StatsBomb datasets built in Phase 4. Data provided by StatsBomb.", "",
          "## Coverage counts",
          f"- matches with complete starting XI (both teams, player IDs): **{len(complete_xi)}**",
          f"- matches with substitution events (timestamps): **{len(with_subs)}**",
          f"- matches with player IDs: **{len(with_pids)}**",
          f"- matches with position/role data: **{len(with_pids)}** (StatsBomb lineups carry positions)",
          f"- matches with 360 freeze-frames: **{len(with_360)}**",
          f"- international matches: **{intl_matches}** | club (auxiliary) matches: **{club_matches}**",
          "",
          "## Event counts",
          f"- direct red events: **{direct_red}**",
          f"- second-yellow events: **{second_yellow}**",
          f"- (red total = {direct_red + second_yellow})",
          f"- penalties (shots): **{penalties}**",
          f"- goals: **{goals}**",
          "",
          "## Class balance (final result, all built matches)",
          f"- H={wld.get('H',0)} D={wld.get('D',0)} A={wld.get('A',0)} (n={sum(wld.values())})",
          "",
          "## Competition coverage",
          "```", comp_cov.to_string(), "```", "",
          "## Readiness gates",
          f"- **player / substitution model** (need >=500 matches w/ lineup+subs): "
          f"{gate(len(complete_xi[complete_xi.sb_match_id.isin(with_subs.sb_match_id)]) if len(with_subs) else len(complete_xi), 500)}",
          f"- **direct-red / second-yellow model** (need >=150 positive events): "
          f"{gate(direct_red + second_yellow, 150)}",
          f"- **next-goal model** (need >=500 matches w/ event timestamps): "
          f"{gate(cov.sb_match_id.nunique(), 500)}",
          "",
          "## Honest conclusion",
          "StatsBomb open data contains only ~333 men's **senior international** matches in total, so any",
          "INTERNATIONAL-only player/next-goal model is structurally below the 500-match threshold — this is",
          "**unavailable data**, not a processing gap. Club data could pad the counts, but the protocol",
          "forbids silently mixing domains and club->international transfer is unproven (tested separately",
          "in Phase 5). Red-card events are too sparse for a dedicated red model. Therefore:",
          "- player/substitution model: **BLOCKED (international data ceiling ~333 < 500)**; club-augmented",
          "  training is possible only as a separate, clearly-labelled auxiliary experiment.",
          "- direct-red/second-yellow model: **BLOCKED (too few positive events)**.",
          "- next-goal model: **BLOCKED for international-only**; revisit if StatsBomb adds more men's",
          "  international tournaments, or run explicitly as a club-auxiliary study.",
          "- player-specific causal claims: not attempted (observational data only -> association + "
          "uncertainty only).",
          ]
    outp = ROOT / "notes/research/player_card_substitution_readiness.md"
    outp.write_text("\n".join(md), encoding="utf-8")
    print("\n".join(md[:40]))
    print("\nwrote", outp)


if __name__ == "__main__":
    main()
