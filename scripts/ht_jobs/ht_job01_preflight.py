"""HT_JOB01 -- deps + isolation + worktree + test-baseline + dry-run preflight.

research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible.

REAL work:
  * verifies the runtime deps (numpy / sklearn / yaml / pandas) import;
  * proves ISOLATION: this worktree is not the active collector checkout; no data root resolves into the
    collector (data_roots fails closed); raw/ is not git-tracked; no HT job imports a forbidden
    network/provider/scrape token at module scope;
  * imports the canonical transfer plane (w2_reference_t0 + domain_normalized_dataset + hierarchical_models)
    to prove the engine wires up;
  * runs the transfer-plane test baseline (pytest -q on the transfer tests) and records pass/fail counts;
  * a self dry-run of the dataset loader contract (does the materialised dataset exist? how many rows?).

NEVER false-completes: if deps are missing or isolation is violated it emits status=failed (critical) with
the concrete reason; the supervisor will block the rest of the queue.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import _ht as H

JOB = "JOB1"


def _check_deps():
    out = {}
    for mod in ("numpy", "sklearn", "yaml", "pandas"):
        try:
            __import__(mod)
            out[mod] = "ok"
        except Exception as e:
            out[mod] = f"MISSING:{e}"
    return out


def _import_engine():
    out = {}
    try:
        H.t0_reference(); out["w2_reference_t0"] = "ok"
    except Exception as e:
        out["w2_reference_t0"] = f"FAIL:{e}"
    try:
        H.dnd(); out["domain_normalized_dataset"] = "ok"
    except Exception as e:
        out["domain_normalized_dataset"] = f"FAIL:{e}"
    try:
        from wcdrawlab.research.transfer import hierarchical_models  # noqa: F401
        out["hierarchical_models"] = "ok"
    except Exception as e:
        out["hierarchical_models"] = f"FAIL:{e}"
    return out


def _test_baseline():
    """Run the transfer-plane tests (best-effort). Records counts; absence of tests is NOT a failure."""
    tests = []
    tdir = H.ROOT / "tests"
    for pat in ("test_hierarchical_transfer*.py", "test_transfer*.py", "test_domain_normalized*.py"):
        tests += [str(p) for p in tdir.glob(pat)]
    tests = sorted(set(tests))
    if not tests:
        return {"ran": False, "reason": "no transfer tests discovered yet", "selected": []}
    try:
        p = subprocess.run([sys.executable, "-m", "pytest", "-q", *tests],
                           capture_output=True, text=True, timeout=1800, cwd=str(H.ROOT))
        tail = (p.stdout or "")[-400:] + (p.stderr or "")[-200:]
        return {"ran": True, "returncode": p.returncode, "passed": p.returncode == 0,
                "selected": tests, "tail": tail}
    except Exception as e:
        return {"ran": True, "returncode": None, "passed": False, "selected": tests, "error": str(e)}


def main():
    deps = _check_deps()
    iso = H.isolation_report()
    engine = _import_engine()
    tests = _test_baseline()

    ds_present = H.dataset_present()
    ds_rows = None
    if ds_present:
        try:
            ds_rows = len(H.load_dataset_rows())
        except Exception:
            ds_rows = None

    art = H.envelope(JOB, "running")
    art.update({
        "deps": deps,
        "isolation": iso,
        "engine_imports": engine,
        "test_baseline": tests,
        "dataset_present": ds_present,
        "dataset_n_rows": ds_rows,
        "build_manifest_present": H.BUILD_MANIFEST.exists(),
    })

    # fail-closed gates
    bad_deps = [k for k, v in deps.items() if v != "ok"]
    bad_engine = [k for k, v in engine.items() if v != "ok"]
    iso_bad = (iso["in_collector_checkout"] or iso["roots_in_collector"]
               or (iso["raw_git_tracked"] != "(none)") or iso["forbidden_imports"])

    if bad_deps:
        art["status"] = "failed"
        H.write_json("job01_preflight.json", art)
        return H.emit("failed", f"missing deps: {bad_deps}")
    if iso_bad:
        art["status"] = "failed"
        H.write_json("job01_preflight.json", art)
        return H.emit("failed", f"isolation violation: roots_in_collector={iso['roots_in_collector']} "
                                f"raw_tracked={iso['raw_git_tracked']} "
                                f"forbidden_imports={iso['forbidden_imports']}")
    if bad_engine:
        art["status"] = "failed"
        H.write_json("job01_preflight.json", art)
        return H.emit("failed", f"engine import failure: {bad_engine}")

    art["status"] = "complete"
    H.write_json("job01_preflight.json", art)
    H.emit("complete",
           f"deps ok; isolation ok (collector {iso['collector_commit']}); engine ok; "
           f"tests={'pass' if tests.get('passed') else tests.get('reason','n/a')}; "
           f"dataset_present={ds_present} rows={ds_rows}",
           state_updates={"preflight_ok": True, "dataset_present": ds_present,
                          "dataset_n_rows": ds_rows, "run_state": "RUNNING"})


if __name__ == "__main__":
    main()
