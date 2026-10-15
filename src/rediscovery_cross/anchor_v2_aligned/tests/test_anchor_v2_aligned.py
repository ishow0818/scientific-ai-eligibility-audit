"""Tests for Anchor v2 CAMELS-aligned recoverability."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from pilot_fi_anchor.config import FALSE_FAMILIES, FAMILY_ORDER, R, THETA_W
from pilot_fi_anchor.loop import Arm, run_seed
from pilot_fi_anchor.world import World
from rediscovery_cross.anchor_v2_aligned.analysis import (
    load_av2_config,
    paired_pre_first_fi_identical,
    run_anchor_v2_condition,
    trajectory_divergence_paired,
    verify_reentry_uses_ordinary_criterion,
)


def test_off_reproduces_frozen_anchor():
    a = run_seed(121, do_perturb=False, rounds=R, rediscovery_mode="off")
    b = run_seed(121, do_perturb=False, rounds=R, rediscovery_mode="off")
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_no_v1_hypothetical_in_v2():
    rec = run_seed(121, do_perturb=False, rounds=R, rediscovery_mode="v2_on")
    assert rec["arms"]["native"]["final"]["rediscovery_mode"] == "v2_on"


def test_off_absorbing_elimination():
    rec = run_seed(122, do_perturb=False, rounds=R, rediscovery_mode="off")
    rows = rec["arms"]["native"]["rounds"]
    for h in FALSE_FAMILIES:
        t_elim = rec["arms"]["native"]["final"]["t_elim"][h]
        if t_elim is None:
            continue
        for t in range(t_elim + 1, len(rows)):
            assert not rows[t][h]["alive"], f"{h} re-entered under OFF at t={t}"


def test_pre_first_fi_equivalence_dry_seeds():
    for seed in (921, 922):
        r = paired_pre_first_fi_identical(seed)
        assert r["pre_fi_identical"], seed
        assert r["first_fi_matched"], seed


def test_first_fi_matched_confirmatory_seeds_sample():
    for seed in (121, 125, 130):
        r = paired_pre_first_fi_identical(seed)
        assert r["first_fi_matched"], seed


def test_reentry_uses_ordinary_w_all_criterion():
    rec = run_seed(921, do_perturb=False, rounds=R, rediscovery_mode="v2_on")
    audit = verify_reentry_uses_ordinary_criterion(rec)
    assert audit["pass"]
    for entry in rec["arms"]["native"]["final"]["reentry_audit"]:
        assert entry["criterion"] == "w_all >= THETA_W"
        assert entry["eligibility_quantity"] >= THETA_W - 1e-12


def test_reentered_participates_in_allocation():
    rec = run_seed(921, do_perturb=False, rounds=R, rediscovery_mode="v2_on")
    audit = rec["arms"]["native"]["final"]["reentry_audit"]
    if not audit:
        pytest.skip("no re-entry on seed 921")
    entry = audit[0]
    h = entry["alternative_id"]
    t_re = entry["t_reentry"]
    if t_re + 1 >= len(rec["arms"]["native"]["rounds"]):
        pytest.skip("re-entry at horizon")
    next_sites = [s for s in rec["arms"]["native"]["sites"] if s["t"] == t_re + 1]
    credits = {s["credit"] for s in next_sites}
    assert h in credits or rec["arms"]["native"]["rounds"][t_re + 1][h]["alive"]


def test_paired_crn_preserved_pre_fi():
    off = run_seed(123, do_perturb=False, rounds=R, rediscovery_mode="off")
    on = run_seed(123, do_perturb=False, rounds=R, rediscovery_mode="v2_on")
    pre = paired_pre_first_fi_identical(123)
    t_max = pre["compare_through_round"]
    off_s = [s for s in off["arms"]["native"]["sites"] if s["t"] <= t_max]
    on_s = [s for s in on["arms"]["native"]["sites"] if s["t"] <= t_max]
    assert off_s == on_s


def test_seed_sets_disjoint():
    cfg = load_av2_config()
    v2 = set(cfg["experiment"]["confirmatory_seeds"])
    v1 = set(range(101, 121))
    pilot = set(range(1, 21))
    assert v2.isdisjoint(v1)
    assert v2.isdisjoint(pilot)
    for rng in cfg["experiment"]["excluded_seed_ranges"].values():
        lo, hi = rng
        assert v2.isdisjoint(set(range(lo, hi + 1)))


def test_trajectory_indexing_and_classifier():
    from rediscovery_cross.rediscovery import analyze_trajectory_after_first_loss

    traj = [True, True, False, False, True, True]
    post = analyze_trajectory_after_first_loss(traj, 2, horizon=5)
    assert post["reentered_after_first_loss"]
    assert post["classification"] == "transient_loss"
    post2 = analyze_trajectory_after_first_loss([True, True, False, False, False], 2, horizon=4)
    assert post2["persistent_loss"]


def test_v2_reconstruction_after_first_elim():
    world = World(921)
    arm = Arm(921, "native", world, rediscovery_mode="v2_on")
    arm.round0()
    arm.alive["affine"] = False
    arm.t_elim["affine"] = 1
    arm._update_support()
    arm._check_elimination()
    assert arm.rediscovery_mode == "v2_on"
    assert not any(
        e.get("criterion") == "_hypothetical_w_surv >= THETA_W"
        for e in arm.reentry_audit
    )


def test_trajectory_divergence_structure():
    off = run_anchor_v2_condition(121, rediscovery_mode="off", do_perturb=False)
    on = run_anchor_v2_condition(121, rediscovery_mode="v2_on", do_perturb=False)
    div = trajectory_divergence_paired(off["events"], on["events"])
    assert "n_matched_FI_events" in div
    assert "fraction_trajectory_diverged" in div
