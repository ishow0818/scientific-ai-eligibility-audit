"""Per-seed world: candidate grid, noise field, shared initial observations.

Matching scheme (EXPERIMENT_DESIGN.md 2.5): the observation at site (seed, x)
is fully determined by the seed's noise field, so both arms measuring the same
site get the SAME y.  The initial-design sites carry eps0 drawn once from a
fixed seed and shared across every seed and arm: all seeds fork from
bit-identical initial observations.
"""

from __future__ import annotations

import numpy as np

from .config import N_CAND, NOISE_INIT_SEED, SIGMA, X0_IDX, X_MAX, X_MIN
from .mechanisms import TRUTH, TRUTH_THETA


class World:
    def __init__(self, seed: int):
        self.seed = seed
        self.grid = np.linspace(X_MIN, X_MAX, N_CAND)
        assert len(set(X0_IDX)) == len(X0_IDX), "X0_IDX must be distinct"
        assert all(0 <= i < N_CAND for i in X0_IDX), "X0_IDX out of grid"

        from .rng import world_rng

        rng = world_rng(seed)
        self.noise = rng.normal(0.0, SIGMA, N_CAND)

        # Shared eps0 overrides the field at the initial sites: identical
        # initial observations for every seed and both arms.
        rng0 = np.random.default_rng(NOISE_INIT_SEED)
        eps0 = rng0.normal(0.0, SIGMA, len(X0_IDX))
        for i, eps in zip(X0_IDX, eps0):
            self.noise[i] = eps

    def x(self, idx: int) -> float:
        return float(self.grid[idx])

    def y(self, idx: int) -> float:
        """Noiseless truth + frozen noise: same y for both arms."""
        return float(TRUTH.predict(np.array([self.grid[idx]]), TRUTH_THETA)[0]
                     + self.noise[idx])

    def initial_sites(self) -> list[int]:
        return list(X0_IDX)
