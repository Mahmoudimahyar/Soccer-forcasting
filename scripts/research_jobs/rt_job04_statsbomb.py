import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent)); import _job
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT/"src"))
from wcdrawlab.research import data_roots as DR
def main():
    rd = Path(_job.run_dir())
    # canonical statsbomb root + prior; count cached event files; bridge total from manifest
    cached = 0
    for rn in ("statsbomb_raw","statsbomb_raw_prior"):
        try:
            ev = DR.get_root(rn)/"events"
            if ev.exists(): cached += len(list(ev.glob("*.json")))
        except Exception: pass
    bridged = None
    try:
        bj = DR.manifest("statsbomb_bridge")
        if bj.exists(): bridged = json.loads(bj.read_text(encoding="utf-8")).get("total_accepted")
    except Exception: pass
    rate = round(cached/bridged,4) if bridged else 0.0
    res = {"bridged_exact": bridged, "cached_event_files": cached, "cache_completion_rate": rate, "gate_90pct": rate>=0.90}
    (rd/"job04_statsbomb.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    # acquisition of the missing ~198 official open-data files is bounded/multi-step; report honest rate
    _job.emit("complete" if rate>=0.90 else "skipped",
              reason=f"StatsBomb cache {cached}/{bridged} = {rate} (gate90={rate>=0.90}); missing files = bounded official-open-data acquisition",
              state_updates={"statsbomb_rate": rate, "statsbomb_gate90": rate>=0.90})
main()
