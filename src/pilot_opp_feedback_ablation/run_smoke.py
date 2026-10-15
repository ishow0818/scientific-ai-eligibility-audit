#!/usr/bin/env python3
"""Minimal 2-seed Opportunity-Feedback Ablation smoke (v0.2 CRN RNG; no confirmatory claim)."""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pilot_fi_anchor.config import FALSE_FAMILIES, R, TRUTH_FAMILY  # noqa: E402
from pilot_opp_feedback_ablation.config import (  # noqa: E402
    ABLATION_VERSION,
    ARM_NATIVE,
    ARM_NO_OPP,
    RESULTS_DIR,
    RESULTS_DIR_V1,
    SMOKE_SEEDS,
)
from pilot_opp_feedback_ablation.loop_ablation import (  # noqa: E402
    compare_native_to_formal,
    fi_events,
    run_paired_seed,
)

OUT = ROOT / RESULTS_DIR
FORMAL_DIR = ROOT / "outputs" / "pilot_fi_anchor"
V1_DIR = ROOT / RESULTS_DIR_V1


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


def sites_rows(seed: int, rec: dict) -> list[dict]:
    rows = []
    for tag in (ARM_NATIVE, ARM_NO_OPP):
        for s in rec["arms"][tag]["sites"]:
            rows.append(
                {
                    "seed": seed,
                    "arm": tag,
                    "t": s["t"],
                    "idx": s["idx"],
                    "x": s["x"],
                    "y": s["y"],
                    "credit": s["credit"],
                }
            )
    return rows


def weight_rows(seed: int, rec: dict) -> list[dict]:
    rows = []
    for tag in (ARM_NATIVE, ARM_NO_OPP):
        for row in rec["arms"][tag]["rounds"]:
            for h in (TRUTH_FAMILY,) + FALSE_FAMILIES:
                st = row[h]
                rows.append(
                    {
                        "seed": seed,
                        "arm": tag,
                        "t": row["t"],
                        "family": h,
                        "w_all": st["w_all"],
                        "w_surv": st["w_surv"],
                        "alive": st["alive"],
                        "violated": st["violated"],
                        "excluded": st["excluded"],
                        "t_elim": st["t_elim"],
                        "t_excl": st["t_excl"],
                        "S": st["S"],
                    }
                )
    return rows


def event_rows(seed: int, rec: dict) -> list[dict]:
    rows = []
    for tag in (ARM_NATIVE, ARM_NO_OPP):
        for e in fi_events(rec["arms"][tag]):
            rows.append({"seed": seed, "arm": tag, **e})
    return rows


def paired_summary(seed: int, rec: dict) -> dict[str, Any]:
    out: dict[str, Any] = {"seed": seed}
    for tag in (ARM_NATIVE, ARM_NO_OPP):
        final = rec["arms"][tag]["final"]
        ev = fi_events(rec["arms"][tag])
        false_fi = [e for e in ev if (not e["is_truth"]) and e["fi"]]
        truth_fi = [e for e in ev if e["is_truth"] and e["fi"]]
        out[f"{tag}_incumbent"] = final["incumbent"]
        out[f"{tag}_n_false_fi"] = len(false_fi)
        out[f"{tag}_truth_fi"] = bool(truth_fi)
        out[f"{tag}_t_elim_hump"] = final["t_elim"].get(TRUTH_FAMILY)
        out[f"{tag}_alive_hump"] = final["alive"].get(TRUTH_FAMILY)
    n_idx = [s["idx"] for s in rec["arms"][ARM_NATIVE]["sites"]]
    u_idx = [s["idx"] for s in rec["arms"][ARM_NO_OPP]["sites"]]
    first_diff = next((i for i, (a, b) in enumerate(zip(n_idx, u_idx)) if a != b), None)
    out["first_site_index_diff_position"] = first_diff
    out["n_sites_equal"] = n_idx == u_idx
    return out


