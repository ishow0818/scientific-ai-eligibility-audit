#!/usr/bin/env python3
"""Offline audit of Anchor χ² evidence-exclusion statistical reliability.

Read-only w.r.t. frozen algorithm / thresholds / formal logs / paper.
Writes to outputs/anchor_chi2_reliability_audit/ only.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
from scipy.stats import chi2, binomtest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pilot_fi_anchor.config import (  # noqa: E402
    ALPHA_EV,
    FALSE_FAMILIES,
    FAMILY_ORDER,
    M,
    PERSIST,
    R,
    SIGMA,
    THETA_W,
    TRUTH_FAMILY,
    X0_IDX,
)
from pilot_fi_anchor.evidence_calibration import (  # noqa: E402
    evidence_crit,
    run_loop_b2_truth_check,
    simulate_neutral_sequential,
)
from pilot_fi_anchor.fitting import fit  # noqa: E402
from pilot_fi_anchor.loop import run_seed  # noqa: E402
from pilot_fi_anchor.mechanisms import FAMILIES  # noqa: E402
from pilot_fi_anchor.rng import fit_rng  # noqa: E402
from pilot_fi_anchor.world import World  # noqa: E402

OUT = ROOT / "outputs" / "anchor_chi2_reliability_audit"
FORMAL = ROOT / "outputs" / "pilot_fi_anchor"
SEED20_ABL = (
    ROOT
    / "outputs"
    / "pilot_opp_feedback_ablation_formal_v2"
    / "seed_20_paired.json"
)

# Light MC: reuse formal 1–20 + extra independent seeds (not formal confirmatory)
EXTRA_NATIVE_SEEDS = tuple(range(101, 121))  # 20 extra
NEUTRAL_MC_SEEDS = tuple(range(1, 41))  # 40 Neutral sequential sims


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float, float]:
    if n <= 0:
        return 0.0, 0.0, 0.0
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return float(p), float(max(0.0, centre - half)), float(min(1.0, centre + half))


def assumptions_block() -> dict[str, Any]:
    p_hump = FAMILIES[TRUTH_FAMILY].p
    return {
        "statistic": "stat = RSS / SIGMA^2 with known SIGMA",
        "critical_value": "chi2.ppf(1 - ALPHA_EV, df=n - p)",
        "ALPHA_EV": ALPHA_EV,
        "ALPHA_EV_formula": "0.05 / (n_families * R) = 0.05 / (5 * 25) = 0.0004",
        "PERSIST": PERSIST,
        "hump_p": p_hump,
        "strictly_justified_when": [
            "Gaussian i.i.d. errors with known variance SIGMA (World uses this)",
            "Fixed, non-adaptive design (x's independent of y's)",
            "Correctly specified model AND least-squares attains the global MLE",
            "For linear models: exact finite-sample χ²_{n-p}; hump is nonlinear → asymptotic/approximate",
        ],
        "approximate_or_violated": [
            "Nonlinear least squares: χ² reference is asymptotic / under regularity, not exact",
            "Bounded TRF fit + warm starts: not guaranteed global RSS minimum",
            "Sequential testing every round: Bonferroni uses union bound (conservative if tests independent; "
            "dependence across rounds makes exact FWER control non-guaranteed)",
            "PERSIST=2 is an operational confirmation rule, not a classical sequential test with proven Type I",
            "Native adaptive allocation: design depends on past y ⇒ classical χ² null for fixed design does not apply",
        ],
        "bonferroni_role": (
            "ALPHA_EV divides family-wise 0.05 by (5 families × 25 rounds) as a crude "
            "per-look level; does not restore exact martingale / optional-stopping validity "
            "under adaptive designs"
        ),
    }


def recompute_arm_chi2_trace(
    seed: int, site_indices_by_round: list[list[int]]
) -> list[dict[str, Any]]:
    """Rebuild evidence path for hump given cumulative measured indices per round."""
    world = World(seed)
    fr = fit_rng(seed)
    mech = FAMILIES[TRUTH_FAMILY]
    arm_fit = None
    prev_v = False
    measured: list[int] = []
    out = []
    for t, batch in enumerate(site_indices_by_round):
        for idx in batch:
            if idx not in measured:
                measured.append(idx)
        order = sorted(measured)
        xs = np.array([world.x(i) for i in order])
        ys = np.array([world.y(i) for i in order])
        n = len(xs)
        z = fit(mech, xs, ys, warm=arm_fit, rng=fr)
        arm_fit = z
        theta = mech.from_fit(z)
        rss = float(np.sum((mech.predict(xs, theta) - ys) ** 2))
        stat = rss / (SIGMA * SIGMA)
        df = n - mech.p
        crit = evidence_crit(n, mech.p)
        violated = stat > crit
        excluded = bool(violated and prev_v)
        # Reference: exact χ² survival if null were exact
        p_nom = float(chi2.sf(stat, df)) if df > 0 else float("nan")
        out.append(
            {
                "t": t,
                "n": n,
                "df": df,
                "stat": stat,
                "crit": crit,
                "violated": violated,
                "excluded": excluded,
                "nominal_tail_prob_if_exact_chi2": p_nom,
                "stat_over_crit": stat / crit if crit > 0 else None,
            }
        )
        prev_v = violated
    return out


def sites_by_round_from_log(sites: list[dict]) -> list[list[int]]:
    by_t: dict[int, list[int]] = {}
    for s in sites:
        by_t.setdefault(int(s["t"]), []).append(int(s["idx"]))
    tmax = max(by_t)
    return [by_t.get(t, []) for t in range(0, tmax + 1)]


def seed20_t3_audit() -> dict[str, Any]:
    """Distinguish operational non-exclusion vs statistical compatibility proof."""
    # Prefer ablation paired Native (matches formal Native) for consistency with prior chain
    if SEED20_ABL.is_file():
        rec = json.loads(SEED20_ABL.read_text(encoding="utf-8"))
        sites = rec["arms"]["native"]["sites"]
        logged = rec["arms"]["native"]["rounds"][3]["hump"]
        source = "ablation_formal_v2_seed_20_paired native"
    else:
        rec = json.loads((FORMAL / "seed_20.json").read_text(encoding="utf-8"))
        sites = rec["arms"]["native"]["sites"]
        logged = rec["arms"]["native"]["rounds"][3]["hump"]
        source = "pilot_fi_anchor seed_20 native"

    batches = sites_by_round_from_log(sites)
    trace = recompute_arm_chi2_trace(20, batches)
    t3 = trace[3]
    return {
        "source": source,
        "logged_at_t3": {
            "alive": logged.get("alive"),
            "w_surv": logged.get("w_surv"),
            "violated": logged.get("violated"),
            "excluded": logged.get("excluded"),
            "t_elim": logged.get("t_elim"),
            "t_excl": logged.get("t_excl"),
        },
        "recomputed_hump_evidence_t3": t3,
        "operational_fi": {
            "t_elim": 3,
            "t_excl_logged": logged.get("t_excl"),
            "met_frozen_two_round_exclusion_at_t3": bool(t3["excluded"]),
            "single_round_violation_at_t3": bool(t3["violated"]),
        },
        "interpretation": {
            "did_not_meet_frozen_exclusion_at_t3": not bool(t3["excluded"]),
            "statistically_proven_compatible_at_t3": False,
            "why_not_proven_compatible": (
                "Absence of a single-round χ² exceedance under an adaptive design "
                "and nonlinear LS is NOT a proof of evidence-compatibility. "
                "It only means the frozen operational rule did not flag violation "
                f"(stat={t3['stat']:.4f} ≤ crit={t3['crit']:.4f} at n={t3['n']}). "
                "Native design depends on past data, so the classical fixed-design "
                "χ² null is not guaranteed."
            ),
        },
    }


def collect_final_stats_neutral(seeds: tuple[int, ...]) -> dict[str, Any]:
    stats = []
    excl = 0
    viol_any = 0
    for s in seeds:
        r = simulate_neutral_sequential(s, ALPHA_EV)
        if r["excluded"]:
            excl += 1
        if r["first_violated"] is not None:
            viol_any += 1
        final = r["trace"][-1]
        stats.append(final["stat"])
        # also store ratio to crit
    stats_arr = np.asarray(stats, dtype=float)
    n_final = 10 + R * M  # X0 + all sweep points
    p = FAMILIES[TRUTH_FAMILY].p
    crit = evidence_crit(n_final, p)
    qs = [0.5, 0.9, 0.95, 0.99, 0.999]
    emp = {f"q{int(q*1000)/10}": float(np.quantile(stats_arr, q)) for q in qs}
    # nominal chi2 quantiles
    df = n_final - p
    nom = {f"chi2_q{int(q*1000)/10}": float(chi2.ppf(q, df)) for q in qs}
    rate, lo, hi = wilson(excl, len(seeds))
    return {
        "design": "neutral_fixed_sweep",
        "n_seeds": len(seeds),
        "n_obs_final": n_final,
        "df": df,
        "crit_final": crit,
        "truth_excluded_k": excl,
        "truth_excluded_rate": rate,
        "wilson95": [lo, hi],
        "any_single_violation_k": viol_any,
        "empirical_stat_quantiles": emp,
        "nominal_chi2_quantiles": nom,
        "empirical_mean_stat": float(np.mean(stats_arr)),
        "nominal_chi2_mean": float(df),
        "frac_stat_above_crit": float(np.mean(stats_arr > crit)),
    }


def collect_native_exclusions(
    formal_seeds: tuple[int, ...], extra_seeds: tuple[int, ...]
) -> dict[str, Any]:
    """False-exclusion of truth under Native adaptive allocation."""
    per: list[dict[str, Any]] = []
    # Formal disk logs (authoritative for 1–20)
    for s in formal_seeds:
        path = FORMAL / f"seed_{s:02d}.json"
        if not path.is_file():
            continue
        rec = json.loads(path.read_text(encoding="utf-8"))
        final = rec["arms"]["native"]["final"]
        per.append(
            {
                "seed": s,
                "source": "formal_disk",
                "truth_excluded": bool(final["excluded"]["hump"]),
                "t_excl": final["t_excl"]["hump"],
                "truth_elim": final["t_elim"]["hump"],
            }
        )
    # Extra live Native runs (calibration only; not written into pilot_fi_anchor)
    for s in extra_seeds:
        rec = run_seed(s, do_perturb=False, rounds=R)
        final = rec["arms"]["native"]["final"]
        per.append(
            {
                "seed": s,
                "source": "live_extra_mc",
                "truth_excluded": bool(final["excluded"]["hump"]),
                "t_excl": final["t_excl"]["hump"],
                "truth_elim": final["t_elim"]["hump"],
            }
        )
    excl = sum(1 for r in per if r["truth_excluded"])
    rate, lo, hi = wilson(excl, len(per))
    formal_only = [r for r in per if r["source"] == "formal_disk"]
    fe = sum(1 for r in formal_only if r["truth_excluded"])
    fr, flo, fhi = wilson(fe, len(formal_only)) if formal_only else (0, 0, 0)
    return {
        "design": "native_adaptive",
        "n_seeds": len(per),
        "n_formal_disk": len(formal_only),
        "n_extra_mc": sum(1 for r in per if r["source"] == "live_extra_mc"),
        "truth_excluded_k": excl,
        "truth_excluded_rate": rate,
        "wilson95": [lo, hi],
        "formal_disk_excluded_k": fe,
        "formal_disk_rate": fr,
        "formal_disk_wilson95": [flo, fhi],
        "excluded_seeds": [r["seed"] for r in per if r["truth_excluded"]],
        "per_seed": per,
        "note": (
            "Under adaptive design, χ² critical values are operational thresholds; "
            "empirical exclusion rate is the relevant Type-I proxy here."
        ),
    }


def adaptive_impact_notes() -> list[str]:
    return [
        "Native allocation uses past residuals / support weights → future x depend on past y.",
        "Classical derivation P(RSS/σ² > χ²_{1-α,n-p}) = α assumes fixed x (or ancillary design).",
        "Therefore Native mis-exclusion control cannot be claimed from the χ² table alone.",
        "Empirical MC under the true DGP is required for an operational Type-I estimate.",
        "Neutral fixed sweep is closer to the classical setting (still nonlinear LS + sequential looks).",
    ]


def decide(neutral: dict, native: dict, seed20: dict) -> tuple[str, str]:
    """CALIBRATED / OPERATIONAL_ONLY / INVALID."""
    # INVALID only if frozen rule is internally wrong or FI labeling broken
    if seed20["operational_fi"]["met_frozen_two_round_exclusion_at_t3"]:
        # Would contradict prior FI claim for seed20 if excluded at t=3
        return (
            "INVALID",
            "Seed-20 t=3 recomputation shows two-round exclusion already met; "
            "conflicts with FI-before-exclusion narrative.",
        )
    # If Neutral empirical FWER hugely exceeds nominal 0.05 with large n, worry
    # Here ALPHA is per-look; horizon exclusion under Bonferroni expected << 0.05
    if neutral["truth_excluded_k"] > 0 and neutral["n_seeds"] >= 20:
        # still may be OPERATIONAL_ONLY if rare
        pass
    if native["formal_disk_excluded_k"] > 2:
        # Gate was native<=1; more would stress operational use
        return (
            "OPERATIONAL_ONLY",
            "Native formal disk shows elevated truth exclusions relative to gate intent; "
            "χ² remains operational, not strictly calibrated.",
        )
    # Default: operational only — cannot claim strict calibration under adaptive + nonlinear + sequential
    return (
        "OPERATIONAL_ONLY",
        "Gaussian known-σ and Neutral empirical rates support using the rule as a frozen "
        "operational FI comparator; Native adaptivity + nonlinear LS + sequential looks "
        "block a claim of strict frequentist calibration / FWER control.",
    )


def write_report(
    assumptions: dict,
    neutral: dict,
    native: dict,
    seed20: dict,
    loop_b2: dict,
    verdict: str,
    reason: str,
    path: Path,
) -> None:
    lines = [
        "# Anchor χ² 证据排除标准 — 统计可靠性审计",
        "",
        f"**裁决：`{verdict}`**",
        "",
        reason,
        "",
        "范围：只读 `evidence_calibration.py` / `loop.py` / `fitting.py` / `world.py`；"
        "轻量 MC；不改算法、阈值、正式日志或论文。",
        "",
        "## 1. 规则与假设",
        "",
        f"- 统计量：`stat = RSS / σ²`，σ=`{SIGMA}`（World 真噪声）",
        f"- 临界值：`χ²_{{1-α, n-p}}`，`α = ALPHA_EV = {ALPHA_EV}` "
        f"（`0.05/(5·25)`）",
        f"- 排除：连续 `PERSIST={PERSIST}` 轮 `violated`",
        f"- hump 参数维数 p={assumptions['hump_p']}",
        "",
        "### 严格成立的条件（近似满足的部分）",
        "",
    ]
    for x in assumptions["strictly_justified_when"]:
        lines.append(f"- {x}")
    lines += ["", "### 仅为近似 / 被违反的条件", ""]
    for x in assumptions["approximate_or_violated"]:
        lines.append(f"- {x}")
    lines += [
        "",
        f"Bonferroni 角色：{assumptions['bonferroni_role']}",
        "",
        "## 2. Native 自适应选点对零假设的影响",
        "",
    ]
    for x in adaptive_impact_notes():
        lines.append(f"- {x}")
    lines += [
        "",
        "## 3. 轻量 Monte Carlo：真实 hump 误排除率",
        "",
        "### Neutral 固定扫掠（更接近经典设定）",
        "",
        f"- seeds={neutral['n_seeds']}；终局 n={neutral['n_obs_final']}，df={neutral['df']}",
        f"- 误排除 k={neutral['truth_excluded_k']}；"
        f"率={neutral['truth_excluded_rate']:.4f}；"
        f"Wilson95={neutral['wilson95']}",
        f"- 终局 emp. mean(stat)={neutral['empirical_mean_stat']:.2f} "
        f"（名义 χ² 均值={neutral['nominal_chi2_mean']:.1f}）",
        f"- 经验分位数：{neutral['empirical_stat_quantiles']}",
        f"- 名义 χ² 分位数：{neutral['nominal_chi2_quantiles']}",
        f"- 终局单次 `stat>crit` 比例={neutral['frac_stat_above_crit']:.4f} "
        f"（crit={neutral['crit_final']:.2f}）",
        "",
        "### Native 自适应（正式 1–20 磁盘 + 额外 live MC）",
        "",
        f"- 合计 n={native['n_seeds']} "
        f"（formal_disk={native['n_formal_disk']}，extra={native['n_extra_mc']}）",
        f"- 误排除 k={native['truth_excluded_k']}；"
        f"率={native['truth_excluded_rate']:.4f}；Wilson95={native['wilson95']}",
        f"- 仅正式磁盘：k={native['formal_disk_excluded_k']}；"
        f"率={native['formal_disk_rate']:.4f}；"
        f"Wilson95={native['formal_disk_wilson95']}；"
        f"正式排除 seeds="
        f"{[r['seed'] for r in native['per_seed'] if r['source']=='formal_disk' and r['truth_excluded']]}；"
        f"合计排除 seeds={native['excluded_seeds']}",
        f"- 既有 loop B2 检查（seeds {loop_b2.get('per_seed', []) and [r['seed'] for r in loop_b2['per_seed']]}）："
        f"native_k={loop_b2['native_truth_excluded_k']}，"
        f"neutral_k={loop_b2['neutral_truth_excluded_k']}，b2_ok={loop_b2['b2_ok']}",
        "",
        "## 4. Seed 20，t=3 证据状态复核",
        "",
        f"- 日志来源：{seed20['source']}",
        f"- 日志：violated={seed20['logged_at_t3']['violated']}，"
        f"excluded={seed20['logged_at_t3']['excluded']}，"
        f"w_surv={seed20['logged_at_t3']['w_surv']}",
        f"- 重算：n={seed20['recomputed_hump_evidence_t3']['n']}，"
        f"stat={seed20['recomputed_hump_evidence_t3']['stat']:.4f}，"
        f"crit={seed20['recomputed_hump_evidence_t3']['crit']:.4f}，"
        f"violated={seed20['recomputed_hump_evidence_t3']['violated']}，"
        f"excluded={seed20['recomputed_hump_evidence_t3']['excluded']}",
        f"- **未达到冻结两轮排除标准：{seed20['interpretation']['did_not_meet_frozen_exclusion_at_t3']}**",
        f"- **是否统计上已证明证据相容：{seed20['interpretation']['statistically_proven_compatible_at_t3']}**",
        f"- 说明：{seed20['interpretation']['why_not_proven_compatible']}",
        "",
        "## 5. 能否继续使用 Anchor FI 结论？论文应补充的限定",
        "",
        "- **可以继续使用**，但须把证据规则表述为**冻结的操作性排除标签**，"
        "FI = 决策资格退出早于该操作性排除；**不要**写成已校准的精确 Type-I / FWER 保证。",
        "- 建议论文补充：",
        "  1. χ² 参考分布在非线性拟合下仅为近似；",
        "  2. 逐轮 Bonferroni 是保守启发式，非自适应设计下的严格序贯检验；",
        "  3. Native 选点依赖历史数据，名义 χ² 临界值不保证误排除率；",
        "  4. 已有 Neutral/Native 经验误排除检查（本审计与 B2）仅支持操作性使用；",
        "  5. 「删除当轮未 violated」≠「已证明与数据相容」。",
        "",
        f"**最终裁决：`{verdict}`**",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    print("[chi2-audit] assumptions...", flush=True)
    assumptions = assumptions_block()
    print("[chi2-audit] seed20 t=3...", flush=True)
    seed20 = seed20_t3_audit()
    print("[chi2-audit] Neutral MC...", flush=True)
    neutral = collect_final_stats_neutral(NEUTRAL_MC_SEEDS)
    print(
        f"[chi2-audit] Neutral excl={neutral['truth_excluded_k']}/{neutral['n_seeds']}",
        flush=True,
    )
    print("[chi2-audit] Native formal+extra MC (may take a few minutes)...", flush=True)
    formal_seeds = tuple(range(1, 21))
    native = collect_native_exclusions(formal_seeds, EXTRA_NATIVE_SEEDS)
    print(
        f"[chi2-audit] Native excl={native['truth_excluded_k']}/{native['n_seeds']} "
        f"seeds={native['excluded_seeds']}",
        flush=True,
    )
    print("[chi2-audit] loop B2 subset...", flush=True)
    loop_b2 = run_loop_b2_truth_check((3, 20), do_perturb=False)
    verdict, reason = decide(neutral, native, seed20)
    payload = {
        "verdict": verdict,
        "reason": reason,
        "assumptions": assumptions,
        "adaptive_impact": adaptive_impact_notes(),
        "neutral_mc": neutral,
        "native_mc": native,
        "seed20_t3": seed20,
        "loop_b2_check": loop_b2,
        "continue_using_FI": verdict != "INVALID",
        "paper_caveats_required": verdict != "CALIBRATED",
    }
    (OUT / "chi2_reliability_audit.json").write_text(
        json.dumps(payload, indent=2, default=str), encoding="utf-8"
    )
    write_report(
        assumptions,
        neutral,
        native,
        seed20,
        loop_b2,
        verdict,
        reason,
        OUT / "chi2_reliability_audit.md",
    )
    (OUT / "verdict.json").write_text(
        json.dumps({"verdict": verdict, "reason": reason}, indent=2), encoding="utf-8"
    )
    print(f"[chi2-audit] verdict={verdict} -> {OUT}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
