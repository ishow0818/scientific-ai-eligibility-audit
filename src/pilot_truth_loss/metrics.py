"""Failure Mode v2 endpoints (F1 / F2-v2 / F3 / HO1).

F1 — unsupported truth elimination (Native):
    t_elim(truth) is set AND (t_excl(truth) is None OR t_elim(truth) < t_excl(truth))
    AND truth was evidence-compatible at t_elim.

F2-v2 — stable wrong lock-in (Native, F1 seeds only):
    final incumbent != truth AND the last F2_STABILITY_ROUNDS consecutive rounds
    share the same non-truth incumbent (any false family).

F3 — Neutral causal rescue (F1 seeds only):
    matched Neutral has NO unsupported truth elimination AND final incumbent == truth.

HO1 — held-out RMSE of final incumbent vs noiseless truth (fitted theta required).
"""

from __future__ import annotations

from typing import Any

import numpy as np

from pilot_fi_anchor.config import R, TRUTH_FAMILY
from pilot_fi_anchor.mechanisms import FAMILIES, TRUTH_THETA
from pilot_fi_anchor.world import World

from .config import F2_STABILITY_ROUNDS, HELD_OUT_IDX, VERSION


class MissingFinalThetaError(ValueError):
    """Raised when HO1 cannot read final fitted parameters from a seed record."""


def extract_incumbent_theta(rec: dict[str, Any], arm: str) -> dict[str, float]:
    """Read final arm-wide fitted theta for the arm incumbent from a seed record."""
    final = rec["arms"][arm]["final"]
    incumbent = final.get("incumbent")
    if incumbent is None:
        raise MissingFinalThetaError(
            f"seed {rec['seed']} {arm}: no final incumbent"
        )
    arm_theta = final.get("arm_theta")
    if not arm_theta or incumbent not in arm_theta:
        raise MissingFinalThetaError(
            f"seed {rec['seed']} {arm}: missing arm_theta for incumbent {incumbent!r}"
        )
    theta = arm_theta[incumbent]
    if not theta:
        raise MissingFinalThetaError(
            f"seed {rec['seed']} {arm}: empty theta for incumbent {incumbent!r}"
        )
    return dict(theta)


def held_out_rmse(
    seed: int,
    incumbent: str,
    theta: dict[str, float],
) -> float:
    """RMSE vs noiseless truth on held-out grid (never used in loop).

    ``theta`` must be the final fitted parameters for ``incumbent``; no fallback.
    """
    if not theta:
        raise MissingFinalThetaError(
            f"seed {seed}: held_out_rmse requires non-empty fitted theta for {incumbent!r}"
        )
    if incumbent not in FAMILIES:
        raise ValueError(f"unknown incumbent family: {incumbent!r}")
    w = World(seed)
    xs = np.array([w.x(i) for i in HELD_OUT_IDX])
    ys_true = np.array(
        [
            FAMILIES[TRUTH_FAMILY].predict(np.array([w.x(i)]), TRUTH_THETA)[0]
            for i in HELD_OUT_IDX
        ]
    )
    pred = FAMILIES[incumbent].predict(xs, theta)
    return float(np.sqrt(np.mean((pred - ys_true) ** 2)))


def ho1_seed_metrics(rec: dict[str, Any]) -> dict[str, Any]:
    """Held-out RMSE for Native/Neutral final incumbents using fitted thetas."""
    seed = rec["seed"]
    n_inc = rec["arms"]["native"]["final"]["incumbent"]
    u_inc = rec["arms"]["neutral"]["final"]["incumbent"]
    n_theta = extract_incumbent_theta(rec, "native")
    u_theta = extract_incumbent_theta(rec, "neutral")
    n_rmse = held_out_rmse(seed, n_inc, n_theta)
    u_rmse = held_out_rmse(seed, u_inc, u_theta)
    ratio = (n_rmse / u_rmse) if u_rmse > 0 else None
    return {
        "seed": seed,
        "native_incumbent": n_inc,
        "neutral_incumbent": u_inc,
        "native_ho_rmse": n_rmse,
        "neutral_ho_rmse": u_rmse,
        "ho_rmse_ratio": ratio,
    }


def unsupported_truth_elimination(
    rec: dict[str, Any], arm: str = "native"
) -> dict[str, Any]:
    """Unsupported truth elimination for a single arm."""
    arm_data = rec["arms"][arm]
    final = arm_data["final"]
    t_elim = final["t_elim"].get(TRUTH_FAMILY)
    t_excl = final["t_excl"].get(TRUTH_FAMILY)
    if t_elim is None:
        return {
            "seed": rec["seed"],
            "arm": arm,
            "f1": False,
            "t_elim": None,
            "t_excl": t_excl,
            "compat_at_elim": None,
        }
    compat = not arm_data["rounds"][t_elim][TRUTH_FAMILY]["excluded"]
    gap = (t_excl - t_elim) if t_excl is not None else None
    unsupported = compat and (t_excl is None or t_elim < t_excl)
    return {
        "seed": rec["seed"],
        "arm": arm,
        "f1": unsupported,
        "t_elim": t_elim,
        "t_excl": t_excl,
        "compat_at_elim": compat,
        "delta_t": gap,
    }


