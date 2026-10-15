"""
Analysis: local amplification, early stochastic dispersion, summaries.

No figure code. No legacy terminal-threshold estimator of R_id=1.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

from .config import (
    D1_FLOOR,
    EARLY_TS,
    K_PRIMARY,
    K_ROBUST,
    LOCAL_EPSILONS,
    NUMERICAL_FLOOR,
    BudgetConfig,
    StochasticGrid,
)
from .deterministic import iterate_deterministic
from .dynamics import R_id, alpha_c
from .stochastic import ArmKind, simulate_trajectory


SUMMARY_COLUMNS = [
    "arm",
    "alpha",
    "mu",
    "R_id",
    "N",
    "beta",
    "q0_mode",
    "n_seeds",
    "P_collapse",
    "P_A",
    "P_B",
    "directional_asymmetry",
    "median_q_T",
    "mean_q_T",
    "median_H_T",
    "mean_H_T",
    "median_N_eff_T",
    "mean_N_eff_T",
    "median_tau_among_collapsed",
    "fraction_terminal_collapsed",
    "median_abs_qT_minus_half",
    "mean_abs_qT_minus_half",
    "distance_to_threshold",
]


def summarize_condition(df: pd.DataFrame) -> pd.DataFrame:
    keys = ["arm", "alpha", "mu", "N", "beta", "q0_mode"]
    if "q0_mode" not in df.columns:
        df = df.copy()
        df["q0_mode"] = "exact"
    rows = []
    for key, g in df.groupby(keys, sort=True):
        arm, alpha, mu, N, beta, q0_mode = key
        R = float(g["R_id"].iloc[0])
        collapsed = g["collapsed"].astype(bool)
        direction = g["collapse_direction"]
        p_coll = float(collapsed.mean())
        p_a = float((direction == "A").mean())
        p_b = float((direction == "B").mean())
        taus = g.loc[collapsed, "collapse_time"].astype(float)
        med_tau = float(np.nanmedian(taus)) if collapsed.any() else float("nan")
        rows.append(
            {
                "arm": arm,
                "alpha": float(alpha),
                "mu": float(mu),
                "R_id": R,
                "N": int(N),
                "beta": float(beta),
                "q0_mode": q0_mode,
                "n_seeds": int(len(g)),
                "P_collapse": p_coll,
                "P_A": p_a,
                "P_B": p_b,
                "directional_asymmetry": p_a - p_b,
                "median_q_T": float(g["q_T"].median()),
                "mean_q_T": float(g["q_T"].mean()),
                "median_H_T": float(g["H_T"].median()),
                "mean_H_T": float(g["H_T"].mean()),
                "median_N_eff_T": float(g["N_eff_T"].median()),
                "mean_N_eff_T": float(g["N_eff_T"].mean()),
                "median_tau_among_collapsed": med_tau,
                "fraction_terminal_collapsed": p_coll,
                "median_abs_qT_minus_half": float(g["abs_qT_minus_half"].median()),
                "mean_abs_qT_minus_half": float(g["abs_qT_minus_half"].mean()),
                "distance_to_threshold": R - 1.0,
            }
        )
    out = pd.DataFrame(rows)
    for c in SUMMARY_COLUMNS:
        if c not in out.columns:
            out[c] = np.nan
    return out[SUMMARY_COLUMNS]


def seed_summary_schema_ok(df: pd.DataFrame) -> bool:
    required = {
        "alpha", "mu", "R_id", "N", "beta", "seed", "q0", "q_T", "H_T",
        "collapsed", "collapse_direction", "collapse_time", "N_eff_0", "N_eff_T",
        "delta_N_eff", "arm",
    }
    return required.issubset(set(df.columns))


# ----- Experiment 1–2: deterministic local amplification -----


def local_growth_from_trajectory(
    traj: np.ndarray,
    *,
    K: int,
    numerical_floor: float = NUMERICAL_FLOOR,
) -> dict[str, float]:
    q0 = float(traj[0])
    qK = float(traj[min(K, len(traj) - 1)])
    d0 = q0 - 0.5
    dK = qK - 0.5
    abs_d0 = abs(d0)
    abs_dK = abs(dK)
    if abs_d0 < numerical_floor:
        return {
            "delta_0": d0,
            "delta_K": dK,
            "A_K": float("nan"),
            "lambda_emp": float("nan"),
            "valid": 0.0,
        }
    A = abs_dK / abs_d0
    ratio = max(abs_dK, numerical_floor) / abs_d0
    lam = (1.0 / K) * math.log(ratio)
    return {
        "delta_0": d0,
        "delta_K": dK,
        "A_K": float(A),
        "lambda_emp": float(lam),
        "valid": 1.0,
    }


def run_deterministic_local_growth(
    alphas: tuple[float, ...] | None = None,
    mus: tuple[float, ...] | None = None,
    epsilons: tuple[float, ...] = LOCAL_EPSILONS,
    beta: float = 0.0,
    T: int = 20,
) -> pd.DataFrame:
    grid = StochasticGrid()
    alphas = alphas or grid.alphas
    mus = mus or grid.mus
    rows = []
    for mu in mus:
        for alpha in alphas:
            R = R_id(alpha, mu)
            lam_th = math.log(R) if R > 0 else float("-inf")
            for eps in epsilons:
                for side, q0 in (("minus", 0.5 - eps), ("plus", 0.5 + eps)):
                    traj = iterate_deterministic(q0, alpha, mu, beta=beta, T=T)
                    g5 = local_growth_from_trajectory(traj, K=K_PRIMARY)
                    g10 = local_growth_from_trajectory(traj, K=K_ROBUST)
                    pred = 1 if R > 1 else (-1 if R < 1 else 0)
                    emp5 = (
                        1
                        if g5["lambda_emp"] > 0
                        else (-1 if g5["lambda_emp"] < 0 else 0)
                    )
                    rows.append(
                        {
                            "mu": mu,
                            "alpha": alpha,
                            "R_id": R,
                            "beta": beta,
                            "epsilon": eps,
                            "side": side,
                            "q0": q0,
                            "lambda_theory": lam_th,
                            "lambda_emp_K5": g5["lambda_emp"],
                            "lambda_emp_K10": g10["lambda_emp"],
                            "A5": g5["A_K"],
                            "A10": g10["A_K"],
                            "delta_0": g5["delta_0"],
                            "delta_5": g5["delta_K"],
                            "delta_10": g10["delta_K"],
                            "predicted_sign": pred,
                            "empirical_sign_K5": emp5,
                            "sign_match_K5": int(pred == emp5) if pred != 0 else int(emp5 == 0),
                            "valid_K5": int(g5["valid"]),
                            "valid_K10": int(g10["valid"]),
                        }
                    )
    return pd.DataFrame(rows)


def threshold_alignment(growth: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (mu, eps, side), g in growth.groupby(["mu", "epsilon", "side"], sort=True):
        g = g.sort_values("alpha")
        theory = float(alpha_c(float(mu)))
        alphas = g["alpha"].to_numpy()
        lams = g["lambda_emp_K5"].to_numpy()
        interval_lo = float("nan")
        interval_hi = float("nan")
        exact = float("nan")
        status = "NO_CROSSING"
        for i in range(len(alphas) - 1):
            if abs(lams[i]) < 1e-12:
                exact = float(alphas[i])
                status = "EXACT_GRID"
                interval_lo = interval_hi = exact
                break
            if lams[i] <= 0.0 and lams[i + 1] >= 0.0:
                interval_lo = float(alphas[i])
                interval_hi = float(alphas[i + 1])
                status = "INTERVAL"
                break
        aligned = False
        if status == "EXACT_GRID":
            aligned = abs(theory - exact) < 1e-9
        elif status == "INTERVAL":
            aligned = interval_lo - 1e-12 <= theory <= interval_hi + 1e-12
        rows.append(
            {
                "mu": float(mu),
                "epsilon": float(eps),
                "side": side,
                "theory_alpha_c": theory,
                "empirical_crossing_lo": interval_lo,
                "empirical_crossing_hi": interval_hi,
                "status": status,
                "aligned": bool(aligned) if status != "NO_CROSSING" else False,
                "resolvable": status != "NO_CROSSING",
            }
        )
    return pd.DataFrame(rows)


def growth_law_summary(growth: pd.DataFrame) -> pd.DataFrame:
    df = growth[
        (growth["valid_K5"] == 1)
        & (growth["epsilon"] <= 0.005)
        & (growth["R_id"] >= 0.7)
        & (growth["R_id"] <= 1.4)
    ].copy()
    rows = []

    def _one(label: str, g: pd.DataFrame) -> dict[str, Any]:
        x = g["lambda_theory"].to_numpy()
        y = g["lambda_emp_K5"].to_numpy()
        if len(g) < 3:
            return {
                "subset": label,
                "n": int(len(g)),
                "pearson_r": float("nan"),
                "spearman_rho": float("nan"),
                "MAE": float("nan"),
                "RMSE": float("nan"),
            }
        return {
            "subset": label,
            "n": int(len(g)),
            "pearson_r": float(stats.pearsonr(x, y).statistic),
            "spearman_rho": float(stats.spearmanr(x, y).statistic),
            "MAE": float(np.mean(np.abs(y - x))),
            "RMSE": float(np.sqrt(np.mean((y - x) ** 2))),
        }

    for eps, g in df.groupby("epsilon", sort=True):
        rows.append(_one(f"epsilon={eps}", g))
    rows.append(_one("pooled", df))
    return pd.DataFrame(rows)


# ----- Experiment 3–4: early stochastic -----


def early_dispersion_from_trajectories(
    trajs: dict[int, np.ndarray],
    *,
    times: tuple[int, ...] = EARLY_TS,
) -> dict[str, float]:
    M = np.vstack([np.abs(traj - 0.5) for traj in trajs.values()])
    out: dict[str, float] = {"n_seeds": float(len(trajs))}
    D: dict[int, float] = {}
    for t in times:
        D[t] = float(np.mean(M[:, t])) if t < M.shape[1] else float("nan")
        out[f"D_{t}"] = D[t]
    d1 = D.get(1, float("nan"))
    out["D_1"] = d1
    out["D1_valid"] = float(np.isfinite(d1) and d1 >= D1_FLOOR)
    for t in times:
        if t == 1:
            continue
        out[f"Delta_D_{t}"] = (
            D[t] - d1 if np.isfinite(d1) and np.isfinite(D[t]) else float("nan")
        )
        if out["D1_valid"] and np.isfinite(D[t]):
            out[f"A_stoch_{t}"] = D[t] / d1
        else:
            out[f"A_stoch_{t}"] = float("nan")
    return out


def simulate_early_condition(
    *,
    alpha: float,
    mu: float,
    N: int,
    beta: float,
    n_seeds: int,
    arm: ArmKind,
    T_early: int = 20,
    seed_offset: int = 0,
    q0: float = 0.5,
) -> dict[str, Any]:
    trajs: dict[int, np.ndarray] = {}
    for s in range(n_seeds):
        seed = seed_offset + s
        trajs[seed] = simulate_trajectory(
            q0, T=T_early, N=N, alpha=alpha, mu=mu, beta=beta, seed=seed, arm=arm
        )
    disp = early_dispersion_from_trajectories(trajs)
    return {
        "arm": arm,
        "alpha": alpha,
        "mu": mu,
        "R_id": R_id(alpha, mu),
        "N": N,
        "beta": beta,
        "n_seeds": n_seeds,
        **disp,
    }


def run_stochastic_early_grid(
    grid: StochasticGrid | None = None,
    *,
    n_seeds: int | None = None,
    arms: tuple[ArmKind, ...] = ("recursive", "no_recursion"),
) -> pd.DataFrame:
    grid = grid or StochasticGrid()
    ns = grid.n_seeds if n_seeds is None else n_seeds
    rows = []
    for arm in arms:
        for mu in grid.mus:
            for alpha in grid.alphas:
                rows.append(
                    simulate_early_condition(
                        alpha=alpha,
                        mu=mu,
                        N=grid.N,
                        beta=grid.beta,
                        n_seeds=ns,
                        arm=arm,
                    )
                )
    return pd.DataFrame(rows)


def recursive_vs_nr_early(early: pd.DataFrame) -> pd.DataFrame:
    rec = early[early["arm"] == "recursive"].set_index(["mu", "alpha", "N", "beta"])
    nr = early[early["arm"] == "no_recursion"].set_index(["mu", "alpha", "N", "beta"])
    rows = []
    for key in rec.index.intersection(nr.index):
        r = rec.loc[key]
        n = nr.loc[key]
        if isinstance(r, pd.DataFrame):
            r = r.iloc[0]
        if isinstance(n, pd.DataFrame):
            n = n.iloc[0]
        a_ex = (
            float(r["A_stoch_10"] - n["A_stoch_10"])
            if np.isfinite(r["A_stoch_10"]) and np.isfinite(n["A_stoch_10"])
            else float("nan")
        )
        rows.append(
            {
                "mu": key[0],
                "alpha": key[1],
                "N": key[2],
                "beta": key[3],
                "R_id": float(r["R_id"]),
                "D1_rec": float(r["D_1"]),
                "D10_rec": float(r["D_10"]),
                "A10_rec": float(r["A_stoch_10"]),
                "D1_nr": float(n["D_1"]),
                "D10_nr": float(n["D_10"]),
                "A10_nr": float(n["A_stoch_10"]),
                "Amplification_excess_10": a_ex,
                "Dispersion_excess_10": float(r["D_10"]) - float(n["D_10"]),
            }
        )
    return pd.DataFrame(rows)


def run_budget_early(
    cfg: BudgetConfig | None = None,
    *,
    n_seeds: int | None = None,
) -> pd.DataFrame:
    cfg = cfg or BudgetConfig()
    ns = cfg.n_seeds if n_seeds is None else n_seeds
    rows = []
    for label, (mu, alpha) in (("below", cfg.below), ("above", cfg.above)):
        for N in cfg.Ns:
            for arm in ("recursive", "no_recursion"):
                row = simulate_early_condition(
                    alpha=alpha,
                    mu=mu,
                    N=N,
                    beta=cfg.beta,
                    n_seeds=ns,
                    arm=arm,  # type: ignore[arg-type]
                )
                row["budget_regime"] = label
                rows.append(row)
    return pd.DataFrame(rows)


def attach_terminal_consequence(
    vs_early: pd.DataFrame,
    phase_summary: pd.DataFrame | None,
    nr_summary: pd.DataFrame | None,
) -> pd.DataFrame:
    """Join verified terminal summaries onto early Rec vs NR table."""
    out = vs_early.copy()
    if phase_summary is None or nr_summary is None:
        out["P_collapse_rec"] = "MISSING"
        out["P_collapse_nr"] = "MISSING"
        out["median_H_T_rec"] = "MISSING"
        out["median_H_T_nr"] = "MISSING"
        return out

    def _lookup(summary: pd.DataFrame, mu: float, alpha: float, N: int, beta: float) -> pd.Series | None:
        m = summary[
            np.isclose(summary["mu"], mu)
            & np.isclose(summary["alpha"], alpha)
            & (summary["N"] == N)
            & np.isclose(summary["beta"], beta)
        ]
        if "arm" in m.columns:
            # prefer matching if present; phase may be recursive-only
            pass
        return m.iloc[0] if len(m) else None

    pc_r, pc_n, h_r, h_n = [], [], [], []
    for _, row in out.iterrows():
        rr = _lookup(phase_summary, row["mu"], row["alpha"], int(row["N"]), row["beta"])
        nn = _lookup(nr_summary, row["mu"], row["alpha"], int(row["N"]), row["beta"])
        pc_r.append(float(rr["P_collapse"]) if rr is not None else float("nan"))
        pc_n.append(float(nn["P_collapse"]) if nn is not None else float("nan"))
        h_r.append(float(rr["median_H_T"]) if rr is not None else float("nan"))
        h_n.append(float(nn["median_H_T"]) if nn is not None else float("nan"))
    out["P_collapse_rec"] = pc_r
    out["P_collapse_nr"] = pc_n
    out["median_H_T_rec"] = h_r
    out["median_H_T_nr"] = h_n
    return out


def load_verified_summary(path: Path) -> pd.DataFrame | None:
    if path.is_file():
        return pd.read_csv(path)
    return None
