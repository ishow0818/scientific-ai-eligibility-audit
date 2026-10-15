from pilot_fi_anchor.gates import evaluate


def _endpoints(**overrides):
    base = {
        "neutral_converged_k": 19,
        "neutral_converged_frac": 0.95,
        "neutral_truth_excluded_count": 0,
        "native_truth_excluded_count": 0,
        "round0_all_compat_k": 19,
        "round0_all_compat_frac": 0.95,
        "n_seeds": 20,
        "neutral_max_abs_gain": 0.0,
        "runtime_s": 100.0,
        "E1_seed_k": 10,
        "E1_seed_n": 20,
        "E3_rescue_frac": 0.75,
        "E2_median_finite_dFI": 4.0,
        "E2_frac_dFI_ge1": 0.7,
        "native_final_truth_frac": 0.5,
    }
    base.update(overrides)
    return base


def test_pass_gates_use_seed_e1_and_dfi():
    gates = evaluate(_endpoints(), {"ok": True, "detail": []})
    assert gates["PASS-A1"]["status"] == "PASS"
    assert gates["PASS-A2"]["status"] == "PASS"
    assert gates["PASS-A3"]["status"] == "PASS"
    assert gates["DESC-A4"]["status"] == "INFO"
    assert "PASS-A4" not in gates
    assert gates["summary"]["pass_all_pass"] is True


def test_a1_ambiguous_band():
    gates = evaluate(_endpoints(E1_seed_k=5), {"ok": True, "detail": []})
    assert gates["PASS-A1"]["status"] == "AMBIGUOUS"


def test_a3_uses_frac_dfi_not_dcross():
    gates = evaluate(
        _endpoints(E2_frac_dFI_ge1=None, E2_median_finite_dFI=99.0,
                   E2_median_dCross=99.0, E2_frac_dCross_ge1=1.0),
        {"ok": True, "detail": []},
    )
    assert gates["PASS-A3"]["status"] == "FAIL"


def test_a3_median_finite_not_required():
    gates = evaluate(
        _endpoints(E2_median_finite_dFI=None, E2_frac_dFI_ge1=0.65),
        {"ok": True, "detail": []},
    )
    assert gates["PASS-A3"]["status"] == "PASS"


def test_kill_b1_b3_fixed_20_seed_count_not_fraction():
    gates = evaluate(
        _endpoints(neutral_converged_k=5, round0_all_compat_k=5, n_seeds=5),
        {"ok": True, "detail": []},
    )
    assert gates["KILL-B1"]["status"] == "FAIL"
    assert gates["KILL-B3"]["status"] == "FAIL"
    assert gates["KILL-B1"]["threshold"] == ">= 18/20"

    gates_ok = evaluate(
        _endpoints(neutral_converged_k=18, round0_all_compat_k=18),
        {"ok": True, "detail": []},
    )
    assert gates_ok["KILL-B1"]["status"] == "PASS"
    assert gates_ok["KILL-B3"]["status"] == "PASS"
