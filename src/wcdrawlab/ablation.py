from __future__ import annotations

import pandas as pd
from wcdrawlab.evaluation import metric_report


def run_ablation(models: dict, train: pd.DataFrame, test: pd.DataFrame, y_col: str = "outcome") -> pd.DataFrame:
    """Fit/evaluate a dict of sklearn-like models.

    Each model must implement fit(train, y) or fit(train_y only for prior), and predict_proba(test).
    """
    rows = []
    for name, model in models.items():
        try:
            model.fit(train, train[y_col])
        except TypeError:
            model.fit(train[y_col])
        probs = model.predict_proba(test)
        metrics = metric_report(test[y_col], probs)
        rows.append({"model": name, **metrics})
    return pd.DataFrame(rows).sort_values("rps")
