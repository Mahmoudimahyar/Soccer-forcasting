"""JOB3: deterministic auxiliary event-process manifest. CLUB matches only (international comps are the primary
TEST population, never auxiliary). Group by comp-season, sort by date+match_id, fixed-seed match-id hash for
deterministic order, allocate evenly across groups, cap per group, total <=1000, date<2025-01-01. NO selection
by scoreline/goals/xG/player/club-fame/cards/outcome. research_only."""
import csv, hashlib, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
SEED = "event_process_aux_v1"; TARGET = 1000; CAP_PER_GROUP = 80; CAP_PER_COMPETITION = 150
INTERNATIONAL = {"FIFA World Cup", "UEFA Euro", "African Cup of Nations", "Copa America"}
def _h(mid): return int(hashlib.sha256(f"{SEED}:{mid}".encode()).hexdigest(), 16)
def main():
    rows = list(csv.DictReader(open(ROOT/"data/reference/statsbomb_event_process_catalog.csv", encoding="utf-8")))
    elig = [r for r in rows if r["competition"] not in INTERNATIONAL and r["match_date"] and r["match_date"] < "2025-01-01"]
    groups = {}
    for r in elig:
        groups.setdefault((r["competition"], r["season"]), []).append(r)
    for g in groups.values():
        g.sort(key=lambda r: (r["match_date"], str(r["match_id"])))      # documented order
        g.sort(key=lambda r: _h(r["match_id"]))                          # fixed-seed deterministic hash
    # even round-robin allocation across groups, capped per group AND per competition (diversity:
    # no single league may dominate even though it has many seasons)
    order = sorted(groups.keys()); sel = []; idx = {k: 0 for k in order}; comp_count = {}
    while len(sel) < TARGET:
        progressed = False
        for k in order:
            comp = k[0]; g = groups[k]; i = idx[k]
            if i < min(len(g), CAP_PER_GROUP) and comp_count.get(comp, 0) < CAP_PER_COMPETITION:
                sel.append(g[i]); idx[k] += 1; comp_count[comp] = comp_count.get(comp, 0) + 1; progressed = True
                if len(sel) >= TARGET: break
        if not progressed: break
    man = [{"rank": n+1, "match_id": r["match_id"], "competition_id": r["competition_id"],
            "season_id": r["season_id"], "competition": r["competition"], "season": r["season"],
            "match_date": r["match_date"], "home": r["home"], "away": r["away"]} for n, r in enumerate(sel)]
    out = ROOT/"data/reference"
    (out/"event_process_auxiliary_manifest.json").write_text(json.dumps({"seed": SEED, "target": TARGET,
        "cap_per_group": CAP_PER_GROUP, "n_selected": len(man), "n_groups": len(groups), "fixtures": man}, indent=1), encoding="utf-8")
    with (out/"event_process_auxiliary_manifest.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(man[0].keys())); w.writeheader(); w.writerows(man)
    print(json.dumps({"selected": len(man), "groups": len(groups), "min_gate_500": len(man) >= 500}))
if __name__ == "__main__": main()
