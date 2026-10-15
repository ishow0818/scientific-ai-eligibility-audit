"""Entropy / N_eff / summary schema tests."""

from __future__ import annotations

import numpy as np
import pandas as pd

from identifiability_dynamics_final.analysis import SUMMARY_COLUMNS, seed_summary_schema_ok, summarize_condition
from identifiability_dynamics_final.metrics import N_eff, alternative_entropy, summarize_seed_run
from identifiability_dynamics_final.stochastic import run_condition_seeds


def test_entropy_boundaries():
    assert abs(alternative_entropy(0.5) - 1.0) < 1e-12
    assert alternative_entropy(0.0) == 0.0
    assert alternative_entropy(1.0) == 0.0
    assert np.isfinite(alternative_entropy(1e-15))


def test_N_eff_boundaries():
    assert abs(N_eff(0.5) - 2.0) < 1e-12
    assert abs(N_eff(0.0) - 1.0) < 1e-12
    assert abs(N_eff(1.0) - 1.0) < 1e-12


def test_phase_summary_row_counts():
    df = run_condition_seeds(
        alpha=1.0, mu=0.1, N=50, beta=0.0, T=10, n_seeds=5, arm="recursive"
    )
    assert len(df) == 5
    summary = summarize_condition(df)
    assert len(summary) == 1
    assert list(summary.columns) == SUMMARY_COLUMNS


def test_output_schema_complete():
    traj = np.linspace(0.5, 0.4, 11)
    row = summarize_seed_run(
        traj, alpha=1.0, mu=0.1, R=0.9, N=100, beta=0.0, seed=0, q0=0.5, arm="recursive"
    )
    assert seed_summary_schema_ok(pd.DataFrame([row]))
    assert "collapse_time" in row
