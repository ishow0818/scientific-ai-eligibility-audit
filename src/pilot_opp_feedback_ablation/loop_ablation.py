"""Paired Native vs No-Opportunity-Feedback runner.

Isolation mechanism (ISOLATABLE):
  In ``pilot_fi_anchor.loop.Arm._allocate_native``, support weights enter
  *only* as proposer-draw probabilities over alive candidates. Nomination
  rankings ``u(x)`` do not read allocation weights. Support update / pruning
  use ``self.w_all`` / ``self.w_surv`` after measurement, unaffected by the
  ``w_override`` passed into ``step``.

  No-Opportunity-Feedback therefore calls the same ``_allocate_native`` with
  ``w_override = uniform among currently alive``; Native calls ``step`` with
  default ``w_override=None`` (uses ``self.w_all``). ``pilot_fi_anchor`` source
  is not modified.

RNG pairing (v0.2 CRN):
  Both arms use SeedSequence([MASTER_SALT, seed, ARM_CODE['native'], RNG_ALLOC, t])
  and each receives an *independent* Generator with that identical initial state.
  Same state + same proposer weights + same RNG seed ⇒ identical sites.
  Only proposer weights differ under CRN ⇒ isolates opportunity feedback.
"""
from __future__ import annotations

from typing import Any

import numpy as np

from pilot_fi_anchor.config import MASTER_SALT, R, RNG_ALLOC
from pilot_fi_anchor.loop import Arm
from pilot_fi_anchor.mechanisms import ALL_FAMILIES
from pilot_fi_anchor.rng import seed_sequence
from pilot_fi_anchor.world import World

from .config import (
    ABLATION_VERSION,
    ALLOC_RNG_ARM_CODE,
    ARM_NATIVE,
    ARM_NO_OPP,
)


def allocation_seed_sequence(seed: int, t: int) -> np.random.SeedSequence:
    """Shared allocation entropy for Native and No-Opp (formal Native code)."""
    return seed_sequence(seed, ALLOC_RNG_ARM_CODE, RNG_ALLOC, t)


def alloc_rng(seed: int, t: int) -> np.random.Generator:
    """Independent Generator from the shared Native allocation SeedSequence.

    Calling twice with the same (seed, t) yields two instances with identical
    initial state (CRN), not one shared mutable generator.
    """
    return np.random.default_rng(allocation_seed_sequence(seed, t))


def paired_alloc_rngs(seed: int, t: int) -> tuple[np.random.Generator, np.random.Generator]:
    """(native_rng, no_opp_rng) — same seed, independent instances."""
    return alloc_rng(seed, t), alloc_rng(seed, t)


def uniform_alive_allocation_weights(arm: Arm) -> dict[str, float]:
    """Equal positive mass on currently alive candidates; zero on eliminated.

    Used *only* as ``w_override`` for opportunity allocation. Does not write
    into ``arm.w_all`` / ``arm.w_surv``.
    """
    alive = [h for h in ALL_FAMILIES if arm.alive[h]]
    if not alive:
        return {h: 0.0 for h in ALL_FAMILIES}
    u = 1.0 / float(len(alive))
    return {h: (u if arm.alive[h] else 0.0) for h in ALL_FAMILIES}


def nomination_rankings(arm: Arm) -> dict[str, list[int]]:
    """Reproduce Native nomination lists (identical function of stream fits)."""
    from pilot_fi_anchor.config import N_CAND, SIGMA
    from pilot_fi_anchor.fitting import residual_field
    from pilot_fi_anchor.mechanisms import FAMILIES

    alive = [h for h in ALL_FAMILIES if arm.alive[h]]
    unmeasured = [i for i in range(N_CAND) if i not in arm.measured]
    xq = arm.world.grid[unmeasured]
    ranked: dict[str, list[int]] = {}
    for h in alive:
        mech = FAMILIES[h]
        xs = np.array([arm.world.x(i) for (_, i, _) in arm.streams[h]])
        ys = np.array([y for (_, _, y) in arm.streams[h]])
        if len(xs) == 0:
            continue
        rhat = residual_field(mech, arm.stream_theta[h], xs, ys, xq)
        u = np.exp(-((rhat / SIGMA) ** 2))
        ranked[h] = [unmeasured[j] for j in np.argsort(-u)]
    return ranked


def legal_unmeasured(arm: Arm) -> set[int]:
    from pilot_fi_anchor.config import N_CAND

    return {i for i in range(N_CAND) if i not in arm.measured}


