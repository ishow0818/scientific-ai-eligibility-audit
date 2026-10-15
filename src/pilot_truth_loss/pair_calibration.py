"""Phase-1 pair calibration (static + sequential evidence; no Native/Neutral loop).

Selection rule PC1–PC5 is fixed in EXPERIMENT_DESIGN.md §3.  The chosen
competitor is the false family with the **smallest** median initial-window
fitted-prediction gap vs truth among candidates passing compatibility gates.
Ties break lexicographically.  Failure rates are never used.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from pilot_fi_anchor.config import (
    FALSE_FAMILIES,
    PERSIST,
    SIGMA,
    TRUTH_FAMILY,
    X0_IDX,
)
from pilot_fi_anchor.evidence_calibration import (
    _neutral_sweep_indices,
    evidence_crit,
    simulate_neutral_sequential,
)
from pilot_fi_anchor.fitting import fit, loglik
from pilot_fi_anchor.mechanisms import FAMILIES, TRUTH_THETA
from pilot_fi_anchor.world import World

from .config import (
    COMPETITOR_FAMILY,
    EXTENDED_MIN_TAIL_DIV_SIGMA,
    EXTENDED_TAIL_X_MIN,
    HELD_OUT_IDX,
    INITIAL_MAX_GAP_SIGMA,
    PAIR_CALIBRATION_SEEDS,
)


def _initial_obs(seed: int) -> tuple[np.ndarray, np.ndarray, list[int]]:
    w = World(seed)
    idxs = list(X0_IDX)
    xs = np.array([w.x(i) for i in idxs])
    ys = np.array([w.y(i) for i in idxs])
    return xs, ys, idxs


def _extended_obs(seed: int) -> tuple[np.ndarray, np.ndarray]:
    w = World(seed)
    idxs = list(X0_IDX) + _neutral_sweep_indices()
    xs = np.array([w.x(i) for i in idxs])
    ys = np.array([w.y(i) for i in idxs])
    return xs, ys


def _evidence_compatible(mech_name: str, xs: np.ndarray, ys: np.ndarray) -> bool:
    mech = FAMILIES[mech_name]
    z = fit(mech, xs, ys, warm=None, rng=np.random.default_rng(0))
    theta = mech.from_fit(z)
    rss = float(np.sum((mech.predict(xs, theta) - ys) ** 2))
    stat = rss / (SIGMA * SIGMA)
    return stat <= evidence_crit(len(xs), mech.p)


def _evidence_excluded_persist(mech_name: str, xs: np.ndarray, ys: np.ndarray) -> bool:
    """Two-round persistence on a single static dataset (calibration proxy)."""
    mech = FAMILIES[mech_name]
    prev = False
    for _ in range(max(PERSIST, 2)):
        z = fit(mech, xs, ys, warm=None, rng=np.random.default_rng(0))
        theta = mech.from_fit(z)
        rss = float(np.sum((mech.predict(xs, theta) - ys) ** 2))
        stat = rss / (SIGMA * SIGMA)
        violated = stat > evidence_crit(len(xs), mech.p)
        excluded = violated and prev
        prev = violated
        if excluded:
            return True
    return False


def _initial_fit_gap(competitor: str, xs: np.ndarray, ys: np.ndarray) -> float:
    truth = FAMILIES[TRUTH_FAMILY]
    comp = FAMILIES[competitor]
    zt = fit(truth, xs, ys, warm=None, rng=np.random.default_rng(0))
    zc = fit(comp, xs, ys, warm=None, rng=np.random.default_rng(0))
    pt = truth.predict(xs, truth.from_fit(zt))
    pc = comp.predict(xs, comp.from_fit(zc))
    return float(np.max(np.abs(pt - pc)))


def _tail_divergence(competitor: str, xs: np.ndarray, ys: np.ndarray) -> float:
    comp = FAMILIES[competitor]
    truth = FAMILIES[TRUTH_FAMILY]
    zc = fit(comp, xs, ys, warm=None, rng=np.random.default_rng(0))
    theta_c = comp.from_fit(zc)
    mask = xs >= EXTENDED_TAIL_X_MIN
    if not np.any(mask):
        return 0.0
    xt = xs[mask]
    return float(
        np.max(np.abs(truth.predict(xt, TRUTH_THETA) - comp.predict(xt, theta_c)))
    )


def _total_loglik(mech_name: str, xs: np.ndarray, ys: np.ndarray) -> float:
    mech = FAMILIES[mech_name]
    z = fit(mech, xs, ys, warm=None, rng=np.random.default_rng(0))
    theta = mech.from_fit(z)
    return float(sum(loglik(mech, theta, float(x), float(y)) for x, y in zip(xs, ys)))


def evaluate_competitor(
    competitor: str, seeds: tuple[int, ...] = PAIR_CALIBRATION_SEEDS
) -> dict[str, Any]:
    assert competitor in FALSE_FAMILIES
    n = len(seeds)
    gaps: list[float] = []
    tails: list[float] = []
    truth_init_ok = comp_init_ok = 0
    comp_ext_excl = truth_ext_ok = 0
    truth_ll_better = 0
    for seed in seeds:
        xs0, ys0, _ = _initial_obs(seed)
        xs1, ys1 = _extended_obs(seed)
        if _evidence_compatible(TRUTH_FAMILY, xs0, ys0):
            truth_init_ok += 1
        if _evidence_compatible(competitor, xs0, ys0):
            comp_init_ok += 1
        gaps.append(_initial_fit_gap(competitor, xs0, ys0))
        tails.append(_tail_divergence(competitor, xs1, ys1))
        if _evidence_excluded_persist(competitor, xs1, ys1):
            comp_ext_excl += 1
        if _evidence_compatible(TRUTH_FAMILY, xs1, ys1):
            truth_ext_ok += 1
        ll_t = _total_loglik(TRUTH_FAMILY, xs1, ys1)
        ll_c = _total_loglik(competitor, xs1, ys1)
        if ll_t > ll_c:
            truth_ll_better += 1
    gap_med = float(np.median(gaps))
    gap_max = float(np.max(gaps))
    tail_min = float(np.min(tails))
    return {
        "competitor": competitor,
        "n_seeds": n,
        "truth_initial_compatible_k": truth_init_ok,
        "competitor_initial_compatible_k": comp_init_ok,
        "initial_gap_median": gap_med,
        "initial_gap_max": gap_max,
        "extended_competitor_excluded_k": comp_ext_excl,
        "extended_truth_compatible_k": truth_ext_ok,
        "truth_loglik_wins_k": truth_ll_better,
        "tail_divergence_min": tail_min,
        "passes_pc1": truth_init_ok == n and comp_init_ok == n,
        "passes_pc2_bound": gap_max <= INITIAL_MAX_GAP_SIGMA * SIGMA,
        "passes_pc3": comp_ext_excl == n,
        "passes_pc4": truth_ext_ok == n,
        "passes_pc5": truth_ll_better == n,
        "passes_pc6": tail_min >= EXTENDED_MIN_TAIL_DIV_SIGMA * SIGMA,
    }


def select_competitor_by_rule(
    seeds: tuple[int, ...] = PAIR_CALIBRATION_SEEDS,
) -> dict[str, Any]:
    """Apply frozen PC1–PC6 filter + minimum-gap ranking (no failure-rate input)."""
    ranked: list[tuple[str, dict[str, Any]]] = []
    for h in FALSE_FAMILIES:
        ev = evaluate_competitor(h, seeds)
        structural_ok = all(
            ev[k]
            for k in (
                "passes_pc1",
                "passes_pc2_bound",
                "passes_pc3",
                "passes_pc4",
                "passes_pc5",
                "passes_pc6",
            )
        )
        ranked.append((h, {**ev, "structural_ok": structural_ok}))
    eligible = [(h, ev) for h, ev in ranked if ev["structural_ok"]]
    if not eligible:
        chosen = None
        reason = "no candidate passes PC1–PC6"
    else:
        chosen = min(
            eligible,
            key=lambda t: (t[1]["initial_gap_median"], t[0]),
        )[0]
        reason = (
            "minimum median initial fitted-prediction gap among PC1–PC6 survivors; "
            "tie-break lexicographic family id"
        )
    return {
        "rule": "PC1-PC6 filter + min median initial_gap",
        "chosen": chosen,
        "reason": reason,
        "candidates": {h: ev for h, ev in ranked},
    }


def verify_sequential_truth_safety(
    seeds: tuple[int, ...] = PAIR_CALIBRATION_SEEDS,
) -> dict[str, Any]:
    """Truth must not be spuriously evidence-excluded under Neutral sequential path."""
    excluded = [
        s
        for s in seeds
        if simulate_neutral_sequential(s)["excluded"]
    ]
    return {
        "n_seeds": len(seeds),
        "truth_excluded_k": len(excluded),
        "excluded_seeds": excluded,
        "ok": len(excluded) == 0,
    }


def verify_held_out_disjoint() -> dict[str, Any]:
    blocked = set(X0_IDX) | set(_neutral_sweep_indices())
    overlap = [i for i in HELD_OUT_IDX if i in blocked]
    return {
        "n_held_out": len(HELD_OUT_IDX),
        "overlap_with_measured_sets": overlap,
        "ok": len(overlap) == 0 and len(HELD_OUT_IDX) >= 10,
    }


def run_pair_calibration(
    seeds: tuple[int, ...] = PAIR_CALIBRATION_SEEDS,
) -> dict[str, Any]:
    selection = select_competitor_by_rule(seeds)
    sequential = verify_sequential_truth_safety(seeds)
    held_out = verify_held_out_disjoint()
    frozen_match = (
        selection["chosen"] == COMPETITOR_FAMILY if selection["chosen"] else False
    )
    cal_ok = (
        selection["chosen"] is not None
        and sequential["ok"]
        and held_out["ok"]
        and frozen_match
    )
    return {
        "ok": cal_ok,
        "ready": cal_ok,
        "truth_family": TRUTH_FAMILY,
        "competitor_family": COMPETITOR_FAMILY,
        "selection": selection,
        "sequential_truth_safety": sequential,
        "held_out": held_out,
        "frozen_config_match": frozen_match,
    }
