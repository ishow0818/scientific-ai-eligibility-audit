import numpy as np

from pilot_fi_anchor.mechanisms import FAMILIES, TRUTH, TRUTH_THETA


def test_truth_probe_values():
    x = np.array([4.5, 10.0])
    y = TRUTH.fn(x, **TRUTH_THETA)
    assert abs(y[0] - 8.0) < 1e-9
    assert abs(y[1] - 8.0 * np.exp(-30.25 / 12.5)) < 1e-9


def test_fit_space_roundtrip():
    for mech in FAMILIES.values():
        theta = mech.from_fit(mech.to_fit(mech.theta0))
        for k in mech.params:
            assert abs(theta[k] - mech.theta0[k]) < 1e-9


def test_bounds_contain_theta0():
    for mech in FAMILIES.values():
        lo, hi = mech.bounds_fit()
        z0 = mech.to_fit(mech.theta0)
        assert np.all(z0 > lo) and np.all(z0 < hi)


def test_truth_is_in_family_set():
    assert "hump" in FAMILIES
    assert TRUTH.name == "hump"
