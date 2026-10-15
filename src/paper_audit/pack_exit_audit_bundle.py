#!/usr/bin/env python3
"""Pack Anchor exit-mechanism audit bundle ZIP for human review."""
from __future__ import annotations

import json
import zipfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "anchor_exit_mechanism_audit"
STAMP = datetime.now().strftime("%Y%m%d_%H%M")
BUNDLE = OUT / f"anchor_exit_mechanism_audit_bundle_{STAMP}.zip"

README = """# Anchor Exit Mechanism Audit Bundle

打包目的：支持人工复核以下四项（只读；不含论文自动修改）。

## 1. 删除机制
- 源码：`code/pilot_fi_anchor/loop.py`（`step` / `_check_elimination` / `_update_evidence`）
- 阈值：`code/pilot_fi_anchor/config.py`（`THETA_W=0.02`, `PERSIST=2`）
- 审计分类：`code/paper_audit/anchor_exit_mechanism_audit.py`
- 结论摘要：正式队列 `alive=False` 仅由 `w_surv < THETA_W` 触发；`_update_evidence` 只写 excluded/t_excl。

## 2. 事件统计
- 明细：`audit/exit_events.csv`
- 配对时序：`audit/paired_exit_timing.csv`
- 汇总：`audit/exit_mechanism_summary.csv`、`audit/anchor_exit_mechanism_audit.md`、`audit/verdict.json`
- 目标数字：Native FI=78，Neutral FI=80；当轮 violated=false 为 26/77；配对更早 71/7/2。
- 一键重算：解压后运行 `python reproduce_counts.py`

## 3. 真实模型丢失
- 正式队列 1–20：`logs/formal_1_20/seed_XX.json`（关注 seed 17、20 的 hump/quad）
- 扩展队列 21–40：`logs/truth_loss_21_40/seed_0XX.json`（F1: 29/31/36/37）
- 同一 FI 定义：`t_elim` 存在且 (`t_excl` 为空或 `t_elim < t_excl`)；见审计脚本。

## 4. 机制归因
- 报告 A–F：`audit/anchor_exit_mechanism_audit.md`
- 分叉证据：配对表 `init_shared` / `first_site_diff_round`；源码 Native vs Neutral 分配函数。

## 目录结构
```
README.md
MANIFEST.json
reproduce_counts.py
code/pilot_fi_anchor/
code/paper_audit/
logs/formal_1_20/
logs/truth_loss_21_40/
audit/
```
"""

REPRODUCE = '''#!/usr/bin/env python3
"""Recompute key counts from bundled logs (stdlib only)."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FALSE = ("affine", "pow", "expsat", "quad")
R = 25


def load_seeds(folder: Path):
    files = sorted(folder.glob("seed_*.json"))
    return [json.loads(p.read_text(encoding="utf-8")) for p in files]


def is_fi(t_elim, t_excl) -> bool:
    if t_elim is None:
        return False
    return t_excl is None or t_elim < t_excl


def main() -> None:
    formal = load_seeds(ROOT / "logs" / "formal_1_20")
    assert len(formal) == 20, len(formal)
    n_fi = u_fi = 0
    n_nov = u_nov = 0
    earlier_n = earlier_u = same = 0
    for rec in formal:
        nf = rec["arms"]["native"]["final"]
        uf = rec["arms"]["neutral"]["final"]
        nr = rec["arms"]["native"]["rounds"]
        ur = rec["arms"]["neutral"]["rounds"]
        for h in FALSE:
            te_n, tx_n = nf["t_elim"][h], nf["t_excl"][h]
            te_u, tx_u = uf["t_elim"][h], uf["t_excl"][h]
            if is_fi(te_n, tx_n):
                n_fi += 1
                if not nr[te_n][h]["violated"]:
                    n_nov += 1
            if is_fi(te_u, tx_u):
                u_fi += 1
                if not ur[te_u][h]["violated"]:
                    u_nov += 1
            a = te_n if te_n is not None else R + 1
            b = te_u if te_u is not None else R + 1
            if te_n is None and te_u is None:
                continue
            if a < b:
                earlier_n += 1
            elif b < a:
                earlier_u += 1
            else:
                same += 1
    print("Native FI", n_fi, "Neutral FI", u_fi)
    print("no single-chi2 at elim Native/Neutral", n_nov, u_nov)
    print("paired earlier Native/Neutral/same", earlier_n, earlier_u, same)

    # Mechanism spot-check: every false exit has w_surv < 0.02 at t_elim
    bad = 0
    for rec in formal:
        for arm_name in ("native", "neutral"):
            arm = rec["arms"][arm_name]
            for h in FALSE:
                te = arm["final"]["t_elim"][h]
                if te is None:
                    continue
                w = arm["rounds"][te][h]["w_surv"]
                if not (w < 0.02):
                    bad += 1
                    print("BAD weight prune", rec["seed"], arm_name, h, te, w)
                # excluded must not precede elim in final labels for FI cases
    print("exits with w_surv>=0.02 at elim (expect 0):", bad)

    for s in (17, 20):
        rec = next(r for r in formal if r["seed"] == s)
        print(
            "formal seed",
            s,
            "native t_elim hump/quad",
            rec["arms"]["native"]["final"]["t_elim"]["hump"],
            rec["arms"]["native"]["final"]["t_elim"]["quad"],
            "inc",
            rec["arms"]["native"]["final"]["incumbent"],
        )

    ext = load_seeds(ROOT / "logs" / "truth_loss_21_40")
    f1 = []
    for rec in ext:
        te = rec["arms"]["native"]["final"]["t_elim"]["hump"]
        tx = rec["arms"]["native"]["final"]["t_excl"]["hump"]
        if is_fi(te, tx):
            f1.append(rec["seed"])
    print("truth-loss F1 native seeds", f1, "count", len(f1))


if __name__ == "__main__":
    main()
'''


