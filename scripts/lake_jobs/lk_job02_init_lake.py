"""LK_JOB02 -- initialize the persistent external lake + assert the retention contract.

REAL work via the canonical lake engine (no fabrication):
  * Lake.resolve() (fails closed if the lake would live inside any git worktree / the active collector).
  * idempotently create objects/indexes/manifests/quarantine/integrity/logs, an empty index skeleton if
    none exists, and an empty manifest if none exists. NEVER deletes anything.
  * record the retention contract (never_delete_valid_object / never_git_clean_the_lake / immutable /
    first_write_wins / fail_closed_conditions) read from the contract config -- the rules this run binds to.
  * run the fail-closed sentinel over whatever is already in the lake and record its verdict.

A pre-existing populated lake is fine (this is idempotent). The retention contract assertion FAILS only
if the contract config is missing or malformed (we never silently weaken it).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _lk


def main():
    L = _lk.lake_engine()
    try:
        lake = L.Lake.resolve()
    except Exception as e:
        _lk.emit("failed", reason=f"lake_resolve_failed: {e!r}")
        return

    for d in (lake.root, lake.objects, lake.indexes, lake.manifests,
              lake.quarantine, lake.integrity, lake.logs):
        d.mkdir(parents=True, exist_ok=True)

    created_index = False
    if not lake.index_json.exists():
        L.write_index(lake, {})
        created_index = True
    if not lake.manifest_jsonl.exists():
        lake.manifest_jsonl.write_text("", encoding="utf-8")

    subdirs_ok = all(d.is_dir() for d in (
        lake.objects, lake.indexes, lake.manifests, lake.quarantine, lake.integrity, lake.logs))

    # retention contract (the binding rules; failing to read it is a hard failure -- never weaken silently)
    try:
        contract = L.load_contract()
        retention = contract.get("retention", {})
        fail_closed = contract.get("fail_closed_conditions", {})
        content = contract.get("content_addressing", {})
        contract_ok = bool(retention) and bool(fail_closed) and bool(content.get("immutable"))
    except Exception as e:
        _lk.emit("failed", reason=f"retention_contract_unreadable: {e!r}")
        return
    if not contract_ok:
        _lk.emit("failed", reason="retention_contract_incomplete_or_weakened")
        return

    index = L.read_index(lake)
    # sentinel over the existing lake (records, does not fabricate; a populated lake should pass)
    try:
        rep = L.run_sentinel(lake, write_report=True)
        sentinel = rep.to_dict()
    except Exception as e:
        sentinel = {"all_ok": False, "error": repr(e)}

    out = {
        "lake_root": str(lake.root),
        "subdirs_ok": subdirs_ok,
        "index_created": created_index,
        "object_count": len(index),
        "manifest_exists": lake.manifest_jsonl.exists(),
        "retention_contract": {
            "never_delete_valid_object": retention.get("never_delete_valid_object"),
            "never_git_clean_the_lake": retention.get("never_git_clean_the_lake"),
            "immutable": content.get("immutable"),
            "first_write_wins": content.get("first_write_wins"),
            "fail_closed_conditions": sorted(fail_closed.keys()),
        },
        "sentinel": {"all_ok": sentinel.get("all_ok"), "checked": sentinel.get("checked"),
                     "failure_count": sentinel.get("failure_count")},
        "utc": _lk.utc(), "labels": _lk.LABELS,
    }
    L.log_run(lake, "lk_job02_init", out)
    _lk.write_json("lk_init_lake.json", out)

    status = "complete" if (subdirs_ok and contract_ok) else "failed"
    _lk.emit(status,
             reason=f"lake_initialized object_count={len(index)} subdirs_ok={subdirs_ok} "
                    f"retention_contract_bound=True sentinel_all_ok={sentinel.get('all_ok')}",
             state_updates={"lake_initialized": True, "lake_object_count": len(index),
                            "lake_root": str(lake.root),
                            "sentinel_all_ok_at_init": sentinel.get("all_ok")})


main()
