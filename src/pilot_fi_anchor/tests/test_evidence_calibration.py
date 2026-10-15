from pilot_fi_anchor.config import ALPHA_EV
from pilot_fi_anchor.evidence_calibration import run_calibration, run_calibration_batch


def test_evidence_calibration_sanity():
    result = run_calibration(seed=1)
    assert result["hump_compatible_initial"]
    assert result["hump_compatible_late"]
    assert result["all_false_excluded_late"]
    assert result["scrambled_any_excluded"]
    assert result["ok"]


def test_evidence_calibration_batch():
    batch = run_calibration_batch(seeds=(1, 2, 3), loop_check_seeds=(3,))
    assert batch["n_seeds"] == 3
    assert batch["n_hump_initial_ok"] == 3
    assert batch["n_all_false_excluded_late"] == 3
    assert batch["sequential"]["current_truth_excluded_k"] == 0
    assert batch["alpha_ev"] == ALPHA_EV
    assert batch["loop_b2_check"]["b2_ok"]
    assert not batch["extreme_x_pathology"]["pathology"]
    assert batch["ok"]
