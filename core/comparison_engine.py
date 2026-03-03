"""Pair selection, storage, spot-check sampling."""

import itertools
import random
import numpy as np


STRATEGIES = {
    "round_robin": {
        "label": "Round Robin (all pairs)",
        "description": "Every item compared with every other. Most thorough but most API calls.",
    },
    "chain": {
        "label": "Chain (nearest neighbours)",
        "description": "Each item compared with its K nearest neighbours in item order. Fewest API calls.",
    },
    "swiss": {
        "label": "Swiss Tournament (adaptive)",
        "description": "Multiple rounds pairing similarly-ranked items. Moderate API calls.",
    },
}


def generate_pairs_round_robin(n_items: int) -> list[tuple[int, int]]:
    """Full round-robin: all (n choose 2) pairs."""
    return list(itertools.combinations(range(n_items), 2))


def generate_pairs_chain(n_items: int, k: int = 3) -> list[tuple[int, int]]:
    """Chain approach: compare each item with its K nearest neighbours.

    Items are assumed to be in roughly increasing difficulty order (by position).
    Each item i is compared with items i+1, i+2, ..., i+K (where they exist).
    The overlapping links propagate difficulty information along the full scale.

    Args:
        n_items: number of items.
        k: number of neighbours to compare each item with.

    Returns:
        list of (i, j) index pairs.
    """
    pairs = set()
    for i in range(n_items):
        for offset in range(1, k + 1):
            j = i + offset
            if j < n_items:
                pairs.add((i, j))
    return sorted(pairs)


def generate_pairs_swiss(n_items: int, rankings: np.ndarray | None = None,
                         n_rounds: int = 8) -> list[tuple[int, int]]:
    """Swiss-tournament style adaptive pairing.

    Pairs items with similar current rankings to maximise information.
    """
    if rankings is None:
        rankings = np.zeros(n_items)

    done = set()
    pairs = []

    for _ in range(n_rounds):
        order = np.argsort(-rankings)
        available = list(order)
        round_pairs = []

        while len(available) >= 2:
            a = available.pop(0)
            for j, b in enumerate(available):
                if (min(a, b), max(a, b)) not in done:
                    round_pairs.append((a, b))
                    done.add((min(a, b), max(a, b)))
                    available.pop(j)
                    break
            else:
                continue

        pairs.extend(round_pairs)

    return pairs


def select_pairs(n_items: int, strategy: str = "chain", k: int = 3) -> list[tuple[int, int]]:
    """Select pairs using the chosen strategy.

    Args:
        n_items: number of items.
        strategy: 'round_robin', 'chain', or 'swiss'.
        k: neighbours for chain strategy (ignored by others).

    Returns:
        list of (i, j) index pairs.
    """
    if strategy == "round_robin":
        return generate_pairs_round_robin(n_items)
    elif strategy == "chain":
        return generate_pairs_chain(n_items, k=k)
    elif strategy == "swiss":
        n_rounds = min(12, max(6, n_items // 5))
        return generate_pairs_swiss(n_items, n_rounds=n_rounds)
    else:
        raise ValueError(f"Unknown strategy: {strategy}")


def count_pairs(n_items: int, strategy: str = "chain", k: int = 3) -> int:
    """Preview how many pairs a strategy will produce without generating them."""
    if strategy == "round_robin":
        return n_items * (n_items - 1) // 2
    elif strategy == "chain":
        return sum(min(k, n_items - 1 - i) for i in range(n_items))
    elif strategy == "swiss":
        # Approximate — depends on rounds
        n_rounds = min(12, max(6, n_items // 5))
        return min(n_rounds * (n_items // 2), n_items * (n_items - 1) // 2)
    return 0


def spot_check_sample(comparisons: list[dict], n: int = 10,
                      seed: int = 42) -> list[int]:
    """Select a random sample of comparison indices for spot-checking."""
    rng = random.Random(seed)
    n = min(n, len(comparisons))
    return rng.sample(range(len(comparisons)), n)


def comparisons_to_btl_data(comparisons: list[dict], item_ids: list[str]) -> list[tuple[int, int]]:
    """Convert comparison results to (winner, loser) index tuples for BTL.

    Each comparison dict has: item_a_id, item_b_id, harder ('A' or 'B').
    Winner (harder) goes first.
    """
    id_to_idx = {id_: i for i, id_ in enumerate(item_ids)}
    btl_pairs = []
    for comp in comparisons:
        a_idx = id_to_idx[comp["item_a_id"]]
        b_idx = id_to_idx[comp["item_b_id"]]
        if comp["harder"] == "A":
            btl_pairs.append((a_idx, b_idx))
        else:
            btl_pairs.append((b_idx, a_idx))
    return btl_pairs
