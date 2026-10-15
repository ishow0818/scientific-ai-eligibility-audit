"""Deterministic threshold tests."""

from __future__ import annotations

from identifiability_dynamics_final.deterministic import (
    classify_deterministic,
    iterate_deterministic,
    run_deterministic_validation,
)
from identifiability_dynamics_final.dynamics import R_id


def test_below_threshold_convergence():
    mu, alpha = 0.10, 0.90
    assert R_id(alpha, mu) < 1.0
    for q0 in (0.49, 0.51):
        traj = iterate_deterministic(q0, alpha, mu, beta=0.0, T=100)
        assert abs(traj[-1] - 0.5) < abs(q0 - 0.5)
        assert classify_deterministic(q0, float(traj[-1])) == "toward_half"


def test_above_threshold_divergence():
    mu, alpha = 0.10, 1.30
    assert R_id(alpha, mu) > 1.0
    for q0 in (0.49, 0.51):
        traj = iterate_deterministic(q0, alpha, mu, beta=0.0, T=100)
        assert abs(traj[-1] - 0.5) > abs(q0 - 0.5)
        assert classify_deterministic(q0, float(traj[-1])) == "away_from_half"


def test_exact_half_stays_half_beta0():
    for mu, alpha in ((0.10, 0.90), (0.10, 1.30), (0.0, 2.0)):
        traj = iterate_deterministic(0.5, alpha, mu, beta=0.0, T=100)
        assert abs(traj[-1] - 0.5) < 1e-12


def test_validation_table_shape():
    df = run_deterministic_validation()
    assert len(df) == 6
    assert set(df["regime"]) == {"below", "above"}
