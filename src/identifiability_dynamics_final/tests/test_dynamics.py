"""Tests for core dynamics maps."""

from __future__ import annotations

import numpy as np

from identifiability_dynamics_final.dynamics import (
    F,
    F_prime_at_half,
    R_id,
    alpha_c,
    logit,
    numerical_F_prime_at_half,
    p_B,
    sigmoid,
)


def test_sigmoid_logit_stability():
    x = np.array([-100.0, -1.0, 0.0, 1.0, 100.0])
    s = sigmoid(x)
    assert np.all(np.isfinite(s))
    assert np.all(s >= 0.0) and np.all(s <= 1.0)
    q = np.array([1e-15, 0.5, 1 - 1e-15])
    assert np.all(np.isfinite(logit(q)))


def test_F_half_is_half_beta0():
    for mu in (0.0, 0.1, 0.4):
        for alpha in (0.8, 1.2, 2.0):
            assert abs(float(F(0.5, alpha, mu, beta=0.0)) - 0.5) < 1e-12


def test_analytic_derivative_matches_numerical():
    for mu in (0.0, 0.1, 0.3):
        for alpha in (0.7, 1.0, 1.5):
            analytic = F_prime_at_half(alpha, mu, beta=0.0)
            numeric = numerical_F_prime_at_half(alpha, mu, beta=0.0)
            assert abs(analytic - R_id(alpha, mu)) < 1e-12
            assert abs(analytic - numeric) < 1e-5


def test_alpha_c():
    assert abs(alpha_c(0.1) - 1.0 / 0.9) < 1e-12


def test_mu_one_removes_recursive_dependence():
    for q in (0.1, 0.3, 0.7, 0.9):
        assert abs(float(F(q, alpha=2.0, mu=1.0, beta=0.0)) - 0.5) < 1e-12


def test_p_B_depends_on_q_when_alpha_positive():
    p_low = float(p_B(0.2, alpha=1.5, beta=0.0))
    p_high = float(p_B(0.8, alpha=1.5, beta=0.0))
    assert p_high > p_low
