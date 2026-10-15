"""Independent evaluation grid — midpoints off the measurable candidate pool."""
from __future__ import annotations

import numpy as np

from pilot_fi_anchor.config import N_CAND, X_MAX, X_MIN
from pilot_fi_anchor.mechanisms import FAMILIES, TRUTH, TRUTH_THETA

from .config import EVAL_PROTOCOL_VERSION


def measurable_grid() -> np.ndarray:
    return np.linspace(X_MIN, X_MAX, N_CAND)


def eval_x_midpoints() -> np.ndarray:
    """400 midpoints between consecutive measurable grid nodes."""
    g = measurable_grid()
    return 0.5 * (g[:-1] + g[1:])


EVAL_X_MIDPOINTS = eval_x_midpoints()


def assert_eval_disjoint_from_measurable(atol: float = 1e-15) -> None:
    g = measurable_grid()
    ex = EVAL_X_MIDPOINTS
    for x in ex:
        if np.any(np.abs(g - x) <= atol):
            raise AssertionError(f"eval x={x} collides with measurable grid")


def truth_noiseless(xs: np.ndarray | None = None) -> np.ndarray:
    xs = EVAL_X_MIDPOINTS if xs is None else np.asarray(xs, dtype=float)
    return np.asarray(TRUTH.predict(xs, TRUTH_THETA), dtype=float)


def rmse_fail_zero_predictor(xs: np.ndarray | None = None) -> float:
    """Frozen penalty: RMSE of f̂≡0 vs noiseless truth."""
    f = truth_noiseless(xs)
    return float(np.sqrt(np.mean(f * f)))


RMSE_FAIL = rmse_fail_zero_predictor()


def rmse_noiseless(
    family: str | None,
    theta: dict[str, float] | None,
    xs: np.ndarray | None = None,
) -> tuple[float | None, str]:
    """Return (RMSE, status). status OK or DECISION_EMPTY."""
    if family is None or theta is None:
        return None, "DECISION_EMPTY"
    xs = EVAL_X_MIDPOINTS if xs is None else np.asarray(xs, dtype=float)
    mech = FAMILIES[family]
    pred = np.asarray(mech.predict(xs, theta), dtype=float)
    f = truth_noiseless(xs)
    return float(np.sqrt(np.mean((f - pred) ** 2))), "OK"


def eval_meta() -> dict:
    return {
        "eval_protocol_version": EVAL_PROTOCOL_VERSION,
        "n_eval": int(len(EVAL_X_MIDPOINTS)),
        "n_measurable": int(N_CAND),
        "rmse_fail_zero_predictor": RMSE_FAIL,
        "x_min": float(EVAL_X_MIDPOINTS.min()),
        "x_max": float(EVAL_X_MIDPOINTS.max()),
    }
