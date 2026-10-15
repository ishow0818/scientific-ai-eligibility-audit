#!/usr/bin/env python3
"""Post-hoc Open Eligibility endgame contrast on frozen Stage-2 seeds 201–240.

Read-only over stage2_formal JSON: reuse Native observations, final thetas, and
w_all. No new seeds, resampling, refitting, or edits to frozen arm packs.

Rules
-----
Native           : argmax w_all among historically alive (not weight-pruned)
Open Eligibility : argmax w_all among all five fitted models (ignore prune & χ²)
Decision-Only    : argmax w_all among excluded=False (operational evidence gate)

Answers whether Decision-Only gains come from reopening eligibility alone, or
whether evidence gating has additional effects relative to the full pool.
"""
from __future__ import annotations

import csv
import json
import math
import statistics
from pathlib import Path
from typing import Any

from .config import FAMILY_ORDER, FORMAL_SEEDS, TRUTH_FAMILY
from .eligibility import require_family_bool_map, require_family_flag
from .eval_grid import RMSE_FAIL, rmse_noiseless

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "outputs" / "stage2_formal"
OUT = ROOT / "outputs" / "open_eligibility_posthoc"
FROZEN_DIR = ROOT / "frozen"
LOCK_PATH = FROZEN_DIR / "open_eligibility_lock_v1.json"
LOCK_VERSION = "open-eligibility-lock-v1"
RMSE_ATOL = 1e-12

ARM_A = "native"
ARM_B = "decision_only"
ARM_O = "open_eligibility"


def wilson(k: int, n: int, z: float = 1.96) -> list[float]:
    if n <= 0:
        return [0.0, 0.0, 0.0]
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return [float(p), float(max(0.0, centre - half)), float(min(1.0, centre + half))]


def write_csv(path: Path, rows: list[dict]) -> None:
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


def last_w_all(arm_pack: dict) -> dict[str, float]:
    last = arm_pack["rounds"][-1]
    return {h: float(last[h]["w_all"]) for h in FAMILY_ORDER}


def select_max(w_all: dict[str, float], pool: list[str]) -> str | None:
    if not pool:
        return None
    return max(pool, key=lambda h: float(w_all[h]))


def open_eligibility_from_native(native: dict[str, Any]) -> dict[str, Any]:
    """Offline Open Eligibility: full-pool argmax w_all; ignore prune & excluded."""
    final = native["final"]
    w_all = last_w_all(native)
    pool = list(FAMILY_ORDER)
    incumbent = select_max(w_all, pool)
    excluded = require_family_bool_map(final["excluded"], "final.excluded")
    alive = require_family_bool_map(final["alive"], "final.alive")
    arm_theta = {h: dict(final["arm_theta"][h]) for h in FAMILY_ORDER}
    theta = dict(arm_theta[incumbent]) if incumbent is not None else None
    return {
        "arm_tag": ARM_O,
        "allocation_mode": "offline_reuse_native_trajectory",
        "final": {
            "incumbent": incumbent,
            "eligible": {h: True for h in FAMILY_ORDER},
            "excluded_ignored": excluded,
            "alive_native": alive,
            "w_all": w_all,
            "arm_theta": arm_theta,
            "incumbent_theta": theta,
            "decision_rule": "argmax w_all among all five fitted models",
        },
        "isolation": {
            "reused_native_sites": True,
            "reused_native_rounds": True,
            "reused_native_theta": True,
            "reused_native_w_all": True,
            "closed_loop_rerun": False,
            "uses_history_prune": False,
            "uses_chi2_exclusion": False,
        },
    }


def score_arm(incumbent: str | None, theta: dict | None, n_measured: int) -> dict:
    rmse, status = rmse_noiseless(incumbent, theta)
    is_fail = status != "OK" or rmse is None
    pen = RMSE_FAIL if is_fail else float(rmse)
    return {
        "rmse_eval_noiseless": None if is_fail else float(rmse),
        "rmse_with_fail_penalty": float(pen),
        "primary_status": status,
        "is_failure": is_fail,
        "truth_selected": incumbent == TRUTH_FAMILY,
        "n_measured": n_measured,
    }


