"""Deterministic recursion q_{t+1}=F(q_t)."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from .config import DeterministicConfig, EPS
from .dynamics import F, R_id
from .metrics import alternative_entropy


def iterate_deterministic(
    q0: float,
    alpha: float,
    mu: float,
    beta: float = 0.0,
    T: int = 100,
    eps: float = EPS,
) -> np.ndarray:
    q = np.empty(T + 1, dtype=np.float64)
    q[0] = float(q0)
    for t in range(T):
        q[t + 1] = float(F(q[t], alpha, mu, beta, eps))
    return q


def classify_deterministic(q0: float, q_T: float, tol_away: float = 0.02) -> str:
    if abs(q0 - 0.5) < 1e-15:
        if abs(q_T - 0.5) < 1e-10:
            return "fixed_at_half"
        return "broke_exact_half"
    d0 = abs(q0 - 0.5)
    dT = abs(q_T - 0.5)
    if dT < d0 - 1e-6:
        return "toward_half"
    if dT > d0 + tol_away * 0.5:
        return "away_from_half"
    if dT > d0 + 1e-6:
        return "away_from_half"
    return "neutral"


def run_deterministic_validation(cfg: DeterministicConfig | None = None) -> pd.DataFrame:
    cfg = cfg or DeterministicConfig()
    rows: list[dict[str, Any]] = []
    for regime, mu, alpha in (
        ("below", cfg.below_mu, cfg.below_alpha),
        ("above", cfg.above_mu, cfg.above_alpha),
    ):
        R = R_id(alpha, mu)
        for q0 in cfg.q0_list:
            traj = iterate_deterministic(q0, alpha, mu, cfg.beta, cfg.T)
            q_T = float(traj[-1])
            rows.append(
                {
                    "regime": regime,
                    "mu": mu,
                    "alpha": alpha,
                    "R_id": R,
                    "beta": cfg.beta,
                    "q0": q0,
                    "q_T": q_T,
                    "H_T": float(alternative_entropy(q_T)),
                    "abs_qT_minus_half": abs(q_T - 0.5),
                    "behavior": classify_deterministic(q0, q_T),
                }
            )
    return pd.DataFrame(rows)
