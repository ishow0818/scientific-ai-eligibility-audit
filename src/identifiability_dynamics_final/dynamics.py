"""Core maps: logit, sigmoid, p_B, F, R_id. Frozen — do not modify."""

from __future__ import annotations

import numpy as np

from .config import EPS


def clip_q(q: float | np.ndarray, eps: float = EPS) -> float | np.ndarray:
    return np.clip(q, eps, 1.0 - eps)


def logit(q: float | np.ndarray, eps: float = EPS) -> float | np.ndarray:
    qc = clip_q(q, eps)
    return np.log(qc / (1.0 - qc))


def sigmoid(x: float | np.ndarray) -> float | np.ndarray:
    x_arr = np.asarray(x, dtype=np.float64)
    scalar = x_arr.ndim == 0
    x_arr = np.atleast_1d(x_arr)
    out = np.empty_like(x_arr, dtype=np.float64)
    pos = x_arr >= 0
    out[pos] = 1.0 / (1.0 + np.exp(-x_arr[pos]))
    expx = np.exp(x_arr[~pos])
    out[~pos] = expx / (1.0 + expx)
    if scalar:
        return float(out[0])
    return out


def p_B(q: float | np.ndarray, alpha: float, beta: float, eps: float = EPS) -> float | np.ndarray:
    """Recursive generation probability for alternative B."""
    return sigmoid(alpha * logit(q, eps) - beta)


def F(
    q: float | np.ndarray,
    alpha: float,
    mu: float,
    beta: float = 0.0,
    eps: float = EPS,
) -> float | np.ndarray:
    """
    Deterministic expectation map:
      F(q) = (1-mu) * sigmoid(alpha * logit(q) - beta) + mu * 0.5
    """
    return (1.0 - mu) * p_B(q, alpha, beta, eps) + mu * 0.5


def R_id(alpha: float, mu: float) -> float:
    """Dimensionless recursion parameter: (1-mu)*alpha."""
    return float((1.0 - mu) * alpha)


def alpha_c(mu: float) -> float:
    """Critical alpha at R_id=1: 1/(1-mu)."""
    if mu >= 1.0:
        return float("inf")
    return 1.0 / (1.0 - mu)


def F_prime_at_half(alpha: float, mu: float, beta: float = 0.0) -> float:
    """Analytic F'(0.5)=(1-mu)*alpha for beta=0."""
    if abs(beta) > 1e-15:
        raise ValueError("analytic F'(0.5)=(1-mu)*alpha holds for beta=0 only")
    return R_id(alpha, mu)


def numerical_F_prime_at_half(
    alpha: float,
    mu: float,
    beta: float = 0.0,
    h: float = 1e-6,
    eps: float = EPS,
) -> float:
    return float((F(0.5 + h, alpha, mu, beta, eps) - F(0.5 - h, alpha, mu, beta, eps)) / (2.0 * h))