def analyze_seed(seed: int) -> dict[str, Any]:
    rec = json.loads((DATA / f"seed_{seed}.json").read_text(encoding="utf-8"))
    a = rec["arms"][ARM_A]
    b = rec["arms"][ARM_B]
    af, bf = a["final"], b["final"]
    w_all = last_w_all(a)

    alive = require_family_bool_map(af["alive"], "native.final.alive")
    excluded = require_family_bool_map(af["excluded"], "native.final.excluded")
    # Reconstruct Native / Decision-Only winners from frozen fields (sanity).
    alive_pool = [h for h in FAMILY_ORDER if alive[h]]
    evidence_pool = [h for h in FAMILY_ORDER if not excluded[h]]
    full_pool = list(FAMILY_ORDER)

    native_recon = select_max(w_all, alive_pool)
    decision_recon = select_max(w_all, evidence_pool)
    open_pack = open_eligibility_from_native(a)
    open_inc = open_pack["final"]["incumbent"]
    assert open_inc is not None

    # Frozen recorded winners
    a_inc = af["incumbent"]
    b_inc = bf["incumbent"]

    n_meas = int(rec["scores"][ARM_A]["n_measured"])
    sc_a = rec["scores"][ARM_A]
    sc_b = rec["scores"][ARM_B]
    sc_o = score_arm(open_inc, open_pack["final"]["incumbent_theta"], n_meas)

    open_winner_excluded = require_family_flag(excluded, open_inc, "excluded")
    open_winner_pruned = not require_family_flag(alive, open_inc, "alive")

    # Parameter reuse: Open theta must be an exact copy of Native arm_theta[winner]
    native_theta_winner = dict(af["arm_theta"][open_inc])
    open_theta = open_pack["final"]["incumbent_theta"]
    theta_reused = open_theta == native_theta_winner
    w_all_reused = open_pack["final"]["w_all"] == w_all

    return {
        "seed": seed,
        "w_all": w_all,
        "alive": alive,
        "excluded": excluded,
        "native_incumbent": a_inc,
        "native_recon": native_recon,
        "decision_only_incumbent": b_inc,
        "decision_only_recon": decision_recon,
        "open_incumbent": open_inc,
        "native_matches_recon": a_inc == native_recon,
        "decision_matches_recon": b_inc == decision_recon,
        "native_truth": bool(sc_a["truth_selected"]),
        "decision_truth": bool(sc_b["truth_selected"]),
        "open_truth": bool(sc_o["truth_selected"]),
        "native_rmse": sc_a["rmse_eval_noiseless"],
        "decision_rmse": sc_b["rmse_eval_noiseless"],
        "open_rmse": sc_o["rmse_eval_noiseless"],
        "native_rmse_penalty": sc_a["rmse_with_fail_penalty"],
        "decision_rmse_penalty": sc_b["rmse_with_fail_penalty"],
        "open_rmse_penalty": sc_o["rmse_with_fail_penalty"],
        "open_vs_native_same": open_inc == a_inc,
        "open_vs_decision_same": open_inc == b_inc,
        "decision_vs_native_same": b_inc == a_inc,
        "open_winner_excluded_by_evidence": open_winner_excluded,
        "open_winner_pruned_by_history": open_winner_pruned,
        "theta_reused_from_native": theta_reused,
        "w_all_reused_from_native": w_all_reused,
        "open_incumbent_theta": open_theta,
        "alive_pool": alive_pool,
        "evidence_pool": evidence_pool,
        "full_pool": full_pool,
        "scores_open": sc_o,
        "open_pack_final": open_pack["final"],
        "isolation": open_pack["isolation"],
    }


