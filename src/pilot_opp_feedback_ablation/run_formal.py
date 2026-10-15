#!/usr/bin/env python3
"""Formal 20-seed Opportunity-Feedback Ablation (v0.2 CRN; no TeX edits).

Native vs No-Opp-Feedback. Does not tune thresholds or select seeds by outcome.
"""
from __future__ import annotations

import csv
import json
import statistics
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pilot_fi_anchor.config import FALSE_FAMILIES, R, THETA_W, TRUTH_FAMILY  # noqa: E402
from pilot_opp_feedback_ablation.config import (  # noqa: E402
    ABLATION_VERSION,
    ARM_NATIVE,
    ARM_NO_OPP,
    FORMAL_RESULTS_DIR,
    FORMAL_SEEDS,
)
from pilot_opp_feedback_ablation.loop_ablation import (  # noqa: E402
    fi_events,
    run_paired_seed,
)

OUT = ROOT / FORMAL_RESULTS_DIR
FORMAL_DISK = ROOT / "outputs" / "pilot_fi_anchor"


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    keys: list[str] = []
    seen: set[str] = set()
    for r in rows:
        for k in r:
            if k not in seen:
                keys.append(k)
                seen.add(k)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)


def paired_direction(te_n: int | None, te_u: int | None) -> str:
    if te_n is None and te_u is None:
        return "both_censored"
    if te_n is not None and te_u is not None and te_n == te_u:
        return "same_round"
    if te_n is not None and (te_u is None or te_n < te_u):
        return "native_earlier"
    if te_u is not None and (te_n is None or te_u < te_n):
        return "no_opp_earlier"
    return "UNKNOWN"


def finite_delta(te_n: int | None, te_u: int | None) -> int | None:
    if te_n is None or te_u is None:
        return None
    return int(te_n) - int(te_u)


def analyze_seed(rec: dict) -> dict[str, Any]:
    seed = int(rec["seed"])
    n_final = rec["arms"][ARM_NATIVE]["final"]
    u_final = rec["arms"][ARM_NO_OPP]["final"]
    n_ev = fi_events(rec["arms"][ARM_NATIVE])
    u_ev = fi_events(rec["arms"][ARM_NO_OPP])
    n_false_fi = [e for e in n_ev if (not e["is_truth"]) and e["fi"]]
    u_false_fi = [e for e in u_ev if (not e["is_truth"]) and e["fi"]]
    n_truth_fi = any(e["is_truth"] and e["fi"] for e in n_ev)
    u_truth_fi = any(e["is_truth"] and e["fi"] for e in u_ev)

    # per-family paired timing (false only for primary event table)
    timing_rows = []
    for h in FALSE_FAMILIES:
        te_n = n_final["t_elim"].get(h)
        te_u = u_final["t_elim"].get(h)
        tx_n = n_final["t_excl"].get(h)
        tx_u = u_final["t_excl"].get(h)
        direction = paired_direction(te_n, te_u)
        d_fin = finite_delta(te_n, te_u)

        def state_at(arm_tag: str, te: int | None) -> dict:
            if te is None:
                return {"violated": None, "excluded": None, "w_surv": None}
            st = rec["arms"][arm_tag]["rounds"][te][h]
            return {
                "violated": st["violated"],
                "excluded": st["excluded"],
                "w_surv": st["w_surv"],
            }

        sn, su = state_at(ARM_NATIVE, te_n), state_at(ARM_NO_OPP, te_u)
        timing_rows.append(
            {
                "seed": seed,
                "family": h,
                "t_elim_native": te_n if te_n is not None else "",
                "t_elim_no_opp": te_u if te_u is not None else "",
                "t_excl_native": tx_n if tx_n is not None else "",
                "t_excl_no_opp": tx_u if tx_u is not None else "",
                "fi_native": bool(te_n is not None and (tx_n is None or te_n < tx_n)),
                "fi_no_opp": bool(te_u is not None and (tx_u is None or te_u < tx_u)),
                "direction": direction,
                "native_earlier": direction == "native_earlier",
                "no_opp_earlier": direction == "no_opp_earlier",
                "same_round": direction == "same_round",
                "both_censored": direction == "both_censored",
                "delta_finite_native_minus_no_opp": d_fin if d_fin is not None else "",
                "violated_at_elim_native": sn["violated"],
                "violated_at_elim_no_opp": su["violated"],
                "excluded_at_elim_native": sn["excluded"],
                "excluded_at_elim_no_opp": su["excluded"],
                "w_surv_at_elim_native": sn["w_surv"],
                "w_surv_at_elim_no_opp": su["w_surv"],
            }
        )

    # truth row
    te_n = n_final["t_elim"].get(TRUTH_FAMILY)
    te_u = u_final["t_elim"].get(TRUTH_FAMILY)
    truth_row = {
        "seed": seed,
        "family": TRUTH_FAMILY,
        "t_elim_native": te_n if te_n is not None else "",
        "t_elim_no_opp": te_u if te_u is not None else "",
        "truth_fi_native": n_truth_fi,
        "truth_fi_no_opp": u_truth_fi,
        "direction": paired_direction(te_n, te_u),
        "native_incumbent": n_final["incumbent"],
        "no_opp_incumbent": u_final["incumbent"],
        "native_alive_hump": n_final["alive"].get(TRUTH_FAMILY),
        "no_opp_alive_hump": u_final["alive"].get(TRUTH_FAMILY),
    }

    seed_summary = {
        "seed": seed,
        "n_false_fi_native": len(n_false_fi),
        "n_false_fi_no_opp": len(u_false_fi),
        "truth_fi_native": n_truth_fi,
        "truth_fi_no_opp": u_truth_fi,
        "native_incumbent": n_final["incumbent"],
        "no_opp_incumbent": u_final["incumbent"],
        "native_truth_incumbent": n_final["incumbent"] == TRUTH_FAMILY,
        "no_opp_truth_incumbent": u_final["incumbent"] == TRUTH_FAMILY,
        "delta_false_fi_native_minus_no_opp": len(n_false_fi) - len(u_false_fi),
    }
    return {
        "seed_summary": seed_summary,
        "timing_rows": timing_rows,
        "truth_row": truth_row,
        "exit_events": (
            [{"seed": seed, "arm": ARM_NATIVE, **e} for e in n_ev]
            + [{"seed": seed, "arm": ARM_NO_OPP, **e} for e in u_ev]
        ),
    }


