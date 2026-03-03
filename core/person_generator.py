"""Generate simulated persons and response matrix."""

import numpy as np
import pandas as pd


def generate_response_matrix(abilities: np.ndarray, difficulties: np.ndarray,
                             discriminations: np.ndarray = None,
                             seed: int = 42) -> pd.DataFrame:
    """Generate a binary response matrix using the 2PL IRT model.

    P(correct) = 1 / (1 + exp(-a * (theta - b)))

    Args:
        abilities: (N,) person abilities.
        difficulties: (K,) item difficulties.
        discriminations: (K,) item discrimination params (default all 1.0).
        seed: random seed.

    Returns:
        DataFrame of shape (N, K) with 0/1 responses.
    """
    rng = np.random.default_rng(seed)
    N = len(abilities)
    K = len(difficulties)

    if discriminations is None:
        discriminations = np.ones(K)

    # Broadcast: (N, 1) - (1, K) -> (N, K)
    theta = abilities.reshape(-1, 1)
    b = difficulties.reshape(1, -1)
    a = discriminations.reshape(1, -1)

    prob = 1.0 / (1.0 + np.exp(-a * (theta - b)))
    responses = (rng.random((N, K)) < prob).astype(int)

    return pd.DataFrame(responses)