def pair_delta(rows: list[dict], key_a: str, key_b: str) -> dict:
    deltas = [float(r[key_a]) - float(r[key_b]) for r in rows]
    return {
        "delta_rmse_penalty_median": statistics.median(deltas),
        "delta_rmse_penalty_mean": statistics.fmean(deltas),
        "n_positive": sum(1 for d in deltas if d > 0),
        "n_negative": sum(1 for d in deltas if d < 0),
        "n_zero": sum(1 for d in deltas if d == 0),
    }


def aggregate(rows: list[dict]) -> dict[str, Any]:
    n = len(rows)
    out: dict[str, Any] = {"n": n}

    for tag, truth_key, rmse_key, pen_key in (
        ("native", "native_truth", "native_rmse", "native_rmse_penalty"),
        ("open_eligibility", "open_truth", "open_rmse", "open_rmse_penalty"),
        ("decision_only", "decision_truth", "decision_rmse", "decision_rmse_penalty"),
    ):
        k = sum(1 for r in rows if r[truth_key])
        rmse_ok = [float(r[rmse_key]) for r in rows if r[rmse_key] is not None]
        pens = [float(r[pen_key]) for r in rows]
        out[tag] = {
            "truth_selected_k": k,
            "truth_selected_rate_wilson95": wilson(k, n),
            "rmse_finite_n": len(rmse_ok),
            "rmse_finite_median": statistics.median(rmse_ok) if rmse_ok else None,
            "rmse_finite_mean": statistics.fmean(rmse_ok) if rmse_ok else None,
            "rmse_penalty_median": statistics.median(pens),
            "rmse_penalty_mean": statistics.fmean(pens),
        }

    out["A_minus_O"] = pair_delta(rows, "native_rmse_penalty", "open_rmse_penalty")
    out["A_minus_B"] = pair_delta(rows, "native_rmse_penalty", "decision_rmse_penalty")
    out["O_minus_B"] = pair_delta(rows, "open_rmse_penalty", "decision_rmse_penalty")

    out["selection_diff"] = {
        "open_ne_native": [r["seed"] for r in rows if not r["open_vs_native_same"]],
        "open_ne_decision": [r["seed"] for r in rows if not r["open_vs_decision_same"]],
        "decision_ne_native": [r["seed"] for r in rows if not r["decision_vs_native_same"]],
        "open_eq_decision_all": all(r["open_vs_decision_same"] for r in rows),
    }

    out["truth_pair"] = {
        "A_yes_O_no": sum(1 for r in rows if r["native_truth"] and not r["open_truth"]),
        "A_no_O_yes": sum(1 for r in rows if (not r["native_truth"]) and r["open_truth"]),
        "O_yes_B_no": sum(1 for r in rows if r["open_truth"] and not r["decision_truth"]),
        "O_no_B_yes": sum(1 for r in rows if (not r["open_truth"]) and r["decision_truth"]),
        "A_yes_B_no": sum(1 for r in rows if r["native_truth"] and not r["decision_truth"]),
        "A_no_B_yes": sum(1 for r in rows if (not r["native_truth"]) and r["decision_truth"]),
    }

    out["open_winner_evidence_excluded_k"] = sum(
        1 for r in rows if r["open_winner_excluded_by_evidence"]
    )
    out["open_winner_history_pruned_k"] = sum(
        1 for r in rows if r["open_winner_pruned_by_history"]
    )
    out["recon_ok"] = {
        "native_all": all(r["native_matches_recon"] for r in rows),
        "decision_all": all(r["decision_matches_recon"] for r in rows),
    }

    # Interpretation flag (descriptive, not a claim of mechanism universality)
    if out["selection_diff"]["open_eq_decision_all"]:
        out["interpretation"] = (
            "Open Eligibility and Decision-Only select identically on all 40 seeds; "
            "observed A→B corrections are explained by reopening eligibility "
            "(full-pool argmax), with no additional case where evidence gating "
            "changes the endgame winner relative to the full pool."
        )
    else:
        out["interpretation"] = (
            "Open Eligibility and Decision-Only differ on some seeds; "
            "inspect per-seed cases for evidence-gate help vs harm "
            "(no presupposed direction)."
        )
    return out


