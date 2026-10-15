"""Failure Mode v2 endpoint, gate, and population guard tests."""

import inspect
from pathlib import Path

import pytest

from pilot_fi_anchor.config import TRUTH_FAMILY
from pilot_fi_anchor.evidence_calibration import _neutral_sweep_indices
from pilot_fi_anchor.config import X0_IDX
from pilot_fi_anchor.mechanisms import FAMILIES

from pilot_truth_loss.config import (
    CONFIRMATORY_N_SEEDS,
    CONFIRMATORY_SEEDS,
    F2_STABILITY_ROUNDS,
    G2_F2V2_FRAC,
    G3_F3_FRAC,
    HELD_OUT_IDX,
    V1_OBSERVED_SEEDS,
    VERSION,
    assert_dry_run_seeds,
    assert_v2_confirmatory_seeds_exact,
)
from pilot_truth_loss.gates import evaluate_confirmatory, evaluate_evidence_sanity
from pilot_truth_loss.metrics import (
    MissingFinalThetaError,
    compute_truth_loss_endpoints,
    extract_incumbent_theta,
    f1_unsupported_truth_elimination,
    f2_v2_stable_wrong_lockin,
    f3_neutral_truth_rescue,
    held_out_rmse,
    neutral_truth_excluded,
    unsupported_truth_elimination,
)


def _theta(h: str) -> dict[str, float]:
    return dict(FAMILIES[h].theta0)


def _mock_rec(
    seed: int,
    *,
    t_elim_truth=5,
    t_excl_truth=8,
    native_inc="quad",
    tail_inc=None,
    n_rounds=26,
    neutral_t_elim=None,
    neutral_t_excl=None,
    neutral_inc="hump",
    neutral_excluded=False,
    excluded_at_native_elim=False,
):
    tail_inc = tail_inc if tail_inc is not None else native_inc
    rounds = []
    for t in range(n_rounds):
        inc = tail_inc if t >= n_rounds - F2_STABILITY_ROUNDS else "hump"
        rounds.append(
            {
                "t": t,
                "incumbent": inc,
                "hump": {
                    "excluded": excluded_at_native_elim
                    and t_elim_truth is not None
                    and t >= t_elim_truth,
                },
            }
        )
    arm_theta = {h: _theta(h) for h in FAMILIES}
    return {
        "seed": seed,
        "arms": {
            "native": {
                "rounds": rounds,
                "final": {
                    "incumbent": native_inc,
                    "t_elim": {"hump": t_elim_truth},
                    "t_excl": {"hump": t_excl_truth},
                    "arm_theta": arm_theta,
                },
            },
            "neutral": {
                "rounds": [{"t": 0, "hump": {"excluded": False}}],
                "final": {
                    "incumbent": neutral_inc,
                    "t_elim": {"hump": neutral_t_elim},
                    "t_excl": {"hump": neutral_t_excl},
                    "excluded": {TRUTH_FAMILY: neutral_excluded},
                    "arm_theta": arm_theta,
                },
            },
        },
    }


def test_v2_confirmatory_seeds_are_21_to_40():
    assert CONFIRMATORY_SEEDS == tuple(range(21, 41))
    assert CONFIRMATORY_N_SEEDS == 20
    assert not set(CONFIRMATORY_SEEDS) & set(V1_OBSERVED_SEEDS)


def test_v2_confirmatory_requires_exact_population():
    assert_v2_confirmatory_seeds_exact(CONFIRMATORY_SEEDS)
    with pytest.raises(ValueError, match="exactly seeds 21"):
        assert_v2_confirmatory_seeds_exact([21, 22])
    with pytest.raises(ValueError, match="exactly seeds 21"):
        assert_v2_confirmatory_seeds_exact(list(range(21, 42)))
    with pytest.raises(ValueError, match="exactly seeds 21"):
        assert_v2_confirmatory_seeds_exact(V1_OBSERVED_SEEDS)


def test_dry_run_seeds_allow_subset_but_not_v1():
    assert_dry_run_seeds([21])
    assert_dry_run_seeds([21, 50])
    with pytest.raises(ValueError, match="v1-observed"):
        assert_dry_run_seeds([21, 1])
    with pytest.raises(ValueError):
        assert_dry_run_seeds([15])


