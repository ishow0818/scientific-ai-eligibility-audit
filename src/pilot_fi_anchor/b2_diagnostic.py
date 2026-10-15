"""One-off B2 root-cause diagnostic (sequential vs extreme-x fitting)."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from .config import ALPHA_EV, SIGMA, TRUTH_FAMILY, X0_IDX
from .evidence_calibration import (
    ALPHA_EV_LEGACY,
    EXTREME_X_IDX,
    evidence_crit,
    simulate_neutral_sequential,
)
from .fitting import fit
from .mechanisms import FAMILIES, TRUTH_THETA
from .world import World

B2_FAIL_SEEDS = (3, 20)
OUTPUT_DIR = Path("outputs/pilot_fi_anchor")


def extreme_x_check(seed: int, sigma_override: float | None = None) -> dict:
    w = World(seed)
    idxs = list(X0_IDX) + list(EXTREME_X_IDX)
    xs = np.array([w.x(i) for i in idxs])
    mech = FAMILIES[TRUTH_FAMILY]
    if sigma_override is None:
        ys = np.array([w.y(i) for i in idxs])
        sig = SIGMA
    else:
        ys = np.array([mech.predict(w.x(i), TRUTH_THETA) for i in idxs])
        if sigma_override > 0:
            rng = np.random.default_rng(seed + 777)
            ys = ys + rng.normal(0, sigma_override, size=len(ys))
        sig = sigma_override if sigma_override > 0 else 1e-12
    z = fit(mech, xs, ys, warm=None, rng=np.random.default_rng(0))
    theta = mech.from_fit(z)
    pred = mech.predict(xs, theta)
    rss = float(np.sum((pred - ys) ** 2))
    stat = rss / (sig * sig)
    n, p = len(xs), mech.p
    return {
        "seed": seed,
        "sigma": sig,
        "n": n,
        "stat": stat,
        "crit_legacy": evidence_crit(n, p, ALPHA_EV_LEGACY),
        "crit_current": evidence_crit(n, p, ALPHA_EV),
        "excl_legacy": stat > evidence_crit(n, p, ALPHA_EV_LEGACY),
        "excl_current": stat > evidence_crit(n, p, ALPHA_EV),
        "min_pred": float(np.min(pred)),
        "fit": theta,
    }


def pilot_hump_trace(seed: int) -> dict:
    path = OUTPUT_DIR / f"seed_{seed:02d}.json"
    if not path.exists():
        return {"seed": seed, "missing": True}
    rec = json.loads(path.read_text(encoding="utf-8"))
    out = {"seed": seed, "version": rec.get("version"), "arms": {}}
    for arm in ("native", "neutral"):
        rounds = rec["arms"][arm]["rounds"]
        t_excl = next((r["t"] for r in rounds if r["hump"]["excluded"]), None)
        violations = [
            {
                "t": r["t"],
                "n_arm": r["n_arm"],
                "violated": r["hump"]["violated"],
                "excluded": r["hump"]["excluded"],
            }
            for r in rounds
            if r["hump"]["violated"] or r["hump"]["excluded"]
        ]
        out["arms"][arm] = {"t_excl": t_excl, "violations": violations}
    return out


def run_b2_diagnostic() -> dict:
    sequential = {
        "legacy": {
            "alpha": ALPHA_EV_LEGACY,
            "excluded_seeds": [
                s
                for s in range(1, 21)
                if simulate_neutral_sequential(s, ALPHA_EV_LEGACY)["excluded"]
            ],
        },
        "current": {
            "alpha": ALPHA_EV,
            "excluded_seeds": [
                s
                for s in range(1, 21)
                if simulate_neutral_sequential(s, ALPHA_EV)["excluded"]
            ],
        },
    }
    extreme = {}
    for seed in B2_FAIL_SEEDS:
        extreme[seed] = {
            "sigma_0.5": extreme_x_check(seed, None),
            "sigma_0": extreme_x_check(seed, 0.0),
            "sigma_0.1": extreme_x_check(seed, 0.1),
        }
    pilot = {s: pilot_hump_trace(s) for s in B2_FAIL_SEEDS}
    legacy_k = len(sequential["legacy"]["excluded_seeds"])
    current_k = len(sequential["current"]["excluded_seeds"])
    any_pathology = any(
        r["sigma_0"]["min_pred"] < 0.05 or r["sigma_0"]["excl_legacy"]
        for r in extreme.values()
    )
    verdict = (
        "fitting_pathology"
        if any_pathology
        else "sequential_calibration"
        if legacy_k > 0 and current_k == 0
        else "mixed_or_other"
    )
    return {
        "verdict": verdict,
        "sequential": sequential,
        "extreme_x": extreme,
        "pilot_v111_traces": pilot,
        "b2_v2_recommendation": (
            "minimal sequential Bonferroni fix (ALPHA_EV = 0.05/(5*R)); no fitting change"
            if verdict == "sequential_calibration"
            else "fix hump fitting at extreme-x before any alpha relaxation"
            if verdict == "fitting_pathology"
            else "investigate mixed causes (native arm vs neutral; seed-specific)"
        ),
    }


if __name__ == "__main__":
    import json as _json

    print(_json.dumps(run_b2_diagnostic(), indent=2))
