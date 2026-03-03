"""Discrimination flag handling."""

import pandas as pd

DISCRIM_LEVELS = {
    "Normal": 1.0,
    "Slightly Low": 0.7,
    "Low": 0.5,
    "Very Low": 0.3,
}


def apply_discrimination(items_df: pd.DataFrame, flags: dict[str, str]) -> pd.DataFrame:
    """Apply discrimination flags to items.

    Args:
        items_df: DataFrame with item_id column.
        flags: {item_id: level_label} mapping.

    Returns:
        DataFrame with 'discrimination' and 'discrim_label' columns added.
    """
    df = items_df.copy()
    df["discrim_label"] = df["item_id"].map(flags).fillna("Normal")
    df["discrimination"] = df["discrim_label"].map(DISCRIM_LEVELS).fillna(1.0)
    return df