def run_paired_seed(
    seed: int,
    *,
    rounds: int = R,
) -> dict[str, Any]:
    """Run Native + No-Opp-Feedback on a shared World (paired noise + CRN alloc)."""
    world = World(seed)
    arms: dict[str, Arm] = {
        ARM_NATIVE: Arm(seed, "native", world, rediscovery_mode="off"),
        ARM_NO_OPP: Arm(seed, "native", world, rediscovery_mode="off"),
    }
    for a in arms.values():
        a.round0()

    for t in range(1, rounds + 1):
        rng_n, rng_u = paired_alloc_rngs(seed, t)
        # Native: original opportunity feedback (w_all → proposer probs)
        arms[ARM_NATIVE].step(t, rng=rng_n, w_override=None)
        # No-Opp: uniform among alive only for allocation
        w_u = uniform_alive_allocation_weights(arms[ARM_NO_OPP])
        arms[ARM_NO_OPP].step(t, rng=rng_u, w_override=w_u)

    def pack(tag: str, a: Arm) -> dict[str, Any]:
        return {
            "arm_tag": tag,
            "allocation_mode": (
                "support_weighted_w_all"
                if tag == ARM_NATIVE
                else "uniform_alive_override"
            ),
            "rounds": a.rows,
            "sites": a.site_rows,
            "final": {
                "incumbent": a._incumbent(),
                "alive": dict(a.alive),
                "t_elim": dict(a.t_elim),
                "t_excl": dict(a.t_excl),
                "excluded": dict(a.excluded),
                "arm_theta": {h: dict(a.arm_theta[h]) for h in ALL_FAMILIES},
            },
        }

    return {
        "seed": seed,
        "ablation": "opportunity_feedback",
        "version": ABLATION_VERSION,
        "master_salt": MASTER_SALT,
        "alloc_rng_arm_code": ALLOC_RNG_ARM_CODE,
        "rng_pairing": {
            "mode": "CRN_same_seed_independent_instances",
            "seed_sequence_parts": [
                "MASTER_SALT",
                "seed",
                "ARM_CODE[native]==0",
                "RNG_ALLOC",
                "t",
            ],
            "note": (
                "v0.1 incorrectly used distinct arm code=2 for No-Opp; "
                "v0.2 uses shared Native code for both arms"
            ),
        },
        "arms": {tag: pack(tag, a) for tag, a in arms.items()},
        "isolation": {
            "status": "ISOLATABLE",
            "mechanism": (
                "w_override into Arm._allocate_native proposer probs only; "
                "nomination / fit / support / prune / evidence unchanged; "
                "CRN allocation RNG pairing"
            ),
            "pilot_fi_anchor_modified": False,
        },
    }


def fi_events(arm_pack: dict[str, Any], families: tuple[str, ...] | None = None) -> list[dict]:
    from pilot_fi_anchor.config import FALSE_FAMILIES, TRUTH_FAMILY

    fams = families if families is not None else FALSE_FAMILIES + (TRUTH_FAMILY,)
    final = arm_pack["final"]
    rounds = arm_pack["rounds"]
    out = []
    for h in fams:
        te = final["t_elim"].get(h)
        tx = final["t_excl"].get(h)
        if te is None:
            continue
        st = rounds[te][h]
        fi = tx is None or te < tx
        out.append(
            {
                "family": h,
                "is_truth": h == TRUTH_FAMILY,
                "t_elim": te,
                "t_excl": tx,
                "fi": fi,
                "w_surv_at_elim": st["w_surv"],
                "w_all_at_elim": st["w_all"],
                "violated_at_elim": st["violated"],
                "excluded_at_elim": st["excluded"],
            }
        )
    return out


def compare_native_to_formal(
    seed: int,
    *,
    rounds: int = 5,
    formal_path: Any | None = None,
) -> dict[str, Any]:
    """Check ablation Native sites/elim vs formal pilot Native (do_perturb=False)."""
    from pathlib import Path

    from pilot_fi_anchor.loop import run_seed

    formal = run_seed(seed, do_perturb=False, rounds=rounds)
    abl = run_paired_seed(seed, rounds=rounds)
    f_sites = [
        (s["t"], s["idx"], s["credit"])
        for s in formal["arms"]["native"]["sites"]
    ]
    a_sites = [
        (s["t"], s["idx"], s["credit"])
        for s in abl["arms"][ARM_NATIVE]["sites"]
    ]
    f_elim = formal["arms"]["native"]["final"]["t_elim"]
    a_elim = abl["arms"][ARM_NATIVE]["final"]["t_elim"]
    sites_match = f_sites == a_sites
    elim_match = f_elim == a_elim
    # Optional: compare to on-disk formal full-horizon log if provided
    disk_note = None
    if formal_path is not None:
        p = Path(formal_path)
        if p.is_file():
            import json

            disk = json.loads(p.read_text(encoding="utf-8"))
            # Full formal logs include Neutral + may include perturb; compare Native only
            d_sites = [
                (s["t"], s["idx"], s.get("credit"))
                for s in disk["arms"]["native"]["sites"]
                if int(s["t"]) <= rounds
            ]
            # disk has full R=25; filter
            disk_note = {
                "path": str(p),
                "prefix_sites_match_ablation_native": d_sites[: len(a_sites)] == a_sites
                if rounds < 25
                else (
                    [
                        (s["t"], s["idx"], s.get("credit"))
                        for s in disk["arms"]["native"]["sites"]
                    ]
                    == a_sites
                ),
            }
    return {
        "seed": seed,
        "rounds": rounds,
        "sites_match": sites_match,
        "t_elim_match": elim_match,
        "reproduces_formal_native": sites_match and elim_match,
        "n_formal_sites": len(f_sites),
        "n_ablation_native_sites": len(a_sites),
        "disk_check": disk_note,
        "reason_if_fail": None
        if (sites_match and elim_match)
        else (
            "Ablation Native should match formal run_seed(..., do_perturb=False) "
            "when alloc RNG uses ARM_CODE[native]; investigate fit/world divergence"
        ),
    }
