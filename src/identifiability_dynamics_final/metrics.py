"""Entropy, N_eff, collapse, first-passage."""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from .config import COLLAPSE_HI, COLLAPSE_LO, EPS


def alternative_entropy(q: float | np.ndarray, eps: float = EPS) -> float | np.ndarray:
    q = np.asarray(q, dtype=np.float64)
    scalar = q.ndim == 0
    q = np.atleast_1d(q)
    h = np.zeros_like(q, dtype=np.float64)
    mask = (q > 0.0) & (q < 1.0)
    qi = np.clip(q[mask], eps, 1.0 - eps)
    h[mask] = -(qi * np.log(qi) + (1.0 - qi) * np.log(1.0 - qi)) / math.log(2.0)
    h = np.clip(h, 0.0, 1.0)
    if scalar:
        return float(h[0])
    return h


def N_eff(q: float | np.ndarray, eps: float = EPS) -> float | np.ndarray:
    q = np.asarray(q, dtype=np.float64)
    scalar = q.ndim == 0
    q = np.atleast_1d(q)
    out = np.ones_like(q, dtype=np.float64)
    mask = (q > 0.0) & (q < 1.0)
    qi = np.clip(q[mask], eps, 1.0 - eps)
    ent = -(qi * np.log(qi) + (1.0 - qi) * np.log(1.0 - qi))
    out[mask] = np.exp(ent)
    if scalar:
        return float(out[0])
    return out


def collapse_flags(
    q: float,
    lo: float = COLLAPSE_LO,
    hi: float = COLLAPSE_HI,
) -> tuple[bool, str]:
    if q <= lo:
        return True, "A"
    if q >= hi:
        return True, "B"
    return False, "none"


def first_passage_time(
    trajectory: np.ndarray,
    lo: float = COLLAPSE_LO,
    hi: float = COLLAPSE_HI,
) -> float:
    for t, q in enumerate(trajectory):
        if q <= lo or q >= hi:
            return float(t)
    return float("nan")


def summarize_seed_run(
    trajectory: np.ndarray,
    *,
    alpha: float,
    mu: float,
    R: float,
    N: int,
    beta: float,
    seed: int,
    q0: float,
    arm: str,
    lo: float = COLLAPSE_LO,
    hi: float = COLLAPSE_HI,
) -> dict[str, Any]:
    q_T = float(trajectory[-1])
    collapsed, direction = collapse_flags(q_T, lo, hi)
    tau = first_passage_time(trajectory, lo, hi)
    return {
        "arm": arm,
        "alpha": alpha,
        "mu": mu,
        "R_id": R,
        "N": N,
        "beta": beta,
        "seed": seed,
        "q0": q0,
        "q_T": q_T,
        "H_0": float(alternative_entropy(float(trajectory[0]))),
        "H_T": float(alternative_entropy(q_T)),
        "N_eff_0": float(N_eff(float(trajectory[0]))),
        "N_eff_T": float(N_eff(q_T)),
        "delta_N_eff": float(N_eff(q_T)) - float(N_eff(float(trajectory[0]))),
        "collapsed": bool(collapsed),
        "collapsed_at_T": bool(collapsed),
        "collapse_direction": direction,
        "collapse_time": tau,
        "abs_qT_minus_half": abs(q_T - 0.5),
    }
