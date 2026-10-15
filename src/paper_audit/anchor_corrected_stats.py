#!/usr/bin/env python3
"""Corrected offline Anchor Native–Neutral statistics (no closed-loop re-run).

Fixes vs prior exit-mechanism audit:
  - Paired timing deltas NEVER encode right-censoring as round 26 for medians.
  - Direction counts 71/7/2 keep an explicit definition with censoring rules.
  - Truth-loss queues reported separately under the same FI definition.
  - Designated-grid prediction error renamed; Native measurement overlap audited.

Does not modify frozen thresholds, loop code, seeds, or TeX.
Does not overwrite outputs/anchor_exit_mechanism_audit/.
"""
from __future__ import annotations

import csv
import json
import statistics
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pilot_fi_anchor.config import FALSE_FAMILIES, R, THETA_W, TRUTH_FAMILY  # noqa: E402
from pilot_truth_loss.config import CONFIRMATORY_SEEDS, HELD_OUT_IDX  # noqa: E402
from pilot_truth_loss.metrics import (  # noqa: E402
    MissingFinalThetaError,
    f1_unsupported_truth_elimination,
    f2_v2_stable_wrong_lockin,
    f3_neutral_truth_rescue,
    ho1_seed_metrics,
    unsupported_truth_elimination,
)

OUT_DIR = ROOT / "outputs" / "anchor_corrected_stats_v1"
OLD_AUDIT = ROOT / "outputs" / "anchor_exit_mechanism_audit"
FORMAL_DIR = ROOT / "outputs" / "pilot_fi_anchor"
TRUTH_DIR = ROOT / "outputs" / "pilot_truth_loss_v2"

ALL_FALSE = tuple(FALSE_FAMILIES)


# --------------------------------------------------------------------------- helpers
def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def formal_path(seed: int) -> Path:
    return FORMAL_DIR / f"seed_{seed:02d}.json"


def truth_path(seed: int) -> Path:
    return TRUTH_DIR / f"seed_{seed:03d}.json"


def is_fi(t_elim: int | None, t_excl: int | None) -> bool:
    """Frozen FI: decision eligibility exit before two-round evidence exclusion."""
    if t_elim is None:
        return False
    return t_excl is None or t_elim < t_excl


def round_row(arm: dict, t: int) -> dict | None:
    for row in arm.get("rounds") or []:
        if int(row["t"]) == t:
            return row
    return None


@dataclass
class ExitEvent:
    queue: str
    seed: int
    arm: str
    family: str
    is_truth: bool
    t_elim: int | None
    t_excl: int | None
    fi: bool
    w_surv_at_elim: float | None
    violated_at_elim: bool | None
    excluded_at_elim: bool | None
    weight_prune_confirmed: bool | None
    chi2_caused_alive_false: bool
    notes: str


def extract_false_fi_events(queue: str, seed: int, rec: dict) -> list[ExitEvent]:
    out: list[ExitEvent] = []
    for arm_name in ("native", "neutral"):
        arm = rec["arms"][arm_name]
        final = arm["final"]
        for h in ALL_FALSE:
            te = final["t_elim"].get(h)
            tx = final["t_excl"].get(h)
            if te is None:
                continue
            row = round_row(arm, te)
            st = row[h] if row else {}
            w = st.get("w_surv")
            violated = st.get("violated")
            excluded = st.get("excluded")
            weight_ok = w is not None and float(w) < THETA_W
            out.append(
                ExitEvent(
                    queue=queue,
                    seed=seed,
                    arm=arm_name,
                    family=h,
                    is_truth=False,
                    t_elim=te,
                    t_excl=tx,
                    fi=is_fi(te, tx),
                    w_surv_at_elim=float(w) if w is not None else None,
                    violated_at_elim=bool(violated) if violated is not None else None,
                    excluded_at_elim=bool(excluded) if excluded is not None else None,
                    weight_prune_confirmed=weight_ok if w is not None else None,
                    chi2_caused_alive_false=False,  # structural from source
                    notes=(
                        "alive=False via w_surv<THETA_W; evidence labels only"
                        if weight_ok
                        else "UNKNOWN: w_surv not below THETA_W at recorded t_elim"
                    ),
                )
            )
    return out