def check_disk_native(seed: int, rec: dict) -> dict[str, Any]:
    path = FORMAL_DISK / f"seed_{seed:02d}.json"
    if not path.is_file():
        return {"seed": seed, "disk_present": False, "match": False, "reason": "missing_disk"}
    disk = json.loads(path.read_text(encoding="utf-8"))
    a_sites = [(s["t"], s["idx"], s["credit"]) for s in rec["arms"][ARM_NATIVE]["sites"]]
    d_sites = [(s["t"], s["idx"], s.get("credit")) for s in disk["arms"]["native"]["sites"]]
    elim_ok = (
        rec["arms"][ARM_NATIVE]["final"]["t_elim"] == disk["arms"]["native"]["final"]["t_elim"]
    )
    excl_ok = (
        rec["arms"][ARM_NATIVE]["final"]["t_excl"] == disk["arms"]["native"]["final"]["t_excl"]
    )
    sites_ok = a_sites == d_sites
    return {
        "seed": seed,
        "disk_present": True,
        "sites_match": sites_ok,
        "t_elim_match": elim_ok,
        "t_excl_match": excl_ok,
        "match": sites_ok and elim_ok and excl_ok,
        "reason": None if (sites_ok and elim_ok and excl_ok) else "native_mismatch_vs_disk",
    }


def binomial_wilson(k: int, n: int) -> tuple[float, float, float]:
    """Simple Wilson score 95% CI for a proportion (seed-level)."""
    if n <= 0:
        return 0.0, 0.0, 0.0
    from math import sqrt

    z = 1.96
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return p, max(0.0, centre - half), min(1.0, centre + half)