def case_notes(rows: list[dict]) -> list[dict]:
    notes = []
    for r in rows:
        if r["open_vs_native_same"] and r["open_vs_decision_same"]:
            continue
        note = {
            "seed": r["seed"],
            "native": r["native_incumbent"],
            "open": r["open_incumbent"],
            "decision_only": r["decision_only_incumbent"],
            "native_truth": r["native_truth"],
            "open_truth": r["open_truth"],
            "decision_truth": r["decision_truth"],
            "native_rmse": r["native_rmse"],
            "open_rmse": r["open_rmse"],
            "decision_rmse": r["decision_rmse"],
            "open_winner_excluded": r["open_winner_excluded_by_evidence"],
            "open_winner_pruned": r["open_winner_pruned_by_history"],
            "w_all": {h: r["w_all"][h] for h in FAMILY_ORDER},
            "alive": r["alive"],
            "excluded": r["excluded"],
        }
        # Brief attribution text
        if (not r["open_vs_native_same"]) and r["open_vs_decision_same"]:
            note["role"] = (
                "Open==Decision≠Native: gain/loss vs Native attributable to "
                "reopening eligibility; evidence gate does not further change winner"
            )
        elif (not r["open_vs_decision_same"]) and r["open_truth"] and not r["decision_truth"]:
            note["role"] = (
                "Evidence gate harms relative to Open: Decision-Only rejects "
                "full-pool winner (or otherwise selects differently) and loses truth"
            )
        elif (not r["open_vs_decision_same"]) and (not r["open_truth"]) and r["decision_truth"]:
            note["role"] = (
                "Evidence gate helps relative to Open: Decision-Only excludes "
                "full-pool winner and recovers truth"
            )
        elif not r["open_vs_decision_same"]:
            note["role"] = (
                "Open≠Decision: evidence gate changes endgame winner; "
                "truth outcome unchanged or both wrong — inspect weights/exclusion"
            )
        else:
            note["role"] = "Open≠Native with Decision differing — inspect"
        notes.append(note)
    return notes


