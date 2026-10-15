"""Frozen hyperparameters. Do not tune."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


EPS = 1e-12

COLLAPSE_LO = 0.10
COLLAPSE_HI = 0.90

# Local amplification epsilons / horizons
LOCAL_EPSILONS = (0.001, 0.002, 0.005)
K_PRIMARY = 5
K_ROBUST = 10
NUMERICAL_FLOOR = 1e-15
D1_FLOOR = 1e-12
EARLY_TS = (1, 5, 10, 20)


@dataclass(frozen=True)
class DeterministicConfig:
    T: int = 100
    beta: float = 0.0
    q0_list: tuple[float, ...] = (0.49, 0.50, 0.51)
    below_alpha: float = 0.90
    below_mu: float = 0.10
    above_alpha: float = 1.30
    above_mu: float = 0.10


@dataclass(frozen=True)
class StochasticGrid:
    T: int = 100
    n_seeds: int = 500
    N: int = 100
    beta: float = 0.0
    alphas: tuple[float, ...] = (
        0.60, 0.80, 0.90, 1.00, 1.05, 1.10, 1.20, 1.30, 1.50, 1.80, 2.00,
    )
    mus: tuple[float, ...] = (0.00, 0.05, 0.10, 0.20, 0.30, 0.40)
    q0_exact: float = 0.5
    q0_jitter_std: float = 0.005


@dataclass(frozen=True)
class BiasConfig:
    T: int = 100
    n_seeds: int = 500
    N: int = 100
    conditions: tuple[tuple[float, float], ...] = (
        (0.10, 0.90),
        (0.10, 1.11),
        (0.10, 1.33),
        (0.10, 1.67),
    )
    betas: tuple[float, ...] = (0.00, 0.01, 0.03, 0.05)


@dataclass(frozen=True)
class BudgetConfig:
    T: int = 100
    n_seeds: int = 500
    beta: float = 0.0
    Ns: tuple[int, ...] = (20, 50, 100, 500, 2000)
    below: tuple[float, float] = (0.10, 0.90)
    above: tuple[float, float] = (0.10, 1.30)


@dataclass(frozen=True)
class PilotConfig:
    eps: float = EPS
    collapse_lo: float = COLLAPSE_LO
    collapse_hi: float = COLLAPSE_HI
    deterministic: DeterministicConfig = field(default_factory=DeterministicConfig)
    stochastic: StochasticGrid = field(default_factory=StochasticGrid)
    bias: BiasConfig = field(default_factory=BiasConfig)
    budget: BudgetConfig = field(default_factory=BudgetConfig)
    results_dir: str = "identifiability_dynamics_final/results"
    # Verified 500-seed summaries (terminal metrics); early trajs re-simulated.
    provenance_dir: str = "outputs/pilot_alt_dynamics"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