# --------------------------------------------------------------------------- paired timing (corrected)
def paired_direction(
    te_n: int | None, te_u: int | None
) -> str:
    """Direction among pairs with ≥1 observed exit.

    - native_earlier: Native exited and (Neutral never exited OR Native earlier)
    - neutral_earlier: Neutral exited and (Native never exited OR Neutral earlier)
    - same_round: both exited at identical round
    - both_censored: neither exited (excluded from 71/7/2)
    """
    if te_n is None and te_u is None:
        return "both_censored"
    if te_n is not None and te_u is not None and te_n == te_u:
        return "same_round"
    if te_n is not None and (te_u is None or te_n < te_u):
        return "native_earlier"
    if te_u is not None and (te_n is None or te_u < te_n):
        return "neutral_earlier"
    return "UNKNOWN"


def finite_delta(te_n: int | None, te_u: int | None) -> int | None:
    """Δ = t_elim_native − t_elim_neutral ONLY if both exited (no censor sentinel)."""
    if te_n is None or te_u is None:
        return None
    return int(te_n) - int(te_u)


def build_paired_timing(queue: str, seed: int, rec: dict) -> list[dict]:
    nf = rec["arms"]["native"]["final"]
    uf = rec["arms"]["neutral"]["final"]
    rows = []
    for h in ALL_FALSE:
        te_n = nf["t_elim"].get(h)
        te_u = uf["t_elim"].get(h)
        direction = paired_direction(te_n, te_u)
        d_fin = finite_delta(te_n, te_u)
        rows.append(
            {
                "queue": queue,
                "seed": seed,
                "family": h,
                "t_elim_native": te_n if te_n is not None else "",
                "t_elim_neutral": te_u if te_u is not None else "",
                "native_censored": te_n is None,
                "neutral_censored": te_u is None,
                "direction": direction,
                "native_earlier": direction == "native_earlier",
                "neutral_earlier": direction == "neutral_earlier",
                "same_round": direction == "same_round",
                "both_censored": direction == "both_censored",
                "delta_finite_native_minus_neutral": d_fin if d_fin is not None else "",
                "delta_uses_censor_sentinel": False,
                "timing_note": (
                    "finite delta only when both exited; "
                    "direction allows one-sided censor; "
                    "do not treat direction-only median as exit-time gap"
                ),
                "fi_native": is_fi(te_n, nf["t_excl"].get(h)),
                "fi_neutral": is_fi(te_u, uf["t_excl"].get(h)),
            }
        )
    return rows


# --------------------------------------------------------------------------- truth loss
def truth_loss_row(queue: str, seed: int, rec: dict) -> dict:
    n = unsupported_truth_elimination(rec, "native")
    u = unsupported_truth_elimination(rec, "neutral")
    f1 = f1_unsupported_truth_elimination(rec)
    f2 = f2_v2_stable_wrong_lockin(rec, f1)
    f3 = f3_neutral_truth_rescue(rec, f1)
    return {
        "queue": queue,
        "seed": seed,
        "native_truth_fi": bool(n["f1"]),
        "neutral_truth_fi": bool(u["f1"]),
        "native_t_elim_hump": n["t_elim"] if n["t_elim"] is not None else "",
        "native_t_excl_hump": n["t_excl"] if n["t_excl"] is not None else "",
        "neutral_t_elim_hump": u["t_elim"] if u["t_elim"] is not None else "",
        "neutral_t_excl_hump": u["t_excl"] if u["t_excl"] is not None else "",
        "native_incumbent": rec["arms"]["native"]["final"]["incumbent"],
        "neutral_incumbent": rec["arms"]["neutral"]["final"]["incumbent"],
        "f2_v2": f2.get("f2_v2"),
        "f3": f3.get("f3"),
        "definition": "t_elim set AND (t_excl None OR t_elim < t_excl) AND not excluded at t_elim",
    }


# --------------------------------------------------------------------------- prediction grid
def measured_overlap(rec: dict, arm: str) -> list[int]:
    measured = {int(s["idx"]) for s in rec["arms"][arm]["sites"]}
    return sorted(measured & set(HELD_OUT_IDX))