def render_md(agg: dict, cases: list[dict], rows: list[dict]) -> str:
    a, o, b = agg["native"], agg["open_eligibility"], agg["decision_only"]
    lines = [
        "# Open Eligibility 事后终局对照（冻结 Stage-2，种子 201–240）",
        "",
        "性质：**事后终局重算**。复用 Native 观测、最终拟合参数与 `w_all`；",
        "不新增种子、不重新采样、不重新拟合、不改写 `stage2_formal` 冻结结果。",
        "",
        "## 终局规则",
        "",
        "| 规则 | 选择范围 |",
        "|---|---|",
        "| Native | 未被历史剪枝的模型（`alive`） |",
        "| Open Eligibility | 全部五个已拟合模型 |",
        "| Decision-Only | 未被操作性证据规则排除的模型（`excluded=False`） |",
        "",
        "## 汇总",
        "",
        f"| 指标 | Native | Open Eligibility | Decision-Only |",
        f"|---|---:|---:|---:|",
        f"| 真实模型选择 | {a['truth_selected_k']}/40 | {o['truth_selected_k']}/40 | {b['truth_selected_k']}/40 |",
        f"| 平均预测 RMSE | {a['rmse_finite_mean']:.4f} | {o['rmse_finite_mean']:.4f} | {b['rmse_finite_mean']:.4f} |",
        f"| 中位预测 RMSE | {a['rmse_finite_median']:.4f} | {o['rmse_finite_median']:.4f} | {b['rmse_finite_median']:.4f} |",
        "",
        "### 配对 ΔRMSE（惩罚尺度；正值=前者更差）",
        "",
        f"- Native−Open：{agg['A_minus_O']}",
        f"- Native−Decision-Only：{agg['A_minus_B']}",
        f"- Open−Decision-Only：{agg['O_minus_B']}",
        "",
        "### 选择差异种子",
        "",
        f"- Open ≠ Native：{agg['selection_diff']['open_ne_native']}",
        f"- Open ≠ Decision-Only：{agg['selection_diff']['open_ne_decision']}",
        f"- Decision-Only ≠ Native：{agg['selection_diff']['decision_ne_native']}",
        f"- Open 与 Decision-Only 全队列相同：{agg['selection_diff']['open_eq_decision_all']}",
        "",
        "### 全池赢家与证据/剪枝标签",
        "",
        f"- 全池赢家已被证据规则排除：{agg['open_winner_evidence_excluded_k']}/40",
        f"- 全池赢家已被历史剪枝：{agg['open_winner_history_pruned_k']}/40",
        "",
        f"真模型选择配对：{agg['truth_pair']}",
        "",
        f"重建一致性（应用原规则重算赢家）：{agg['recon_ok']}",
        "",
        "## 解释",
        "",
        agg["interpretation"],
        "",
        "## 差异个案",
        "",
    ]
    if not cases:
        lines.append("（无差异种子）")
    else:
        for c in cases:
            lines.append(f"### 种子 {c['seed']}")
            lines.append(
                f"- 选择：Native=`{c['native']}`，Open=`{c['open']}`，"
                f"Decision-Only=`{c['decision_only']}`"
            )
            lines.append(
                f"- 真值选中：N={c['native_truth']} / O={c['open_truth']} / "
                f"B={c['decision_truth']}"
            )
            lines.append(
                f"- RMSE：N={c['native_rmse']} / O={c['open_rmse']} / "
                f"B={c['decision_rmse']}"
            )
            lines.append(
                f"- 全池赢家 excluded={c['open_winner_excluded']}，"
                f"pruned={c['open_winner_pruned']}"
            )
            lines.append(f"- 角色：{c['role']}")
            lines.append("")
    lines.append("## 逐种子一行表")
    lines.append("")
    lines.append(
        "| seed | Native | Open | Decision | N✓ | O✓ | B✓ | "
        "Open=Dec | winner_excl |"
    )
    lines.append("|---:|---|---|---|---|---|---|---|---|")
    for r in rows:
        lines.append(
            f"| {r['seed']} | {r['native_incumbent']} | {r['open_incumbent']} | "
            f"{r['decision_only_incumbent']} | {int(r['native_truth'])} | "
            f"{int(r['open_truth'])} | {int(r['decision_truth'])} | "
            f"{int(r['open_vs_decision_same'])} | "
            f"{int(r['open_winner_excluded_by_evidence'])} |"
        )
    lines.append("")
    return "\n".join(lines)


