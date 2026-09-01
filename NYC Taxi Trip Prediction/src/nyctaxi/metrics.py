"""Scoring functions shared by training and evaluation.

RMSLE is the headline metric, matching the Kaggle competition. It is the right
choice here for a reason worth stating: trip duration spans two orders of
magnitude, and being 5 minutes wrong on a 90-minute airport run is a very
different error from being 5 minutes wrong on a 6-minute hop. RMSLE scores the
*ratio*, so both are judged proportionally.
"""

from __future__ import annotations

import numpy as np


def rmsle(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Root mean squared log error, on raw seconds."""
    yt = np.clip(np.asarray(y_true, dtype=float), 0, None)
    yp = np.clip(np.asarray(y_pred, dtype=float), 0, None)
    return float(np.sqrt(np.mean((np.log1p(yp) - np.log1p(yt)) ** 2)))


def rmse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.sqrt(np.mean((np.asarray(y_pred) - np.asarray(y_true)) ** 2)))


def mae(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.mean(np.abs(np.asarray(y_pred) - np.asarray(y_true))))


def mape(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    yt = np.asarray(y_true, dtype=float)
    mask = yt > 0
    if not mask.any():
        return float("nan")
    return float(np.mean(np.abs(np.asarray(y_pred)[mask] - yt[mask]) / yt[mask]) * 100.0)


def r2(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    yt = np.asarray(y_true, dtype=float)
    ss_res = float(np.sum((yt - np.asarray(y_pred)) ** 2))
    ss_tot = float(np.sum((yt - yt.mean()) ** 2))
    return 1.0 - ss_res / ss_tot if ss_tot else float("nan")


def score_all(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    """The full metric set, in seconds-space."""
    return {
        "rmsle": round(rmsle(y_true, y_pred), 5),
        "rmse_s": round(rmse(y_true, y_pred), 2),
        "mae_s": round(mae(y_true, y_pred), 2),
        "mape_pct": round(mape(y_true, y_pred), 2),
        "r2": round(r2(y_true, y_pred), 4),
    }


def interval_coverage(
    y_true: np.ndarray, lower: np.ndarray, upper: np.ndarray
) -> dict[str, float]:
    """How often the truth actually falls inside the predicted band.

    The honest test of the P10-P90 interval. Nominal coverage is 80%; a band
    that covers far less is overconfident, far more is uselessly wide.
    """
    yt = np.asarray(y_true, dtype=float)
    inside = (yt >= np.asarray(lower)) & (yt <= np.asarray(upper))
    return {
        "coverage_pct": round(100.0 * float(np.mean(inside)), 2),
        "nominal_pct": 80.0,
        "mean_width_s": round(float(np.mean(np.asarray(upper) - np.asarray(lower))), 1),
        "median_width_s": round(float(np.median(np.asarray(upper) - np.asarray(lower))), 1),
    }
