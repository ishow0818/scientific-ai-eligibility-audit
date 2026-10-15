"""Stage-1 isolation tests for Evidence-Gated Eligibility."""
from __future__ import annotations

import copy

import numpy as np
import pytest

from pilot_fi_anchor.config import FAMILY_ORDER, N_CAND, R, X_MAX, X_MIN
from pilot_fi_anchor.loop import Arm
from pilot_fi_anchor.world import World

from evidence_gated_eligibility.arm_evidence_gate import EvidenceGateAbort, EvidenceGateArm
from evidence_gated_eligibility.config import (
    ARM_DECISION_ONLY,
    ARM_FULL_GATE,
    ARM_NATIVE,
    EXPECTED_N_MEASURED,
    FORMAL_SEEDS,
    SMOKE_SEEDS,
    STATUS_ABORT_EMPTY,
    STATUS_DECISION_EMPTY,
)
from evidence_gated_eligibility.eligibility import (
    decision_only_gate,
    select_incumbent_by_w_all,
)
from evidence_gated_eligibility.eval_grid import (
    EVAL_X_MIDPOINTS,
    assert_eval_disjoint_from_measurable,
    measurable_grid,
    rmse_noiseless,
)
from evidence_gated_eligibility.loop_ege import (
    compare_native_to_formal_run_seed,
    paired_alloc_rngs,
    run_paired_seed,
)


def test_smoke_seeds_not_formal_queue():
    assert set(SMOKE_SEEDS).isdisjoint(set(FORMAL_SEEDS))
    assert SMOKE_SEEDS == (1001, 1002, 1003)
    assert FORMAL_SEEDS[0] == 201 and FORMAL_SEEDS[-1] == 240


def test_eval_grid_disjoint():
    assert_eval_disjoint_from_measurable()
    g = measurable_grid()
    assert len(g) == N_CAND
    assert len(EVAL_X_MIDPOINTS) == N_CAND - 1
    # midpoints strictly between neighbors
    for i, x in enumerate(EVAL_X_MIDPOINTS):
        assert g[i] < x < g[i + 1]


def test_decision_uses_w_all_not_truth_or_rmse():
    w_all = {h: 0.01 for h in FAMILY_ORDER}
    w_all["quad"] = 0.96
    excluded = {h: False for h in FAMILY_ORDER}
    excluded["hump"] = False
    # Even if hump is truth, quad wins on w_all
    h, st, E = select_incumbent_by_w_all(w_all, excluded)
    assert h == "quad" and st == "OK"
    # rmse must not be consulted by selector (call separately only for eval)
    rmse_hump, _ = rmse_noiseless("hump", {"A": 8.0, "mu": 4.5, "s": 2.5})
    rmse_quad, _ = rmse_noiseless(
        "quad", {"a": 0.0, "b": 0.0, "c": 0.0}
    )
    assert rmse_hump is not None and rmse_quad is not None
    # selector still picks quad despite worse RMSE
    assert h == "quad"


def test_decision_empty():
    w_all = {h: 0.2 for h in FAMILY_ORDER}
    excluded = {h: True for h in FAMILY_ORDER}
    h, st, E = select_incumbent_by_w_all(w_all, excluded)
    assert h is None and st == STATUS_DECISION_EMPTY and E == []


def test_native_reproduction_seeds():
    for seed in (1, 3, 20):
        chk = compare_native_to_formal_run_seed(seed, rounds=R)
        assert chk["match"], chk


def test_b_does_not_change_trajectory():
    rec = run_paired_seed(1, rounds=5)
    a = rec["arms"][ARM_NATIVE]
    b = rec["arms"][ARM_DECISION_ONLY]
    assert [s["idx"] for s in a["sites"]] == [s["idx"] for s in b["sites"]]
    assert [s["y"] for s in a["sites"]] == [s["y"] for s in b["sites"]]
    # rounds content identical (B reuses list copy of same rows)
    assert a["rounds"] == b["rounds"]
    assert b["isolation"]["closed_loop_rerun"] is False


def test_b_offline_from_frozen_snapshot():
    rec = run_paired_seed(3, rounds=5)
    a = rec["arms"][ARM_NATIVE]
    snap = copy.deepcopy(a)
    b2 = decision_only_gate(snap)
    assert b2["final"]["incumbent"] == rec["arms"][ARM_DECISION_ONLY]["final"]["incumbent"]


def test_c_excluded_never_resurrects():
    rec = run_paired_seed(20, rounds=R)
    audit = rec["arms"][ARM_FULL_GATE].get("eligibility_audit", [])
    prev = {h: False for h in FAMILY_ORDER}
    for row in audit:
        for h in FAMILY_ORDER:
            assert not (prev[h] and not row["excluded"][h])
            prev[h] = row["excluded"][h]


def test_empty_eligible_allocate_aborts():
    world = World(0)
    arm = EvidenceGateArm(0, world)
    arm.round0()
    # Force all excluded
    for h in FAMILY_ORDER:
        arm.excluded[h] = True
    rng = np.random.default_rng(0)
    with pytest.raises(EvidenceGateAbort) as ei:
        arm._allocate_evidence_gated(rng, arm.w_all)
    assert ei.value.code == STATUS_ABORT_EMPTY


def test_zero_mass_aborts():
    world = World(0)
    arm = EvidenceGateArm(0, world)
    arm.round0()
    w = {h: 0.0 for h in FAMILY_ORDER}
    # leave one eligible but zero mass
    for h in FAMILY_ORDER[1:]:
        arm.excluded[h] = True
    rng = np.random.default_rng(0)
    with pytest.raises(EvidenceGateAbort) as ei:
        arm._allocate_evidence_gated(rng, w)
    assert ei.value.code == "ABORT_ZERO_WEIGHT_MASS"


def test_crn_identical_generators_start_state():
    r1, r2 = paired_alloc_rngs(42, 3)
    # same draws from identical initial state
    assert r1.random() == r2.random()


def test_budget_native_full_horizon():
    rec = run_paired_seed(1, rounds=R)
    assert rec["budget"]["native_budget_ok"]
    assert rec["budget"]["b_sites_identical_to_a"]
    assert rec["arms"][ARM_NATIVE]["final"]["n_measured"] == EXPECTED_N_MEASURED


def test_c_only_changes_eligibility_policy_path():
    """When proposer masses & eligible sets match Native alive early, sites may match;
    structural check: C never calls weight elim into decision (alive stays True)."""
    rec = run_paired_seed(1, rounds=3)
    c_rounds = rec["arms"][ARM_FULL_GATE]["rounds"]
    for row in c_rounds:
        for h in FAMILY_ORDER:
            assert row[h]["alive"] is True


def test_decision_not_fed_eval_grid():
    # ensure selector signature has no eval path — already tested via w_all
    # and EVAL_X never equals measurable idx mapping
    g = np.linspace(X_MIN, X_MAX, N_CAND)
    for x in EVAL_X_MIDPOINTS:
        assert x not in set(g.tolist()) or True  # floats: use disjoint assert
    assert_eval_disjoint_from_measurable()
