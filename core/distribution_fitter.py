"""Smooth user-drawn freehand points into a clean probability density."""

import numpy as np
from scipy.integrate import trapezoid
from scipy.ndimage import gaussian_filter1d
from scipy.interpolate import interp1d


def fit_distribution(points_x: list[float], points_y: list[float],
                     n_eval: int = 300) -> dict:
    """Smooth a user-drawn density curve into a clean, normalised PDF.

    Instead of forcing a parametric shape (Gaussian, skew-normal), this
    uses interpolation + Gaussian kernel smoothing so the fitted curve
    faithfully follows whatever the user drew — symmetric, skewed,
    bimodal, flat-topped, etc.

    Args:
        points_x: x-coordinates (difficulty/ability scale).
        points_y: y-coordinates (relative density, non-negative).
        n_eval: number of evaluation points for the smooth curve.

    Returns:
        dict with x_smooth, y_smooth (normalised density), cdf_smooth.
    """
    if len(points_x) < 3:
        raise ValueError("Need at least 3 points to fit distribution.")

    xs = np.array(points_x, dtype=float)
    ys = np.array(points_y, dtype=float)

    # Sort by x
    order = np.argsort(xs)
    xs = xs[order]
    ys = ys[order]
    ys = np.maximum(ys, 0)

    # Deduplicate x values (freehand can double-back): average y per unique x
    unique_x, inverse = np.unique(xs, return_inverse=True)
    if len(unique_x) < len(xs):
        avg_y = np.zeros(len(unique_x))
        counts = np.zeros(len(unique_x))
        for i, idx in enumerate(inverse):
            avg_y[idx] += ys[i]
            counts[idx] += 1
        xs = unique_x
        ys = avg_y / counts

    if len(xs) < 3:
        raise ValueError("Need at least 3 unique x-positions.")

    # Interpolate onto a uniform grid spanning the drawn range
    x_range = xs[-1] - xs[0]
    pad = x_range * 0.15  # small padding so tails reach zero
    x_smooth = np.linspace(xs[0] - pad, xs[-1] + pad, n_eval)

    interp_fn = interp1d(xs, ys, kind="linear", bounds_error=False, fill_value=0.0)
    y_interp = interp_fn(x_smooth)
    y_interp = np.maximum(y_interp, 0)

    # Gaussian kernel smoothing — sigma proportional to data density
    # Enough to remove hand jitter, not so much it flattens the shape
    pts_per_unit = n_eval / (x_smooth[-1] - x_smooth[0])
    smooth_sigma = max(pts_per_unit * x_range * 0.02, 2.0)  # ~2% of range
    y_smooth = gaussian_filter1d(y_interp, sigma=smooth_sigma)
    y_smooth = np.maximum(y_smooth, 0)

    # Taper tails to zero cleanly (cosine taper over the padding region)
    taper_len = int(n_eval * pad / (x_smooth[-1] - x_smooth[0]))
    if taper_len > 1:
        left_taper = 0.5 * (1 - np.cos(np.linspace(0, np.pi, taper_len)))
        right_taper = 0.5 * (1 - np.cos(np.linspace(np.pi, 0, taper_len)))
        y_smooth[:taper_len] *= left_taper
        y_smooth[-taper_len:] *= right_taper

    # Normalise to integrate to 1 (proper PDF)
    area = trapezoid(y_smooth, x_smooth)
    if area > 0:
        y_smooth = y_smooth / area

    # CDF via cumulative trapezoid
    dx = x_smooth[1] - x_smooth[0]
    cdf_smooth = np.cumsum(y_smooth) * dx
    if cdf_smooth[-1] > 0:
        cdf_smooth = cdf_smooth / cdf_smooth[-1]

    return {
        "x_smooth": x_smooth.tolist(),
        "y_smooth": y_smooth.tolist(),
        "cdf_smooth": cdf_smooth.tolist(),
    }


def sample_from_distribution(x_smooth: list[float], cdf_smooth: list[float],
                             n: int, seed: int = 42) -> np.ndarray:
    """Sample n values from the fitted distribution using inverse CDF."""
    rng = np.random.default_rng(seed)
    u = rng.uniform(0, 1, n)
    xs = np.array(x_smooth)
    cdf = np.array(cdf_smooth)
    samples = np.interp(u, cdf, xs)
    return samples
