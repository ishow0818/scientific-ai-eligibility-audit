"""Stochastic finite-budget tests."""

from __future__ import annotations

import numpy as np

from identifiability_dynamics_final.metrics import first_passage_time
from identifiability_dynamics_final.stochastic import simulate_trajectory


def test_stochastic_q_in_unit_interval():
    traj = simulate_trajectory(
        0.5, T=50, N=100, alpha=1.3, mu=0.1, beta=0.0, seed=0, arm="recursive"
    )
    assert np.all(traj >= 0.0) and np.all(traj <= 1.0)
    assert np.all(np.isfinite(traj))


def test_seed_reproducibility():
    a = simulate_trajectory(0.5, T=30, N=50, alpha=1.2, mu=0.1, beta=0.0, seed=123)
    b = simulate_trajectory(0.5, T=30, N=50, alpha=1.2, mu=0.1, beta=0.0, seed=123)
    np.testing.assert_array_equal(a, b)
    c = simulate_trajectory(0.5, T=30, N=50, alpha=1.2, mu=0.1, beta=0.0, seed=124)
    assert not np.array_equal(a, c)


def test_collapse_time_logic():
    traj = np.array([0.5, 0.4, 0.2, 0.05, 0.2])
    tau = first_passage_time(traj, lo=0.10, hi=0.90)
    assert tau == 3.0
    traj2 = np.linspace(0.45, 0.55, 20)
    assert np.isnan(first_passage_time(traj2))


def test_no_nan_except_tau():
    traj = simulate_trajectory(0.5, T=20, N=100, alpha=0.8, mu=0.2, beta=0.0, seed=1)
    assert np.all(np.isfinite(traj))