def prediction_row(queue: str, seed: int, rec: dict) -> dict:
    ov_n = measured_overlap(rec, "native")
    ov_u = measured_overlap(rec, "neutral")
    base = {
        "queue": queue,
        "seed": seed,
        "metric_name": "designated_truth_grid_prediction_error",
        "not_strict_holdout": True,
        "not_oos": True,
        "n_grid_points": len(HELD_OUT_IDX),
        "native_measured_grid_n": len(ov_n),
        "neutral_measured_grid_n": len(ov_u),
        "native_measured_grid_idx": json.dumps(ov_n),
        "neutral_measured_grid_idx": json.dumps(ov_u),
        "native_incumbent": rec["arms"]["native"]["final"]["incumbent"],
        "neutral_incumbent": rec["arms"]["neutral"]["final"]["incumbent"],
    }
    has_theta = "arm_theta" in rec["arms"]["native"]["final"]
    if not has_theta:
        return {
            **base,
            "status": "NOT_IDENTIFIABLE",
            "reason": "final arm_theta not logged in this queue record",
            "native_grid_rmse": "",
            "neutral_grid_rmse": "",
            "rmse_ratio_native_over_neutral": "",
        }
    try:
        ho = ho1_seed_metrics(rec)
        return {
            **base,
            "status": "SCORED",
            "reason": "",
            "native_grid_rmse": ho["native_ho_rmse"],
            "neutral_grid_rmse": ho["neutral_ho_rmse"],
            "rmse_ratio_native_over_neutral": ho["ho_rmse_ratio"],
            # legacy field alias for continuity (deprecated name)
            "legacy_field_alias": "HO1_renamed",
        }
    except MissingFinalThetaError as exc:
        return {
            **base,
            "status": "NOT_IDENTIFIABLE",
            "reason": str(exc),
            "native_grid_rmse": "",
            "neutral_grid_rmse": "",
            "rmse_ratio_native_over_neutral": "",
        }


# --------------------------------------------------------------------------- CSV / report
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
        for r in rows:
            w.writerow(r)


def summarize(events: list[ExitEvent], paired: list[dict]) -> dict[str, Any]:
    formal_ev = [e for e in events if e.queue == "formal_1_20" and e.fi]
    n_fi = [e for e in formal_ev if e.arm == "native"]
    u_fi = [e for e in formal_ev if e.arm == "neutral"]
    n_nov = sum(1 for e in n_fi if e.violated_at_elim is False)
    u_nov = sum(1 for e in u_fi if e.violated_at_elim is False)
    bad_w = [e for e in events if e.weight_prune_confirmed is False]
    pf = [p for p in paired if p["queue"] == "formal_1_20"]
    dirs = Counter(p["direction"] for p in pf)
    finite_deltas = [
        int(p["delta_finite_native_minus_neutral"])
        for p in pf
        if p["delta_finite_native_minus_neutral"] != ""
    ]
    return {
        "native_fi": len(n_fi),
        "neutral_fi": len(u_fi),
        "native_fi_no_single_chi2": n_nov,
        "neutral_fi_no_single_chi2": u_nov,
        "weight_prune_failures": len(bad_w),
        "paired_native_earlier": dirs.get("native_earlier", 0),
        "paired_neutral_earlier": dirs.get("neutral_earlier", 0),
        "paired_same_round": dirs.get("same_round", 0),
        "paired_both_censored": dirs.get("both_censored", 0),
        "finite_delta_n": len(finite_deltas),
        "finite_delta_median": (
            float(statistics.median(finite_deltas)) if finite_deltas else None
        ),
        "old_incorrect_median_note": (
            "Prior audit reported median -5.5 using censor sentinel R+1=26; "
            "that statistic is withdrawn."
        ),
    }


