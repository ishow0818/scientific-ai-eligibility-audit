"""
Reproduce final validation summaries for the frozen dynamics package.

Deterministic local amplification is always recomputed.
Early stochastic (t<=20) is recomputed under frozen seeds/grids.
Terminal consequence / bias / budget terminal metrics are reanalyzed from
verified provenance summaries when available (full T=100 500-seed grids
are not re-run by default).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from identifiability_dynamics_final.analysis import (
    attach_terminal_consequence,
    growth_law_summary,
    load_verified_summary,
    recursive_vs_nr_early,
    run_budget_early,
    run_deterministic_local_growth,
    run_stochastic_early_grid,
    threshold_alignment,
)
from identifiability_dynamics_final.config import PilotConfig
from identifiability_dynamics_final.gates import evaluate_final_gates


def _write_json(path: Path, obj: dict) -> None:
    path.write_text(json.dumps(obj, indent=2, default=str), encoding="utf-8")


def _md_table(df: pd.DataFrame) -> str:
    try:
        return df.to_markdown(index=False)
    except Exception:
        return df.to_string(index=False)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Frozen dynamics final validation")
    p.add_argument(
        "--provenance",
        type=str,
        default=None,
        help="Directory with verified 500-seed summaries (default: config.provenance_dir)",
    )
    p.add_argument(
        "--results",
        type=str,
        default=None,
        help="Output results directory",
    )
    p.add_argument(
        "--skip-stochastic-resim",
        action="store_true",
        help="Reuse verified early CSVs from provenance/local_amplification if present",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    cfg = PilotConfig()
    root = Path.cwd()
    provenance = Path(args.provenance) if args.provenance else root / cfg.provenance_dir
    out = Path(args.results) if args.results else root / cfg.results_dir
    out.mkdir(parents=True, exist_ok=True)

    provenance_note = {
        "deterministic": "recomputed in this package with frozen F(q) and grids",
        "early_stochastic": None,
        "terminal_summaries": str(provenance),
    }

    # ----- Exp 1–2: deterministic -----
    print("=== Deterministic local amplification (recompute) ===")
    growth = run_deterministic_local_growth(
        alphas=cfg.stochastic.alphas,
        mus=cfg.stochastic.mus,
    )
    growth.to_csv(out / "deterministic_local_growth.csv", index=False)
    alignment = threshold_alignment(growth)
    # one row per mu (aggregate over epsilon/side — all should match)
    align_mu = (
        alignment.groupby("mu", as_index=False)
        .agg(
            theory_alpha_c=("theory_alpha_c", "first"),
            empirical_crossing_lo=("empirical_crossing_lo", "first"),
            empirical_crossing_hi=("empirical_crossing_hi", "first"),
            status=("status", "first"),
            aligned=("aligned", "all"),
        )
    )
    align_mu.to_csv(out / "threshold_alignment.csv", index=False)
    law = growth_law_summary(growth)
    law.to_csv(out / "growth_law_summary.csv", index=False)

    # ----- Exp 3: early Rec vs NR -----
    local_prev = provenance / "local_amplification"
    early_path = local_prev / "stochastic_early_amplification.csv"
    vs_path = local_prev / "recursive_vs_nr_early.csv"

    if args.skip_stochastic_resim and early_path.is_file():
        print("=== Early stochastic: reanalyze verified CSV ===")
        early = pd.read_csv(early_path)
        provenance_note["early_stochastic"] = f"reanalyzed {early_path}"
        vs = (
            pd.read_csv(vs_path)
            if vs_path.is_file()
            else recursive_vs_nr_early(early)
        )
    else:
        print("=== Early stochastic: frozen re-simulation t<=20 ===")
        early = run_stochastic_early_grid(cfg.stochastic, n_seeds=cfg.stochastic.n_seeds)
        provenance_note["early_stochastic"] = (
            "recomputed with frozen StochasticGrid (same N,T seeds as verified run)"
        )
        vs = recursive_vs_nr_early(early)

    phase = load_verified_summary(provenance / "phase_summary.csv")
    nr = load_verified_summary(provenance / "no_recursion_summary.csv")
    vs = attach_terminal_consequence(vs, phase, nr)
    vs.to_csv(out / "recursive_vs_nr.csv", index=False)

    # ----- Exp 4: large-N + bias -----
    bud_prev = local_prev / "budget_early_amplification.csv"
    if args.skip_stochastic_resim and bud_prev.is_file():
        print("=== Budget early: reanalyze verified CSV ===")
        bud_early = pd.read_csv(bud_prev)
    else:
        print("=== Budget early: frozen re-simulation ===")
        bud_early = run_budget_early(cfg.budget, n_seeds=cfg.budget.n_seeds)

    bud_sum = load_verified_summary(provenance / "budget_summary.csv")
    bud_nr_sum = load_verified_summary(provenance / "budget_no_recursion_summary.csv")
    pairs = []
    above = bud_early[bud_early["budget_regime"] == "above"]
    for N in cfg.budget.Ns:
        r = above[(above["arm"] == "recursive") & (above["N"] == N)]
        n = above[(above["arm"] == "no_recursion") & (above["N"] == N)]
        if len(r) == 0 or len(n) == 0:
            pairs.append({"N": N, "status": "MISSING"})
            continue
        rr, nn = r.iloc[0], n.iloc[0]
        a_ex = (
            float(rr["A_stoch_10"] - nn["A_stoch_10"])
            if np.isfinite(rr["A_stoch_10"]) and np.isfinite(nn["A_stoch_10"])
            else float("nan")
        )
        pc_r = pc_n = float("nan")
        if bud_sum is not None:
            tr = bud_sum[(np.isclose(bud_sum["alpha"], rr["alpha"])) & (bud_sum["N"] == N)]
            if len(tr):
                pc_r = float(tr["P_collapse"].iloc[0])
        if bud_nr_sum is not None:
            tn = bud_nr_sum[
                (np.isclose(bud_nr_sum["alpha"], nn["alpha"])) & (bud_nr_sum["N"] == N)
            ]
            if len(tn):
                pc_n = float(tn["P_collapse"].iloc[0])
        pairs.append(
            {
                "N": int(N),
                "D10_rec": float(rr["D_10"]),
                "D10_nr": float(nn["D_10"]),
                "Amplification_excess_10": a_ex,
                "ok": bool(rr["D_10"] > nn["D_10"] and a_ex > 0),
                "terminal_Pcollapse_rec": pc_r if np.isfinite(pc_r) else "MISSING",
                "terminal_Pcollapse_nr": pc_n if np.isfinite(pc_n) else "MISSING",
            }
        )
    large_n = pd.DataFrame(pairs)
    large_n.to_csv(out / "large_n_control.csv", index=False)

    bias = load_verified_summary(provenance / "bias_summary.csv")
    if bias is None:
        bias_out = pd.DataFrame([{"status": "MISSING"}])
    else:
        bias_out = bias.sort_values(["R_id", "beta"]).reset_index(drop=True)
    bias_out.to_csv(out / "bias_control.csv", index=False)

    # For gate L5, need numeric ok column
    large_n_gate = large_n.copy()
    if "ok" not in large_n_gate.columns:
        large_n_gate["ok"] = False
    else:
        large_n_gate["ok"] = large_n_gate["ok"].fillna(False).astype(bool)

    payload = evaluate_final_gates(
        growth=growth,
        alignment=alignment,
        law=law,
        vs_nr=vs,
        large_n=large_n_gate,
        phase_summary=phase,
        bias_summary=bias if bias is not None else None,
    )
    _write_json(out / "final_gates.json", payload["gates"])
    verdict = payload["layered_verdict"]
    verdict["provenance"] = provenance_note
    _write_json(out / "final_verdict.json", verdict)

    # summary markdown
    sign = growth[growth["valid_K5"] == 1].copy()

    def _bin(r: float) -> str:
        if r <= 0.95:
            return "R<=0.95"
        if r >= 1.05:
            return "R>=1.05"
        return "0.95<R<1.05"

    sign["R_range"] = sign["R_id"].map(_bin)
    t1 = sign.groupby("R_range", sort=False).agg(
        median_lambda_emp=("lambda_emp_K5", "median"),
        sign_match_rate=("sign_match_K5", "mean"),
        n=("lambda_emp_K5", "count"),
    ).reset_index()

    vs2 = vs.copy()
    vs2["R_bin"] = pd.cut(
        vs2["R_id"],
        bins=[-0.1, 0.9, 1.2, 10],
        labels=["R<=0.9", "0.9<R<1.2", "R>=1.2"],
    )
    t4 = (
        vs2.groupby("R_bin", observed=True)
        .agg(
            A10_Rec=("A10_rec", "median"),
            A10_NR=("A10_nr", "median"),
            Amp_excess=("Amplification_excess_10", "median"),
            Pcollapse_Rec=("P_collapse_rec", "median"),
            Pcollapse_NR=("P_collapse_nr", "median"),
            H_T_Rec=("median_H_T_rec", "median"),
            H_T_NR=("median_H_T_nr", "median"),
        )
        .reset_index()
    )

    md = []
    md.append("# Final validation summary\n\n")
    md.append("## Layered verdict\n\n")
    for k, v in verdict.items():
        if k == "provenance":
            continue
        md.append(f"- **{k}**: `{v}`\n")
    md.append("\n## Provenance\n\n")
    for k, v in provenance_note.items():
        md.append(f"- **{k}**: {v}\n")
    md.append("\n## Deterministic local threshold\n\n")
    md.append(_md_table(t1) + "\n")
    md.append("\n## Threshold alignment\n\n")
    md.append(_md_table(align_mu) + "\n")
    md.append("\n## Growth law\n\n")
    md.append(_md_table(law) + "\n")
    md.append("\n## Recursive vs No-recursion\n\n")
    md.append(_md_table(t4) + "\n")
    md.append("\n## Large-N control\n\n")
    md.append(_md_table(large_n) + "\n")
    (out / "final_summary.md").write_text("".join(md), encoding="utf-8")

    print("\n=== FINAL VERDICT ===")
    for k, v in verdict.items():
        if k == "provenance":
            continue
        print(f"  {k}: {v}")
    return 0 if verdict.get("revised_core_mechanism") == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