def build_lock(rows: list[dict], agg: dict[str, Any]) -> dict[str, Any]:
    """Frozen contract for winners / RMSE / aggregate (do not edit lightly)."""
    per_seed = []
    for r in rows:
        per_seed.append(
            {
                "seed": r["seed"],
                "native_incumbent": r["native_incumbent"],
                "open_incumbent": r["open_incumbent"],
                "decision_only_incumbent": r["decision_only_incumbent"],
                "native_truth": r["native_truth"],
                "open_truth": r["open_truth"],
                "decision_truth": r["decision_truth"],
                "native_rmse": r["native_rmse"],
                "open_rmse": r["open_rmse"],
                "decision_rmse": r["decision_rmse"],
                "open_winner_excluded_by_evidence": r[
                    "open_winner_excluded_by_evidence"
                ],
                "open_winner_pruned_by_history": r["open_winner_pruned_by_history"],
                "theta_reused_from_native": r["theta_reused_from_native"],
                "w_all_reused_from_native": r["w_all_reused_from_native"],
                "open_incumbent_theta": r["open_incumbent_theta"],
                "w_all": r["w_all"],
            }
        )
    return {
        "lock_version": LOCK_VERSION,
        "source_stage2": "evidence_gated_eligibility/outputs/stage2_formal",
        "n": len(rows),
        "seeds": list(FORMAL_SEEDS),
        "rmse_atol": RMSE_ATOL,
        "aggregate": {
            "native_truth_selected_k": agg["native"]["truth_selected_k"],
            "open_truth_selected_k": agg["open_eligibility"]["truth_selected_k"],
            "decision_truth_selected_k": agg["decision_only"]["truth_selected_k"],
            "native_rmse_mean": agg["native"]["rmse_finite_mean"],
            "open_rmse_mean": agg["open_eligibility"]["rmse_finite_mean"],
            "decision_rmse_mean": agg["decision_only"]["rmse_finite_mean"],
            "open_ne_native": agg["selection_diff"]["open_ne_native"],
            "open_ne_decision": agg["selection_diff"]["open_ne_decision"],
            "decision_ne_native": agg["selection_diff"]["decision_ne_native"],
            "open_winner_evidence_excluded_k": agg["open_winner_evidence_excluded_k"],
            "open_winner_history_pruned_k": agg["open_winner_history_pruned_k"],
        },
        "per_seed": per_seed,
    }