def aggregate(
    seed_summaries: list[dict],
    timing_rows: list[dict],
    truth_rows: list[dict],
    disk_checks: list[dict],
) -> dict[str, Any]:
    n = len(seed_summaries)
    truth_n = sum(1 for s in seed_summaries if s["truth_fi_native"])
    truth_u = sum(1 for s in seed_summaries if s["truth_fi_no_opp"])
    false_fi_n = sum(s["n_false_fi_native"] for s in seed_summaries)
    false_fi_u = sum(s["n_false_fi_no_opp"] for s in seed_summaries)
    # paired seed-level: which arm has more false FI
    more_n = sum(1 for s in seed_summaries if s["n_false_fi_native"] > s["n_false_fi_no_opp"])
    more_u = sum(1 for s in seed_summaries if s["n_false_fi_no_opp"] > s["n_false_fi_native"])
    tie_fi = sum(1 for s in seed_summaries if s["n_false_fi_native"] == s["n_false_fi_no_opp"])

    dirs = Counter(r["direction"] for r in timing_rows)
    finite = [
        int(r["delta_finite_native_minus_no_opp"])
        for r in timing_rows
        if r["delta_finite_native_minus_no_opp"] != ""
    ]
    # evidence at elim among FI events
    n_fi_rows = [r for r in timing_rows if r["fi_native"]]
    u_fi_rows = [r for r in timing_rows if r["fi_no_opp"]]
    n_nov = sum(1 for r in n_fi_rows if r["violated_at_elim_native"] is False)
    u_nov = sum(1 for r in u_fi_rows if r["violated_at_elim_no_opp"] is False)

    inc_n = Counter(s["native_incumbent"] for s in seed_summaries)
    inc_u = Counter(s["no_opp_incumbent"] for s in seed_summaries)
    truth_lock_n = sum(1 for s in seed_summaries if s["native_truth_incumbent"])
    truth_lock_u = sum(1 for s in seed_summaries if s["no_opp_truth_incumbent"])

    disk_ok = all(d.get("match") for d in disk_checks)

    p_tn, lo_tn, hi_tn = binomial_wilson(truth_n, n)
    p_tu, lo_tu, hi_tu = binomial_wilson(truth_u, n)

    # McNemar-style discordant for truth FI (seed-level)
    n_only = sum(
        1 for s in seed_summaries if s["truth_fi_native"] and not s["truth_fi_no_opp"]
    )
    u_only = sum(
        1 for s in seed_summaries if s["truth_fi_no_opp"] and not s["truth_fi_native"]
    )
    both_t = sum(
        1 for s in seed_summaries if s["truth_fi_native"] and s["truth_fi_no_opp"]
    )
    neither_t = sum(
        1
        for s in seed_summaries
        if (not s["truth_fi_native"]) and (not s["truth_fi_no_opp"])
    )

    return {
        "n_seeds": n,
        "theta_w": THETA_W,
        "rounds": R,
        "version": ABLATION_VERSION,
        "false_fi_total_native": false_fi_n,
        "false_fi_total_no_opp": false_fi_u,
        "false_fi_per_seed_native": [s["n_false_fi_native"] for s in seed_summaries],
        "false_fi_per_seed_no_opp": [s["n_false_fi_no_opp"] for s in seed_summaries],
        "false_fi_mean_native": false_fi_n / n,
        "false_fi_mean_no_opp": false_fi_u / n,
        "seeds_native_more_false_fi": more_n,
        "seeds_no_opp_more_false_fi": more_u,
        "seeds_tie_false_fi": tie_fi,
        "truth_fi_native_k": truth_n,
        "truth_fi_no_opp_k": truth_u,
        "truth_fi_native_rate": p_tn,
        "truth_fi_native_wilson95": [lo_tn, hi_tn],
        "truth_fi_no_opp_rate": p_tu,
        "truth_fi_no_opp_wilson95": [lo_tu, hi_tu],
        "truth_fi_discordant_native_only": n_only,
        "truth_fi_discordant_no_opp_only": u_only,
        "truth_fi_both": both_t,
        "truth_fi_neither": neither_t,
        "paired_direction_counts": dict(dirs),
        "finite_delta_n": len(finite),
        "finite_delta_median": float(statistics.median(finite)) if finite else None,
        "finite_delta_mean": float(statistics.mean(finite)) if finite else None,
        "fi_no_single_chi2_native": n_nov,
        "fi_no_single_chi2_no_opp": u_nov,
        "fi_events_native": len(n_fi_rows),
        "fi_events_no_opp": len(u_fi_rows),
        "incumbent_native": dict(inc_n),
        "incumbent_no_opp": dict(inc_u),
        "truth_lock_native_k": truth_lock_n,
        "truth_lock_no_opp_k": truth_lock_u,
        "native_disk_reproduction_all_match": disk_ok,
        "disk_fail_seeds": [d["seed"] for d in disk_checks if not d.get("match")],
    }