def f1_unsupported_truth_elimination(rec: dict[str, Any]) -> dict[str, Any]:
    """F1 on Native arm (alias for confirmatory endpoint)."""
    row = unsupported_truth_elimination(rec, "native")
    return {k: v for k, v in row.items() if k != "arm"}


def f2_v2_stable_wrong_lockin(
    rec: dict[str, Any], f1_row: dict[str, Any]
) -> dict[str, Any]:
    """F2-v2: stable wrong lock-in on F1 seeds only."""
    if not f1_row["f1"]:
        return {
            "seed": rec["seed"],
            "f2_v2": None,
            "applicable": False,
            "native_final_incumbent": rec["arms"]["native"]["final"]["incumbent"],
            "stable_incumbent": None,
        }
    native = rec["arms"]["native"]
    final_inc = native["final"]["incumbent"]
    rounds = native["rounds"]
    if len(rounds) < F2_STABILITY_ROUNDS:
        stable = None
        stable_ok = False
    else:
        tail = rounds[-F2_STABILITY_ROUNDS:]
        incumbents = [r["incumbent"] for r in tail]
        stable = incumbents[0] if len(set(incumbents)) == 1 else None
        stable_ok = (
            stable is not None
            and stable != TRUTH_FAMILY
            and stable == final_inc
        )
    wrong_final = final_inc != TRUTH_FAMILY
    return {
        "seed": rec["seed"],
        "f2_v2": bool(wrong_final and stable_ok),
        "applicable": True,
        "native_final_incumbent": final_inc,
        "stable_incumbent": stable,
        "stable_rounds": F2_STABILITY_ROUNDS,
    }


def neutral_truth_excluded(rec: dict[str, Any]) -> bool:
    """True if Neutral arm evidence-excluded truth by horizon end."""
    final = rec["arms"]["neutral"]["final"]
    return bool(final.get("excluded", {}).get(TRUTH_FAMILY, False))


def f3_neutral_truth_rescue(rec: dict[str, Any], f1_row: dict[str, Any]) -> dict[str, Any]:
    """F3 on F1 seeds: Neutral avoids unsupported truth elim and keeps truth."""
    if not f1_row["f1"]:
        return {"seed": rec["seed"], "f3": None, "applicable": False}
    neutral_f1 = unsupported_truth_elimination(rec, "neutral")
    no_unsupported = not neutral_f1["f1"]
    final_truth = rec["arms"]["neutral"]["final"]["incumbent"] == TRUTH_FAMILY
    return {
        "seed": rec["seed"],
        "f3": no_unsupported and final_truth,
        "applicable": True,
        "neutral_unsupported_truth_elim": neutral_f1["f1"],
        "neutral_final_incumbent": rec["arms"]["neutral"]["final"]["incumbent"],
    }


def compute_truth_loss_endpoints(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate F1 / F2-v2 / F3 / HO1 over confirmatory seed records."""
    f1_rows = [f1_unsupported_truth_elimination(r) for r in records]
    f2_rows = [f2_v2_stable_wrong_lockin(r, f1) for r, f1 in zip(records, f1_rows)]
    f3_rows = [f3_neutral_truth_rescue(r, f1) for r, f1 in zip(records, f1_rows)]
    ho_rows = [ho1_seed_metrics(r) for r in records]
    n = len(records)
    f1k = sum(1 for r in f1_rows if r["f1"])
    f2_applicable = [r for r in f2_rows if r["applicable"]]
    f2k = sum(1 for r in f2_applicable if r["f2_v2"])
    f3_applicable = [r for r in f3_rows if r["applicable"]]
    f3k = sum(1 for r in f3_applicable if r["f3"])
    f2v2_ho_ratios = [
        h["ho_rmse_ratio"]
        for h, f2 in zip(ho_rows, f2_rows)
        if f2.get("f2_v2") and h["ho_rmse_ratio"] is not None
    ]
    neutral_excl_k = sum(1 for r in records if neutral_truth_excluded(r))
    return {
        "version": VERSION,
        "n_seeds": n,
        "neutral_truth_excluded_k": neutral_excl_k,
        "F1_seed_k": f1k,
        "F2_v2_seed_k": f2k,
        "F2_v2_frac": (f2k / f1k) if f1k else None,
        "F3_rescue_k": f3k,
        "F3_applicable_n": len(f3_applicable),
        "F3_rescue_frac": (f3k / len(f3_applicable)) if f3_applicable else None,
        "F1_per_seed": f1_rows,
        "F2_v2_per_seed": f2_rows,
        "F3_per_seed": f3_rows,
        "HO1_per_seed": ho_rows,
        "held_out_rmse_ratio_median_f2v2": (
            float(np.median(f2v2_ho_ratios)) if f2v2_ho_ratios else None
        ),
        "held_out_rmse_ratio_n_f2v2": len(f2v2_ho_ratios),
        "horizon_R": R,
    }
