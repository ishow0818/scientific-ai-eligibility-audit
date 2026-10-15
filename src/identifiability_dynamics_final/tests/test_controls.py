"""No-recursion and bias control tests."""

from __future__ import annotations

import numpy as np

from identifiability_dynamics_final.dynamics import p_B
from identifiability_dynamics_final.stochastic import step_stochastic


def test_no_recursion_generation_independent_of_q():
    rng1 = np.random.default_rng(0)
    rng2 = np.random.default_rng(0)
    q_a = step_stochastic(0.1, N=200, alpha=1.5, mu=0.0, beta=0.0, rng=rng1, arm="no_recursion")
    q_b = step_stochastic(0.9, N=200, alpha=1.5, mu=0.0, beta=0.0, rng=rng2, arm="no_recursion")
    assert q_a == q_b


def test_recursive_generation_depends_on_q():
    def mean_step(q, seed):
        rng = np.random.default_rng(seed)
        vals = [
            step_stochastic(q, N=500, alpha=1.5, mu=0.0, beta=0.0, rng=rng, arm="recursive")
            for _ in range(200)
        ]
        return float(np.mean(vals))

    m_low = mean_step(0.2, 0)
    m_high = mean_step(0.8, 1)
    assert m_high > m_low
    assert abs(m_low - float(p_B(0.2, 1.5, 0.0))) < 0.05
    assert abs(m_high - float(p_B(0.8, 1.5, 0.0))) < 0.05


def test_beta_positive_favors_A():
    p0 = float(p_B(0.5, alpha=1.0, beta=0.0))
    p_pos = float(p_B(0.5, alpha=1.0, beta=0.05))
    assert p_pos < p0
    assert abs(p0 - 0.5) < 1e-12
