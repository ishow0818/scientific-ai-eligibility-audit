import numpy as np

from pilot_fi_anchor.fitting import fit, loglik
from pilot_fi_anchor.mechanisms import TRUTH, TRUTH_THETA


def test_recover_truth_from_noiseless_data():
    x = np.linspace(0.2, 10.0, 200)
    y = TRUTH.fn(x, **TRUTH_THETA)
    z = fit(TRUTH, x, y, rng=np.random.default_rng(0))
    th = TRUTH.from_fit(z)
    for k in TRUTH.params:
        assert abs(th[k] - TRUTH_THETA[k]) < 1e-3


def test_loglik_perfect_fit_matches_noise_pdf():
    # residual = 0 -> loglik = -0.5 * log(2 pi sigma^2)
    import math

    from pilot_fi_anchor.config import SIGMA

    x, y = 3.0, float(TRUTH.fn(np.array([3.0]), **TRUTH_THETA)[0])
    expect = -0.5 * math.log(2 * math.pi * SIGMA * SIGMA)
    assert abs(loglik(TRUTH, TRUTH_THETA, x, y) - expect) < 1e-12