def write_report(agg: dict, path: Path) -> str:
    disk_ok = agg["native_disk_reproduction_all_match"]
    n = agg["n_seeds"]
    if n != 20:
        verdict = "INVALID"
        reason = f"expected 20 seeds, got {n}"
    elif not disk_ok:
        verdict = "FIX"
        reason = f"Native disk reproduction failed for seeds {agg['disk_fail_seeds']}"
    else:
        verdict = "PASS"
        reason = "20/20 completed; Native matches formal disk; CRN ablation intact"

    # Independent causal role — descriptive only (post-experiment judgment text)
    causal_note = (
        "机会分配反馈是否具有独立因果作用：本报告仅提供配对描述性证据。"
        "若两臂在真实模型 FI / 假模型 FI 时序上出现系统性差异，支持"
        "「proposer 权重通道」在完整闭环中改变退出轨迹；"
        "因仍保留拟合→支持→剪枝反馈，不能解释为取消全部递归。"
        "种子级差异与 Wilson 区间见下；候选事件非独立样本。"
    )

    lines = [
        "# Opportunity-Feedback Ablation — 正式实验报告（v0.2 CRN）",
        "",
        f"**裁决：`{verdict}`** — {reason}",
        "",
        f"版本：`{agg['version']}`  |  seeds=1–20  |  R={agg['rounds']}  |  Θ_W={agg['theta_w']}",
        f"输出：`{FORMAL_RESULTS_DIR}`",
        "",
        "## 设计回顾",
        "",
        "- Native：proposer 抽样 ∝ `w_all`（原机会分配反馈）",
        "- No-Opp-Feedback：存活候选均匀 proposer 权重（CRN 同 RNG seed）",
        "- 提名函数 / 拟合 / 支持更新 / `w_surv<0.02` 剪枝 / χ² / 预算：**相同**",
        "- `pilot_fi_anchor`：**未修改**；未调参、未按结果筛种子",
        "",
        "## Native 与原正式日志复现",
        "",
        f"- 全部 20 seed 与 `outputs/pilot_fi_anchor/seed_XX.json` Native 轨迹一致："
        f"**{disk_ok}**",
        f"- 失败 seeds：{agg['disk_fail_seeds'] or '无'}",
        "",
        "## 真实模型失去决策资格（seed 级，n=20）",
        "",
        f"| 臂 | k/20 | 率 | Wilson 95% CI |",
        f"|---|---|---|---|",
        f"| Native | {agg['truth_fi_native_k']}/20 | {agg['truth_fi_native_rate']:.2f} | "
        f"[{agg['truth_fi_native_wilson95'][0]:.2f}, {agg['truth_fi_native_wilson95'][1]:.2f}] |",
        f"| No-Opp | {agg['truth_fi_no_opp_k']}/20 | {agg['truth_fi_no_opp_rate']:.2f} | "
        f"[{agg['truth_fi_no_opp_wilson95'][0]:.2f}, {agg['truth_fi_no_opp_wilson95'][1]:.2f}] |",
        "",
        f"配对四格：Native-only={agg['truth_fi_discordant_native_only']}；"
        f"NoOpp-only={agg['truth_fi_discordant_no_opp_only']}；"
        f"both={agg['truth_fi_both']}；neither={agg['truth_fi_neither']}。",
        "",
        "## 假模型 FI 退出",
        "",
        f"- 事件总数：Native **{agg['false_fi_total_native']}**；"
        f"No-Opp **{agg['false_fi_total_no_opp']}**"
        f"（每臂至多 20×4=80；事件相关，非独立）",
        f"- 每 seed 均值：Native {agg['false_fi_mean_native']:.2f}；"
        f"No-Opp {agg['false_fi_mean_no_opp']:.2f}",
        f"- 每 seed 计数 Native：{agg['false_fi_per_seed_native']}",
        f"- 每 seed 计数 No-Opp：{agg['false_fi_per_seed_no_opp']}",
        f"- seed 级比较：Native 更多假 FI 的 seeds={agg['seeds_native_more_false_fi']}；"
        f"No-Opp 更多={agg['seeds_no_opp_more_false_fi']}；平局={agg['seeds_tie_false_fi']}",
        "",
        "## 配对退出时序（假模型 × seed，右删失正确处理）",
        "",
        f"- 方向计数：{agg['paired_direction_counts']}",
        f"  （`native_earlier` / `no_opp_earlier` / `same_round` / `both_censored`）",
        f"- 有限 Δ（双端均退出）n={agg['finite_delta_n']}；"
        f"中位={agg['finite_delta_median']}；均={agg['finite_delta_mean']}",
        "- **未**用删失哨兵填入中位数",
        "",
        "## 退出当轮证据状态（假模型 FI 事件）",
        "",
        f"- Native FI 事件中当轮 `violated=false`："
        f"{agg['fi_no_single_chi2_native']}/{agg['fi_events_native']}",
        f"- No-Opp FI 事件中当轮 `violated=false`："
        f"{agg['fi_no_single_chi2_no_opp']}/{agg['fi_events_no_opp']}",
        "",
        "## 最终首位模型",
        "",
        f"- Native incumbent：{agg['incumbent_native']}；锁定 hump {agg['truth_lock_native_k']}/20",
        f"- No-Opp incumbent：{agg['incumbent_no_opp']}；锁定 hump {agg['truth_lock_no_opp_k']}/20",
        "",
        "## 机制解释（实验后判断，非调参）",
        "",
        causal_note,
        "",
        "## 产物",
        "",
        "- `seed_XX_paired.json`（逐轮 rounds + sites）",
        "- `formal_seed_summary.csv`",
        "- `formal_paired_timing.csv`",
        "- `formal_truth_loss.csv`",
        "- `formal_exit_events.csv`",
        "- `formal_native_reproduction.csv`",
        "- `formal_aggregate.json` / `formal_report.md` / `verdict.json`",
        "",
        "**未修改论文；未启动其他实验。**",
        "",
        f"**最终裁决：`{verdict}`**",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return verdict


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    # Refuse if isolation marker failed
    marker = Path(__file__).resolve().parent / "_isolation_tests_ok"
    if not (marker.is_file() and marker.read_text(encoding="utf-8").strip() == "PASS"):
        print("[formal] isolation tests marker not PASS — refusing", flush=True)
        (OUT / "verdict.json").write_text(
            json.dumps({"verdict": "INVALID", "reason": "isolation_marker_missing"}, indent=2),
            encoding="utf-8",
        )
        return 2

    seed_summaries: list[dict] = []
    timing_all: list[dict] = []
    truth_all: list[dict] = []
    exits_all: list[dict] = []
    disk_checks: list[dict] = []
    t0 = time.time()

    for seed in FORMAL_SEEDS:
        print(f"[formal] seed={seed}/20 ...", flush=True)
        t_s = time.time()
        rec = run_paired_seed(seed, rounds=R)
        (OUT / f"seed_{seed:02d}_paired.json").write_text(
            json.dumps(rec, indent=2, default=str), encoding="utf-8"
        )
        ana = analyze_seed(rec)
        seed_summaries.append(ana["seed_summary"])
        timing_all.extend(ana["timing_rows"])
        truth_all.append(ana["truth_row"])
        exits_all.extend(ana["exit_events"])
        disk_checks.append(check_disk_native(seed, rec))
        print(
            f"[formal] seed={seed} done in {time.time()-t_s:.1f}s; "
            f"false_fi N/U={ana['seed_summary']['n_false_fi_native']}/"
            f"{ana['seed_summary']['n_false_fi_no_opp']}; "
            f"truth_fi N/U={ana['seed_summary']['truth_fi_native']}/"
            f"{ana['seed_summary']['truth_fi_no_opp']}; "
            f"disk={disk_checks[-1]['match']}",
            flush=True,
        )

    agg = aggregate(seed_summaries, timing_all, truth_all, disk_checks)
    write_csv(OUT / "formal_seed_summary.csv", seed_summaries)
    write_csv(OUT / "formal_paired_timing.csv", timing_all)
    write_csv(OUT / "formal_truth_loss.csv", truth_all)
    write_csv(OUT / "formal_exit_events.csv", exits_all)
    write_csv(OUT / "formal_native_reproduction.csv", disk_checks)
    (OUT / "formal_aggregate.json").write_text(
        json.dumps(agg, indent=2, default=str), encoding="utf-8"
    )
    verdict = write_report(agg, OUT / "formal_report.md")
    (OUT / "verdict.json").write_text(
        json.dumps(
            {
                "verdict": verdict,
                "version": ABLATION_VERSION,
                "elapsed_sec": time.time() - t0,
                "aggregate": agg,
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"[formal] verdict={verdict} elapsed={time.time()-t0:.1f}s -> {OUT}", flush=True)
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
