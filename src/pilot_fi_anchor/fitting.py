"""Fitting (MLE in bounded fit space), residual fields, log-likelihood.

Deterministic given (data, warm start): the only stochastic part is the
3-start initialisation at first fit, which draws from a caller-supplied
seeded RNG.
"""

from __future__ import annotations

import numpy as np
from scipy.optimize import least_squares

from .config import SIGMA
from .mechanisms import Mechanism

LOG_2PI_S2 = float(np.log(2.0 * np.pi * SIGMA * SIGMA))


def _cost(mech: Mechanism, z: np.ndarray, xs: np.ndarray, ys: np.ndarray) -> float:
    r = (mech.predict(xs, mech.from_fit(z)) - ys) / SIGMA
    return float(r @ r)


def fit(
    mech: Mechanism,
    xs: np.ndarray,
    ys: np.ndarray,
    warm: np.ndarray | None = None,
    rng: np.random.Generator | None = None,
) -> np.ndarray:
    """Bounded least squares in fit space.

    warm: previous fit vector (warm start).  If None, three seeded starts
    around the family's theta0 are tried and the best is kept.
    """
    lo, hi = mech.bounds_fit()
    xs = np.asarray(xs, dtype=float)
    ys = np.asarray(ys, dtype=float)

    def resid(z: np.ndarray) -> np.ndarray:
        return (mech.predict(xs, mech.from_fit(z)) - ys) / SIGMA

    def solve(z0: np.ndarray) -> np.ndarray:
        sol = least_squares(
            resid, z0, bounds=(lo, hi), max_nfev=2000, method="trf"
        )
        return sol.x

    if warm is not None:
        return solve(np.clip(np.asarray(warm, dtype=float), lo, hi))

    rng = rng if rng is not None else np.random.default_rng(0)
    z0 = mech.to_fit(mech.theta0)
    candidates = [z0]
    for _ in range(2):
        jitter = 0.15 * (hi - lo) * rng.uniform(-1.0, 1.0, size=len(z0))
        candidates.append(np.clip(z0 + jitter, lo, hi))
    best = min((solve(z) for z in candidates), key=lambda z: _cost(mech, z, xs, ys))
    return best


def loglik(mech: Mechanism, theta: dict[str, float], x: float, y: float) -> float:
    r = y - float(mech.fn(np.array([x]), **theta)[0])
    return -0.5 * (r * r / (SIGMA * SIGMA) + LOG_2PI_S2)


def residual_field(
    mech: Mechanism,
    theta: dict[str, float],
    xs_measured: np.ndarray,
    ys_measured: np.ndarray,
    x_query: np.ndarray,
) -> np.ndarray:
    """Interpolated residual field at query points.

    Linear interpolation over the hypothesis's own measured sites, flat
    extension beyond the outermost sites (EXPERIMENT_DESIGN.md 3.1).
    """
    xs = np.asarray(xs_measured, dtype=float)
    ys = np.asarray(ys_measured, dtype=float)
    if len(xs) == 0:
        return np.zeros_like(np.asarray(x_query, dtype=float))
    order = np.argsort(xs)
    xs_s, ys_s = xs[order], ys[order]
    r = ys_s - mech.predict(xs_s, theta)
    field = np.interp(np.asarray(x_query, dtype=float), xs_s, r)
    field = np.where(x_query < xs_s[0], r[0], field)
    field = np.where(x_query > xs_s[-1], r[-1], field)
    return field
