"""Validate the canonical model identity + alias registry (Offline Hardening Phase 0).
Exits non-zero on any violation. Read-only; never rewrites historical rows."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from wcdrawlab.research.model_identity import (  # noqa: E402
    load_identity, load_aliases, resolve, check_invariants)


def main():
    identity = load_identity(); aliases = load_aliases()
    problems = []

    # 1. invariants (exactly B1 runtime-eligible; nothing trade-eligible; no research model runtime)
    problems += check_invariants(identity)

    # 2. every alias resolves to a defined canonical model
    for (ctx, alias), cid in aliases.items():
        if cid not in identity:
            problems.append(f"alias ({ctx},{alias}) -> undefined canonical {cid}")

    # 3. the M2 collision is resolved by namespace
    m2_pre = resolve("M2", "prematch", aliases); m2_in = resolve("M2", "inplay", aliases)
    if m2_pre == m2_in:
        problems.append(f"M2 collision NOT disambiguated: prematch={m2_pre} inplay={m2_in}")
    if m2_pre != "prematch.market_novig" or m2_in != "inplay.remaining_time_poisson_m2":
        problems.append(f"M2 resolution wrong: prematch={m2_pre} inplay={m2_in}")

    # 4. no research/shadow model is runtime or trade eligible
    for cid, m in identity.items():
        if m.get("approval_status") != "approved" and (m.get("runtime_eligible") or m.get("trade_eligible")):
            problems.append(f"{cid}: non-approved model marked runtime/trade eligible")

    print(f"models={len(identity)} aliases={len(aliases)} | M2 prematch->{m2_pre} | M2 inplay->{m2_in}")
    if problems:
        print("MODEL IDENTITY FAILURES:")
        for p in problems:
            print("  -", p)
        sys.exit(1)
    print("MODEL IDENTITY OK: invariants hold, aliases resolve, M2 collision disambiguated, "
          "no research model runtime/trade-eligible.")


if __name__ == "__main__":
    main()
