"""Final gate tests (G1–G7). No legacy terminal-threshold KILL-E."""

from __future__ import annotations

import json
import math

import numpy as np
import pandas as pd

from identifiability_dynamics_final.analysis import (
    early_dispersion_from_trajectories,
    growth_law_summary,
    local_growth_from_trajectory,
    run_deterministic_local_growth,
    threshold_alignment,
)
from identifiability_dynamics_final.gates import evaluate_final_gates


def test_local_growth_matches_geometric():
    d0 = -0.005
    traj = 0.5 + d0 * (0.8 ** np.arange(0, 11))
    g = local_growth_from_trajectory(traj, K=5)
    assert g["lambda_emp"] < 0
    assert abs(g["lambda_emp"] - math.log(0.8)) < 1e-9


def test_deterministic_sign_flip_on_small_grid():
    df = run_deterministic_local_growth(
        alphas=(0.9, 1.3),
        mus=(0.1,),
        epsilons=(0.001, 0.005),
    )
    low = df[df["R_id"] < 1]
    high = df[df["R_id"] > 1]
    assert (low["lambda_emp_K5"] < 0).all()
    assert (high["lambda_emp_K5"] > 0).all()


def test_dispersion_metric():
    trajs = {
        0: np.concatenate([np.array([0.5, 0.6, 0.7, 0.7, 0.7, 0.8]), np.full(15, 0.8)]),
        1: np.concatenate([np.array([0.5, 0.4, 0.3, 0.3, 0.3, 0.2]), np.full(15, 0.2)]),
    }
    d = early_dispersion_from_trajectories(trajs)
    assert abs(d["D_1"] - 0.1) < 1e-12
    assert d["D1_valid"] == 1.0


def test_gates_pass_on_tiny_synthetic():
    growth = run_deterministic_local_growth(
        alphas=(0.8, 1.0, 1.2),
        mus=(0.0,),
        epsilons=(0.001,),
    )
    alignment = threshold_alignment(growth)
    law = growth_law_summary(growth)
    vs = pd.DataFrame(
        [
            {
                "mu": 0.0,
                "alpha": 1.5,
                "N": 100,
                "beta": 0.0,
                "R_id": 1.5,
                "D1_rec": 0.04,
                "D10_rec": 0.3,
                "A10_rec": 7.5,
                "D1_nr": 0.04,
                "D10_nr": 0.04,
                "A10_nr": 1.0,
                "Amplification_excess_10": 6.5,
                "Dispersion_excess_10": 0.26,
            }
        ]
    )
    large_n = pd.DataFrame(
        [
            {"N": 500, "ok": True, "D10_rec": 0.1, "D10_nr": 0.02, "Amplification_excess_10": 5.0},
            {"N": 2000, "ok": True, "D10_rec": 0.05, "D10_nr": 0.01, "Amplification_excess_10": 5.0},
        ]
    )
    phase = pd.DataFrame(
        [
            {
                "arm": "recursive",
                "alpha": 1.5,
                "mu": 0.0,
                "R_id": 1.5,
                "N": 100,
                "beta": 0.0,
                "P_collapse": 0.9,
                "median_H_T": 0.2,
            }
        ]
    )
    bias = pd.DataFrame(
        [
            {
                "alpha": 1.5,
                "mu": 0.0,
                "N": 100,
                "R_id": 1.5,
                "beta": 0.0,
                "directional_asymmetry": 0.0,
            },
            {
                "alpha": 1.5,
                "mu": 0.0,
                "N": 100,
                "R_id": 1.5,
                "beta": 0.05,
                "directional_asymmetry": 0.4,
            },
        ]
    )
    payload = evaluate_final_gates(
        growth=growth,
        alignment=alignment,
        law=law,
        vs_nr=vs,
        large_n=large_n,
        phase_summary=phase,
        bias_summary=bias,
    )
    assert payload["gates"]["G1_local_sign_transition"]["pass"]
    assert payload["layered_verdict"]["Universal_finite_time_collapse_threshold"] == "NOT CLAIMED"
    assert "KILL-E" not in json.dumps(payload)
    assert "legacy_KILL" not in json.dumps(payload)
