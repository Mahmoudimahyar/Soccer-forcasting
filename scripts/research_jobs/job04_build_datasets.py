import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent)); import _job, _common as C
def main():
    rd = Path(_job.run_dir())
    fixtures, events, lineups = C.load_corpus()
    intl = C.regulation_snapshots(fixtures, events, lineups, international_only=True)
    club = C.regulation_snapshots(fixtures, events, lineups, international_only=False)
    club = [r for r in club if r["comp_type"]=="club"]
    (rd/"snapshots_intl.json").write_text(json.dumps(intl), encoding="utf-8")
    (rd/"snapshots_club.json").write_text(json.dumps(club), encoding="utf-8")
    im = len({r["match_id"] for r in intl}); cm = len({r["match_id"] for r in club})
    _job.emit("complete", reason=f"intl_snaps={len(intl)} ({im} matches) club_snaps={len(club)} ({cm} matches)",
              state_updates={"intl_matches": im, "club_matches": cm, "intl_rows": len(intl)})
main()
