"""JOB2: build+commit player-history manifest. The manifest is built BEFORE any event retrieval by
scripts/player_history_predeclare.py (metadata-only, fixed-seed hash stratification). It already exists
for this worktree, so this job VERIFIES it: presence, schema, fixed seed, deterministic inclusion rule,
non-empty fixture list, club-only comp_type. No network unless the manifest is absent (predeclare needs
API and is not run here to preserve fail-closed budget). research_only / experimental."""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent)); import _job
ROOT = Path(__file__).resolve().parents[2]
MAN = ROOT / "data/reference/player_history_corpus_manifest.json"
EXPECT_SEED = "player_impact_v1_fixed_seed"
EXPECT_RULE = "hash_stratified_100_per_league_season_fixed_seed"


def main():
    rd = Path(_job.run_dir())
    if not MAN.exists():
        # do NOT auto-run predeclare (needs API + budget); surface as blocked-with-reason
        _job.emit("failed", reason="player_history_corpus_manifest.json absent; run scripts/player_history_predeclare.py first")
        return
    try:
        man = json.loads(MAN.read_text(encoding="utf-8"))
    except Exception as e:
        _job.emit("failed", reason=f"manifest unreadable: {e}"); return
    fixtures = man.get("fixtures") or []
    seed_ok = man.get("seed") == EXPECT_SEED
    rule_ok = bool(fixtures) and all(f.get("inclusion_rule") == EXPECT_RULE for f in fixtures)
    club_ok = all(f.get("comp_type") == "club" for f in fixtures)
    ids_ok = all(f.get("provider_fixture_id") is not None for f in fixtures)
    n = len(fixtures)
    ok = seed_ok and rule_ok and club_ok and ids_ok and n > 0
    res = {"manifest_path": str(MAN.relative_to(ROOT)), "seed": man.get("seed"), "seed_ok": seed_ok,
           "inclusion_rule_ok": rule_ok, "comp_type_club_ok": club_ok, "provider_ids_ok": ids_ok,
           "n_fixtures": n, "fixture_target": man.get("fixture_target"),
           "leagues": man.get("leagues"), "seasons": man.get("seasons")}
    (rd / "job02_manifest.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    _job.emit("complete" if ok else "failed",
              reason=(f"manifest verified: {n} fixtures, seed/rule/club ok" if ok
                      else f"manifest invalid: seed_ok={seed_ok} rule_ok={rule_ok} club_ok={club_ok} ids_ok={ids_ok} n={n}"),
              state_updates={"manifest_fixtures": n, "manifest_target": man.get("fixture_target")})


main()
