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

    # ── Summary statistics for the pairwise model ──────────────────────
    mean_location = float(np.mean(params))
    variance = float(np.var(params, ddof=0))
    mean_se2 = float(np.mean(se ** 2)) if not np.all(np.isnan(se)) else 0.0

    # Mean square error: residual variance (observed - expected) from BTL
    # Approximate via average squared SE (JMLE-like MSE)
    mse = mean_se2

    # Separation index (reliability-like): proportion of observed variance
    # that is "true" variance, analogous to person separation reliability.
    # sep_var = max(0, variance - mean_se2)
    # G = sqrt(sep_var) / sqrt(mean_se2)  → separation ratio
    # Reliability = sep_var / variance
    sep_var = max(0.0, variance - mean_se2)
    separation_index = float(sep_var / variance) if variance > 0 else 0.0

    # Degrees of freedom: n_comparisons - (n_items - 1)
    # (n_items - 1 free parameters since scale is centred)
    df = len(comparisons) - (n_items - 1)

    summary = {
        "mean_location": round(mean_location, 4),
        "variance": round(variance, 4),
        "mse": round(mse, 4),
        "separation_index": round(separation_index, 4),
        "df": int(df),
    }

    # ── Per-item fit statistics ────────────────────────────────────────
    item_stats = _compute_item_fit(comparisons, params, n_items)

    return {
        "params": params,
        "se": se,
        "comparisons_used": len(comparisons),
        "summary": summary,
        "item_stats": item_stats,
    }


def _compute_item_fit(comparisons, params, n_items):
    """Compute per-item fit statistics from pairwise comparison data.

    For each item, calculates:
      - n_comparisons: total comparisons the item was involved in
      - obs_proportion: observed win proportion (chosen as harder)
      - outfit: outfit mean-square (avg squared standardised residual)
      - chi_sq: chi-squared goodness-of-fit
      - df: degrees of freedom (number of opponents)
    """
    # Collect per-item comparison results
    # comparisons = list of (winner, loser) tuples
    # For each item, track opponents and outcomes
    item_opponents = [[] for _ in range(n_items)]   # list of (opponent, won?)

    for winner, loser in comparisons:
        item_opponents[winner].append((loser, True))   # this item won (judged harder)
        item_opponents[loser].append((winner, False))   # this item lost

    stats = []
    for i in range(n_items):
        opponents = item_opponents[i]
        n_comp = len(opponents)

        if n_comp == 0:
            stats.append({
                "n_comparisons": 0, "n_selected": 0, "obs_proportion": 0.0,
                "outfit": 0.0, "chi_sq": 0.0, "df": 0,
            })
            continue

        # Count unique opponents for df
        unique_opponents = set(opp for opp, _ in opponents)
        item_df = len(unique_opponents)

        # Observed win count
        wins = sum(1 for _, won in opponents if won)
        obs_prop = wins / n_comp if n_comp > 0 else 0.0

        # Compute residuals per comparison
        # BTL probability: P(i beats j) = exp(d_i) / (exp(d_i) + exp(d_j))
        chi_sq = 0.0
        outfit_sum = 0.0
        for opp, won in opponents:
            p_win = np.exp(params[i]) / (np.exp(params[i]) + np.exp(params[opp]))
            observed = 1.0 if won else 0.0
            residual = observed - p_win
            variance = p_win * (1.0 - p_win)
            if variance > 1e-10:
                std_resid = residual / np.sqrt(variance)
                outfit_sum += std_resid ** 2
                chi_sq += (residual ** 2) / variance

        outfit = outfit_sum / n_comp if n_comp > 0 else 0.0

        stats.append({
            "n_comparisons": n_comp,
            "n_selected": wins,
            "obs_proportion": round(obs_prop, 3),
            "outfit": round(outfit, 3),
            "chi_sq": round(chi_sq, 3),
            "df": item_df,
        })

    return stats


def btl_results_to_df(items_df: pd.DataFrame, btl_result: dict) -> pd.DataFrame:
    """Merge BTL parameters into item DataFrame."""
    df = items_df.copy()
    df["difficulty"] = btl_result["params"]
    df["difficulty_se"] = btl_result["se"]

    # Per-item fit stats
    item_stats = btl_result.get("item_stats", [])
    if item_stats:
        df["n_comparisons"] = [s["n_comparisons"] for s in item_stats]
        df["n_selected"] = [s["n_selected"] for s in item_stats]
        df["obs_proportion"] = [s["obs_proportion"] for s in item_stats]
        df["outfit"] = [s["outfit"] for s in item_stats]
        df["chi_sq"] = [s["chi_sq"] for s in item_stats]
        df["item_df"] = [s["df"] for s in item_stats]

    df = df.sort_values("difficulty", ascending=False).reset_index(drop=True)
    df["rank"] = range(1, len(df) + 1)
    return df
