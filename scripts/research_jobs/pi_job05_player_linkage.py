"""JOB5: build player-history + linkage datasets. Produces leakage-safe regulation snapshots
(international + club-auxiliary) and an EXACT player-id linkage coverage report. Linkage uses ONLY the
API-Football integer player.id (NEVER fuzzy name matching); rows that cannot be linked by id are counted
in explicit unmatched / ambiguous categories. Player priors are knowable-at-kickoff only (starting XI
from lineups published pre-kickoff); no future appearances. No network. research_only / experimental.

CAUSAL: in-play features at minute t use ONLY events elapsed<=t; regulation targets exclude ET/shootout.
"""
import sys, json
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent)); import _job, _common as C


def _linkage_report(lineups):
    """Exact player.id linkage coverage over starting XIs. matched = integer id present;
    unmatched = missing id; ambiguous = duplicate id within a single lineup."""
    matched = unmatched = ambiguous = total = 0
    for fid, resp in (lineups or {}).items():
        for team in (resp or []):
            ids = []
            for slot in (team.get("startXI") or []):
                pid = ((slot or {}).get("player") or {}).get("id")
                total += 1
                if pid is None or not isinstance(pid, int):
                    unmatched += 1
                else:
                    ids.append(pid)
            dup = [k for k, v in Counter(ids).items() if v > 1]
            ambiguous += sum(Counter(ids)[d] for d in dup)
            matched += len(ids) - sum(Counter(ids)[d] for d in dup)
    return {"starters_total": total, "exact_id_matched": matched, "unmatched_no_id": unmatched,
            "ambiguous_dup_id": ambiguous,
            "match_rate": round(matched / total, 4) if total else None,
            "linkage_rule": "exact_api_football_player_id_only_no_fuzzy_name"}


def main():
    rd = Path(_job.run_dir())
    fixtures, events, lineups = C.load_corpus()
    intl = C.regulation_snapshots(fixtures, events, lineups, international_only=True)
    club = C.regulation_snapshots(fixtures, events, lineups, international_only=False)
    club = [r for r in club if r["comp_type"] == "club"]
    (rd / "snapshots_intl.json").write_text(json.dumps(intl), encoding="utf-8")
    (rd / "snapshots_club.json").write_text(json.dumps(club), encoding="utf-8")
    link = _linkage_report(lineups)
    (rd / "job05_linkage.json").write_text(json.dumps(link, indent=2), encoding="utf-8")
    im = len({r["match_id"] for r in intl}); cm = len({r["match_id"] for r in club})
    if not intl and not club:
        _job.emit("skipped", reason="no snapshots yet (backfill/corpus incomplete)",
                  state_updates={"intl_matches": 0, "club_matches": 0}); return
    _job.emit("complete",
              reason=(f"intl_snaps={len(intl)} ({im} matches) club_snaps={len(club)} ({cm} matches); "
                      f"exact player-id match_rate={link['match_rate']}"),
              state_updates={"intl_matches": im, "club_matches": cm, "intl_rows": len(intl),
                             "linkage_match_rate": link["match_rate"]})


main()
