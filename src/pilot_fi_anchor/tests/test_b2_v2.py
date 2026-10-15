"""B2-v2: sequential Bonferroni fix — targeted regression tests."""

import inspect

import pytest

from pilot_fi_anchor.config import ALPHA_EV, R, FAMILY_ORDER
from pilot_fi_anchor.evidence_calibration import (
    ALPHA_EV_LEGACY,
    B2_LOOP_CHECK_SEEDS,
    run_loop_b2_truth_check,
    run_sequential_calibration,
    simulate_neutral_sequential,
)
from pilot_fi_anchor.loop import Arm, run_seed


def test_b2_v2_alpha_is_sequential_bonferroni():
    assert ALPHA_EV == pytest.approx(0.05 / (len(FAMILY_ORDER) * R))
    assert ALPHA_EV < ALPHA_EV_LEGACY


def test_loop_uses_shared_evidence_crit():
    src = inspect.getsource(Arm._update_evidence)
    assert "evidence_crit" in src
    assert "chi2.ppf" not in src


def test_legacy_sequential_reproduces_v111_neutral_failure():
    seq = run_sequential_calibration(seeds=(20,))
    assert seq["legacy_truth_excluded_k"] == 1
    assert seq["legacy_excluded_seeds"] == [20]
    assert seq["current_truth_excluded_k"] == 0


@pytest.mark.parametrize("seed", (1, 20))
def test_sequential_sim_matches_neutral_loop(seed):
    """Normal path (seed 1) and legacy-failure path (seed 20) vs formal Neutral loop."""
    sim = simulate_neutral_sequential(seed, ALPHA_EV)
    rec = run_seed(seed, do_perturb=False)
    loop_excl = rec["arms"]["neutral"]["final"]["excluded"]["hump"]
    assert sim["excluded"] == loop_excl
    assert sim["t_excl"] == rec["arms"]["neutral"]["final"]["t_excl"]["hump"]


def test_v111_seed3_native_recovered_under_b2_v2():
    """Seed 3 was native-only legacy failure; sequential fix must clear it."""
    rec = run_seed(3, do_perturb=False)
    assert not rec["arms"]["native"]["final"]["excluded"]["hump"]
    assert not rec["arms"]["neutral"]["final"]["excluded"]["hump"]


def test_v111_seed20_neutral_false_exclusion_fixed_native_may_stay_excluded():
    """Seed 20 under B2-v2: Neutral spurious truth exclusion is fixed.

    KILL-B2 pre-registers native truth evidence-excluded in ≤1/20 seeds;
    this test does not require Native 'recovery' — only Neutral fix + B2 budget.
    """
    rec = run_seed(20, do_perturb=False)
    assert not rec["arms"]["neutral"]["final"]["excluded"]["hump"]
    assert rec["arms"]["native"]["final"]["excluded"]["hump"]


def test_loop_b2_check_subset_passes():
    chk = run_loop_b2_truth_check(B2_LOOP_CHECK_SEEDS)
    assert chk["b2_ok"]
    assert chk["neutral_truth_excluded_k"] == 0
    assert chk["native_truth_excluded_k"] <= 1


def test_no_seed_specific_constants_in_config():
    from pilot_fi_anchor import config

    src = inspect.getsource(config)
    for token in ("seed_3", "seed_20", "SEED_3", "SEED_20"):
        assert token not in src
