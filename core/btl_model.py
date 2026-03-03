"""Bradley-Terry-Luce model fitting via choix."""

import numpy as np
import pandas as pd
import choix


def fit_btl(comparisons: list[tuple[int, int]], n_items: int,
            n_bootstrap: int = 200) -> dict:
    """Fit BTL model from paired comparison data.

    Args:
        comparisons: list of (winner_index, loser_index) tuples.
            Winner = harder item (higher difficulty).
        n_items: total number of items.
        n_bootstrap: number of bootstrap samples for SEs.

    Returns:
        dict with keys: params (array), se (array), comparisons_used (int).
    """
    if len(comparisons) < n_items - 1:
        raise ValueError(f"Need at least {n_items - 1} comparisons, got {len(comparisons)}.")

    params = choix.ilsr_pairwise(n_items, comparisons, alpha=0.01)
    # Centre on zero
    params = params - np.mean(params)

    # Bootstrap SEs
    boot_params = []
    rng = np.random.default_rng(42)
    comps_arr = np.array(comparisons)
    for _ in range(n_bootstrap):
        idx = rng.choice(len(comps_arr), size=len(comps_arr), replace=True)
        boot_comps = [tuple(comps_arr[i]) for i in idx]
        try:
            bp = choix.ilsr_pairwise(n_items, boot_comps, alpha=0.01)
            bp = bp - np.mean(bp)
            boot_params.append(bp)
        except Exception:
            continue

    if boot_params:
        se = np.std(boot_params, axis=0)
    else:
        se = np.full(n_items, np.nan)

    return {
        "params": params,
        "se": se,
        "comparisons_used": len(comparisons),
    }


def btl_results_to_df(items_df: pd.DataFrame, btl_result: dict) -> pd.DataFrame:
    """Merge BTL parameters into item DataFrame."""
    df = items_df.copy()
    df["difficulty"] = btl_result["params"]
    df["difficulty_se"] = btl_result["se"]
    df = df.sort_values("difficulty", ascending=False).reset_index(drop=True)
    df["rank"] = range(1, len(df) + 1)
    return df