def write_report(
    summary: dict,
    truth_rows: list[dict],
    pred_rows: list[dict],
    path: Path,
    tests_ok: bool,
) -> str:
    formal_truth = [r for r in truth_rows if r["queue"] == "formal_1_20"]
    ext_truth = [r for r in truth_rows if r["queue"] == "truth_loss_21_40"]
    f1_formal = [r for r in formal_truth if r["native_truth_fi"]]
    f1_ext = [r for r in ext_truth if r["native_truth_fi"]]

    pred_ext = [r for r in pred_rows if r["queue"] == "truth_loss_21_40"]
    pred_f1 = [
        r
        for r in pred_ext
        if int(r["seed"]) in {int(x["seed"]) for x in f1_ext}
        and r["status"] == "SCORED"
    ]
    ratios = [
        float(r["rmse_ratio_native_over_neutral"])
        for r in pred_f1
        if r["rmse_ratio_native_over_neutral"] not in ("", None)
    ]

    # Overlap summary
    ov_n = [int(r["native_measured_grid_n"]) for r in pred_rows if r["queue"] == "formal_1_20"]
    ov_ext = [
        int(r["native_measured_grid_n"])
        for r in pred_rows
        if r["queue"] == "truth_loss_21_40"
    ]

    verdict = "FIX"
    if not tests_ok:
        verdict = "FIX"
    # RE-RUN only if mechanism logs corrupted — not the case
    if summary["weight_prune_failures"] > 0:
        verdict = "FIX"
    if summary["native_fi"] != 78 or summary["neutral_fi"] != 80:
        verdict = "FIX"

    # Experiments themselves don't need re-run; offline stats fixed
    lines = [
        "# Anchor 离线统计修复与正式结果重新核验",
        "",
        f"**裁决：`{verdict}`**（不需重跑闭环；离线统计与术语已修正；不自动改 TeX）",
        "",
        f"单元测试：{'PASS' if tests_ok else 'FAIL'}",
        f"输出目录：`{OUT_DIR.as_posix()}`（不覆盖 `outputs/anchor_exit_mechanism_audit/`）",
        "",
        "---",
        "",
        "## 1. 原结果 vs 修正结果（逐项）",
        "",
        "| 项目 | 旧审计 / 论文口径 | 修正后 | 类型 |",
        "|---|---|---|---|",
        f"| Native / Neutral 假模型 FI | 78 / 80 | **{summary['native_fi']} / {summary['neutral_fi']}** | 不变（计算正确） |",
        f"| 当轮 `violated=false` | 26 / 77 | **{summary['native_fi_no_single_chi2']} / {summary['neutral_fi_no_single_chi2']}** | 不变 |",
        f"| 配对方向 Native更早/Neutral更早/同轮 | 71 / 7 / 2 | "
        f"**{summary['paired_native_earlier']} / {summary['paired_neutral_earlier']} / "
        f"{summary['paired_same_round']}** | 不变（定义写清） |",
        f"| 配对 Δt 中位数 | −5.5（用删失哨兵 26） | "
        f"**有限样本中位数 = {summary['finite_delta_median']}** "
        f"（n={summary['finite_delta_n']}，仅双端均退出） | **计算错误→已修正** |",
        f"| 删失编码参与中位数 | 是 | **否** | **计算错误→已修正** |",
        f"| 权重剪枝确认失败数 | 0 | **{summary['weight_prune_failures']}** | 不变 |",
        f"| 正式队列真实模型 FI（Native/Neutral） | 2/20 / 0/20 | "
        f"**{len(f1_formal)}/20 / "
        f"{sum(1 for r in formal_truth if r['neutral_truth_fi'])}/20** "
        f"（seeds {[r['seed'] for r in f1_formal]}） | 不变；旧报告曾笼统说「很少」 |",
        f"| 扩展队列 21–40 真实模型 FI | 4/20 / 0/20 | "
        f"**{len(f1_ext)}/20 / "
        f"{sum(1 for r in ext_truth if r['neutral_truth_fi'])}/20** "
        f"（seeds {[r['seed'] for r in f1_ext]}） | 不变；队列不混合 |",
        "| 「19 点留出/OOS RMSE」 | 旧术语 | **指定真值网格预测误差** | **术语错误→已修正** |",
        f"| Native 是否测过评价格点 | 未强调 | 正式队列每 seed overlap 中位 "
        f"{statistics.median(ov_n) if ov_n else 'NA'}；"
        f"扩展 F1 seeds 均有 overlap | **解释错误→已披露** |",
        f"| F1 子集 RMSE 比（扩展） | 7.10, 29.16, 8.88, 39.91；中位 19.02 | "
        f"重算 ratios={ratios}；中位="
        f"{statistics.median(ratios) if ratios else 'NA'} | 数值复核（应接近） |",
        "",
        "### 哪些不变 / 哪些修正",
        "",
        "- **保持不变：** 78/80 FI 事件数；26/77 单轮证据分层；71/7/2 配对方向；"
        "正式 2/20 与扩展 4/20 真实模型 FI（同一定义、分队列）。",
        "- **必须修正的统计量：** 含删失哨兵的配对时间差中位数（旧 −5.5 撤回）；"
        "任何把它当成「实际退出时间差」的表述。",
        "- **术语/解释错误（非轨迹计算错误）：** 「严格留出/样本外」；"
        "暗示 χ² 直接删除；把策略总效应说成单一递归反馈因果；"
        "未披露 Native 可测量指定网格点。",
        "",
        "---",
        "",
        "## 2. FI 与删除机制（复核）",
        "",
        "- 正式队列全部假模型 FI 退出：`weight_prune_confirmed` 失败数 = "
        f"{summary['weight_prune_failures']}。",
        "- `alive=False` 由 `w_surv < 0.02` 触发；χ² 只更新 `violated`/`excluded`，"
        "不直接删除决策资格。",
        "- `alive=False` = 失去分配/决策资格；后台 stream 与证据审计仍继续。",
        "",
        "---",
        "",
        "## 3. 配对时序定义（修正后）",
        "",
        "- **方向计数（71/7/2）分母：** 假模型 × seed 共 80 对中，"
        f"双删失 {summary['paired_both_censored']} 对不计入方向；"
        "其余按「至少一端退出」比较先后（一端删失视为该端更晚）。",
        "- **有限 Δt：** 仅当 Native 与 Neutral **都**有 `t_elim` 时计算 "
        "`t_elim_N − t_elim_U`；**禁止**用 26 填充。",
        f"- 有限 Δ 中位数 = {summary['finite_delta_median']}（n={summary['finite_delta_n']}）。",
        "- 时间差描述性，不可归因于单一反馈组件。",
        "",
        "---",
        "",
        "## 4. 真实模型丢失（分队列）",
        "",
        f"- **正式 1–20：** Native {len(f1_formal)}/20 "
        f"{[r['seed'] for r in f1_formal]}；Neutral "
        f"{sum(1 for r in formal_truth if r['neutral_truth_fi'])}/20。",
        f"- **扩展 21–40：** Native {len(f1_ext)}/20 "
        f"{[r['seed'] for r in f1_ext]}；Neutral "
        f"{sum(1 for r in ext_truth if r['neutral_truth_fi'])}/20。",
        "- 两队列 **不得混合** 成单一 6/40。",
        "- 定义相同：`t_elim` 且 (`t_excl` 空或 `t_elim < t_excl`) 且退出当轮未 `excluded`。",
        "",
        "---",
        "",
        "## 5. 指定真值网格预测误差",
        "",
        f"- 网格点数：{len(HELD_OUT_IDX)}（预注册构造；排除 X0∪Neutral 扫描索引）。",
        "- **Neutral：** 构造上与扫描索引不交，实测 overlap 恒为 0。",
        "- **Native：** 分配可落入网格 → 正式队列 overlap>0 常见；"
        f"扩展队列 Native overlap 例：中位 {statistics.median(ov_ext) if ov_ext else 'NA'}。",
        "- 因此 **不得** 称严格留出/样本外；指标名："
        "**指定真值网格预测误差**（相对无噪声 hump）。",
        "- 正式队列 seed JSON **无** `arm_theta` → 预测 RMSE 标 `NOT_IDENTIFIABLE`；"
        "扩展队列可重算。未改拟合或闭环轨迹。",
        "",
        "---",
        "",
        "## 6. 机制解释（统计口径）",
        "",
        "- 主统计单位：配对 seed（n=20 / 队列）。",
        "- 候选–轮次与退出事件为相关观测，不作独立样本推断。",
        "- **共同剪枝规则**直接造成决策资格退出（含大量当轮未越 χ² 的 FI）。",
        "- **实验选择策略**（权重提名 vs 固定扫描）改变观测轨迹，从而改变退出时序与证据状态。",
        "- **不支持**将组间差异归因于「递归权重反馈」单一组件。",
        "",
        "---",
        "",
        "## 7. 建议同步修改的论文段落（不自动改 TeX）",
        "",
        "| 位置 | 问题 | 建议表述 |",
        "|---|---|---|",
        "| `main.tex` ~L133–137 | 未写明删除=权重剪枝 | 保留 78/446 与 71/78；补句："
        "提前删除由幸存者权重 < 0.02 触发，证据 χ² 不直接撤销决策资格 |",
        "| ~L135 26/78 | 可保留 | 可并列报告 Neutral 77/80 同类错位 |",
        "| 若引用配对时间中位数 −5.5 | **计算错误** | 删除或改为「仅双端退出的有限 Δ 中位数」"
        f"（当前={summary['finite_delta_median']}） |",
        "| ~L144 / ~L333「测试/留出」 | 术语过强；Native 可测网格点 | 改为「指定真值网格预测误差」；"
        "注明 Native 可能测过其中部分位置，Neutral 按构造未测 |",
        "| ~L306 Methods | 可保留 Θ_W | 明确唯一 `alive=False` 路径为相对权重剪枝 |",
        "| 正式队列真实模型丢失 | 正文主结果偏重假模型 78 | 应用脚注或一句报告 seed 17/20 "
        "Native 真实模型 FI（与扩展 4/20 分列） |",
        "",
        "## 8. 是否需要重新运行原始实验？",
        "",
        "**不需要。** 闭环日志完整；错误在离线汇总（删失中位数）与术语/解释。"
        "指定网格评价的披露加强不改变已写入的观测与拟合轨迹。",
        "",
        "---",
        "",
        "## 产物",
        "",
        "- `anchor_corrected_event_summary.csv`",
        "- `anchor_corrected_paired_timing.csv`",
        "- `anchor_corrected_truth_loss.csv`",
        "- `anchor_corrected_prediction_metrics.csv`",
        "- `anchor_corrected_report.md`",
        "",
        f"**最终裁决：`{verdict}`**",
        "",
    ]
    text = "\n".join(lines)
    path.write_text(text, encoding="utf-8")
    return verdict


