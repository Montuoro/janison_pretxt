"""Aggregate results for reporting."""

import numpy as np
import pandas as pd


def build_item_params_table(items_df: pd.DataFrame, tam_results: dict = None) -> pd.DataFrame:
    """Build combined item parameters table.

    Args:
        items_df: DataFrame with BTL difficulty, discrimination columns.
        tam_results: dict from TAM with item_params, fit_stats.

    Returns:
        DataFrame with all item parameters.
    """
    df = items_df[["item_id", "stem", "difficulty", "difficulty_se"]].copy()
    df.rename(columns={"difficulty": "btl_difficulty", "difficulty_se": "btl_se"}, inplace=True)

    if tam_results and "item_params" in tam_results:
        tam_items = pd.DataFrame(tam_results["item_params"])
        if "xsi" in tam_items.columns:
            df["rasch_difficulty"] = tam_items["xsi"].values[:len(df)]
        if "se_xsi" in tam_items.columns:
            df["rasch_se"] = tam_items["se_xsi"].values[:len(df)]

    if tam_results and "fit_stats" in tam_results:
        fit = pd.DataFrame(tam_results["fit_stats"])
        if "Infit" in fit.columns:
            df["infit"] = fit["Infit"].values[:len(df)]
        if "Infit_t" in fit.columns:
            df["infit_t"] = fit["Infit_t"].values[:len(df)]
        if "Outfit" in fit.columns:
            df["outfit"] = fit["Outfit"].values[:len(df)]
        if "Outfit_t" in fit.columns:
            df["outfit_t"] = fit["Outfit_t"].values[:len(df)]

    if "discrimination" in items_df.columns:
        df["discrimination"] = items_df["discrimination"].values

    return df


def identify_misfit_items(params_df: pd.DataFrame,
                          lower: float = 0.7, upper: float = 1.3) -> pd.DataFrame:
    """Flag items with infit or outfit outside bounds."""
    df = params_df.copy()
    df["misfit"] = False
    if "infit" in df.columns:
        df["misfit"] = df["misfit"] | (df["infit"] < lower) | (df["infit"] > upper)
    if "outfit" in df.columns:
        df["misfit"] = df["misfit"] | (df["outfit"] < lower) | (df["outfit"] > upper)
    return df


def find_gaps(item_diffs: np.ndarray, person_abilities: np.ndarray,
              gap_threshold: float = 0.5) -> list[dict]:
    """Find gaps between item coverage and person distribution."""
    all_vals = np.sort(np.concatenate([item_diffs, person_abilities]))
    lo, hi = np.percentile(person_abilities, [5, 95])

    # Bin the scale
    bins = np.linspace(lo - 1, hi + 1, 30)
    item_hist, _ = np.histogram(item_diffs, bins=bins)
    person_hist, _ = np.histogram(person_abilities, bins=bins)

    # Normalise
    if person_hist.max() > 0:
        person_norm = person_hist / person_hist.max()
    else:
        person_norm = person_hist

    gaps = []
    centres = (bins[:-1] + bins[1:]) / 2
    for i, centre in enumerate(centres):
        if person_norm[i] > 0.1 and item_hist[i] == 0:
            gaps.append({
                "location": float(centre),
                "person_density": float(person_norm[i]),
                "description": f"Gap at {centre:.2f}: persons present but no items",
            })

    return gaps


def guttman_scalogram(response_matrix: pd.DataFrame, abilities: np.ndarray,
                      difficulties: np.ndarray, n_show: int = 20) -> pd.DataFrame:
    """Find most aberrant Guttman patterns.

    Returns the n_show most aberrant response patterns sorted by aberrance.
    """
    N, K = response_matrix.shape

    # Sort items by difficulty (easiest first)
    item_order = np.argsort(difficulties)
    sorted_responses = response_matrix.iloc[:, item_order].values

    # Expected pattern: 1s on left, 0s on right
    # Count inversions as a measure of aberrance
    aberrance = np.zeros(N)
    for i in range(N):
        pattern = sorted_responses[i]
        # Count times a 0 appears before a 1
        ones_seen = 0
        inversions = 0
        for val in pattern:
            if val == 1:
                ones_seen += 1
            else:
                inversions += ones_seen
        aberrance[i] = inversions

    # Most aberrant
    top_idx = np.argsort(-aberrance)[:n_show]

    rows = []
    for idx in top_idx:
        pattern_str = "".join(str(int(v)) for v in sorted_responses[idx])
        rows.append({
            "person": idx,
            "ability": float(abilities[idx]) if idx < len(abilities) else np.nan,
            "score": int(sorted_responses[idx].sum()),
            "aberrance": int(aberrance[idx]),
            "pattern": pattern_str,
        })

    return pd.DataFrame(rows)
