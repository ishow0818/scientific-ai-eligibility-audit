#!/usr/bin/env python3
"""Stage 2 formal: seeds 201–240. No threshold tuning. No paper edits."""
from __future__ import annotations

import csv
import json
import platform
import statistics
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import scipy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from evidence_gated_eligibility.config import (  # noqa: E402
    ARM_DECISION_ONLY,
    ARM_FULL_GATE,
    ARM_NATIVE,
    EGE_VERSION,
    FORMAL_SEEDS,
)
from evidence_gated_eligibility.eval_grid import (  # noqa: E402
    assert_eval_disjoint_from_measurable,
    eval_meta,
)
from evidence_gated_eligibility.loop_ege import run_paired_seed  # noqa: E402

OUT = ROOT / "evidence_gated_eligibility" / "outputs" / "stage2_formal"
ARMS = (ARM_NATIVE, ARM_DECISION_ONLY, ARM_FULL_GATE)


def wilson(k: int, n: int, z: float = 1.96) -> list[float]:
    if n <= 0:
        return [0.0, 0.0, 0.0]
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * (p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5 / den
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


def median(xs: list[float]) -> float | None:
    return float(statistics.median(xs)) if xs else None


def mean(xs: list[float]) -> float | None:
    return float(statistics.mean(xs)) if xs else None


def summarize(seed_rows: list[dict]) -> dict[str, Any]:
    n = len(seed_rows)
    out: dict[str, Any] = {"n_seeds": n, "arms": {}}
    for arm in ARMS:
        fail_k = sum(1 for r in seed_rows if r[f"{arm}_is_failure"])
        truth_sel = sum(1 for r in seed_rows if r[f"{arm}_truth_selected"])
        truth_excl = sum(1 for r in seed_rows if r[f"{arm}_truth_excluded_operational"])
        truth_lost = sum(1 for r in seed_rows if r[f"{arm}_truth_eligibility_lost"])
        rmse_ok = [
            float(r[f"{arm}_rmse"])
            for r in seed_rows
            if r[f"{arm}_rmse"] != "" and r[f"{arm}_rmse"] is not None
        ]
        rmse_pen = [float(r[f"{arm}_rmse_penalty"]) for r in seed_rows]
        fail_types: dict[str, int] = {}
        for r in seed_rows:
            ft = r.get(f"{arm}_failure_type") or ""
            if ft:
                fail_types[ft] = fail_types.get(ft, 0) + 1
        out["arms"][arm] = {
            "failure_k": fail_k,
            "failure_rate_wilson95": wilson(fail_k, n),
            "truth_selected_k": truth_sel,
            "truth_selected_rate_wilson95": wilson(truth_sel, n),
            "truth_excluded_operational_k": truth_excl,
            "truth_eligibility_lost_k": truth_lost,
            "truth_eligibility_lost_rate_wilson95": wilson(truth_lost, n),
            "rmse_finite_n": len(rmse_ok),
            "rmse_finite_median": median(rmse_ok),
            "rmse_finite_mean": mean(rmse_ok),
            "rmse_penalty_median": median(rmse_pen),
            "rmse_penalty_mean": mean(rmse_pen),
            "failure_type_counts": fail_types,
            "n_false_eligible_mean": mean(
                [float(r[f"{arm}_n_false_eligible"]) for r in seed_rows]
            ),
        }

    # paired deltas (penalty RMSE so failures included)
    for a, b, tag in (
        (ARM_NATIVE, ARM_DECISION_ONLY, "A_minus_B"),
        (ARM_NATIVE, ARM_FULL_GATE, "A_minus_C"),
        (ARM_DECISION_ONLY, ARM_FULL_GATE, "B_minus_C"),
    ):
        deltas = [
            float(r[f"{a}_rmse_penalty"]) - float(r[f"{b}_rmse_penalty"])
            for r in seed_rows
        ]
        signs = Counter_signs(deltas)
        out[tag] = {
            "delta_rmse_penalty_median": median(deltas),
            "delta_rmse_penalty_mean": mean(deltas),
            "n_positive": signs["pos"],
            "n_negative": signs["neg"],
            "n_zero": signs["zero"],
        }

    # truth selection discordances
    out["truth_selection_pairs"] = {
        "A_yes_B_no": sum(
            1
            for r in seed_rows
            if r[f"{ARM_NATIVE}_truth_selected"]
            and not r[f"{ARM_DECISION_ONLY}_truth_selected"]
        ),
        "A_no_B_yes": sum(
            1
            for r in seed_rows
            if (not r[f"{ARM_NATIVE}_truth_selected"])
            and r[f"{ARM_DECISION_ONLY}_truth_selected"]
        ),
        "A_yes_C_no": sum(
            1
            for r in seed_rows
            if r[f"{ARM_NATIVE}_truth_selected"]
            and not r[f"{ARM_FULL_GATE}_truth_selected"]
        ),
        "A_no_C_yes": sum(
            1
            for r in seed_rows
            if (not r[f"{ARM_NATIVE}_truth_selected"])
            and r[f"{ARM_FULL_GATE}_truth_selected"]
        ),
    }
    return out


def Counter_signs(deltas: list[float]) -> dict[str, int]:
    pos = sum(1 for d in deltas if d > 0)
    neg = sum(1 for d in deltas if d < 0)
    zero = sum(1 for d in deltas if d == 0)
    return {"pos": pos, "neg": neg, "zero": zero}


def write_report(agg: dict, env: dict, path: Path) -> None:
    lines = [
        "# Evidence-Gated Eligibility — Stage 2 正式报告",
        "",
        f"版本：`{EGE_VERSION}`  |  seeds **201–240** (n={agg['n_seeds']})",
        "χ²：`OPERATIONAL_ONLY`  |  未改阈值 / 未改 `pilot_fi_anchor` / 未改论文",
        "",
        "## 运行环境（结果绑定）",
        "",
        f"- platform: `{env['platform']}`",
        f"- Python: `{env['python'].splitlines()[0]}`",
        f"- NumPy: `{env['numpy']}`  |  SciPy: `{env['scipy']}`",
        f"- executable: `{env['executable']}`",
        "",
        "> Stage1 已记录跨 OS 数值敏感性；本正式结果仅对该环境有效。",
        "",
        "## Primary：独立网格无噪声 RMSE",
        "",
    ]
    for arm in ARMS:
        a = agg["arms"][arm]
        lines += [
            f"### {arm}",
            f"- 失败 k={a['failure_k']}/40；率 Wilson95={a['failure_rate_wilson95']}",
            f"- 失败类型：{a['failure_type_counts']}",
            f"- 有限 RMSE：n={a['rmse_finite_n']}；"
            f"median={a['rmse_finite_median']}；mean={a['rmse_finite_mean']}",
            f"- 惩罚 RMSE（失败→RMSE_FAIL）："
            f"median={a['rmse_penalty_median']}；mean={a['rmse_penalty_mean']}",
            f"- 终局错误模型资格数均值：{a['n_false_eligible_mean']}",
            "",
        ]
    lines += [
        "## 配对 ΔRMSE（惩罚尺度；正值=前者更差）",
        "",
        f"- A−B：{agg['A_minus_B']}",
        f"- A−C：{agg['A_minus_C']}",
        f"- B−C：{agg['B_minus_C']}",
        "",
        "## Secondary",
        "",
    ]
    for arm in ARMS:
        a = agg["arms"][arm]
        lines.append(
            f"- {arm}: truth_selected={a['truth_selected_k']}/40 "
            f"{a['truth_selected_rate_wilson95']}；"
            f"truth_excl_op={a['truth_excluded_operational_k']}；"
            f"truth_elig_lost={a['truth_eligibility_lost_k']} "
            f"{a['truth_eligibility_lost_rate_wilson95']}"
        )
    lines += [
        "",
        f"真模型选择配对差：{agg['truth_selection_pairs']}",
        "",
        "## 机制解读边界",
        "",
        "- Primary 看发现质量（RMSE），不把「保留更多候选」当成功。",
        "- B=离线终局资格；C=闭环资格；差异含数据轨迹效应。",
        "- 真模型操作性排除计失败（非 oracle）。",
        "",
        "**未修改论文。**",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    assert list(FORMAL_SEEDS) == list(range(201, 241))
    assert_eval_disjoint_from_measurable()

    env = {
        "platform": platform.platform(),
        "python": sys.version,
        "numpy": np.__version__,
        "scipy": scipy.__version__,
        "executable": sys.executable,
    }
    (OUT / "environment.json").write_text(json.dumps(env, indent=2), encoding="utf-8")
    (OUT / "eval_grid_check.json").write_text(
        json.dumps({"ok": True, "eval": eval_meta()}, indent=2), encoding="utf-8"
    )

    seed_rows: list[dict] = []
    t0 = time.perf_counter()
    for i, seed in enumerate(FORMAL_SEEDS, 1):
        print(f"[formal] ({i}/40) seed={seed}", flush=True)
        rec = run_paired_seed(seed)
        (OUT / f"seed_{seed}.json").write_text(
            json.dumps(rec, indent=2, default=str), encoding="utf-8"
        )
        row: dict[str, Any] = {"seed": seed, "wall_s": rec["wall_s"]}
        for arm in ARMS:
            sc = rec["scores"][arm]
            # ensure failure fields present
            assert "truth_eligibility_lost" in sc and "failure_type" in sc and "is_failure" in sc
            row[f"{arm}_incumbent"] = rec["arms"][arm]["final"].get("incumbent")
            row[f"{arm}_primary_status"] = sc["primary_status"]
            row[f"{arm}_failure_type"] = sc["failure_type"] or ""
            row[f"{arm}_is_failure"] = sc["is_failure"]
            row[f"{arm}_rmse"] = (
                sc["rmse_eval_noiseless"]
                if sc["rmse_eval_noiseless"] is not None
                else ""
            )
            row[f"{arm}_rmse_penalty"] = sc["rmse_with_fail_penalty"]
            row[f"{arm}_truth_selected"] = sc["truth_selected"]
            row[f"{arm}_truth_excluded_operational"] = sc[
                "truth_excluded_operational"
            ]
            row[f"{arm}_truth_eligibility_lost"] = sc["truth_eligibility_lost"]
            row[f"{arm}_n_false_eligible"] = sc["n_false_eligible"]
            row[f"{arm}_n_measured"] = sc["n_measured"]
        seed_rows.append(row)

    write_csv(OUT / "formal_seed_summary.csv", seed_rows)
    agg = summarize(seed_rows)
    agg["wall_s_total"] = time.perf_counter() - t0
    agg["version"] = EGE_VERSION
    agg["seeds"] = list(FORMAL_SEEDS)
    agg["chi2_status"] = "OPERATIONAL_ONLY"
    agg["environment"] = env
    (OUT / "formal_aggregate.json").write_text(
        json.dumps(agg, indent=2, default=str), encoding="utf-8"
    )
    write_report(agg, env, OUT / "formal_report.md")

    # descriptive verdict (not paper claim)
    a = agg["arms"][ARM_NATIVE]
    b = agg["arms"][ARM_DECISION_ONLY]
    c = agg["arms"][ARM_FULL_GATE]
    verdict = {
        "stage": 2,
        "verdict": "FORMAL_COMPLETE",
        "n_seeds": 40,
        "seeds": "201-240",
        "environment_bound": True,
        "primary_penalty_rmse_median": {
            ARM_NATIVE: a["rmse_penalty_median"],
            ARM_DECISION_ONLY: b["rmse_penalty_median"],
            ARM_FULL_GATE: c["rmse_penalty_median"],
        },
        "paired_delta_penalty_median": {
            "A_minus_B": agg["A_minus_B"]["delta_rmse_penalty_median"],
            "A_minus_C": agg["A_minus_C"]["delta_rmse_penalty_median"],
            "B_minus_C": agg["B_minus_C"]["delta_rmse_penalty_median"],
        },
        "truth_selected_k": {
            ARM_NATIVE: a["truth_selected_k"],
            ARM_DECISION_ONLY: b["truth_selected_k"],
            ARM_FULL_GATE: c["truth_selected_k"],
        },
        "failure_k": {
            ARM_NATIVE: a["failure_k"],
            ARM_DECISION_ONLY: b["failure_k"],
            ARM_FULL_GATE: c["failure_k"],
        },
        "paper_modified": False,
        "pilot_fi_anchor_modified": False,
        "thresholds_tuned": False,
        "note": (
            "Descriptive formal panel under pinned Windows env; "
            "χ² OPERATIONAL_ONLY; do not claim cross-OS invariance."
        ),
    }
    (OUT / "verdict.json").write_text(json.dumps(verdict, indent=2), encoding="utf-8")
    print(f"[formal] done -> {OUT}", flush=True)
    print(json.dumps(verdict, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