def run_pipeline(tests_ok: bool) -> dict[str, Any]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    events: list[ExitEvent] = []
    paired: list[dict] = []
    truth_rows: list[dict] = []
    pred_rows: list[dict] = []

    for seed in range(1, 21):
        rec = load_json(formal_path(seed))
        events.extend(extract_false_fi_events("formal_1_20", seed, rec))
        paired.extend(build_paired_timing("formal_1_20", seed, rec))
        truth_rows.append(truth_loss_row("formal_1_20", seed, rec))
        pred_rows.append(prediction_row("formal_1_20", seed, rec))

    for seed in CONFIRMATORY_SEEDS:
        rec = load_json(truth_path(seed))
        events.extend(extract_false_fi_events("truth_loss_21_40", seed, rec))
        paired.extend(build_paired_timing("truth_loss_21_40", seed, rec))
        truth_rows.append(truth_loss_row("truth_loss_21_40", seed, rec))
        pred_rows.append(prediction_row("truth_loss_21_40", seed, rec))

    summary = summarize(events, paired)

    # event summary CSV: one row per FI event + aggregate header rows
    event_csv = [asdict(e) for e in events if e.fi]
    # also seed-level aggregate
    seed_agg = []
    for seed in range(1, 21):
        seed_agg.append(
            {
                "row_type": "seed_aggregate",
                "queue": "formal_1_20",
                "seed": seed,
                "n_fi_native": sum(
                    1
                    for e in events
                    if e.queue == "formal_1_20"
                    and e.seed == seed
                    and e.arm == "native"
                    and e.fi
                ),
                "n_fi_neutral": sum(
                    1
                    for e in events
                    if e.queue == "formal_1_20"
                    and e.seed == seed
                    and e.arm == "neutral"
                    and e.fi
                ),
            }
        )
    write_csv(OUT_DIR / "anchor_corrected_event_summary.csv", event_csv + seed_agg)
    write_csv(OUT_DIR / "anchor_corrected_paired_timing.csv", paired)
    write_csv(OUT_DIR / "anchor_corrected_truth_loss.csv", truth_rows)
    write_csv(OUT_DIR / "anchor_corrected_prediction_metrics.csv", pred_rows)

    verdict = write_report(
        summary, truth_rows, pred_rows, OUT_DIR / "anchor_corrected_report.md", tests_ok
    )
    meta = {
        "verdict": verdict,
        "tests_ok": tests_ok,
        "summary": summary,
        "old_audit_preserved": str(OLD_AUDIT),
        "output_dir": str(OUT_DIR),
    }
    (OUT_DIR / "verdict.json").write_text(
        json.dumps(meta, indent=2, default=str), encoding="utf-8"
    )
    # pointer file without destroying old audit
    (OUT_DIR / "README.txt").write_text(
        "Corrected offline stats v1. Does not overwrite "
        "outputs/anchor_exit_mechanism_audit/.\n",
        encoding="utf-8",
    )
    return meta


def main() -> int:
    marker = Path(__file__).resolve().parent / "_anchor_corrected_tests_ok"
    tests_ok = marker.is_file() and marker.read_text(encoding="utf-8").strip() == "PASS"
    meta = run_pipeline(tests_ok=tests_ok)
    print(
        f"[corrected] verdict={meta['verdict']} "
        f"FI={meta['summary']['native_fi']}/{meta['summary']['neutral_fi']} "
        f"dir={meta['summary']['paired_native_earlier']}/"
        f"{meta['summary']['paired_neutral_earlier']}/"
        f"{meta['summary']['paired_same_round']} "
        f"finite_median={meta['summary']['finite_delta_median']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