def check_disk_native(seed: int, rec: dict) -> dict[str, Any]:
    path = FORMAL_DIR / f"seed_{seed:02d}.json"
    if not path.is_file():
        return {"seed": seed, "disk_present": False, "match": None, "reason": "no_disk_log"}
    disk = json.loads(path.read_text(encoding="utf-8"))
    a_sites = [(s["t"], s["idx"], s["credit"]) for s in rec["arms"][ARM_NATIVE]["sites"]]
    d_sites = [(s["t"], s["idx"], s.get("credit")) for s in disk["arms"]["native"]["sites"]]
    elim_ok = (
        rec["arms"][ARM_NATIVE]["final"]["t_elim"] == disk["arms"]["native"]["final"]["t_elim"]
    )
    sites_ok = a_sites == d_sites
    reason = None
    if not sites_ok or not elim_ok:
        # Formal pilot used do_perturb=True; document whether that matters
        reason = (
            "Mismatch vs on-disk formal Native. Formal pilot logs were produced with "
            "perturbation branches enabled; if main-arm sites still differ, investigate "
            "version/config drift. Live compare_native_to_formal(do_perturb=False) is authoritative."
        )
    return {
        "seed": seed,
        "disk_present": True,
        "sites_match": sites_ok,
        "t_elim_match": elim_ok,
        "match": sites_ok and elim_ok,
        "reason": reason,
    }


