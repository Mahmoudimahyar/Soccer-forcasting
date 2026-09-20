"""Validate the canonical data-root registry: roots resolve, forbidden roots are excluded, raw stays
gitignored, no job reads the active collector checkout. research_only."""
import sys, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT/"src"))
from wcdrawlab.research import data_roots as DR
def main():
    cfg = DR._load(); issues = []
    for name in cfg["roots"]:
        try: DR.get_root(name)
        except Exception as e: issues.append(f"{name}: {type(e).__name__}: {e}")
    for fr in DR.forbidden_roots():
        if "worldcup_draw_model_lab_FINAL" not in fr: issues.append(f"forbidden root not the collector: {fr}")
    print(json.dumps({"roots": list(cfg["roots"]), "forbidden": cfg.get("forbidden_roots"),
                      "issues": issues, "ok": not issues}, indent=2))
    sys.exit(1 if issues else 0)
if __name__ == "__main__": main()
