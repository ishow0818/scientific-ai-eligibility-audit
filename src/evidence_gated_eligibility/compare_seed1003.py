#!/usr/bin/env python3
"""Same-environment re-run of smoke seed 1003 vs archived JSON (do not overwrite archive)."""
from __future__ import annotations

import json
import platform
import sys
from pathlib import Path

import numpy as np
import scipy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from evidence_gated_eligibility.config import (  # noqa: E402
    ARM_DECISION_ONLY,
    ARM_FULL_GATE,
    ARM_NATIVE,
    FAMILY_ORDER,
)
from evidence_gated_eligibility.loop_ege import run_paired_seed  # noqa: E402

ARCHIVE = (
    ROOT
    / "evidence_gated_eligibility"
    / "outputs"
    / "stage1"
    / "smoke_seed_1003.json"
)
OUT = ROOT / "evidence_gated_eligibility" / "outputs" / "stage1_fix"


def round_fingerprint(row: dict, arm: str) -> dict:
    fp = {"t": row["t"], "n_arm": row["n_arm"], "incumbent": row.get("incumbent")}
    for h in FAMILY_ORDER:
        d = row[h]
        fp[h] = {
            "w_all": d["w_all"],
            "w_surv": d.get("w_surv"),
            "alive": d.get("alive"),
            "excluded": d["excluded"],
            "violated": d["violated"],
            "stream_n": d["stream_n"],
        }
        if "shadow_alive" in d:
            fp[h]["shadow_alive"] = d["shadow_alive"]
    return fp


def sites_fp(sites: list[dict]) -> list[tuple]:
    return [(int(s["t"]), int(s["idx"]), float(s["y"])) for s in sites]


