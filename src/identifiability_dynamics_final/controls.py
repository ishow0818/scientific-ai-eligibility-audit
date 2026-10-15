"""No-recursion, bias, and finite-budget controls."""

from __future__ import annotations

import pandas as pd

from .config import BiasConfig, BudgetConfig, StochasticGrid
from .stochastic import ArmKind, run_condition_seeds, run_phase_grid


def run_no_recursion_phase(
    grid: StochasticGrid | None = None,
    *,
    n_seeds: int | None = None,
) -> pd.DataFrame:
    return run_phase_grid(grid, n_seeds=n_seeds, arm="no_recursion")


def run_bias_experiment(cfg: BiasConfig | None = None, n_seeds: int | None = None) -> pd.DataFrame:
    cfg = cfg or BiasConfig()
    ns = cfg.n_seeds if n_seeds is None else n_seeds
    frames = []
    for mu, alpha in cfg.conditions:
        for beta in cfg.betas:
            frames.append(
                run_condition_seeds(
                    alpha=alpha,
                    mu=mu,
                    N=cfg.N,
                    beta=beta,
                    T=cfg.T,
                    n_seeds=ns,
                    arm="recursive",
                )
            )
    return pd.concat(frames, ignore_index=True)


def run_budget_experiment(
    cfg: BudgetConfig | None = None,
    n_seeds: int | None = None,
    *,
    arm: ArmKind = "recursive",
) -> pd.DataFrame:
    cfg = cfg or BudgetConfig()
    ns = cfg.n_seeds if n_seeds is None else n_seeds
    frames = []
    for label, (mu, alpha) in (("below", cfg.below), ("above", cfg.above)):
        for N in cfg.Ns:
            df = run_condition_seeds(
                alpha=alpha,
                mu=mu,
                N=N,
                beta=cfg.beta,
                T=cfg.T,
                n_seeds=ns,
                arm=arm,
            )
            df = df.copy()
            df["budget_regime"] = label
            frames.append(df)
    return pd.concat(frames, ignore_index=True)


def run_matched_budget_pair(
    cfg: BudgetConfig | None = None,
    n_seeds: int | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    return (
        run_budget_experiment(cfg, n_seeds=n_seeds, arm="recursive"),
        run_budget_experiment(cfg, n_seeds=n_seeds, arm="no_recursion"),
    )
