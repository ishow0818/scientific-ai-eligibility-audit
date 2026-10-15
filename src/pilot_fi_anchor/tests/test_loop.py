import json

from pilot_fi_anchor.config import FAMILY_ORDER
from pilot_fi_anchor.loop import Arm, run_seed
from pilot_fi_anchor.recorder import _builtin
from pilot_fi_anchor.world import World


def test_determinism():
    a = _builtin(run_seed(1, do_perturb=False, rounds=5))
    b = _builtin(run_seed(1, do_perturb=False, rounds=5))
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_no_revisits():
    rec = run_seed(2, do_perturb=False, rounds=5)
    for kind in ("native", "neutral"):
        idxs = [s["idx"] for s in rec["arms"][kind]["sites"]]
        assert len(idxs) == len(set(idxs))


def test_support_sums_to_one():
    rec = run_seed(3, do_perturb=False, rounds=5)
    for kind in ("native", "neutral"):
        for row in rec["arms"][kind]["rounds"]:
            s = sum(row[h]["w_all"] for h in FAMILY_ORDER)
            assert abs(s - 1.0) < 1e-9


def test_public_evidence_both_arms():
    """Acquired measurements must enter every hypothesis stream in both arms."""
    rec = run_seed(4, do_perturb=False, rounds=5)
    for kind in ("native", "neutral"):
        rows = rec["arms"][kind]["rounds"]
        n_meas = rows[-1]["n_arm"]
        for h in FAMILY_ORDER:
            assert rows[-1][h]["stream_n"] == n_meas


def test_native_credit_is_provenance_only():
    """Native records proposer credit but does not gate stream access."""
    rec = run_seed(4, do_perturb=False, rounds=5)
    native_sites = rec["arms"]["native"]["sites"]
    t_pos = [s for s in native_sites if s["t"] > 0]
    assert t_pos, "expected post-initial measurements"
    credits = {s["credit"] for s in t_pos}
    assert credits != {"PUBLIC"}, "native should record proposer provenance"
    assert credits <= set(FAMILY_ORDER)
    rows = rec["arms"]["native"]["rounds"]
    n_meas = rows[-1]["n_arm"]
    for h in FAMILY_ORDER:
        assert rows[-1][h]["stream_n"] == n_meas


def test_allocation_only_structural_difference():
    """Within each arm, all families share identical stream sizes (PUBLIC)."""
    rec = run_seed(7, do_perturb=False, rounds=6)
    for kind in ("native", "neutral"):
        for row in rec["arms"][kind]["rounds"]:
            sizes = {row[h]["stream_n"] for h in FAMILY_ORDER}
            assert len(sizes) == 1


def test_round0_identical_across_arms():
    rec = run_seed(5, do_perturb=False, rounds=5)
    n0 = rec["arms"]["native"]["rounds"][0]
    u0 = rec["arms"]["neutral"]["rounds"][0]
    assert n0["n_arm"] == u0["n_arm"]
    for h in FAMILY_ORDER:
        assert n0[h]["S"] == u0[h]["S"]
        assert n0[h]["w_all"] == u0[h]["w_all"]


def test_credit_does_not_change_ingest():
    world = World(99)
    native = Arm(99, "native", world)
    native.round0()
    native._ingest(1, [("affine", 100), ("pow", 101)])
    sizes = {h: len(native.streams[h]) for h in FAMILY_ORDER}
    assert len(set(sizes.values())) == 1
    assert sizes["hump"] == 12  # round0 (10) + 2 new points
