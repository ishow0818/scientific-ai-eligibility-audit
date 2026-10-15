from pilot_fi_anchor.config import DELTA_PERTS, FAMILY_ORDER
from pilot_fi_anchor.loop import Arm, run_seed
from pilot_fi_anchor.perturbation import perturbation_targets, run_perturb_pair
from pilot_fi_anchor.world import World


def test_neutral_gain_is_exactly_zero():
    rec = run_seed(5, do_perturb=True, rounds=6)
    gains = [p["g"] for p in rec["perturb"] if p["arm"] == "neutral"]
    assert gains, "no neutral perturbation records produced"
    assert all(abs(g) < 1e-12 for g in gains)


def test_native_gains_finite_nonnegative():
    rec = run_seed(6, do_perturb=True, rounds=6)
    gains = [p["g"] for p in rec["perturb"] if p["arm"] == "native"]
    assert gains, "no native perturbation records produced"
    for g in gains:
        assert g >= 0.0
        assert g == g  # not NaN


def test_crn_delta_zero_bit_identical():
    world = World(11)
    arm = Arm(11, "native", world)
    arm.round0()
    from pilot_fi_anchor.rng import alloc_rng

    arm.step(1, rng=alloc_rng(11, "native", 1))
    targets = perturbation_targets(arm)
    assert targets
    h = targets[0]
    entry = run_perturb_pair(arm, h, 0.0, 11, 1)
    for fam in FAMILY_ORDER:
        assert entry["w_base_next"][fam] == entry["w_pert_next"][fam]
    assert entry["g"] == 0.0


def test_crn_same_random_draw_delta_nonzero():
    world = World(12)
    arm = Arm(12, "native", world)
    arm.round0()
    from pilot_fi_anchor.rng import alloc_rng

    arm.step(1, rng=alloc_rng(12, "native", 1))
    targets = perturbation_targets(arm)
    assert targets
    h = targets[0]
    delta = 0.05
    entry = run_perturb_pair(arm, h, delta, 12, 1)
    assert any(
        abs(entry["w_pert"][fam] - entry["w_base"][fam]) > 1e-12
        for fam in FAMILY_ORDER
    )
    entry2 = run_perturb_pair(arm, h, delta, 12, 1)
    for fam in FAMILY_ORDER:
        assert entry["w_base_next"][fam] == entry2["w_base_next"][fam]
        assert entry["w_pert_next"][fam] == entry2["w_pert_next"][fam]
    assert entry["base_new_sites"] == entry2["base_new_sites"]
    assert entry["pert_new_sites"] == entry2["pert_new_sites"]


def test_crn_neutral_branches_identical_sites():
    world = World(13)
    arm = Arm(13, "neutral", world)
    arm.round0()
    from pilot_fi_anchor.rng import alloc_rng

    arm.step(1, rng=alloc_rng(13, "neutral", 1))
    targets = perturbation_targets(arm)
    assert targets
    entry = run_perturb_pair(arm, targets[0], 0.05, 13, 1)
    assert entry["base_new_sites"] == entry["pert_new_sites"]
    assert entry["g"] == 0.0


def test_multiple_delta_magnitudes_recorded():
    rec = run_seed(8, do_perturb=True, rounds=4)
    deltas = {p["delta"] for p in rec["perturb"]}
    assert deltas == set(DELTA_PERTS)
