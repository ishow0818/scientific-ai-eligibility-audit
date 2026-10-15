"""Finite-budget stochastic recursion and no-recursion control."""

from __future__ import annotations

from typing import Any, Literal

import numpy as np
import pandas as pd

from .config import EPS, StochasticGrid
from .dynamics import R_id, p_B
from .metrics import summarize_seed_run

ArmKind = Literal["recursive", "no_recursion"]


def step_stochastic(
    q: float,
    *,
    N: int,
    alpha: float,
    mu: float,
    beta: float,
    rng: np.random.Generator,
    arm: ArmKind = "recursive",
    eps: float = EPS,
) -> float:
    """
    Recursive: p = sigmoid(alpha*logit(q)-beta)
    No-recursion: p = 0.5 (independent of q)
    Same N, rediscovery split, and sampling otherwise.
    """
    N_rediscovery = int(rng.binomial(N, mu))
    N_recursive = N - N_rediscovery

    if arm == "recursive":
        p_rec = float(p_B(q, alpha, beta, eps))
    elif arm == "no_recursion":
        p_rec = 0.5
    else:
        raise ValueError(arm)

    n_B_rec = int(rng.binomial(N_recursive, p_rec)) if N_recursive > 0 else 0
    n_B_red = int(rng.binomial(N_rediscovery, 0.5)) if N_rediscovery > 0 else 0
    return (n_B_rec + n_B_red) / float(N)


def simulate_trajectory(
    q0: float,
    *,
    T: int,
    N: int,
    alpha: float,
    mu: float,
    beta: float,
    seed: int,
    arm: ArmKind = "recursive",
    eps: float = EPS,
) -> np.ndarray:
    rng = np.random.default_rng(seed)
    q = np.empty(T + 1, dtype=np.float64)
    q[0] = float(np.clip(q0, 0.0, 1.0))
    for t in range(T):
        q[t + 1] = step_stochastic(
            q[t], N=N, alpha=alpha, mu=mu, beta=beta, rng=rng, arm=arm, eps=eps
        )
    return q


def run_condition_seeds(
    *,
    alpha: float,
    mu: float,
    N: int,
    beta: float,
    T: int,
    n_seeds: int,
    arm: ArmKind = "recursive",
    q0: float = 0.5,
    seed_offset: int = 0,
) -> pd.DataFrame:
    R = R_id(alpha, mu)
    rows = []
    for s in range(n_seeds):
        seed = seed_offset + s
        traj = simulate_trajectory(
            q0, T=T, N=N, alpha=alpha, mu=mu, beta=beta, seed=seed, arm=arm
        )
        row = summarize_seed_run(
            traj,
            alpha=alpha,
            mu=mu,
            R=R,
            N=N,
            beta=beta,
            seed=seed,
            q0=q0,
            arm=arm,
        )
        row["q0_mode"] = "exact"
        row["distance_to_threshold"] = R - 1.0
        rows.append(row)
    return pd.DataFrame(rows)


def run_phase_grid(
    grid: StochasticGrid | None = None,
    *,
    n_seeds: int | None = None,
    arm: ArmKind = "recursive",
) -> pd.DataFrame:
    grid = grid or StochasticGrid()
    ns = grid.n_seeds if n_seeds is None else n_seeds
    frames = []
    for mu in grid.mus:
        for alpha in grid.alphas:
            frames.append(
                run_condition_seeds(
                    alpha=alpha,
                    mu=mu,
                    N=grid.N,
                    beta=grid.beta,
                    T=grid.T,
                    n_seeds=ns,
                    arm=arm,
                    q0=grid.q0_exact,
                )
            )
    return pd.concat(frames, ignore_index=True)