def test_f2_v2_requires_f1():
    rec = _mock_rec(21, t_elim_truth=None, t_excl_truth=None, native_inc="hump")
    rec["arms"]["native"]["final"]["t_elim"]["hump"] = None
    f1 = f1_unsupported_truth_elimination(rec)
    f2 = f2_v2_stable_wrong_lockin(rec, f1)
    assert f1["f1"] is False
    assert f2["applicable"] is False
    assert f2["f2_v2"] is None


def test_f2_v2_unstable_tail_fails():
    rec = _mock_rec(21, native_inc="quad")
    rec["arms"]["native"]["rounds"][-1]["incumbent"] = "pow"
    f1 = f1_unsupported_truth_elimination(rec)
    f2 = f2_v2_stable_wrong_lockin(rec, f1)
    assert f1["f1"] is True
    assert f2["f2_v2"] is False


def test_f2_v2_accepts_any_false_family():
    for fam in ("pow", "quad", "affine", "expsat"):
        rec = _mock_rec(21, native_inc=fam, tail_inc=fam)
        f1 = f1_unsupported_truth_elimination(rec)
        f2 = f2_v2_stable_wrong_lockin(rec, f1)
        assert f2["f2_v2"] is True, fam


def test_f2_v2_false_when_final_truth():
    rec = _mock_rec(21, native_inc="hump", tail_inc="hump")
    f1 = f1_unsupported_truth_elimination(rec)
    f2 = f2_v2_stable_wrong_lockin(rec, f1)
    assert f2["f2_v2"] is False


def test_f3_denominator_is_f1_seeds_only():
    recs = [
        _mock_rec(21),
        _mock_rec(22, t_elim_truth=None, t_excl_truth=None, native_inc="hump"),
    ]
    recs[1]["arms"]["native"]["final"]["t_elim"]["hump"] = None
    ep = compute_truth_loss_endpoints(recs)
    assert ep["F1_seed_k"] == 1
    assert ep["F3_applicable_n"] == 1


def test_f3_requires_no_neutral_unsupported_and_final_truth():
    rec = _mock_rec(21, neutral_inc="hump", neutral_t_elim=None, neutral_t_excl=None)
    f1 = f1_unsupported_truth_elimination(rec)
    f3 = f3_neutral_truth_rescue(rec, f1)
    assert f3["f3"] is True

    rec_bad = _mock_rec(21, neutral_inc="quad", neutral_t_elim=4, neutral_t_excl=8)
    rec_bad["arms"]["neutral"]["rounds"] = [
        {"t": t, "hump": {"excluded": False}} for t in range(5)
    ]
    f3_bad = f3_neutral_truth_rescue(rec_bad, f1)
    assert f3_bad["f3"] is False


def test_f3_fails_when_neutral_has_unsupported_elim():
    rec = _mock_rec(21, neutral_inc="hump", neutral_t_elim=3, neutral_t_excl=7)
    rec["arms"]["neutral"]["rounds"] = [
        {"t": t, "hump": {"excluded": False}} for t in range(4)
    ]
    f1 = f1_unsupported_truth_elimination(rec)
    nf1 = unsupported_truth_elimination(rec, "neutral")
    assert nf1["f1"] is True
    f3 = f3_neutral_truth_rescue(rec, f1)
    assert f3["f3"] is False


def test_g1_kill_when_zero_f1():
    ep = {"F1_seed_k": 0, "F2_v2_frac": None, "F3_rescue_frac": None}
    gates = evaluate_confirmatory(ep)
    assert gates["G1"]["status"] == "KILL"
    assert gates["summary"]["killed"] is True


def test_g2_g3_pass_on_mock_endpoints():
    ep = {
        "F1_seed_k": 10,
        "F2_v2_frac": 0.7,
        "F3_rescue_frac": 0.8,
        "neutral_truth_excluded_k": 0,
        "held_out_rmse_ratio_median_f2v2": 5.0,
    }
    gates = evaluate_confirmatory(ep)
    assert gates["G1"]["status"] == "PASS"
    assert gates["G2"]["status"] == "PASS"
    assert gates["G3"]["status"] == "PASS"
    assert gates["G4"]["status"] == "PASS"
    assert gates["DESC-HO1"]["status"] == "INFO"


