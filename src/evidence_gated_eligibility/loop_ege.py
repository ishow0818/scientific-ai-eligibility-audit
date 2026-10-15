"""Paired Native (A) + Full Evidence Gate (C); Decision-Only (B) from A."""
from __future__ import annotations

import time
from typing import Any

import numpy as np

from pilot_fi_anchor.config import MASTER_SALT, R, RNG_ALLOC, TRUTH_FAMILY
from pilot_fi_anchor.loop import Arm
from pilot_fi_anchor.rng import seed_sequence
from pilot_fi_anchor.world import World

from .arm_evidence_gate import EvidenceGateArm
from .config import (
    ALLOC_ARM_CODE,
    ARM_DECISION_ONLY,
    ARM_FULL_GATE,
    ARM_NATIVE,
    EGE_VERSION,
    EXPECTED_N_MEASURED,
    FALSE_FAMILIES,
    STATUS_OK,
)
from .eligibility import assert_excluded_sticky, decision_only_gate
from .eval_grid import RMSE_FAIL, eval_meta, rmse_noiseless


def alloc_rng(seed: int, t: int) -> np.random.Generator:
    """CRN allocation entropy identical to formal Native arm code 0."""
    return np.random.default_rng(
        seed_sequence(seed, ALLOC_ARM_CODE, RNG_ALLOC, t)
    )


def paired_alloc_rngs(seed: int, t: int) -> tuple[np.random.Generator, np.random.Generator]:
    return alloc_rng(seed, t), alloc_rng(seed, t)


def _pack_native(a: Arm) -> dict[str, Any]:
    return {
        "arm_tag": ARM_NATIVE,
        "allocation_mode": "support_weighted_w_all",
        "rounds": a.rows,
        "sites": a.site_rows,
        "final": {
            "incumbent": a._incumbent(),
            "alive": dict(a.alive),
            "t_elim": dict(a.t_elim),
            "t_excl": dict(a.t_excl),
            "excluded": dict(a.excluded),
            "arm_theta": {h: dict(a.arm_theta[h]) for h in a.arm_theta},
            "incumbent_theta": (
                dict(a.arm_theta[a._incumbent()]) if a._incumbent() else None
            ),
            "primary_status": STATUS_OK if a._incumbent() else "DECISION_EMPTY",
            "n_measured": len(a.measured),
            "decision_rule": "argmax w_surv among alive",
        },
    }


def _pack_gate(a: EvidenceGateArm) -> dict[str, Any]:
    return {
        "arm_tag": ARM_FULL_GATE,
        "allocation_mode": "evidence_gated_w_all",
        "rounds": a.rows,
        "sites": a.site_rows,
        "eligibility_audit": list(a.eligibility_audit),
        "final": a.final_pack(),
    }


def _truth_eligibility_lost(final: dict[str, Any]) -> bool:
    """A: weight-alive lost; B/C: operational excluded (sticky eligibility loss)."""
    excl = final.get("excluded", {})
    if "eligible" in final:
        # Evidence-gated decision surface (B/C): lost iff excluded or not eligible
        if bool(excl.get(TRUTH_FAMILY, False)):
            return True
        elig = final.get("eligible") or {}
        return not bool(elig.get(TRUTH_FAMILY, False))
    alive = final.get("alive", {})
    return not bool(alive.get(TRUTH_FAMILY, True))


def _n_false_eligible(final: dict[str, Any]) -> int:
    elig = final.get("eligible")
    if elig is not None:
        return sum(1 for h in FALSE_FAMILIES if elig.get(h, False))
    alive = final.get("alive", {})
    return sum(1 for h in FALSE_FAMILIES if alive.get(h, False))


def _score_arm(pack: dict[str, Any]) -> dict[str, Any]:
    """Uniform score schema for OK and failure arms (formal stats must not drop fields)."""
    final = pack["final"]
    status = final.get("primary_status") or STATUS_OK
    # Prefer explicit abort code when present
    abort = final.get("abort_status")
    if abort:
        status = abort
    incumb = final.get("incumbent")
    theta = final.get("incumbent_theta")
    excl = final.get("excluded", {})
    n_meas = final.get("n_measured")
    if n_meas is None:
        n_meas = len(pack.get("sites", []))

    is_failure = (status != STATUS_OK) or (incumb is None)
    failure_type = None if not is_failure else status

    if is_failure:
        rmse = None
        rmse_pen = RMSE_FAIL
        truth_sel = False
    else:
        rmse, st = rmse_noiseless(incumb, theta)
        if st != STATUS_OK:
            is_failure = True
            failure_type = st
            status = st
            rmse = None
            rmse_pen = RMSE_FAIL
            truth_sel = False
        else:
            rmse_pen = rmse
            truth_sel = incumb == TRUTH_FAMILY

    return {
        "rmse_eval_noiseless": rmse,
        "rmse_with_fail_penalty": rmse_pen,
        "primary_status": status,
        "failure_type": failure_type,
        "is_failure": bool(is_failure),
        "truth_selected": bool(truth_sel),
        "truth_excluded_operational": bool(excl.get(TRUTH_FAMILY, False)),
        "truth_eligibility_lost": _truth_eligibility_lost(final),
        "n_false_eligible": _n_false_eligible(final),
        "n_measured": int(n_meas) if n_meas is not None else None,
    }


