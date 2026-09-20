import sys, json, subprocess
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent)); import _ep
ROOT=Path(__file__).resolve().parents[2]
def main():
    coll=Path("C:/Users/Mahyar/worldcup_draw_model_lab_FINAL")
    commit=subprocess.run(["git","-C",str(coll),"rev-parse","--short","HEAD"],capture_output=True,text=True).stdout.strip()
    reg=(ROOT/"configs/research_data_roots.yaml").exists()
    cat=(ROOT/"data/reference/statsbomb_event_process_catalog.csv").exists()
    ok = commit=="dc73318" and reg
    _ep.emit("complete" if ok else "failed",
             reason=f"collector={commit}(isolated) data_root_registry={reg} catalog_present={cat} no_external_api=True",
             state_updates={"collector_commit":commit})
main()