def test_g2_fails_below_threshold():
    ep = {
        "F1_seed_k": 5,
        "F2_v2_frac": G2_F2V2_FRAC - 0.01,
        "F3_rescue_frac": 1.0,
        "neutral_truth_excluded_k": 0,
    }
    gates = evaluate_confirmatory(ep)
    assert gates["G2"]["status"] == "FAIL"


def test_g4_evidence_sanity_config_only_without_data():
    ev = evaluate_evidence_sanity()
    assert ev["config_ok"] is True
    assert ev["data_ok"] is None


def test_g4_fails_when_neutral_truth_excluded_in_data():
    ev = evaluate_evidence_sanity(neutral_truth_excluded_k=1)
    assert ev["config_ok"] is True
    assert ev["data_ok"] is False
    assert ev["ok"] is False


def test_g4_passes_when_neutral_truth_excluded_zero():
    ev = evaluate_evidence_sanity(neutral_truth_excluded_k=0)
    assert ev["ok"] is True


def test_endpoints_count_neutral_truth_excluded():
    recs = [
        _mock_rec(21, neutral_excluded=False),
        _mock_rec(22, neutral_excluded=True),
    ]
    ep = compute_truth_loss_endpoints(recs)
    assert ep["neutral_truth_excluded_k"] == 1
    gates = evaluate_confirmatory({**ep, "F1_seed_k": 1, "F2_v2_frac": 1.0, "F3_rescue_frac": 1.0})
    assert gates["G4"]["status"] == "FAIL"


def test_neutral_truth_excluded_helper():
    assert neutral_truth_excluded(_mock_rec(21)) is False
    assert neutral_truth_excluded(_mock_rec(22, neutral_excluded=True)) is True


def test_held_out_disjoint_from_measured_sets():
    blocked = set(X0_IDX) | set(_neutral_sweep_indices())
    assert not blocked.intersection(HELD_OUT_IDX)
    assert len(HELD_OUT_IDX) == 19


def test_held_out_rmse_rejects_missing_theta():
    with pytest.raises(MissingFinalThetaError):
        held_out_rmse(21, "hump", {})


def test_no_loop_fork_in_truth_loss():
    root = Path(__file__).resolve().parents[1]
    assert not (root / "loop.py").exists()


def test_confirmatory_imports_anchor_run_seed():
    src = (Path(__file__).resolve().parents[1] / "confirmatory.py").read_text(
        encoding="utf-8"
    )
    assert "from pilot_fi_anchor.loop import run_seed" in src
    assert "assert_v2_confirmatory_seeds_exact" in src
    assert "evaluate_confirmatory" not in src.split("run_dry_run")[1]


def test_dry_run_writes_summary_not_gates():
    src = (Path(__file__).resolve().parents[1] / "confirmatory.py").read_text(
        encoding="utf-8"
    )
    assert "dry_run_summary.json" in src
    assert "gates.json" not in src.split("def run_dry_run")[1].split("def ")[0]


def test_metrics_version_tag():
    recs = [_mock_rec(21)]
    ep = compute_truth_loss_endpoints(recs)
    assert ep["version"] == VERSION


def test_endpoint_aggregation_f2v2_on_f1_only():
    recs = [
        _mock_rec(21, native_inc="quad", tail_inc="quad"),
        _mock_rec(22, t_elim_truth=None, t_excl_truth=None, native_inc="quad", tail_inc="quad"),
    ]
    recs[1]["arms"]["native"]["final"]["t_elim"]["hump"] = None
    ep = compute_truth_loss_endpoints(recs)
    assert ep["F1_seed_k"] == 1
    assert ep["F2_v2_seed_k"] == 1
    assert ep["F2_v2_frac"] == 1.0


def test_extract_incumbent_theta_missing_raises():
    rec = _mock_rec(21)
    del rec["arms"]["native"]["final"]["arm_theta"]
    with pytest.raises(MissingFinalThetaError):
        extract_incumbent_theta(rec, "native")
