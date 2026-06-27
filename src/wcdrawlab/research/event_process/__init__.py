"""Provider-neutral event-process intelligence engine.

research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible.

From provider event streams (StatsBomb open data in Phase 1) this package derives a leakage-safe,
source-quality-flagged view of the *football process*: possession structure, territory, transitions,
attack phases, set pieces, pressure/disruption, and chance quality -- composed into causal in-play
snapshots. Raw JSON is never embedded in tracked artifacts; only hashes/traceability are kept.

Pipeline:
    canonical_events.load_statsbomb_match(path)
        -> (canon, trace, (home_id, away_id))
    snapshots.build_snapshots(canon, trace, home_id, away_id)
        -> [feature_dict, ...]   # one per decision minute, leakage-verified

Leakage contract is centralized in snapshots._truncate + quality.leakage_check.
Canonical model IDs live in registry.py.
"""
from . import contracts  # noqa: F401
from . import canonical_events  # noqa: F401
from . import possession  # noqa: F401
from . import territory  # noqa: F401
from . import transitions  # noqa: F401
from . import attacks  # noqa: F401
from . import set_pieces  # noqa: F401
from . import pressure  # noqa: F401
from . import chance_quality  # noqa: F401
from . import snapshots  # noqa: F401
from . import quality  # noqa: F401
from . import registry  # noqa: F401
from . import models  # noqa: F401
from . import eval  # noqa: F401

__all__ = [
    "contracts", "canonical_events", "possession", "territory", "transitions",
    "attacks", "set_pieces", "pressure", "chance_quality", "snapshots", "quality", "registry",
    "models", "eval",
]
SCHEMA_VERSION = contracts.SCHEMA_VERSION
