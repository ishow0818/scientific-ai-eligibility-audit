"""Guard tests for Phase-2 / v2 implementation vs design."""

import inspect
from pathlib import Path

import pytest

from pilot_fi_anchor.config import TRUTH_FAMILY
from pilot_fi_anchor.evidence_calibration import _neutral_sweep_indices
from pilot_fi_anchor.config import X0_IDX
from pilot_fi_anchor.metrics import _native_event_row

from pilot_truth_loss.config import (
    COMPETITOR_FAMILY,
    CONFIRMATORY_SEEDS,
    F2_STABILITY_ROUNDS,
    G2_F2V2_FRAC,
    G3_F3_FRAC,
    HELD_OUT_IDX,
    V1_OBSERVED_SEEDS,
)
from pilot_truth_loss.metrics import (
    compute_truth_loss_endpoints,
    f1_unsupported_truth_elimination,
    f2_v2_stable_wrong_lockin,
    f3_neutral_truth_rescue,
)
from pilot_truth_loss.pair_calibration import _extended_obs


def _mock_rec(seed, *, t_elim=3, t_excl=7, native_inc="quad", excluded_at_elim=False):
    from pilot_fi_anchor.mechanisms import FAMILIES

    n_rounds = 26
    rounds = []
    for t in range(n_rounds):
        inc = native_inc if t >= n_rounds - F2_STABILITY_ROUNDS else "hump"
        rounds.append(
            {
                "t": t,
                "incumbent": inc,
                "hump": {"excluded": excluded_at_elim and t_elim is not None and t >= t_elim},
            }
        )
    arm_theta = {h: dict(FAMILIES[h].theta0) for h in FAMILIES}
    return {
        "seed": seed,
        "arms": {
            "native": {
                "rounds": rounds,
                "final": {
                    "incumbent": native_inc,
                    "t_elim": {"hump": t_elim},
                    "t_excl": {"hump": t_excl},
                    "arm_theta": arm_theta,
                },
            },
            "neutral": {
                "rounds": [{"t": 0, "hump": {"excluded": False}}],
                "final": {
                    "incumbent": TRUTH_FAMILY,
                    "t_elim": {"hump": None},
                    "t_excl": {"hump": None},
                    "arm_theta": arm_theta,
                },
            },
        },
    }


def test_f1_matches_anchor_e1_pattern_for_truth():
    rec = _mock_rec(21, t_elim=3, t_excl=7, excluded_at_elim=False)
    f1 = f1_unsupported_truth_elimination(rec)
    anchor = _native_event_row(rec, TRUTH_FAMILY, 3)
    assert f1["compat_at_elim"] == anchor["compat_at_elim"]
    assert f1["f1"] == anchor["unsupported"]


def test_f1_false_when_excluded_at_elim():
    rec = _mock_rec(21, t_elim=3, t_excl=7, excluded_at_elim=True)
    assert f1_unsupported_truth_elimination(rec)["f1"] is False


def test_f2_v2_any_false_family_not_pow_only():
    rec_quad = _mock_rec(21, native_inc="quad")
    rec_pow = _mock_rec(22, native_inc="pow")
    rec_affine = _mock_rec(23, native_inc="affine")
    f1q = f1_unsupported_truth_elimination(rec_quad)
    f1p = f1_unsupported_truth_elimination(rec_pow)
    f1a = f1_unsupported_truth_elimination(rec_affine)
    assert f2_v2_stable_wrong_lockin(rec_quad, f1q)["f2_v2"] is True
    assert f2_v2_stable_wrong_lockin(rec_pow, f1p)["f2_v2"] is True
    assert f2_v2_stable_wrong_lockin(rec_affine, f1a)["f2_v2"] is True
    assert COMPETITOR_FAMILY == "pow"


def test_f3_denominator_is_f1_seeds_only():
    recs = [
        _mock_rec(21, t_elim=3, t_excl=7),
        _mock_rec(22, t_elim=None, t_excl=None, native_inc="hump"),
    ]
    recs[1]["arms"]["native"]["final"]["t_elim"]["hump"] = None
    ep = compute_truth_loss_endpoints(recs)
    assert ep["F1_seed_k"] == 1
    assert ep["F3_applicable_n"] == 1


def test_f3_not_applicable_without_f1():
    rec = _mock_rec(21, t_elim=None, t_excl=None)
    rec["arms"]["native"]["final"]["t_elim"]["hump"] = None
    f1 = f1_unsupported_truth_elimination(rec)
    f3 = f3_neutral_truth_rescue(rec, f1)
    assert f3["applicable"] is False
    assert f3["f3"] is None


def test_held_out_not_in_extended_calibration_obs():
    xs_idx = set(X0_IDX) | set(_neutral_sweep_indices())
    assert not set(HELD_OUT_IDX) & xs_idx


def test_extended_obs_excludes_held_out():
    _, ys = _extended_obs(1)
    assert len(HELD_OUT_IDX) == 19
    assert not set(HELD_OUT_IDX) & (set(X0_IDX) | set(_neutral_sweep_indices()))


def test_v2_gate_thresholds_are_module_constants():
    assert G2_F2V2_FRAC == 0.60
    assert G3_F3_FRAC == 0.60
    src = inspect.getsource(__import__("pilot_truth_loss.gates", fromlist=["evaluate_confirmatory"]))
    assert "G2_F2V2_FRAC" in src
    assert "G1" in src


def test_no_loop_module_in_truth_loss_package():
    root = Path(__file__).resolve().parents[1]
    assert not (root / "loop.py").exists()
    assert not (root / "Arm.py").exists()


def test_metrics_does_not_call_pair_selection():
    src = inspect.getsource(__import__("pilot_truth_loss.metrics", fromlist=[""]))
    assert "select_competitor" not in src
    assert "run_pair_calibration" not in src


def test_confirmatory_imports_anchor_run_seed_only():
    src = (Path(__file__).resolve().parents[1] / "confirmatory.py").read_text(
        encoding="utf-8"
    )
    assert "from pilot_fi_anchor.loop import run_seed" in src
    assert "select_competitor_by_rule" not in src
    assert CONFIRMATORY_SEEDS[0] == 21
    assert V1_OBSERVED_SEEDS[-1] == 20


def test_main_wires_confirmatory_seeds():
    src = (Path(__file__).resolve().parents[1] / "__main__.py").read_text(encoding="utf-8")
    assert "--seeds" in src
    assert "run_confirmatory" in src
    assert "run_dry_run" in src
    assert "assert_v2_confirmatory_seeds_exact" in src
    assert "--dry-run" in src


def test_held_out_rmse_rejects_missing_theta():
    from pilot_truth_loss.metrics import MissingFinalThetaError, held_out_rmse

    with pytest.raises(MissingFinalThetaError):
        held_out_rmse(21, "hump", {})
