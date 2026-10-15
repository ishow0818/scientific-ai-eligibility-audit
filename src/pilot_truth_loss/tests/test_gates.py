from pilot_truth_loss.gates import evaluate_calibration, evaluate_confirmatory
from pilot_truth_loss.pair_calibration import run_pair_calibration


def test_calibration_gates_pass():
    cal = run_pair_calibration()
    gates = evaluate_calibration(cal)
    assert gates["summary"]["calibration_all_pass"]
    assert gates["CAL-G1"]["status"] == "PASS"
    assert gates["CAL-G2"]["status"] == "PASS"
    assert gates["CAL-G4"]["status"] == "PASS"


def test_confirmatory_v2_gate_schema():
    endpoints = {
        "F1_seed_k": 10,
        "F2_v2_frac": 0.7,
        "F3_rescue_frac": 0.8,
        "neutral_truth_excluded_k": 0,
        "held_out_rmse_ratio_median_f2v2": 5.0,
    }
    gates = evaluate_confirmatory(endpoints)
    assert gates["G1"]["status"] == "PASS"
    assert gates["G2"]["status"] == "PASS"
    assert gates["G3"]["status"] == "PASS"
    assert gates["G4"]["status"] == "PASS"
    assert gates["DESC-HO1"]["status"] == "INFO"
