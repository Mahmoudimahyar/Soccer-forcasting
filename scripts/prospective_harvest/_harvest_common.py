"""Shared helpers for the Prospective Shadow Score Harvest program.

SAFETY: reads immutable collector artifacts from the main checkout (collector root) by absolute path;
writes ONLY under the worktree scoring root. Never fetches odds, never touches frozen predictions,
never prints secret values. All emitted artifacts carry the five research-only labels.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

# --- roots -----------------------------------------------------------------------------------------
WORKTREE_ROOT = Path(__file__).resolve().parents[2]
COLLECTOR_ROOT = Path(os.environ.get("PSH_COLLECTOR_ROOT", r"C:/Users/Mahyar/worldcup_draw_model_lab_FINAL")).resolve()

# wcdrawlab (identical between worktree and collector — same base commit). Use the worktree's own src.
sys.path.insert(0, str(WORKTREE_ROOT / "src"))

# --- immutable inputs (read-only, from the collector root) -----------------------------------------
PRED_LEDGER = COLLECTOR_ROOT / "outputs/research/live_2026_shadow_predictions.csv"
FORECAST_TARGETS = COLLECTOR_ROOT / "data/processed/forecast_targets_2026.csv"
QUEUE = COLLECTOR_ROOT / "data/reference/future_2026_prospective_queue.csv"
RAW_ODDS_DIR = COLLECTOR_ROOT / "data/raw/odds/live_2026"
COLLECTOR_RESULTS = COLLECTOR_ROOT / "data/processed/results_2026_footballdata.csv"  # read-only reference; NEVER written

# --- worktree-owned scoring outputs (the only write root) ------------------------------------------
SCORING_ROOT = WORKTREE_ROOT / "outputs/live_shadow/scoring_v1"
RESULTS_DIR = SCORING_ROOT / "results"          # refreshed FINAL results live here (not the collector file)
RUN_DIR = SCORING_ROOT                           # scorecards / metrics / manifests

SCORER_VERSION = "prospective_score_harvester_v1"

LABELS = {
    "research_only": True,
    "prospective_evaluation_only": True,
    "not_runtime_approved": True,
    "not_trade_eligible": True,
    "not_live_eligible": True,
}

# Result-source team-name aliases (mirror of fetch_footballdata_2026.EXTRA) so result names map to the
# canonical names used in forecast_targets / predictions.
EXTRA_ALIASES = {
    "Bosnia-Herzegovina": "Bosnia", "Bosnia and Herzegovina": "Bosnia",
    "Czech Republic": "Czechia", "South Korea": "Korea Republic",
    "Curaçao": "Curacao", "DR Congo": "Congo DR", "USA": "United States",
    "Cape Verde Islands": "Cape Verde", "Côte d'Ivoire": "Ivory Coast",
}


def canon(name: str) -> str:
    """Canonical team name with result-source aliases applied first."""
    from wcdrawlab.ingest import canonical_team_name
    s = str(name).strip()
    return EXTRA_ALIASES.get(s, canonical_team_name(s))


def pair_key(team_a: str, team_b: str) -> frozenset:
    return frozenset((canon(team_a), canon(team_b)))


def sha256_file(path: Path) -> str | None:
    p = Path(path)
    if not p.exists():
        return None
    h = hashlib.sha256()
    h.update(p.read_bytes())
    return h.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_collector_env(verbose: bool = False) -> list[str]:
    """Load keys from the COLLECTOR ROOT .env into os.environ WITHOUT printing values. Names only."""
    loaded: list[str] = []
    for fname in (".env", ".env.example"):
        p = COLLECTOR_ROOT / fname
        if not p.exists():
            continue
        for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip().strip('"').strip("'")
            if v and not os.environ.get(k):
                os.environ[k] = v
                loaded.append(k)
    if verbose:
        print(f"[env] loaded {len(loaded)} keys (names only): {sorted(set(loaded))}")
    return loaded


def write_json(path: Path, obj) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, default=str), encoding="utf-8")
    tmp.replace(path)  # atomic on same filesystem


def stamp_labels(d: dict) -> dict:
    out = dict(d)
    out.update(LABELS)
    return out
