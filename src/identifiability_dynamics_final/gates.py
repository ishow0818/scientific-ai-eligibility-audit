"""Final Gates G1–G7 (local amplification aligned). No legacy KILL-E."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def evaluate_final_gates(
    *,
    growth: pd.DataFrame,
    alignment: pd.DataFrame,
    law: pd.DataFrame,
    vs_nr: pd.DataFrame,
    large_n: pd.DataFrame,
    phase_summary: pd.DataFrame | None,
    bias_summary: pd.DataFrame | None,
) -> dict[str, Any]:
    g = growth[growth["valid_K5"] == 1]
    low = g[g["R_id"] <= 0.95]
    high = g[g["R_id"] >= 1.05]
    frac_low = float((low["lambda_emp_K5"] < 0).mean()) if len(low) else float("nan")
    frac_high = float((high["lambda_emp_K5"] > 0).mean()) if len(high) else float("nan")
    g1 = bool(frac_low >= 0.90 and frac_high >= 0.90)

    resolvable = alignment[alignment["resolvable"]]
    if len(resolvable) == 0:
        g2_status = "UNRESOLVED"
        g2 = False
        frac_aligned = float("nan")
    else:
        frac_aligned = float(resolvable["aligned"].mean())
        g2 = frac_aligned >= 0.80
        g2_status = "PASS" if g2 else "FAIL"

    pooled = law[law["subset"] == "pooled"]
    if len(pooled) == 0 or not np.isfinite(pooled.iloc[0]["pearson_r"]):
        g3 = False
        pr = sr = float("nan")
    else:
        pr = float(pooled.iloc[0]["pearson_r"])
        sr = float(pooled.iloc[0]["spearman_rho"])
        g3 = bool(pr >= 0.9 and sr >= 0.9)

    hi = vs_nr[vs_nr["R_id"] >= 1.2]
    if len(hi) == 0:
        g4 = False
        med_ex = med_d10_r = med_d10_n = float("nan")
    else:
        med_ex = float(hi["Amplification_excess_10"].median())
        med_d10_r = float(hi["D10_rec"].median())
        med_d10_n = float(hi["D10_nr"].median())
        g4 = bool(med_ex > 0 and med_d10_r > med_d10_n)

    ln = large_n[large_n["N"].isin([500, 2000])] if len(large_n) else large_n
    g5 = bool(len(ln) >= 2 and bool(ln["ok"].all()))

    local_amp_ok = g1
    downstream = False
    med_pc = med_h = float("nan")
    if phase_summary is not None and len(phase_summary):
        ps = phase_summary
        if "arm" in ps.columns:
            ps = ps[ps["arm"] == "recursive"]
        above0 = ps[ps["R_id"] > 1.0]
        if "beta" in above0.columns:
            above0 = above0[np.isclose(above0["beta"], 0.0)]
        if len(above0):
            med_pc = float(above0["P_collapse"].median())
            med_h = float(above0["median_H_T"].median())
            downstream = bool(med_pc >= 0.3 or med_h < 0.7)
    g6 = bool(local_amp_ok and downstream)

    g7 = False
    med_delta = float("nan")
    n_bias = 0
    if bias_summary is not None and len(bias_summary):
        b = bias_summary[bias_summary["R_id"] > 1.1].copy()
        deltas = []
        for _, grp in b.groupby(["alpha", "mu", "N"], sort=True):
            grp = grp.sort_values("beta")
            b0 = grp[np.isclose(grp["beta"], 0.0)]
            bpos = grp[grp["beta"] > 0]
            if len(b0) == 0 or len(bpos) == 0:
                continue
            a0 = float(b0["directional_asymmetry"].iloc[0])
            a_pos = float(bpos["directional_asymmetry"].mean())
            deltas.append(a_pos - a0)
        if deltas:
            med_delta = float(np.median(deltas))
            n_bias = len(deltas)
            g7 = med_delta > 0.10

    gates = {
        "G1_local_sign_transition": {
            "pass": g1,
            "frac_lambda_neg_R_le_0.95": frac_low,
            "frac_lambda_pos_R_ge_1.05": frac_high,
        },
        "G2_threshold_alignment": {
            "pass": g2,
            "status": g2_status,
            "fraction_aligned": frac_aligned,
            "n_resolvable": int(len(resolvable)),
        },
        "G3_growth_law": {
            "pass": g3,
            "pearson_r_pooled": pr,
            "spearman_rho_pooled": sr,
        },
        "G4_recursion_specificity": {
            "pass": g4,
            "median_Amplification_excess_10": med_ex,
            "median_D10_recursive": med_d10_r,
            "median_D10_NR": med_d10_n,
        },
        "G5_large_N_persistence": {
            "pass": g5,
            "rows": ln.to_dict(orient="records") if len(ln) else [],
        },
        "G6_bias_not_required": {
            "pass": g6,
            "local_amplification_at_beta0": local_amp_ok,
            "downstream_at_beta0": downstream,
            "median_P_collapse_Rgt1": med_pc,
            "median_H_T_Rgt1": med_h,
        },
        "G7_bias_direction": {
            "pass": g7,
            "median_signed_delta_PA_minus_PB": med_delta,
            "n_conditions": n_bias,
        },
    }

    def _pf(ok: bool, unresolved: bool = False) -> str:
        if unresolved:
            return "UNRESOLVED"
        return "PASS" if ok else "FAIL"

    verdict = {
        "Engineering": "PASS",
        "Local_amplification_mechanism": _pf(g1),
        "Theoretical_R_id_threshold": _pf(g2, unresolved=(g2_status == "UNRESOLVED")),
        "Growth_law_correspondence": _pf(g3),
        "Recursion_specificity": _pf(g4),
        "Large_N_persistence": _pf(g5),
        "Bias_not_required": _pf(g6),
        "Bias_selects_direction": _pf(g7),
        "Downstream_apparent_uniqueness": "SUPPORTED" if downstream else "NOT SUPPORTED",
        "Universal_finite_time_collapse_threshold": "NOT CLAIMED",
    }
    core_ok = all(
        [
            g1,
            g2,
            g3,
            g4,
            g5,
            g6,
            g7,
            g2_status != "UNRESOLVED",
        ]
    )
    verdict["revised_core_mechanism"] = "PASS" if core_ok else "FAIL"

    return {"gates": gates, "layered_verdict": verdict}
