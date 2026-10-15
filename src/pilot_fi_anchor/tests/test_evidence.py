import numpy as np
from scipy.stats import chi2

from pilot_fi_anchor.config import ALPHA_EV, R, SIGMA
from pilot_fi_anchor.evidence_calibration import (
    check_extreme_x_pathology,
    evidence_crit,
    run_sequential_calibration,
)


def test_chi2_criterion_arithmetic():
    n, p, rss = 30, 2, 12.0
    stat = rss / (SIGMA * SIGMA)
    crit = evidence_crit(n, p)
    assert abs(stat - 48.0) < 1e-12
    assert crit > float(chi2.ppf(0.99, 28))
    assert not (stat > crit)


def test_alpha_sequential_bonferroni():
    assert abs(ALPHA_EV - 0.05 / (5 * R)) < 1e-15


def test_sequential_calibration_neutral_no_truth_exclusion():
    seq = run_sequential_calibration(seeds=tuple(range(1, 6)))
    assert seq["current_truth_excluded_k"] == 0


def test_extreme_x_no_fitting_pathology():
    """B2 diagnostic: hump must not collapse at high-x under σ=0.5."""
    p = check_extreme_x_pathology(20)
    assert not p["pathology"]
    assert p["min_hump_pred"] > 0.05
    assert not p["excluded_current"]
    assert not p["excluded_legacy"]