def run_paired_seed(seed: int, *, rounds: int = R) -> dict[str, Any]:
    """Run A (Native) + C (Full Gate) on shared World; derive B offline from A."""
    t0 = time.perf_counter()
    world = World(seed)
    arm_a = Arm(seed, "native", world, rediscovery_mode="off")
    arm_c = EvidenceGateArm(seed, world)

    arm_a.round0()
    arm_c.round0()

    for t in range(1, rounds + 1):
        rng_a, rng_c = paired_alloc_rngs(seed, t)
        arm_a.step(t, rng=rng_a)
        if arm_c.abort_status is None:
            arm_c.step(t, rng=rng_c)

    pack_a = _pack_native(arm_a)
    pack_b = decision_only_gate(pack_a)
    pack_c = _pack_gate(arm_c)

    # sticky excluded checks on C audit
    if pack_c.get("eligibility_audit"):
        assert_excluded_sticky([row["excluded"] for row in pack_c["eligibility_audit"]])

    scores = {
        ARM_NATIVE: _score_arm(pack_a),
        ARM_DECISION_ONLY: _score_arm(pack_b),
        ARM_FULL_GATE: _score_arm(pack_c),
    }
    # fix B n_measured / false eligible
    scores[ARM_DECISION_ONLY]["n_measured"] = scores[ARM_NATIVE]["n_measured"]
    b_elig = pack_b["final"]["eligible"]
    scores[ARM_DECISION_ONLY]["n_false_eligible"] = sum(
        1 for h in FALSE_FAMILIES if b_elig.get(h, False)
    )
    scores[ARM_DECISION_ONLY]["truth_eligibility_lost"] = bool(
        pack_b["final"]["excluded"].get(TRUTH_FAMILY, False)
    )

    # budget checks
    budget = {
        "expected_n": EXPECTED_N_MEASURED,
        "native_n": len(pack_a["sites"]),
        "decision_only_n": len(pack_b["sites"]),
        "full_gate_n": len(pack_c["sites"]),
        "native_budget_ok": len(pack_a["sites"]) == EXPECTED_N_MEASURED,
        "b_sites_identical_to_a": [s["idx"] for s in pack_a["sites"]]
        == [s["idx"] for s in pack_b["sites"]],
        "c_budget_ok_or_aborted": (
            len(pack_c["sites"]) == EXPECTED_N_MEASURED
            or pack_c["final"].get("abort_status") is not None
        ),
    }

    return {
        "seed": seed,
        "version": EGE_VERSION,
        "master_salt": MASTER_SALT,
        "alloc_rng_arm_code": ALLOC_ARM_CODE,
        "rng_pairing": {
            "mode": "CRN_same_seed_independent_instances",
            "seed_sequence_parts": [
                "MASTER_SALT",
                "seed",
                "ALLOC_ARM_CODE==0",
                "RNG_ALLOC",
                "t",
            ],
        },
        "eval": eval_meta(),
        "arms": {
            ARM_NATIVE: pack_a,
            ARM_DECISION_ONLY: pack_b,
            ARM_FULL_GATE: pack_c,
        },
        "scores": scores,
        "budget": budget,
        "wall_s": time.perf_counter() - t0,
        "chi2_status": "OPERATIONAL_ONLY",
    }


def compare_native_to_formal_run_seed(seed: int, rounds: int = R) -> dict[str, Any]:
    from pilot_fi_anchor.loop import run_seed

    formal = run_seed(seed, do_perturb=False, rounds=rounds)
    abl = run_paired_seed(seed, rounds=rounds)
    f_sites = [(s["t"], s["idx"], s.get("credit")) for s in formal["arms"]["native"]["sites"]]
    a_sites = [(s["t"], s["idx"], s.get("credit")) for s in abl["arms"][ARM_NATIVE]["sites"]]
    f_elim = formal["arms"]["native"]["final"]["t_elim"]
    a_elim = abl["arms"][ARM_NATIVE]["final"]["t_elim"]
    f_excl = formal["arms"]["native"]["final"]["t_excl"]
    a_excl = abl["arms"][ARM_NATIVE]["final"]["t_excl"]
    return {
        "seed": seed,
        "sites_match": f_sites == a_sites,
        "t_elim_match": f_elim == a_elim,
        "t_excl_match": f_excl == a_excl,
        "match": f_sites == a_sites and f_elim == a_elim and f_excl == a_excl,
    }
