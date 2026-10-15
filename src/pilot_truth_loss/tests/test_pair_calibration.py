from pilot_fi_anchor.config import FALSE_FAMILIES

from pilot_truth_loss.config import COMPETITOR_FAMILY, PAIR_CALIBRATION_SEEDS
from pilot_truth_loss.pair_calibration import (
    evaluate_competitor,
    run_pair_calibration,
    select_competitor_by_rule,
    verify_sequential_truth_safety,
)


def test_all_false_families_evaluated():
    sel = select_competitor_by_rule(seeds=(1, 2, 3))
    assert set(sel["candidates"]) == set(FALSE_FAMILIES)


def test_pow_wins_by_min_gap_rule():
    sel = select_competitor_by_rule(seeds=PAIR_CALIBRATION_SEEDS)
    assert sel["chosen"] == "pow"
    gaps = {
        h: ev["initial_gap_median"]
        for h, ev in sel["candidates"].items()
        if ev["structural_ok"]
    }
    assert gaps["pow"] == min(gaps.values())


def test_pow_passes_structural_gates():
    ev = evaluate_competitor("pow", seeds=PAIR_CALIBRATION_SEEDS)
    assert ev["passes_pc1"]
    assert ev["passes_pc3"]
    assert ev["passes_pc4"]
    assert ev["passes_pc5"]
    assert ev["passes_pc6"]
    assert ev["initial_gap_median"] < 0.15


def test_sequential_truth_safety():
    seq = verify_sequential_truth_safety(seeds=(1, 2, 3, 20))
    assert seq["ok"]
    assert seq["truth_excluded_k"] == 0


def test_full_pair_calibration_ready():
    cal = run_pair_calibration()
    assert cal["ok"]
    assert cal["ready"]
    assert cal["competitor_family"] == COMPETITOR_FAMILY
    assert cal["selection"]["chosen"] == "pow"
    assert cal["sequential_truth_safety"]["ok"]
    assert cal["held_out"]["ok"]
