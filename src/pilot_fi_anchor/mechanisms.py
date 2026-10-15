"""Mechanism families and ground truth.

Every family is fitted in a bounded *fit space*: positive parameters are
log-transformed, the rest stay linear.  ``theta`` always denotes a NATURAL-space
parameter dict keyed by parameter name.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np

from .config import FAMILY_ORDER, TRUTH_FAMILY, TRUTH_PARAMS


def _hump(x: np.ndarray, A: float, mu: float, s: float) -> np.ndarray:
    return A * np.exp(-((x - mu) ** 2) / (2.0 * s * s))


def _affine(x: np.ndarray, a: float, b: float) -> np.ndarray:
    return a + b * x


def _pow(x: np.ndarray, alpha: float, beta: float) -> np.ndarray:
    return alpha * np.power(x, beta)


def _expsat(x: np.ndarray, A: float, tau: float) -> np.ndarray:
    return A * (1.0 - np.exp(-x / tau))


def _quad(x: np.ndarray, a: float, b: float, c: float) -> np.ndarray:
    return a + b * x + c * x * x


@dataclass(frozen=True)
class Mechanism:
    name: str
    fn: Callable[..., np.ndarray]
    params: tuple[str, ...]                 # natural-space parameter order
    log_params: tuple[str, ...]             # positives, fitted in log space
    bounds: dict[str, tuple[float, float]]  # natural-space bounds
    theta0: dict[str, float]                # natural-space initial guess

    @property
    def p(self) -> int:
        return len(self.params)

    def theta_array(self, theta: dict[str, float]) -> np.ndarray:
        return np.array([theta[k] for k in self.params], dtype=float)

    def to_fit(self, theta: dict[str, float]) -> np.ndarray:
        arr = self.theta_array(theta).copy()
        for i, k in enumerate(self.params):
            if k in self.log_params:
                arr[i] = np.log(arr[i])
        return arr

    def from_fit(self, z: np.ndarray) -> dict[str, float]:
        arr = np.asarray(z, dtype=float).copy()
        for i, k in enumerate(self.params):
            if k in self.log_params:
                arr[i] = np.exp(arr[i])
        return {k: float(arr[i]) for i, k in enumerate(self.params)}

    def bounds_fit(self) -> tuple[np.ndarray, np.ndarray]:
        lo, hi = [], []
        for k in self.params:
            a, b = self.bounds[k]
            if k in self.log_params:
                lo.append(np.log(a))
                hi.append(np.log(b))
            else:
                lo.append(a)
                hi.append(b)
        return np.array(lo), np.array(hi)

    def predict(self, x: np.ndarray, theta: dict[str, float]) -> np.ndarray:
        return self.fn(x, *[theta[k] for k in self.params])


FAMILIES: dict[str, Mechanism] = {
    "hump": Mechanism(
        name="hump",
        fn=_hump,
        params=("A", "mu", "s"),
        log_params=("A", "s"),
        bounds={"A": (0.05, 20.0), "mu": (0.0, 10.0), "s": (0.3, 6.0)},
        theta0={"A": 6.0, "mu": 4.0, "s": 2.2},
    ),
    "affine": Mechanism(
        name="affine",
        fn=_affine,
        params=("a", "b"),
        log_params=(),
        bounds={"a": (-5.0, 15.0), "b": (0.05, 5.0)},
        theta0={"a": 1.0, "b": 1.5},
    ),
    "pow": Mechanism(
        name="pow",
        fn=_pow,
        params=("alpha", "beta"),
        log_params=("alpha",),
        bounds={"alpha": (0.05, 20.0), "beta": (0.1, 3.0)},
        theta0={"alpha": 2.5, "beta": 0.7},
    ),
    "expsat": Mechanism(
        name="expsat",
        fn=_expsat,
        params=("A", "tau"),
        log_params=("A", "tau"),
        bounds={"A": (0.05, 20.0), "tau": (0.3, 8.0)},
        theta0={"A": 6.0, "tau": 3.0},
    ),
    "quad": Mechanism(
        name="quad",
        fn=_quad,
        params=("a", "b", "c"),
        log_params=(),
        bounds={"a": (-5.0, 20.0), "b": (-5.0, 10.0), "c": (-1.0, 3.0)},
        theta0={"a": 0.5, "b": 1.5, "c": 0.2},
    ),
}

# Ground truth (see EXPERIMENT_DESIGN.md 2.2)
TRUTH: Mechanism = FAMILIES[TRUTH_FAMILY]
TRUTH_THETA: dict[str, float] = dict(TRUTH_PARAMS)

# Frozen list of family ids; order is used for tie-breaks and records.
ALL_FAMILIES: tuple[str, ...] = FAMILY_ORDER
