from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd


REQUIRED_COLUMNS = {
    "match_id",
    "outcome_label",
    "market_ticker",
    "book_side",
    "mapping_status",
    "reviewed_by",
    "reviewed_at_utc",
}


@dataclass(frozen=True)
class MarketMapping:
    match_id: str
    outcome_label: str
    market_ticker: str
    book_side: str


def load_reviewed_mapping(path: str | Path, match_id: str, outcome_label: str) -> MarketMapping:
    table = pd.read_csv(path)
    missing = REQUIRED_COLUMNS - set(table.columns)
    if missing:
        raise ValueError(f"market_map is missing required columns: {sorted(missing)}")
    rows = table[
        (table["match_id"].astype(str) == str(match_id))
        & (table["outcome_label"].astype(str).str.lower() == str(outcome_label).lower())
        & (table["mapping_status"].astype(str).str.lower() == "approved")
    ]
    if len(rows) != 1:
        raise ValueError("Exactly one manually reviewed approved mapping is required before an order can exist.")
    row = rows.iloc[0]
    if str(row["book_side"]).lower() not in {"bid", "ask"}:
        raise ValueError("book_side must be bid or ask")
    return MarketMapping(
        match_id=str(row["match_id"]),
        outcome_label=str(row["outcome_label"]),
        market_ticker=str(row["market_ticker"]),
        book_side=str(row["book_side"]).lower(),
    )
