import json; from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; RAW=ROOT/"data/raw/player_history_corpus"
prog=RAW/"progress.json"; man=ROOT/"data/reference/player_history_corpus_manifest.json"
done=len(json.loads(prog.read_text(encoding="utf-8"))["done"]) if prog.exists() else 0
target=json.loads(man.read_text(encoding="utf-8")).get("fixture_target",0) if man.exists() else 0
print(json.dumps({"fixtures_done":done,"fixture_target":target}))
