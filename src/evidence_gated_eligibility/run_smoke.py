#!/usr/bin/env python3
"""Stage-1 smoke: seeds 1001–1003 only. No formal 201–240. No paper edits."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from evidence_gated_eligibility.config import (  # noqa: E402
    ARM_DECISION_ONLY,
    ARM_FULL_GATE,
    ARM_NATIVE,
    EGE_VERSION,
    EXPECTED_N_MEASURED,
    FORMAL_SEEDS,
    SMOKE_SEEDS,
)
from evidence_gated_eligibility.eval_grid import (  # noqa: E402
    assert_eval_disjoint_from_measurable,
    eval_meta,
)
from evidence_gated_eligibility.loop_ege import (  # noqa: E402
    compare_native_to_formal_run_seed,
    run_paired_seed,
)

OUT = ROOT / "evidence_gated_eligibility" / "outputs" / "stage1"


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    assert set(SMOKE_SEEDS).isdisjoint(set(FORMAL_SEEDS)), "smoke must not use formal queue"
    assert_eval_disjoint_from_measurable()

    # Native reproduction on classic seeds
    repro = []
    for s in (1, 3, 20):
        print(f"[stage1] native repro seed={s}", flush=True)
        repro.append(compare_native_to_formal_run_seed(s))
    repro_ok = all(r["match"] for r in repro)
    (OUT / "native_reproduction.json").write_text(
        json.dumps({"ok": repro_ok, "per_seed": repro}, indent=2), encoding="utf-8"
    )
    (OUT / "native_reproduction.md").write_text(
        "# Native 复现报告\n\n"
        + f"**ok={repro_ok}**\n\n"
        + "\n".join(
            f"- seed {r['seed']}: match={r['match']} "
            f"(sites={r['sites_match']}, elim={r['t_elim_match']}, excl={r['t_excl_match']})"
            for r in repro
        )
        + "\n",
        encoding="utf-8",
    )

    grid_check = {
        "ok": True,
        "eval": eval_meta(),
        "disjoint_from_measurable": True,
        "note": "EVAL midpoints never queried via World.y / allocate idx",
    }
    (OUT / "eval_grid_check.json").write_text(
        json.dumps(grid_check, indent=2), encoding="utf-8"
    )

    smoke_rows = []
    t0 = time.perf_counter()
    for seed in SMOKE_SEEDS:
        print(f"[stage1] smoke seed={seed}", flush=True)
        rec = run_paired_seed(seed)
        path = OUT / f"smoke_seed_{seed}.json"
        path.write_text(json.dumps(rec, indent=2, default=str), encoding="utf-8")
        smoke_rows.append(
            {
                "seed": seed,
                "budget": rec["budget"],
                "scores": rec["scores"],
                "incumbents": {
                    ARM_NATIVE: rec["arms"][ARM_NATIVE]["final"]["incumbent"],
                    ARM_DECISION_ONLY: rec["arms"][ARM_DECISION_ONLY]["final"]["incumbent"],
                    ARM_FULL_GATE: rec["arms"][ARM_FULL_GATE]["final"]["incumbent"],
                },
                "c_abort": rec["arms"][ARM_FULL_GATE]["final"].get("abort_status"),
                "wall_s": rec["wall_s"],
            }
        )

    # integrity flags (not scientific tuning)
    integrity = {
        "repro_ok": repro_ok,
        "eval_grid_ok": True,
        "all_native_budget_ok": all(r["budget"]["native_budget_ok"] for r in smoke_rows),
        "all_b_sites_eq_a": all(r["budget"]["b_sites_identical_to_a"] for r in smoke_rows),
        "all_c_budget_or_abort": all(r["budget"]["c_budget_ok_or_aborted"] for r in smoke_rows),
        "smoke_seeds": list(SMOKE_SEEDS),
        "formal_queue_untouched": list(FORMAL_SEEDS[:3]) + ["...", FORMAL_SEEDS[-1]],
        "n_smoke": len(smoke_rows),
        "wall_s_total": time.perf_counter() - t0,
    }
    integrity["pass"] = all(
        [
            integrity["repro_ok"],
            integrity["eval_grid_ok"],
            integrity["all_native_budget_ok"],
            integrity["all_b_sites_eq_a"],
            integrity["all_c_budget_or_abort"],
        ]
    )

    (OUT / "smoke_summary.json").write_text(
        json.dumps({"integrity": integrity, "rows": smoke_rows}, indent=2, default=str),
        encoding="utf-8",
    )

    # human reports
    lines = [
        "# Stage 1 Smoke 报告",
        "",
        f"版本：`{EGE_VERSION}`",
        f"Smoke seeds：{list(SMOKE_SEEDS)}（正式 201–240 **未**运行）",
        "",
        f"- Native 复现 (1,3,20)：{'PASS' if repro_ok else 'FAIL'}",
        f"- 独立网格：PASS",
        f"- Native 预算={EXPECTED_N_MEASURED}：{'PASS' if integrity['all_native_budget_ok'] else 'FAIL'}",
        f"- B 轨迹≡A：{'PASS' if integrity['all_b_sites_eq_a'] else 'FAIL'}",
        f"- C 预算或合法中止：{'PASS' if integrity['all_c_budget_or_abort'] else 'FAIL'}",
        "",
        "## 逐 seed（描述性，不调参）",
        "",
    ]
    for r in smoke_rows:
        lines.append(f"### seed {r['seed']}")
        lines.append(f"- incumbents: {r['incumbents']}")
        lines.append(f"- C abort: {r['c_abort']}")
        for arm, sc in r["scores"].items():
            lines.append(
                f"- {arm}: status={sc['primary_status']} "
                f"rmse={sc['rmse_eval_noiseless']} "
                f"truth_sel={sc['truth_selected']} "
                f"truth_excl={sc['truth_excluded_operational']} "
                f"n={sc['n_measured']}"
            )
        lines.append("")
    (OUT / "smoke_report.md").write_text("\n".join(lines), encoding="utf-8")

    print(f"[stage1] smoke integrity.pass={integrity['pass']} -> {OUT}", flush=True)
    return 0 if integrity["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
