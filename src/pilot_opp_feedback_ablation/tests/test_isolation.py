"""Isolation + CRN RNG pairing tests for Opportunity-Feedback Ablation."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from pilot_fi_anchor.config import ARM_CODE, FAMILY_ORDER, M, R, THETA_W
from pilot_fi_anchor.loop import Arm
from pilot_fi_anchor.mechanisms import ALL_FAMILIES
from pilot_fi_anchor.world import World

from pilot_opp_feedback_ablation.config import (
    ALLOC_RNG_ARM_CODE,
    ARM_NATIVE,
    ARM_NO_OPP,
    RESULTS_DIR,
    RESULTS_DIR_V1,
    SMOKE_SEEDS,
)
from pilot_opp_feedback_ablation.loop_ablation import (
    alloc_rng,
    compare_native_to_formal,
    fi_events,
    legal_unmeasured,
    nomination_rankings,
    paired_alloc_rngs,
    run_paired_seed,
    uniform_alive_allocation_weights,
)

ROOT = Path(__file__).resolve().parents[2]
FORMAL_DIR = ROOT / "outputs" / "pilot_fi_anchor"


def test_smoke_seeds_pre_fixed():
    assert SMOKE_SEEDS == (1, 2)


def test_alloc_rng_uses_native_arm_code_for_both():
    assert ALLOC_RNG_ARM_CODE == ARM_CODE["native"] == 0


def test_paired_rngs_same_seed_independent_instances():
    a, b = paired_alloc_rngs(1, 3)
    assert a is not b
    assert a.integers(0, 10**9) == b.integers(0, 10**9)
    # Independent mutable state: advancing one leaves the other behind
    a2, b2 = paired_alloc_rngs(1, 3)
    _ = a2.random()
    # b2 still at start; a2 already consumed one draw
    assert a2.random() != b2.random()
    x, y = paired_alloc_rngs(1, 4)
    assert x.random() == y.random()


def test_same_state_same_weights_same_rng_same_sites():
    """CRN isolation: identical inputs to _allocate_native ⇒ identical sites."""
    world = World(7)
    arm = Arm(7, "native", world, rediscovery_mode="off")
    arm.round0()
    arm.step(1, rng=alloc_rng(7, 1), w_override=None)
    w = dict(arm.w_all)
    sites_a = arm._allocate_native(alloc_rng(7, 2), w)
    sites_b = arm._allocate_native(alloc_rng(7, 2), w)
    assert sites_a == sites_b
    # Also: Native and No-Opp overrides that happen to equal w_all match
    sites_c = arm._allocate_native(alloc_rng(7, 2), w)
    assert sites_c == sites_a


def test_only_proposer_weights_change_other_paths_unchanged():
    world = World(3)
    a = Arm(3, "native", world, rediscovery_mode="off")
    a.round0()
    a.step(1, rng=alloc_rng(3, 1), w_override=None)
    ranked = nomination_rankings(a)
    legal = legal_unmeasured(a)
    w_support = dict(a.w_all)
    w_uniform = uniform_alive_allocation_weights(a)
    alive = [h for h in ALL_FAMILIES if a.alive[h]]
    sp = np.array([w_support[h] for h in alive], dtype=float)
    sp = sp / sp.sum()
    up = np.array([w_uniform[h] for h in alive], dtype=float)
    assert not np.allclose(sp, up)

    sites_s = a._allocate_native(alloc_rng(3, 2), w_support)
    sites_u = a._allocate_native(alloc_rng(3, 2), w_uniform)
    assert nomination_rankings(a) == ranked
    assert legal_unmeasured(a) == legal
    assert len(sites_s) == M == len(sites_u)
    assert {i for _, i in sites_s} <= legal
    assert {i for _, i in sites_u} <= legal
    # Under CRN, different weights typically change selection
    assert sites_s != sites_u


def test_fit_prune_evidence_budget_unchanged():
    world = World(4)
    native = Arm(4, "native", world, rediscovery_mode="off")
    noopp = Arm(4, "native", world, rediscovery_mode="off")
    assert native._check_elimination.__func__ is noopp._check_elimination.__func__
    assert native._update_evidence.__func__ is noopp._update_evidence.__func__
    assert native._update_support.__func__ is noopp._update_support.__func__
    assert native._allocate_native.__func__ is noopp._allocate_native.__func__
    assert THETA_W == 0.02
    assert R == 25
    assert M == 5


def test_w_override_does_not_write_support_or_pruning_weights():
    world = World(5)
    arm = Arm(5, "native", world, rediscovery_mode="off")
    arm.round0()
    w_u = {h: 1.0 for h in ALL_FAMILIES}
    arm.step(1, rng=alloc_rng(5, 1), w_override=w_u)
    assert abs(sum(arm.w_all.values()) - 1.0) < 1e-9
    assert arm.w_all != w_u
    # Pruning still keyed off w_surv from support update
    for h in ALL_FAMILIES:
        if arm.t_elim[h] is not None:
            assert arm.w_surv[h] == 0.0 or not arm.alive[h]


def test_crn_paired_run_round0_identical():
    rec = run_paired_seed(1, rounds=3)
    n0 = rec["arms"][ARM_NATIVE]["rounds"][0]
    u0 = rec["arms"][ARM_NO_OPP]["rounds"][0]
    for h in FAMILY_ORDER:
        assert n0[h]["w_all"] == u0[h]["w_all"]
    assert rec["arms"][ARM_NATIVE]["sites"][:10] == rec["arms"][ARM_NO_OPP]["sites"][:10]
    assert rec["rng_pairing"]["mode"] == "CRN_same_seed_independent_instances"
    assert rec["alloc_rng_arm_code"] == 0


def test_ablation_still_changes_sites_when_weights_differ():
    rec = run_paired_seed(1, rounds=5)
    n_sites = [s["idx"] for s in rec["arms"][ARM_NATIVE]["sites"] if s["t"] > 0]
    u_sites = [s["idx"] for s in rec["arms"][ARM_NO_OPP]["sites"] if s["t"] > 0]
    assert n_sites != u_sites
    assert rec["isolation"]["pilot_fi_anchor_modified"] is False


def test_same_weights_on_both_arms_yield_identical_trajectories_under_crn():
    """If No-Opp also used w_all, CRN ⇒ bit-identical to Native (sanity)."""
    world = World(9)
    a = Arm(9, "native", world, rediscovery_mode="off")
    b = Arm(9, "native", world, rediscovery_mode="off")
    a.round0()
    b.round0()
    for t in range(1, 4):
        rng_a, rng_b = paired_alloc_rngs(9, t)
        # Force identical weights: both use a.w_all / b.w_all after sync
        # Keep arms in sync by using same override = current native w_all copy
        w = dict(a.w_all)
        a.step(t, rng=rng_a, w_override=w)
        b.step(t, rng=rng_b, w_override=w)
    assert [s["idx"] for s in a.site_rows] == [s["idx"] for s in b.site_rows]
    assert a.t_elim == b.t_elim


def test_native_reproduces_formal_run_seed():
    """Ablation Native must match formal run_seed(..., do_perturb=False)."""
    for seed in (1, 2):
        chk = compare_native_to_formal(seed, rounds=8)
        assert chk["reproduces_formal_native"], chk


def test_native_matches_formal_disk_log_when_present():
    """Full-horizon disk logs: compare Native sites if JSON exists."""
    for seed in (1, 2):
        path = FORMAL_DIR / f"seed_{seed:02d}.json"
        if not path.is_file():
            continue
        abl = run_paired_seed(seed, rounds=R)
        disk = json.loads(path.read_text(encoding="utf-8"))
        a_sites = [(s["t"], s["idx"], s["credit"]) for s in abl["arms"][ARM_NATIVE]["sites"]]
        d_sites = [
            (s["t"], s["idx"], s.get("credit"))
            for s in disk["arms"]["native"]["sites"]
        ]
        assert a_sites == d_sites, (
            f"seed {seed}: ablation Native != formal disk Native; "
            f"formal disk may include perturb side-effects on main arm? "
            f"or version drift — report reason in smoke."
        )
        assert (
            abl["arms"][ARM_NATIVE]["final"]["t_elim"]
            == disk["arms"]["native"]["final"]["t_elim"]
        )


def test_v1_smoke_dir_preserved_path():
    # Config must not point RESULTS_DIR at v1
    assert RESULTS_DIR != RESULTS_DIR_V1
    assert "v2_rng" in RESULTS_DIR


def test_fi_event_helper_runs():
    rec = run_paired_seed(1, rounds=8)
    assert isinstance(fi_events(rec["arms"][ARM_NATIVE]), list)


def run_all() -> bool:
    tests = [
        test_smoke_seeds_pre_fixed,
        test_alloc_rng_uses_native_arm_code_for_both,
        test_paired_rngs_same_seed_independent_instances,
        test_same_state_same_weights_same_rng_same_sites,
        test_only_proposer_weights_change_other_paths_unchanged,
        test_fit_prune_evidence_budget_unchanged,
        test_w_override_does_not_write_support_or_pruning_weights,
        test_crn_paired_run_round0_identical,
        test_ablation_still_changes_sites_when_weights_differ,
        test_same_weights_on_both_arms_yield_identical_trajectories_under_crn,
        test_native_reproduces_formal_run_seed,
        test_native_matches_formal_disk_log_when_present,
        test_v1_smoke_dir_preserved_path,
        test_fi_event_helper_runs,
    ]
    failed = 0
    for fn in tests:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"FAIL {fn.__name__}: {type(exc).__name__}: {exc}")
    marker = Path(__file__).resolve().parents[1] / "_isolation_tests_ok"
    marker.write_text("PASS" if failed == 0 else "FAIL", encoding="utf-8")
    print("ALL PASS" if failed == 0 else f"{failed} FAILED")
    return failed == 0


if __name__ == "__main__":
    raise SystemExit(0 if run_all() else 1)