def main() -> int:
    code_files = [
        ROOT / "pilot_fi_anchor" / "loop.py",
        ROOT / "pilot_fi_anchor" / "config.py",
        ROOT / "pilot_fi_anchor" / "metrics.py",
        ROOT / "pilot_fi_anchor" / "evidence_calibration.py",
        ROOT / "pilot_fi_anchor" / "__init__.py",
        ROOT / "paper_audit" / "anchor_exit_mechanism_audit.py",
        ROOT / "paper_audit" / "pack_exit_audit_bundle.py",
    ]
    for extra in ("fitting.py", "mechanisms.py", "EXPERIMENT_DESIGN.md", "rng.py"):
        p = ROOT / "pilot_fi_anchor" / extra
        if p.is_file():
            code_files.append(p)

    formal_logs = sorted((ROOT / "outputs" / "pilot_fi_anchor").glob("seed_*.json"))
    truth_logs: list[Path] = []
    for s in range(21, 41):
        for name in (f"seed_{s:03d}.json", f"seed_{s:02d}.json", f"seed_{s}.json"):
            p = ROOT / "outputs" / "pilot_truth_loss_v2" / name
            if p.is_file():
                truth_logs.append(p)
                break

    audit_files = [
        OUT / "exit_events.csv",
        OUT / "paired_exit_timing.csv",
        OUT / "exit_mechanism_summary.csv",
        OUT / "anchor_exit_mechanism_audit.md",
        OUT / "verdict.json",
    ]
    official = [
        ROOT / "outputs" / "pilot_fi_anchor" / "summary_events.csv",
        ROOT / "outputs" / "pilot_fi_anchor" / "endpoints.json",
    ]

    missing = [p for p in code_files + audit_files if not p.is_file()]
    if missing:
        raise SystemExit(f"missing required files: {missing}")
    if len(formal_logs) != 20:
        raise SystemExit(f"expected 20 formal seeds, got {len(formal_logs)}")
    if len(truth_logs) != 20:
        raise SystemExit(f"expected 20 truth-loss seeds 21-40, got {len(truth_logs)}")

    manifest = {
        "created": datetime.now().isoformat(timespec="seconds"),
        "bundle": BUNDLE.name,
        "purpose": "Human review of Anchor Native-Neutral FI exit mechanism audit",
        "checks": [
            "alive=False only via w_surv<0.02; chi-square evidence does not set alive",
            "counts 78/80, 26/77, 71/7/2",
            "truth-loss formal 17/20 vs extension 4/20 under same FI definition",
            "attribution: shared prune causes eligibility exit; selection strategy changes trajectories",
        ],
        "n_formal_logs": len(formal_logs),
        "n_truth_logs": len(truth_logs),
        "code_files": [str(p.relative_to(ROOT)).replace("\\", "/") for p in code_files],
    }

    OUT.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(BUNDLE, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("README.md", README)
        zf.writestr("MANIFEST.json", json.dumps(manifest, indent=2, ensure_ascii=False))
        zf.writestr("reproduce_counts.py", REPRODUCE)
        for p in code_files:
            if "paper_audit" in p.parts:
                arc = f"code/paper_audit/{p.name}"
            else:
                arc = f"code/pilot_fi_anchor/{p.name}"
            zf.write(p, arc)
        for p in formal_logs:
            zf.write(p, f"logs/formal_1_20/{p.name}")
        for p in truth_logs:
            zf.write(p, f"logs/truth_loss_21_40/{p.name}")
        for p in audit_files:
            zf.write(p, f"audit/{p.name}")
        for p in official:
            if p.is_file():
                zf.write(p, f"logs/formal_1_20/_official/{p.name}")

    print(BUNDLE)
    print(f"size_MB={BUNDLE.stat().st_size / 1024 / 1024:.2f}")
    print(f"formal={len(formal_logs)} truth={len(truth_logs)} code={len(code_files)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