def assert_against_lock(rows: list[dict], agg: dict[str, Any], lock: dict[str, Any]) -> None:
    """Raise AssertionError if recomputation drifts from the frozen lock."""
    assert lock["lock_version"] == LOCK_VERSION
    assert lock["n"] == 40
    assert list(lock["seeds"]) == list(FORMAL_SEEDS)
    assert len(rows) == 40

    exp_agg = lock["aggregate"]
    assert agg["native"]["truth_selected_k"] == exp_agg["native_truth_selected_k"]
    assert agg["open_eligibility"]["truth_selected_k"] == exp_agg["open_truth_selected_k"]
    assert agg["decision_only"]["truth_selected_k"] == exp_agg["decision_truth_selected_k"]
    assert agg["selection_diff"]["open_ne_native"] == exp_agg["open_ne_native"]
    assert agg["selection_diff"]["open_ne_decision"] == exp_agg["open_ne_decision"]
    assert agg["selection_diff"]["decision_ne_native"] == exp_agg["decision_ne_native"]
    assert (
        agg["open_winner_evidence_excluded_k"]
        == exp_agg["open_winner_evidence_excluded_k"]
    )
    assert (
        agg["open_winner_history_pruned_k"] == exp_agg["open_winner_history_pruned_k"]
    )

    atol = float(lock.get("rmse_atol", RMSE_ATOL))
    for key_lock, key_agg in (
        ("native_rmse_mean", "native"),
        ("open_rmse_mean", "open_eligibility"),
        ("decision_rmse_mean", "decision_only"),
    ):
        got = float(agg[key_agg]["rmse_finite_mean"])
        exp = float(exp_agg[key_lock])
        if abs(got - exp) > atol:
            raise AssertionError(f"{key_lock} drifted: got={got} exp={exp}")

    by_seed = {int(r["seed"]): r for r in rows}
    for exp in lock["per_seed"]:
        seed = int(exp["seed"])
        r = by_seed[seed]
        for key in (
            "native_incumbent",
            "open_incumbent",
            "decision_only_incumbent",
            "native_truth",
            "open_truth",
            "decision_truth",
            "open_winner_excluded_by_evidence",
            "open_winner_pruned_by_history",
        ):
            if r[key] != exp[key]:
                raise AssertionError(f"seed {seed} {key}: got={r[key]!r} exp={exp[key]!r}")
        if not r["theta_reused_from_native"] or not r["w_all_reused_from_native"]:
            raise AssertionError(f"seed {seed}: Native param/w_all reuse broken")
        if r["open_incumbent_theta"] != exp["open_incumbent_theta"]:
            raise AssertionError(f"seed {seed}: open_incumbent_theta drifted")
        for arm_key in ("native_rmse", "open_rmse", "decision_rmse"):
            got = float(r[arm_key])
            exp_v = float(exp[arm_key])
            if abs(got - exp_v) > atol:
                raise AssertionError(
                    f"seed {seed} {arm_key} drifted: got={got} exp={exp_v}"
                )
        for h in FAMILY_ORDER:
            if abs(float(r["w_all"][h]) - float(exp["w_all"][h])) > atol:
                raise AssertionError(f"seed {seed} w_all[{h}] drifted")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    FROZEN_DIR.mkdir(parents=True, exist_ok=True)
    rows = [analyze_seed(s) for s in FORMAL_SEEDS]
    agg = aggregate(rows)
    cases = case_notes(rows)

    if not all(r["theta_reused_from_native"] and r["w_all_reused_from_native"] for r in rows):
        bad = [
            r["seed"]
            for r in rows
            if not (r["theta_reused_from_native"] and r["w_all_reused_from_native"])
        ]
        raise AssertionError(f"parameter reuse failed for seeds {bad}")

    # Compact CSV for paper / audit
    csv_rows = []
    for r in rows:
        csv_rows.append(
            {
                "seed": r["seed"],
                "native_incumbent": r["native_incumbent"],
                "open_incumbent": r["open_incumbent"],
                "decision_only_incumbent": r["decision_only_incumbent"],
                "native_truth": r["native_truth"],
                "open_truth": r["open_truth"],
                "decision_truth": r["decision_truth"],
                "native_rmse": r["native_rmse"],
                "open_rmse": r["open_rmse"],
                "decision_rmse": r["decision_rmse"],
                "open_vs_native_same": r["open_vs_native_same"],
                "open_vs_decision_same": r["open_vs_decision_same"],
                "decision_vs_native_same": r["decision_vs_native_same"],
                "open_winner_excluded_by_evidence": r[
                    "open_winner_excluded_by_evidence"
                ],
                "open_winner_pruned_by_history": r["open_winner_pruned_by_history"],
                "theta_reused_from_native": r["theta_reused_from_native"],
                "w_all_reused_from_native": r["w_all_reused_from_native"],
                **{f"w_all_{h}": r["w_all"][h] for h in FAMILY_ORDER},
                **{f"alive_{h}": r["alive"][h] for h in FAMILY_ORDER},
                **{f"excluded_{h}": r["excluded"][h] for h in FAMILY_ORDER},
            }
        )
    write_csv(OUT / "per_seed_open_eligibility.csv", csv_rows)
    write_csv(OUT / "case_diffs.csv", cases if cases else [])

    payload = {
        "kind": "open_eligibility_posthoc",
        "source": str(DATA.relative_to(ROOT.parent)),
        "n": len(rows),
        "seeds": list(FORMAL_SEEDS),
        "aggregate": agg,
        "cases": cases,
        "per_seed": csv_rows,
    }
    (OUT / "open_eligibility_report.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (OUT / "open_eligibility_report.md").write_text(
        render_md(agg, cases, rows), encoding="utf-8"
    )

    lock = build_lock(rows, agg)
    if LOCK_PATH.exists():
        existing = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
        assert_against_lock(rows, agg, existing)
        lock_text = LOCK_PATH.read_text(encoding="utf-8")
    else:
        lock_text = json.dumps(lock, indent=2, ensure_ascii=False) + "\n"
        LOCK_PATH.write_text(lock_text, encoding="utf-8")
    # Audit copy under outputs (canonical lock lives in frozen/)
    (OUT / "open_eligibility_lock_v1.json").write_text(lock_text, encoding="utf-8")

    print(json.dumps(agg, indent=2, ensure_ascii=False))
    print(f"Wrote {OUT}")
    print(f"Lock {LOCK_PATH}")


if __name__ == "__main__":
    main()