def write_report(
    summaries: list[dict],
    repro: list[dict],
    disk_checks: list[dict],
    tests_ok: bool,
    isolation_ok: bool,
    path: Path,
) -> str:
    repro_ok = all(r.get("reproduces_formal_native") for r in repro)
    disk_ok = all(d.get("match") in (True, None) for d in disk_checks)
    # PASS requires tests + isolation + live formal reproduction
    if not tests_ok:
        verdict = "FIX"
    elif not isolation_ok:
        verdict = "NOT_ISOLATABLE"
    elif not repro_ok:
        verdict = "FIX"
    else:
        verdict = "PASS"

    lines = [
        "# Opportunity-Feedback Ablation — Smoke 报告（v0.2 CRN RNG）",
        "",
        f"**裁决：`{verdict}`**",
        "",
        f"版本：`{ABLATION_VERSION}`",
        f"输出：`{RESULTS_DIR}`（保留旧版 `{RESULTS_DIR_V1}`，不覆盖）",
        f"旧版仍在：{V1_DIR.is_dir()}",
        "",
        "## RNG 修复（相对 v0.1）",
        "",
        "| 项 | v0.1（错误配对） | v0.2（本版） |",
        "|---|---|---|",
        "| Allocation SeedSequence | Native code=0；No-Opp code=2 | **两臂均用 Native code=0** |",
        "| Generator | 不同熵 | **相同熵、各自独立实例（CRN）** |",
        "| proposer 权重 | Native=`w_all`；No-Opp=均匀 | **不变** |",
        "| 拟合/剪枝/χ²/预算 | 不变 | **不变** |",
        "| `pilot_fi_anchor` | 未改 | **未改** |",
        "",
        "## 隔离与复现",
        "",
        f"- 隔离测试：{'PASS' if tests_ok else 'FAIL'}",
        f"- 隔离状态：{'ISOLATABLE' if isolation_ok else 'NOT_ISOLATABLE'}",
        f"- 相对 `run_seed(..., do_perturb=False)` 的 Native 复现：{'PASS' if repro_ok else 'FAIL'}",
        "",
    ]
    for r in repro:
        lines.append(
            f"  - seed {r['seed']} rounds={r['rounds']}: "
            f"sites_match={r['sites_match']} t_elim_match={r['t_elim_match']}"
        )
    lines += ["", "### 相对正式磁盘日志（完整 R，可能含扰动分支）", ""]
    for d in disk_checks:
        lines.append(
            f"- seed {d['seed']}: disk_present={d['disk_present']} match={d.get('match')} "
            f"{d.get('reason') or ''}"
        )
    if not disk_ok:
        lines.append(
            "- 说明：磁盘不匹配时以 live `do_perturb=False` 复现为准；"
            "不据此改机制。"
        )

    lines += [
        "",
        "## Smoke 配对摘要（机制完整性，非科学确认）",
        "",
        f"seeds={list(SMOKE_SEEDS)}；rounds={R}",
        "",
        "| seed | Native FI假 | NoOpp FI假 | Native truth FI | NoOpp truth FI | Native 首位 | NoOpp 首位 | 选点分叉 |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for s in summaries:
        lines.append(
            f"| {s['seed']} | {s[f'{ARM_NATIVE}_n_false_fi']} | {s[f'{ARM_NO_OPP}_n_false_fi']} | "
            f"{s[f'{ARM_NATIVE}_truth_fi']} | {s[f'{ARM_NO_OPP}_truth_fi']} | "
            f"{s[f'{ARM_NATIVE}_incumbent']} | {s[f'{ARM_NO_OPP}_incumbent']} | "
            f"{not s['n_sites_equal']} |"
        )
    lines += [
        "",
        "## 建议",
        "",
        "- 仅当本报告裁决为 `PASS` 时，才建议进入正式 20-seed；**本脚本不自动开跑**。",
        "- Smoke 不得用于确认科学效应，也未据此调参。",
        "",
        "## 产物",
        "",
        "- `seed_XX_paired.json`",
        "- `smoke_sites.csv` / `smoke_weights.csv` / `smoke_exit_events.csv`",
        "- `smoke_summary.csv` / `native_reproduction.json` / `smoke_report.md`",
        "",
        f"**最终裁决：`{verdict}`**",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return verdict


def main() -> int:
    marker = Path(__file__).resolve().parent / "_isolation_tests_ok"
    tests_ok = marker.is_file() and marker.read_text(encoding="utf-8").strip() == "PASS"
    if not tests_ok:
        print("[smoke] isolation tests not PASS — refusing to run smoke", flush=True)
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / "verdict.json").write_text(
            json.dumps({"verdict": "FIX", "reason": "isolation_tests_not_pass"}, indent=2),
            encoding="utf-8",
        )
        return 2

    OUT.mkdir(parents=True, exist_ok=True)
    all_sites: list[dict] = []
    all_weights: list[dict] = []
    all_events: list[dict] = []
    summaries: list[dict] = []
    disk_checks: list[dict] = []
    isolation_ok = True

    # Live reproduction vs formal runner (short + full horizon for disk compare)
    repro = [compare_native_to_formal(s, rounds=8) for s in SMOKE_SEEDS]
    print("[smoke] native reproduction vs run_seed(do_perturb=False):", repro, flush=True)

    for seed in SMOKE_SEEDS:
        print(f"[smoke] seed={seed} ...", flush=True)
        rec = run_paired_seed(seed, rounds=R)
        isolation_ok = isolation_ok and rec["isolation"]["status"] == "ISOLATABLE"
        (OUT / f"seed_{seed:02d}_paired.json").write_text(
            json.dumps(rec, indent=2, default=str), encoding="utf-8"
        )
        all_sites.extend(sites_rows(seed, rec))
        all_weights.extend(weight_rows(seed, rec))
        all_events.extend(event_rows(seed, rec))
        summaries.append(paired_summary(seed, rec))
        disk_checks.append(check_disk_native(seed, rec))
        print(
            f"[smoke] seed={seed} done; "
            f"false_fi N/U={summaries[-1][f'{ARM_NATIVE}_n_false_fi']}/"
            f"{summaries[-1][f'{ARM_NO_OPP}_n_false_fi']}; "
            f"disk_match={disk_checks[-1].get('match')}",
            flush=True,
        )

    write_csv(OUT / "smoke_sites.csv", all_sites)
    write_csv(OUT / "smoke_weights.csv", all_weights)
    write_csv(OUT / "smoke_exit_events.csv", all_events)
    write_csv(OUT / "smoke_summary.csv", summaries)
    (OUT / "native_reproduction.json").write_text(
        json.dumps({"live_vs_run_seed": repro, "vs_disk_log": disk_checks}, indent=2),
        encoding="utf-8",
    )
    verdict = write_report(
        summaries, repro, disk_checks, tests_ok, isolation_ok, OUT / "smoke_report.md"
    )
    (OUT / "verdict.json").write_text(
        json.dumps(
            {
                "verdict": verdict,
                "version": ABLATION_VERSION,
                "tests_ok": tests_ok,
                "isolation_ok": isolation_ok,
                "native_repro_ok": all(r["reproduces_formal_native"] for r in repro),
                "v1_preserved": V1_DIR.is_dir(),
                "smoke_seeds": list(SMOKE_SEEDS),
                "summaries": summaries,
                "reproduction": repro,
                "disk_checks": disk_checks,
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    audit_src = Path(__file__).resolve().parent / "SOURCE_AUDIT.md"
    if audit_src.is_file():
        (OUT / "SOURCE_AUDIT.md").write_text(
            audit_src.read_text(encoding="utf-8"), encoding="utf-8"
        )
    print(f"[smoke] verdict={verdict} -> {OUT}", flush=True)
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
