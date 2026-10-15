"""Local perturbation experiment: empirical local gain g (secondary analysis).

At each round t < R, the current representation (full-simplex support w_all)
is perturbed toward each surviving non-incumbent hypothesis while the
evidence (streams / data) is untouched.  Counterfactual one-round branches
use Common Random Numbers (CRN): baseline and perturbed next-steps share the
identical allocation RNG draw; only the representation override differs.

    g = ||w_pert_next - w_base_next|| / ||w_pert - w_base||

This is an empirical local response measure.  It is NOT a direct estimate of
alpha, mu, or R_id unless a strict equivalence is established elsewhere.

Neutral arms ignore support in allocation, so g == 0 exactly under CRN --
a built-in zero-gain control (checked by KILL-B4), but not the sole test of
CRN correctness.
"""

from __future__ import annotations

import copy
from typing import Any

import numpy as np

from .config import DELTA_PERTS
from .mechanisms import ALL_FAMILIES

_ORDER = ALL_FAMILIES


def perturbation_targets(arm: Any) -> list[str]:
    """Surviving non-incumbent hypotheses."""
    if arm.round == 0:
        return []
    alive = [h for h in _ORDER if arm.alive[h]]
    if len(alive) <= 1:
        return []
    incumbent = max(alive, key=lambda h: arm.w_surv[h])
    return [h for h in alive if h != incumbent]


def make_perturbation(
    arm: Any, h: str, delta: float
) -> tuple[dict[str, float], dict[str, float]]:
    """Return (w_pert, w_base) with w_pert = w_base + delta * (e_h - w_base).

    The perturbation sums to zero, so w_pert is already normalised.
    """
    w_base = {hh: float(arm.w_all[hh]) for hh in _ORDER}
    d = {hh: -w_base[hh] for hh in _ORDER}
    d[h] += 1.0
    w_pert = {hh: w_base[hh] + delta * d[hh] for hh in _ORDER}
    return w_pert, w_base


def _gain_from_next(
    w_base: dict[str, float],
    w_pert: dict[str, float],
    w_base_next: dict[str, float],
    w_pert_next: dict[str, float],
) -> tuple[float, float]:
    d = np.array([w_pert[h] - w_base[h] for h in _ORDER])
    delta_w = np.array([w_pert_next[h] - w_base_next[h] for h in _ORDER])
    denom = float(np.linalg.norm(d))
    numer = float(np.linalg.norm(delta_w))
    if denom < 1e-15:
        return 0.0, 0.0
    g = numer / denom
    if numer < 1e-15:
        cos = 0.0
    else:
        cos = float(np.dot(delta_w, d) / (numer * denom))
    return g, cos


def run_perturb_pair(
    arm: Any, h: str, delta: float, seed: int, t: int
) -> dict[str, Any]:
    """CRN counterfactual pair: baseline vs perturbed one-round branch."""
    from .rng import alloc_rng, fork_rng

    w_pert, w_base = make_perturbation(arm, h, delta)

    pre_measured = set(arm.measured)

    base = copy.deepcopy(arm)
    rng0 = alloc_rng(seed, arm.kind, t + 1)
    base.step(
        t + 1,
        rng=fork_rng(rng0),
        w_override=None if delta == 0.0 else w_base,
        record=False,
    )
    w_base_next = {hh: float(base.w_all[hh]) for hh in _ORDER}
    base_new_sites = sorted(base.measured - pre_measured)

    pert = copy.deepcopy(arm)
    rng1 = alloc_rng(seed, arm.kind, t + 1)
    pert.step(
        t + 1,
        rng=fork_rng(rng1),
        w_override=None if delta == 0.0 else w_pert,
        record=False,
    )
    w_pert_next = {hh: float(pert.w_all[hh]) for hh in _ORDER}
    pert_new_sites = sorted(pert.measured - pre_measured)

    g, cos = _gain_from_next(w_base, w_pert, w_base_next, w_pert_next)
    return {
        "t": t,
        "arm": arm.kind,
        "h": h,
        "delta": delta,
        "g": g,
        "cos": cos,
        "w_base": w_base,
        "w_pert": w_pert,
        "w_base_next": w_base_next,
        "w_pert_next": w_pert_next,
        "base_new_sites": base_new_sites,
        "pert_new_sites": pert_new_sites,
    }
