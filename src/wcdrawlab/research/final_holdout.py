"""Frozen in-play model for PROSPECTIVE 2026 scoring (research-only).

After the freeze, the model architecture (M2fit_temp = data-fit goal-rate Poisson + temperature scaling)
and its learned parameters (base, k, temperature) are FIXED. Future 2026 matches are predicted by this
frozen version; results may be used ONLY for scoring, never to retrain or re-select. This module performs
NO fitting — it reconstructs the model from the frozen config and scores deterministically.

Reads `configs/final_holdout_model.yaml`. research_only=true, not_runtime_approved=true.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import yaml

from wcdrawlab.research.inplay_models.models import (
    InPlayState, update_inplay_probabilities, normalize_probs, temperature_scale)

FEATURE_SCHEMA_V1 = ["elo_delta_home", "decision_minute", "score_home", "score_away",
                     "red_home", "red_away"]


class FrozenInPlayModel:
    """Deterministic M2fit_temp with FIXED base/k/temperature. No fitting ever happens here."""
    def __init__(self, base: float, k: float, temperature: float, model_id: str = "m2fit_temp_frozen"):
        self.base = float(base); self.k = float(k); self.temperature = float(temperature)
        self.model_id = model_id

    def predict_wld(self, df) -> np.ndarray:
        out = np.zeros((len(df), 3))
        for i, (_, row) in enumerate(df.reset_index(drop=True).iterrows()):
            delta = float(row["elo_delta_home"])
            lh = self.base * np.exp(self.k * delta / 100.0)
            la = self.base * np.exp(-self.k * delta / 100.0)
            st = InPlayState(minute=float(row["decision_minute"]), goals_a=int(row["score_home"]),
                             goals_b=int(row["score_away"]), red_cards_a=int(row["red_home"]),
                             red_cards_b=int(row["red_away"]))
            p = update_inplay_probabilities(lh, la, st)
            out[i] = [p.p_a_win, p.p_draw, p.p_b_win]
        return temperature_scale(normalize_probs(out), self.temperature)


def load_frozen(config_path: str | Path) -> FrozenInPlayModel:
    cfg = yaml.safe_load(Path(config_path).read_text(encoding="utf-8"))
    mp = cfg["model_parameters"]
    return FrozenInPlayModel(base=mp["base"], k=mp["k"], temperature=mp["temperature"],
                             model_id=cfg.get("model_id", "m2fit_temp_frozen"))