def first_diff(a_rounds, b_rounds, a_sites, b_sites) -> dict:
    # sites first
    sa, sb = sites_fp(a_sites), sites_fp(b_sites)
    n = min(len(sa), len(sb))
    for i in range(n):
        if sa[i] != sb[i]:
            return {
                "kind": "site",
                "index": i,
                "archived": sa[i],
                "rerun": sb[i],
            }
    if len(sa) != len(sb):
        return {
            "kind": "site_length",
            "archived_n": len(sa),
            "rerun_n": len(sb),
        }
    nr = min(len(a_rounds), len(b_rounds))
    for t in range(nr):
        fa = round_fingerprint(a_rounds[t], "")
        fb = round_fingerprint(b_rounds[t], "")
        if fa != fb:
            # detail which family field
            details = []
            for h in FAMILY_ORDER:
                if fa[h] != fb[h]:
                    details.append({"family": h, "archived": fa[h], "rerun": fb[h]})
            return {
                "kind": "round",
                "t": t,
                "incumbent_archived": fa["incumbent"],
                "incumbent_rerun": fb["incumbent"],
                "family_diffs": details[:5],
            }
    if len(a_rounds) != len(b_rounds):
        return {
            "kind": "round_length",
            "archived_n": len(a_rounds),
            "rerun_n": len(b_rounds),
        }
    return {"kind": None, "match": True}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    arch = json.loads(ARCHIVE.read_text(encoding="utf-8"))
    print("[compare] re-running seed 1003 (write to stage1_fix only)...", flush=True)
    rerun = run_paired_seed(1003)
    rerun_path = OUT / "smoke_seed_1003_rerun.json"
    rerun_path.write_text(json.dumps(rerun, indent=2, default=str), encoding="utf-8")

    env = {
        "platform": platform.platform(),
        "python": sys.version,
        "numpy": np.__version__,
        "scipy": scipy.__version__,
        "executable": sys.executable,
    }
    (OUT / "environment.json").write_text(json.dumps(env, indent=2), encoding="utf-8")

    comps = {}
    all_match = True
    for arm in (ARM_NATIVE, ARM_FULL_GATE):
        d = first_diff(
            arch["arms"][arm]["rounds"],
            rerun["arms"][arm]["rounds"],
            arch["arms"][arm]["sites"],
            rerun["arms"][arm]["sites"],
        )
        comps[arm] = d
        if d.get("kind") is not None:
            all_match = False
    # B is derived from A; compare final decision fields
    comps[ARM_DECISION_ONLY] = {
        "incumbent_archived": arch["arms"][ARM_DECISION_ONLY]["final"]["incumbent"],
        "incumbent_rerun": rerun["arms"][ARM_DECISION_ONLY]["final"]["incumbent"],
        "status_archived": arch["arms"][ARM_DECISION_ONLY]["final"]["primary_status"],
        "status_rerun": rerun["arms"][ARM_DECISION_ONLY]["final"]["primary_status"],
        "match": (
            arch["arms"][ARM_DECISION_ONLY]["final"]["incumbent"]
            == rerun["arms"][ARM_DECISION_ONLY]["final"]["incumbent"]
            and arch["arms"][ARM_DECISION_ONLY]["final"]["primary_status"]
            == rerun["arms"][ARM_DECISION_ONLY]["final"]["primary_status"]
        ),
    }
    if not comps[ARM_DECISION_ONLY]["match"]:
        all_match = False

    summary = {
        "archive": str(ARCHIVE),
        "rerun": str(rerun_path),
        "environment": env,
        "same_environment_bitmatch": all_match,
        "archived_endpoints": {
            ARM_NATIVE: arch["arms"][ARM_NATIVE]["final"]["incumbent"],
            ARM_DECISION_ONLY: arch["arms"][ARM_DECISION_ONLY]["final"]["incumbent"],
            ARM_FULL_GATE: {
                "incumbent": arch["arms"][ARM_FULL_GATE]["final"]["incumbent"],
                "abort": arch["arms"][ARM_FULL_GATE]["final"].get("abort_status"),
            },
        },
        "rerun_endpoints": {
            ARM_NATIVE: rerun["arms"][ARM_NATIVE]["final"]["incumbent"],
            ARM_DECISION_ONLY: rerun["arms"][ARM_DECISION_ONLY]["final"]["incumbent"],
            ARM_FULL_GATE: {
                "incumbent": rerun["arms"][ARM_FULL_GATE]["final"]["incumbent"],
                "abort": rerun["arms"][ARM_FULL_GATE]["final"].get("abort_status"),
            },
        },
        "rerun_scores_schema_ok": all(
            "truth_eligibility_lost" in rerun["scores"][a]
            and "failure_type" in rerun["scores"][a]
            for a in (ARM_NATIVE, ARM_DECISION_ONLY, ARM_FULL_GATE)
        ),
        "first_diff_by_arm": comps,
        "interpretation": (
            "Same-Windows re-run matches archive bit-for-bit on sites/rounds "
            if all_match
            else "Same-Windows divergence — see first_diff_by_arm (code/state bug, not cross-env)"
        ),
    }
    (OUT / "seed1003_round_compare.json").write_text(
        json.dumps(summary, indent=2, default=str), encoding="utf-8"
    )
    md = [
        "# Seed 1003 同环境逐轮复现比较",
        "",
        f"- 归档：`{ARCHIVE}`（**未覆盖**）",
        f"- 重跑：`{rerun_path}`",
        f"- Python：{env['python'].splitlines()[0]}",
        f"- NumPy：{env['numpy']}；SciPy：{env['scipy']}",
        f"- 平台：{env['platform']}",
        "",
        f"**同环境逐轮一致：{all_match}**",
        "",
        "## 终点",
        "",
        f"- 归档：{summary['archived_endpoints']}",
        f"- 重跑：{summary['rerun_endpoints']}",
        "",
        "## 首次差异",
        "",
        "```json",
        json.dumps(comps, indent=2, default=str),
        "```",
        "",
        "## 跨环境说明",
        "",
        "若 Linux 独立重算得到三臂 `hump`，而本 Windows 归档/重跑均为 "
        "Native=`quad` / B=`DECISION_EMPTY` / C=`ABORT_EMPTY_ELIGIBLE`，"
        "且同环境逐轮一致，则归类为 **数值环境敏感性**（拟合/BLAS 路径），"
        "而非资格政策或 RNG 协议错误。正式报告须记录运行环境。",
        "",
    ]
    (OUT / "seed1003_round_compare.md").write_text("\n".join(md), encoding="utf-8")
    print(json.dumps({"same_env_match": all_match, "endpoints": summary["rerun_endpoints"]}, indent=2))
    return 0 if all_match else 1


if __name__ == "__main__":
    raise SystemExit(main())
