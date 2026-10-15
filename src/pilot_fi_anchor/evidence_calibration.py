"""Calibration / sanity checks for the frozen evidence criterion.

Static checks: one-shot compatibility on initial and full-coverage datasets.
Sequential checks: simulate 25-round Neutral sweep (truth=hump) and estimate
false exclusion rate under the sequential Bonferroni rule.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from scipy.stats import chi2

from .config import (
    ALPHA_EV,
    FALSE_FAMILIES,
    M,
    NEUTRAL_J0,
    NEUTRAL_SPAN,
    PERSIST,
    R,
    SIGMA,
    TRUTH_FAMILY,
    TRUTH_PARAMS,
    X0_IDX,
)
from .fitting import fit
from .mechanisms import FAMILIES, TRUTH, TRUTH_THETA

CALIBRATION_SEEDS = tuple(range(1, 6))
SEQUENTIAL_SEEDS = tuple(range(1, 21))
# v1.1.1 B2 failures; loop verification subset (not tuned against).
B2_LOOP_CHECK_SEEDS = (3, 20)
# Legacy per-round alpha (pre-v1.1.2); used only for sequential comparison report.
ALPHA_EV_LEGACY = 0.05 / 5.0

# Representative high-x tail indices (x >= 9.5), Native-style extreme sampling.
EXTREME_X_IDX = (382, 384, 387, 389, 392, 394, 396, 398, 400)


def evidence_crit(n: int, p: int, alpha: float = ALPHA_EV) -> float:
    return float(chi2.ppf(1.0 - alpha, n - p))


def _neutral_sweep_indices() -> list[int]:
    total = R * M
    return [
        NEUTRAL_J0 + (NEUTRAL_SPAN * j) // (total - 1)
        for j in range(total)
    ]


def _neutral_round_indices(t: int) -> list[int]:
    assert 1 <= t <= R
    total = R * M
    j0 = (t - 1) * M
    return [
        NEUTRAL_J0 + (NEUTRAL_SPAN * j) // (total - 1)
        for j in range(j0, j0 + M)
    ]


def _hump_exclusion_trace(
    xs: np.ndarray,
    ys: np.ndarray,
    alpha: float,
    fit_rng: np.random.Generator,
) -> dict[str, Any]:
    """Mirror loop.py persistence logic for hump on growing (xs, ys)."""
    mech = FAMILIES[TRUTH_FAMILY]
    arm_fit = None
    prev_v = False
    first_violated = None
    first_excl = None
    rounds = []
    for t in range(len(xs)):
        n = t + 1
        xn = xs[:n]
        yn = ys[:n]
        z = fit(mech, xn, yn, warm=arm_fit, rng=fit_rng)
        arm_fit = z
        theta = mech.from_fit(z)
        rss = float(np.sum((mech.predict(xn, theta) - yn) ** 2))
        stat = rss / (SIGMA * SIGMA)
        crit = evidence_crit(n, mech.p, alpha)
        violated = stat > crit
        excluded = bool(violated and prev_v) if PERSIST == 2 else violated
        if violated and first_violated is None:
            first_violated = t
        if excluded and first_excl is None:
            first_excl = t
        rounds.append({"t": t, "n": n, "stat": stat, "crit": crit, "violated": violated, "excluded": excluded})
        prev_v = violated
    return {
        "excluded": first_excl is not None,
        "t_excl": first_excl,
        "first_violated": first_violated,
        "rounds": rounds,
    }


def simulate_neutral_sequential(
    seed: int, alpha: float = ALPHA_EV
) -> dict[str, Any]:
    """Full 25-round Neutral fixed sweep; truth=hump evidence trace."""
    from .rng import fit_rng
    from .world import World

    world = World(seed)
    measured = list(X0_IDX)
    fr = fit_rng(seed)
    prev_v = False
    first_violated: int | None = None
    first_excl: int | None = None
    mech = FAMILIES[TRUTH_FAMILY]
    arm_fit = None
    trace: list[dict[str, Any]] = []

    def _step(t: int) -> None:
        nonlocal prev_v, first_violated, first_excl, arm_fit
        order = sorted(measured)
        xs = np.array([world.x(i) for i in order])
        ys = np.array([world.y(i) for i in order])
        n = len(xs)
        z = fit(mech, xs, ys, warm=arm_fit, rng=fr)
        arm_fit = z
        theta = mech.from_fit(z)
        rss = float(np.sum((mech.predict(xs, theta) - ys) ** 2))
        stat = rss / (SIGMA * SIGMA)
        crit = evidence_crit(n, mech.p, alpha)
        violated = stat > crit
        excluded = bool(violated and prev_v)
        if violated and first_violated is None:
            first_violated = t
        if excluded and first_excl is None:
            first_excl = t
        trace.append({"t": t, "n": n, "stat": stat, "crit": crit, "violated": violated, "excluded": excluded})
        prev_v = violated

    _step(0)
    for t in range(1, R + 1):
        for idx in _neutral_round_indices(t):
            measured.append(idx)
        _step(t)

    return {
        "seed": seed,
        "alpha": alpha,
        "excluded": first_excl is not None,
        "t_excl": first_excl,
        "first_violated": first_violated,
        "trace": trace,
    }


def run_loop_b2_truth_check(
    seeds: tuple[int, ...],
    *,
    do_perturb: bool = False,
) -> dict[str, Any]:
    """Formal 25-round loop check (both arms); mirrors confirmatory pilot usage."""
    from .loop import run_seed

    per_seed: list[dict[str, Any]] = []
    for seed in seeds:
        rec = run_seed(seed, do_perturb=do_perturb)
        arms = {}
        for kind in ("native", "neutral"):
            final = rec["arms"][kind]["final"]
            arms[kind] = {
                "truth_excluded": bool(final["excluded"]["hump"]),
                "t_excl": final["t_excl"]["hump"],
            }
        per_seed.append({"seed": seed, **arms})
    native_k = sum(1 for r in per_seed if r["native"]["truth_excluded"])
    neutral_k = sum(1 for r in per_seed if r["neutral"]["truth_excluded"])
    return {
        "n_seeds": len(seeds),
        "native_truth_excluded_k": native_k,
        "neutral_truth_excluded_k": neutral_k,
        "native_excluded_seeds": [
            r["seed"] for r in per_seed if r["native"]["truth_excluded"]
        ],
        "neutral_excluded_seeds": [
            r["seed"] for r in per_seed if r["neutral"]["truth_excluded"]
        ],
        "per_seed": per_seed,
        "b2_ok": neutral_k == 0 and native_k <= 1,
    }


def run_sequential_calibration(
    seeds: tuple[int, ...] = SEQUENTIAL_SEEDS,
) -> dict[str, Any]:
    legacy = [simulate_neutral_sequential(s, ALPHA_EV_LEGACY) for s in seeds]
    current = [simulate_neutral_sequential(s, ALPHA_EV) for s in seeds]
    return {
        "n_seeds": len(seeds),
        "legacy_alpha": ALPHA_EV_LEGACY,
        "current_alpha": ALPHA_EV,
        "legacy_truth_excluded_k": sum(1 for r in legacy if r["excluded"]),
        "current_truth_excluded_k": sum(1 for r in current if r["excluded"]),
        "legacy_excluded_seeds": [r["seed"] for r in legacy if r["excluded"]],
        "current_excluded_seeds": [r["seed"] for r in current if r["excluded"]],
        "per_seed_current": [
            {"seed": r["seed"], "excluded": r["excluded"], "t_excl": r["t_excl"]}
            for r in current
        ],
    }


def check_extreme_x_pathology(seed: int = 20) -> dict[str, Any]:
    """Sanity: initial + Native-style high-x tail; check hump fit / chi2."""
    from .world import World

    world = World(seed)
    idxs = list(X0_IDX) + list(EXTREME_X_IDX)
    xs = np.array([world.x(i) for i in idxs])
    ys = np.array([world.y(i) for i in idxs])
    mech = FAMILIES[TRUTH_FAMILY]
    z = fit(mech, xs, ys, warm=None, rng=np.random.default_rng(0))
    theta = mech.from_fit(z)
    pred = mech.predict(xs, theta)
    rss = float(np.sum((pred - ys) ** 2))
    stat = rss / (SIGMA * SIGMA)
    crit_legacy = evidence_crit(len(xs), mech.p, ALPHA_EV_LEGACY)
    crit_current = evidence_crit(len(xs), mech.p, ALPHA_EV)
    min_pred = float(np.min(pred))
    return {
        "seed": seed,
        "n": len(xs),
        "stat": stat,
        "crit_legacy": crit_legacy,
        "crit_current": crit_current,
        "excluded_legacy": stat > crit_legacy,
        "excluded_current": stat > crit_current,
        "min_hump_pred": min_pred,
        "fit_params": theta,
        "pathology": min_pred < 0.05,
    }


def _arm_exclusion(xs: np.ndarray, ys: np.ndarray, family: str) -> bool:
    mech = FAMILIES[family]
    prev = False
    for _ in range(PERSIST):
        z = fit(mech, xs, ys, warm=None, rng=np.random.default_rng(0))
        theta = mech.from_fit(z)
        rss = float(np.sum((mech.predict(xs, theta) - ys) ** 2))
        stat = rss / (SIGMA * SIGMA)
        crit = evidence_crit(len(xs), mech.p)
        violated = stat > crit
        excluded = violated and prev
        prev = violated
        if excluded:
            return True
    return False


def _initial_truth_obs(seed: int = 1) -> tuple[np.ndarray, np.ndarray]:
    from .world import World

    w = World(seed)
    idxs = list(X0_IDX)
    xs = np.array([w.x(i) for i in idxs])
    ys = np.array([w.y(i) for i in idxs])
    return xs, ys


def _late_discriminative_obs(seed: int = 1) -> tuple[np.ndarray, np.ndarray]:
    from .world import World

    w = World(seed)
    idxs = list(X0_IDX) + _neutral_sweep_indices()
    xs = np.array([w.x(i) for i in idxs])
    ys = np.array([w.y(i) for i in idxs])
    return xs, ys


def run_calibration(seed: int = 1) -> dict[str, Any]:
    xs0, ys0 = _initial_truth_obs(seed)
    xs1, ys1 = _late_discriminative_obs(seed)

    hump_ok_initial = not _arm_exclusion(xs0, ys0, TRUTH_FAMILY)
    false_excluded_late = {h: _arm_exclusion(xs1, ys1, h) for h in FALSE_FAMILIES}
    hump_ok_late = not _arm_exclusion(xs1, ys1, TRUTH_FAMILY)

    perm = ys1.copy()
    rng = np.random.default_rng(seed + 999)
    rng.shuffle(perm)
    scrambled_any_excluded = any(_arm_exclusion(xs1, perm, h) for h in FAMILIES)

    ok = hump_ok_initial and hump_ok_late and all(false_excluded_late.values()) and scrambled_any_excluded
    return {
        "ok": ok,
        "seed": seed,
        "hump_compatible_initial": hump_ok_initial,
        "hump_compatible_late": hump_ok_late,
        "false_excluded_late": false_excluded_late,
        "all_false_excluded_late": all(false_excluded_late.values()),
        "scrambled_any_excluded": scrambled_any_excluded,
    }


def run_calibration_batch(
    seeds: tuple[int, ...] = CALIBRATION_SEEDS,
    *,
    loop_check_seeds: tuple[int, ...] = B2_LOOP_CHECK_SEEDS,
) -> dict[str, Any]:
    per_seed = [run_calibration(s) for s in seeds]
    sequential = run_sequential_calibration(SEQUENTIAL_SEEDS)
    pathology = check_extreme_x_pathology(20)
    loop_b2 = run_loop_b2_truth_check(loop_check_seeds)
    ok = (
        all(r["ok"] for r in per_seed)
        and sequential["current_truth_excluded_k"] == 0
        and not pathology["excluded_current"]
        and not pathology["pathology"]
        and loop_b2["b2_ok"]
    )
    return {
        "ok": ok,
        "version": "pilot-v1.1.2-b2-v2",
        "seeds": list(seeds),
        "n_seeds": len(seeds),
        "n_hump_initial_ok": sum(1 for r in per_seed if r["hump_compatible_initial"]),
        "n_all_false_excluded_late": sum(1 for r in per_seed if r["all_false_excluded_late"]),
        "sequential": sequential,
        "extreme_x_pathology": pathology,
        "loop_b2_check": loop_b2,
        "alpha_ev": ALPHA_EV,
        "per_seed": per_seed,
    }
