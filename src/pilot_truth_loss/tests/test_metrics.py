import pytest

from pilot_fi_anchor.mechanisms import FAMILIES

from pilot_truth_loss.config import F2_STABILITY_ROUNDS
from pilot_truth_loss.metrics import (
    MissingFinalThetaError,
    compute_truth_loss_endpoints,
    extract_incumbent_theta,
    f1_unsupported_truth_elimination,
    f2_v2_stable_wrong_lockin,
    f3_neutral_truth_rescue,
    held_out_rmse,
    ho1_seed_metrics,
)


def _theta(h: str) -> dict[str, float]:
    return dict(FAMILIES[h].theta0)


def _mock_rec(seed: int, *, t_elim_truth=5, t_excl_truth=8, native_inc="quad"):
    n_rounds = 26
    rounds = []
    for t in range(n_rounds):
        inc = native_inc if t >= n_rounds - F2_STABILITY_ROUNDS else "hump"
        rounds.append({"t": t, "incumbent": inc, "hump": {"excluded": False}})
    return {
        "seed": seed,
        "arms": {
            "native": {
                "rounds": rounds,
                "final": {
                    "incumbent": native_inc,
                    "t_elim": {"hump": t_elim_truth},
                    "t_excl": {"hump": t_excl_truth},
                    "arm_theta": {h: _theta(h) for h in FAMILIES},
                },
            },
            "neutral": {
                "rounds": [{"t": 0, "hump": {"excluded": False}}],
                "final": {
                    "incumbent": "hump",
                    "t_elim": {"hump": None},
                    "t_excl": {"hump": None},
                    "excluded": {"hump": False},
                    "arm_theta": {h: _theta(h) for h in FAMILIES},
                },
            },
        },
    }


def test_f1_detects_unsupported_truth_elimination():
    rec = _mock_rec(21)
    row = f1_unsupported_truth_elimination(rec)
    assert row["f1"] is True
    assert row["delta_t"] == 3


def test_f2_v2_stable_wrong_lockin():
    rec = _mock_rec(21, native_inc="quad")
    f1 = f1_unsupported_truth_elimination(rec)
    assert f2_v2_stable_wrong_lockin(rec, f1)["f2_v2"] is True


def test_f3_rescue_on_f1():
    rec = _mock_rec(21)
    f1 = f1_unsupported_truth_elimination(rec)
    f3 = f3_neutral_truth_rescue(rec, f1)
    assert f3["f3"] is True


def test_held_out_rmse_requires_fitted_theta():
    with pytest.raises(MissingFinalThetaError):
        held_out_rmse(21, "hump", {})


def test_held_out_rmse_no_theta0_fallback():
    theta = _theta("hump")
    rmse = held_out_rmse(21, "hump", theta)
    assert rmse >= 0.0


def test_extract_incumbent_theta_missing_raises():
    rec = _mock_rec(21)
    del rec["arms"]["native"]["final"]["arm_theta"]
    with pytest.raises(MissingFinalThetaError):
        extract_incumbent_theta(rec, "native")


def test_ho1_uses_fitted_theta():
    rec = _mock_rec(21)
    ho = ho1_seed_metrics(rec)
    assert ho["native_ho_rmse"] >= 0.0
    assert ho["neutral_ho_rmse"] >= 0.0
    assert ho["ho_rmse_ratio"] is not None


def test_endpoint_aggregation_includes_ho1():
    recs = [_mock_rec(i) for i in range(21, 24)]
    ep = compute_truth_loss_endpoints(recs)
    assert ep["F1_seed_k"] == 3
    assert ep["F2_v2_seed_k"] == 3
    assert len(ep["HO1_per_seed"]) == 3
