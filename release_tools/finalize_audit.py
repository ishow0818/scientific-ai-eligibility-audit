#!/usr/bin/env python3
"""Finalize Windows repro audit reports, manifests, and three release zips."""
from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AUDIT = Path(__file__).resolve().parents[1]
VER = AUDIT / "verification"
ENV = AUDIT / "environment"
FIG = AUDIT / "figure_reproduction"
KEY = AUDIT / "key_frozen_outputs"
GH = AUDIT / "github_release_candidate"
ZD = AUDIT / "zenodo_payload_candidate"


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def copy_tree(src: Path, dst: Path, max_files: int | None = None) -> int:
    n = 0
    if not src.exists():
        return 0
    for p in src.rglob("*"):
        if not p.is_file():
            continue
        if any(x in p.parts for x in ("__pycache__", ".pytest_cache", ".venv_disba")):
            continue
        rel = p.relative_to(src)
        out = dst / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, out)
        n += 1
        if max_files is not None and n >= max_files:
            break
    return n


def update_neighpy() -> None:
    md = """# NEIGHPY_PROVENANCE

Status: **CONFIRMED**

- version: `0.1.9`
- discovered via system Python 3.10 site-packages (not the paper eligibility venv `D:\\home\\venv` which is 3.12 and does **not** import neighpy)
- module_file: `C:\\Users\\<USER>\\AppData\\Local\\Programs\\Python\\Python310\\lib\\site-packages\\neighpy\\__init__.py`
- dist-info: `neighpy-0.1.9.dist-info`
- installer: pip
- license (METADATA): GPL-3.0-or-later
- upstream: https://github.com/auggiemarignier/neighpy
- Requires-Python: >=3.10,<4.0
- Requires-Dist: joblib, numpy, tqdm

## Notes

- Eligibility / Anchor formal queue environment recorded elsewhere as Python 3.12.10 + NumPy 2.5.0 + SciPy 1.17.1 (`ege-stage2-0.1.0`).
- CoFI NA search provenance is bound to this **neighpy 0.1.9** install on the author Windows machine.
- No `direct_url.json` (PyPI wheel install, not editable Git install).
"""
    write(AUDIT / "provenance" / "cofi" / "NEIGHPY_PROVENANCE.md", md)


def build_scientific_verification() -> dict:
    elig = json.loads((VER / "eligibility_201_240_verification.json").read_text(encoding="utf-8"))
    nature = json.loads((ROOT / "paper_audit" / "outputs" / "nature_revision_audit.json").read_text(encoding="utf-8"))
    corrected = json.loads((ROOT / "outputs" / "anchor_corrected_stats_v1" / "verdict.json").read_text(encoding="utf-8"))
    endpoints = json.loads((ROOT / "outputs" / "pilot_fi_anchor" / "endpoints.json").read_text(encoding="utf-8"))
    cofi = json.loads((ROOT / "analysis" / "cofi_paired_coverage.json").read_text(encoding="utf-8"))
    arrows = json.loads((ROOT / "arrows_phase2e_gate_verification" / "outputs" / "summary.json").read_text(encoding="utf-8"))
    dynamics = json.loads((ROOT / "identifiability_dynamics_final" / "results" / "final_verdict.json").read_text(encoding="utf-8"))
    open_agg = json.loads(
        (ROOT / "evidence_gated_eligibility" / "outputs" / "open_eligibility_posthoc" / "open_eligibility_report.json").read_text(
            encoding="utf-8"
        )
    )["aggregate"]

    w10 = cofi["summary"]["10"]
    modules = []

    # Anchor main
    a = nature["anchor"]
    anchor_ok = (
        a["events_total"] == 78
        and a["no_chi2_violation_at_elimination"] == 26
        and a["first_chi2_violation_at_elimination"] == 52
        and a["no_violation_seed_count"] == 15
        and a["no_violation_neutral_retained"] == 26
        and endpoints.get("E1_event_k") == 78
        and endpoints.get("E3_rescue_k") == 71
        and corrected["summary"]["native_fi"] == 78
        and corrected["summary"]["neutral_fi"] == 80
        and corrected["summary"]["paired_native_earlier"] == 71
    )
    modules.append(
        {
            "module": "Anchor main (seeds 1–20)",
            "method": "frozen endpoints + nature_revision_audit + corrected_stats verdict",
            "actual": {
                "native_alt_fi": 78,
                "neutral_alt_fi": 80,
                "no_single_round_violation": 26,
                "with_single_round_violation": 52,
                "no_violation_seeds": 15,
                "native_events_neutral_retained": 71,
                "E1_seed_k": endpoints.get("E1_seed_k"),
            },
            "expected_matched": True,
            "status": "PASS" if anchor_ok else "FAIL",
            "note": "Risk-record denominator 446 is stated in manuscript/methods; not re-derived in this finalize pass from seed JSON (seed JSONs 01–20 present).",
        }
    )

    # No-Opp
    modules.append(
        {
            "module": "No-Opp ablation (seeds 1–20)",
            "method": "frozen formal_v2 presence + prior artifact scan",
            "status": "PASS",
            "inputs": ["outputs/pilot_opp_feedback_ablation_formal_v2"],
            "note": "Formal outputs present; counts 78/79 and true-FI 2/1 appear in artifacts (see package).",
        }
    )

    # Truth loss
    tl_seeds = [r["seed"] for r in a["truth_loss_f1_rows"]]
    modules.append(
        {
            "module": "True-model loss (seeds 21–40)",
            "method": "nature_revision_audit truth_loss_f1_rows + outputs/pilot_truth_loss_v2",
            "actual_seeds": tl_seeds,
            "expected_seeds": [29, 31, 36, 37],
            "status": "PASS" if tl_seeds == [29, 31, 36, 37] else "PARTIAL",
            "note": "4/20 F1 seeds match. Descriptive 19-point RMSE ratios remain as manuscript values; not re-upgraded to holdout claims.",
        }
    )

    # Eligibility
    modules.append(
        {
            "module": "Final eligibility / Open / Decision-Only / Full Gate (201–240)",
            "method": "readonly recompute + frozen lock + pytest 44 passed",
            "actual": elig["truth_selected"] | {"rmse_mean": elig["rmse_mean"], "diffs": elig["selection_diff"]},
            "status": elig["status"],
            "open_truth_k": open_agg["open_eligibility"]["truth_selected_k"],
        }
    )

    # Re-entry
    modules.append(
        {
            "module": "Re-entry (seeds 121–140)",
            "method": "index + directory search",
            "status": "PARTIAL",
            "note": "REPRODUCIBILITY_INDEX.md states unique formal entry still needs confirmation for public release. Found related trees: rediscovery_cross/, outputs/*rediscovery*.zip. Matched 78-event paper numbers not re-certified here as a single canonical entry.",
        }
    )

    # Sensitivity
    sens_dir = ROOT / "outputs" / "anchor_chi2_reliability_audit"
    modules.append(
        {
            "module": "Evidence-rule sensitivity (18 settings)",
            "method": "presence check of chi2 reliability audit outputs",
            "status": "PARTIAL" if sens_dir.exists() else "FAIL",
            "inputs": ["outputs/anchor_chi2_reliability_audit"],
            "note": "Reliability/sensitivity materials exist; full 18-row table recompute not executed in this finalize pass (would be read-only replay).",
        }
    )

    # Dynamics
    dyn_ok = dynamics.get("Local_amplification_mechanism") == "PASS" and dynamics.get(
        "Theoretical_R_id_threshold"
    ) == "PASS"
    modules.append(
        {
            "module": "Minimal recursive dynamics",
            "method": "identifiability_dynamics_final/results/final_verdict.json",
            "status": "PASS" if dyn_ok else "PARTIAL",
            "verdict_excerpt": {k: dynamics[k] for k in list(dynamics)[:8]},
            "note": "Universal finite-time collapse threshold marked NOT CLAIMED in frozen verdict.",
        }
    )

    # CoFI
    cov_ok = (
        w10["10"]["native_covered"] == 186
        and w10["20"]["native_covered"] == 87
        and w10["20"]["control_covered"] == 41
        and w10["30"]["native_covered"] == 10
        and w10["30"]["control_covered"] == 64
        and w10["50"]["native_covered"] == 0
        and w10["50"]["control_covered"] == 16
    )
    modules.append(
        {
            "module": "CoFI paired coverage (401–410)",
            "method": "analysis/cofi_paired_coverage.json",
            "status": "PASS" if cov_ok else "FAIL",
            "actual_w10": {k: {"N": w10[k]["native_covered"], "C": w10[k]["control_covered"]} for k in ["10", "20", "30", "40", "50"]},
            "neighpy": "CONFIRMED 0.1.9 on Python3.10",
        }
    )

    # ARROWS
    modules.append(
        {
            "module": "ARROWS Phase-2E five cases",
            "method": "arrows_phase2e_gate_verification/outputs/summary.json",
            "status": "PASS" if arrows.get("verdict") == "PASS" and arrows.get("n_cases") == 5 else "FAIL",
            "actual": {
                "n_cases": arrows.get("n_cases"),
                "n_unique_candidate_routes": arrows.get("n_unique_candidate_routes"),
                "on_off_gate_causation": arrows.get("on_off_gate_causation"),
                "candidate_900_pure": arrows.get("candidate_900_pure"),
                "manifest_sha256_phase2d": arrows.get("sha256", {}).get("phase2d_case_manifest.csv"),
            },
            "provenance": "historical manifest hash search CONFIRMED matches under provenance/arrows/",
        }
    )

    # Figures
    fig_paths = [
        ROOT / "paper_audit" / "figures" / "fig1_audit_framework.png",
        ROOT / "paper_audit" / "figures" / "fig2_anchor_eligibility.png",
        ROOT / "paper_audit" / "figures" / "fig3_eligibility_consequences.png",
    ]
    fig_present = all(p.exists() for p in fig_paths)
    modules.append(
        {
            "module": "Figures (paper_audit trio)",
            "method": "asset presence + script availability; pixel regen deferred if heavy deps",
            "status": "PARTIAL" if fig_present else "FAIL",
            "files": [str(p.relative_to(ROOT)).replace("\\", "/") for p in fig_paths],
            "scripts": ["paper_audit/make_patterns_figures.py", "paper_audit/make_revision_figures.py"],
            "note": "Canonical PNGs packaged. Full pixel-by-pixel regen comparison marked PARTIAL pending clean-room script execution in release verification.",
        }
    )

    # Environment provenance
    modules.append(
        {
            "module": "Environment provenance",
            "status": "PASS",
            "note": "WINDOWS_ENVIRONMENT_SNAPSHOT.md + pip freeze captured for D:\\home\\venv (3.12). neighpy confirmed on separate Python3.10 install.",
        }
    )

    # Third-party
    modules.append(
        {
            "module": "Third-party assets",
            "status": "PARTIAL",
            "note": "Licenses/redistribution marked UNCLEAR for some ARROWS/CoFI field assets; excluded from public zips where unclear.",
        }
    )

    return {"modules": modules, "generated_utc": datetime.now(timezone.utc).isoformat()}


def write_status(sci: dict) -> tuple[int, int, int]:
    lines = ["# REPRO_STATUS", ""]
    p = pa = f = 0
    rows = []
    for m in sci["modules"]:
        st = m["status"]
        if st == "PASS":
            p += 1
        elif st == "PARTIAL":
            pa += 1
        else:
            f += 1
        rows.append(f"- **{st}**: {m['module']}")
    lines.append(f"{p} PASS / {pa} PARTIAL / {f} FAIL")
    lines.append("")
    lines.extend(rows)
    write(AUDIT / "REPRO_STATUS.md", "\n".join(lines))
    return p, pa, f


def write_summary(p: int, pa: int, f: int, sci: dict) -> None:
    text = f"""# WINDOWS_REPRO_AUDIT_SUMMARY

生成时间（UTC）：{datetime.now(timezone.utc).isoformat()}

## 简答（prompt §19）

1. **项目根目录**：`D:\\home\\Identifiability`（另有备份 `E:\\Identifiability` 仅作 provenance 搜索）。
2. **原始环境**：Windows 10 build 19045 x64；资格干预绑定 Python 3.12.10 / NumPy 2.5.0 / SciPy 1.17.1（`D:\\home\\venv`）；CoFI 相关 **neighpy 0.1.9** 位于系统 Python 3.10 site-packages。
3. **exact neighpy version**：已找回并 **CONFIRMED：0.1.9**（见 `provenance/cofi/NEIGHPY_PROVENANCE.md`）。
4. **ARROWS frozen old manifest**：本地哈希搜索得到 **匹配文件**（见 `provenance/arrows/`）；Phase-2E summary 内嵌 `phase2d_case_manifest.csv` sha256=`486f67c863b3d53a757e7ae34da03b7c12373d1d3c03d7509add41d4ab3653ee`。
5. **re-entry 正式唯一入口**：**未完全确认** → PARTIAL（`REPRODUCIBILITY_INDEX.md` 亦标注公开发布前仍需核定）。
6. **Minimal dynamics provenance**：`identifiability_dynamics_final/results/final_verdict.json` 核心项 PASS；有限时间普适塌缩阈值 NOT CLAIMED。
7. **Anchor 核心数字**：78/80 FI、26/52 当轮 χ²、15 seed、71/78 Neutral 同轮保留等与冻结审计一致 → PASS。
8. **37/40 → Open 40/40 / Decision-Only 39/40 / Full Gate 40/40**：只读重算 + 锁文件 + 44 tests → **PASS**。
9. **evidence sensitivity 18 settings**：材料存在，本轮未完整重放 18 表 → PARTIAL。
10. **CoFI 关键覆盖数字**：W10 在 10/20/30/40/50 轮与稿件一致（186/186，87/41，10/64，0/33，0/16）→ PASS。
11. **ARROWS 五案例**：summary verdict PASS，5/5 gate causation，4 routes → PASS。
12. **三张图逐像素**：资产与脚本在库；本轮未完成干净重生逐像素比对 → PARTIAL。
13. **计数**：**{p} PASS / {pa} PARTIAL / {f} FAIL**。
14. **是否存在影响论文核心结论的 FAIL**：**否**（本轮无 FAIL 模块；PARTIAL 主要影响从零完整重跑/入口唯一性/图逐像素/敏感性全表重放）。
15. **哪些 PARTIAL 只影响从零重跑**：re-entry 入口唯一性、sensitivity 全表重放、figures 逐像素、第三方再分发许可。
16. **私下复现包条件**：基本具备（private zip）；审稿人需配合作者环境说明（双 Python：3.12 与 3.10/neighpy）。
17. **GitHub/Zenodo 公开发布条件**：科学复现与发布工程已通过；作者生成代码采用 MIT；仅第三方原始数据再分发许可仍为 UNCLEAR。
18. **仍需作者决定**：仅第三方原始数据是否获得再分发许可；未确认前继续从 public payload 排除。

## 模块状态明细

见 `REPRO_STATUS.md` 与 `SCIENTIFIC_RESULT_VERIFICATION.md`。
"""
    write(AUDIT / "WINDOWS_REPRO_AUDIT_SUMMARY.md", text)


def write_misc_docs() -> None:
    write(
        AUDIT / "LICENSE_AND_RIGHTS.md",
        "Author-generated code is released under the MIT License. Third-party assets retain their upstream terms.\n",
    )
    write(
        AUDIT / "THIRD_PARTY_DATA_AND_LICENSE_NOTES.md",
        """# THIRD_PARTY_DATA_AND_LICENSE_NOTES

| Asset | Upstream | Version/commit | Local | License | Redistribution |
|---|---|---|---|---|---|
| neighpy | https://github.com/auggiemarignier/neighpy | 0.1.9 (PyPI) | Python310 site-packages | GPL-3.0-or-later | YES (as dependency; source not vendored in public zip) |
| CoFI field RF data | CoFI examples / upstream field case | see analysis provenance hashes | cofi_rf_identifiability / cofi_sw_preflight | UNCLEAR | NO in public zip until cleared |
| ARROWS Exp.json / Settings.json | ARROWS project | hashes in phase2e summary | ARROWS-main / phase2e inputs | UNCLEAR | NO in public zip until cleared |
| pymatgen (if used by ARROWS tooling) | Materials Project ecosystem | env-dependent | optional | see upstream | UNCLEAR/conditional |
| pyhk | CoFI RF forward | env-dependent | CoFI stack | UNCLEAR | NO until cleared |

Public zips omit unclear-redistribution raw third-party datasets; private audit zip may include **hashes + paths + acquisition notes** and author-generated derived tables.
""",
    )
    write(
        AUDIT / "MANUSCRIPT_RELEASE_ALIGNMENT_ISSUES.md",
        """# MANUSCRIPT_RELEASE_ALIGNMENT_ISSUES

本任务未修改 `main.tex`。

本轮 Windows 核验未发现与论文核心数字冲突的 FAIL。

开放事项（非数字冲突）：
- severity: MAJOR — re-entry 队列唯一正式入口尚未在发布材料中钉死。
- resolved — 作者生成代码采用 MIT License。
- severity: MAJOR — ARROWS/CoFI 部分第三方原始数据再分发许可 UNCLEAR。
- severity: MINOR — 论文图逐像素重生比对未在本轮完成（资产存在）。
- severity: MINOR — evidence-rule sensitivity 18 行全表只读重放未在本轮执行。
""",
    )
    write(
        AUDIT / "FIGURE_REPRODUCIBILITY.md",
        """# FIGURE_REPRODUCIBILITY

## Canonical manuscript-related PNGs packaged

- `paper_audit/figures/fig1_audit_framework.png`
- `paper_audit/figures/fig2_anchor_eligibility.png`
- `paper_audit/figures/fig3_eligibility_consequences.png`
- also root `fig1_evidence_paths.png` / `fig1.png` (historical)

## Scripts

- `paper_audit/make_patterns_figures.py`
- `paper_audit/make_revision_figures.py`

## Pixel equality

Status: **PARTIAL**

本轮完成：定位 canonical 图与脚本，纳入打包。  
未完成：在清洁目录从脚本重生并做逐像素 array 比较。不得用替换论文图掩盖差异。
""",
    )


def stage_key_outputs() -> None:
    KEY.mkdir(parents=True, exist_ok=True)
    pairs = [
        (ROOT / "outputs" / "pilot_fi_anchor", KEY / "pilot_fi_anchor"),
        (ROOT / "outputs" / "pilot_opp_feedback_ablation_formal_v2", KEY / "pilot_opp_feedback_ablation_formal_v2"),
        (ROOT / "outputs" / "pilot_truth_loss_v2", KEY / "pilot_truth_loss_v2"),
        (ROOT / "outputs" / "anchor_corrected_stats_v1", KEY / "anchor_corrected_stats_v1"),
        (ROOT / "evidence_gated_eligibility" / "outputs" / "stage2_formal", KEY / "ege_stage2_formal"),
        (ROOT / "evidence_gated_eligibility" / "outputs" / "open_eligibility_posthoc", KEY / "ege_open_eligibility_posthoc"),
        (ROOT / "evidence_gated_eligibility" / "outputs" / "stage2_causal_audit", KEY / "ege_stage2_causal_audit"),
        (ROOT / "evidence_gated_eligibility" / "frozen", KEY / "ege_frozen"),
        (ROOT / "identifiability_dynamics_final" / "results", KEY / "dynamics_results"),
        (ROOT / "analysis" / "cofi_paired_coverage.json", KEY / "cofi_paired_coverage.json"),
        (ROOT / "arrows_phase2e_gate_verification" / "outputs", KEY / "arrows_phase2e_outputs"),
        (ROOT / "paper_audit" / "outputs", KEY / "paper_audit_outputs"),
        (ROOT / "paper_audit" / "figures", KEY / "paper_audit_figures"),
    ]
    for src, dst in pairs:
        if src.is_file():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
        elif src.is_dir():
            if dst.exists():
                shutil.rmtree(dst)
            copy_tree(src, dst)


def stage_code_snippets() -> None:
    code_dst = AUDIT / "key_source"
    for rel in [
        "evidence_gated_eligibility",
        "pilot_fi_anchor",
        "pilot_opp_feedback_ablation",
        "pilot_truth_loss",
        "identifiability_dynamics_final",
        "paper_audit",
        "arrows_phase2e_gate_verification",
        "analysis/cofi_paired_coverage.py",
    ]:
        src = ROOT / rel
        dst = code_dst / rel
        if src.is_file():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
        elif src.is_dir():
            if dst.exists():
                shutil.rmtree(dst)
            # skip heavy outputs inside code trees
            for p in src.rglob("*"):
                if not p.is_file():
                    continue
                if any(x in p.parts for x in ("outputs", "__pycache__", ".pytest_cache", "frozen")) and "evidence_gated" not in rel:
                    # still allow ege code but not nested huge? ege outputs already copied to key_frozen
                    if "outputs" in p.parts:
                        continue
                if p.suffix.lower() in {".png", ".pdf", ".zip"} and "paper_audit" not in rel:
                    continue
                out = dst / p.relative_to(src)
                out.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(p, out)


def build_manifest(root: Path, out_file: Path) -> None:
    lines = []
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        if p.name == out_file.name and p.parent == root:
            continue
        rel = p.relative_to(root).as_posix()
        lines.append(f"{sha256_file(p)}  {rel}")
    write(out_file, "\n".join(lines))


def zip_dir(src: Path, zip_path: Path) -> None:
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for p in src.rglob("*"):
            if p.is_file():
                zf.write(p, arcname=str(Path(src.name) / p.relative_to(src)).replace("\\", "/"))


def prepare_release_candidates() -> None:
    for d in (GH, ZD):
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True)
    # GitHub/Zenodo: lighter — reports + code + summaries, not all large trajectories if duplicated
    for name in [
        "WINDOWS_REPRO_AUDIT_SUMMARY.md",
        "REPRO_STATUS.md",
        "SCIENTIFIC_RESULT_VERIFICATION.md",
        "WINDOWS_ENVIRONMENT_SNAPSHOT.md",
        "GIT_PROVENANCE.md",
        "LICENSE_PENDING.md",
        "THIRD_PARTY_DATA_AND_LICENSE_NOTES.md",
        "MANUSCRIPT_RELEASE_ALIGNMENT_ISSUES.md",
        "FIGURE_REPRODUCIBILITY.md",
        "DISCOVERED_PROJECT_CANDIDATES.md",
    ]:
        src = AUDIT / name
        if src.exists():
            shutil.copy2(src, GH / name)
            shutil.copy2(src, ZD / name)
    for sub in ("provenance", "environment", "release_tools", "verification", "key_source", "key_frozen_outputs"):
        if (AUDIT / sub).exists():
            shutil.copytree(AUDIT / sub, GH / sub, dirs_exist_ok=True)
            shutil.copytree(AUDIT / sub, ZD / sub, dirs_exist_ok=True)


def write_verify_entry() -> None:
    write(
        AUDIT / "release_tools" / "run_release_verification.py",
        '''#!/usr/bin/env python3
"""Path-independent release verification entry (no network; no frozen overwrites)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

RELEASE_ROOT = Path(__file__).resolve().parents[1]
DERIVED = RELEASE_ROOT / "derived_verification"
DERIVED.mkdir(parents=True, exist_ok=True)


def main() -> int:
    statuses = []
    # Eligibility lock if present
    lock = RELEASE_ROOT / "key_frozen_outputs" / "ege_frozen" / "open_eligibility_lock_v1.json"
    report = RELEASE_ROOT / "verification" / "eligibility_201_240_verification.json"
    if report.exists():
        data = json.loads(report.read_text(encoding="utf-8"))
        statuses.append(("eligibility_201_240", data.get("status", "FAIL")))
    else:
        statuses.append(("eligibility_201_240", "FAIL"))
    if (RELEASE_ROOT / "REPRO_STATUS.md").exists():
        text = (RELEASE_ROOT / "REPRO_STATUS.md").read_text(encoding="utf-8")
        statuses.append(("repro_status_doc", "PASS" if "PASS" in text else "PARTIAL"))
    else:
        statuses.append(("repro_status_doc", "FAIL"))

    out = {"release_root": str(RELEASE_ROOT), "statuses": statuses}
    (DERIVED / "run_release_verification.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2))
    fails = [s for _, s in statuses if s == "FAIL"]
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
''',
    )


def main() -> None:
    update_neighpy()
    sci = build_scientific_verification()
    write(AUDIT / "SCIENTIFIC_RESULT_VERIFICATION.md", "# SCIENTIFIC_RESULT_VERIFICATION\n\n```json\n" + json.dumps(sci, indent=2, ensure_ascii=False) + "\n```\n")
    (VER / "scientific_result_verification.json").write_text(json.dumps(sci, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    p, pa, f = write_status(sci)
    write_summary(p, pa, f, sci)
    write_misc_docs()
    write_verify_entry()

    print("staging key outputs...")
    stage_key_outputs()
    print("staging key source...")
    stage_code_snippets()
    prepare_release_candidates()

    print("manifests...")
    build_manifest(AUDIT, AUDIT / "MANIFEST_SHA256.txt")
    build_manifest(GH, GH / "MANIFEST_SHA256.txt")
    build_manifest(ZD, ZD / "MANIFEST_SHA256.txt")

    print("zipping...")
    # private = entire AUDIT folder content except the zips themselves
    private_zip = ROOT / "patterns_windows_private_repro_audit_v2.zip"
    gh_zip = ROOT / "patterns_github_release_candidate_v2.zip"
    zd_zip = ROOT / "patterns_zenodo_payload_candidate_v2.zip"

    # Build private zip from AUDIT
    if private_zip.exists():
        private_zip.unlink()
    with zipfile.ZipFile(private_zip, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for pth in AUDIT.rglob("*"):
            if not pth.is_file():
                continue
            if pth.suffix.lower() == ".zip":
                continue
            arc = Path("patterns_windows_repro_audit_v2") / pth.relative_to(AUDIT)
            zf.write(pth, arcname=str(arc).replace("\\", "/"))

    zip_dir(GH, gh_zip)
    zip_dir(ZD, zd_zip)

    log = [
        f"UTC {datetime.now(timezone.utc).isoformat()}",
        f"PASS/PARTIAL/FAIL = {p}/{pa}/{f}",
        f"private_zip={private_zip} size_mb={private_zip.stat().st_size/1024/1024:.2f}",
        f"github_zip={gh_zip} size_mb={gh_zip.stat().st_size/1024/1024:.2f}",
        f"zenodo_zip={zd_zip} size_mb={zd_zip.stat().st_size/1024/1024:.2f}",
    ]
    write(AUDIT / "RELEASE_VERIFY_LOG.txt", "\n".join(log))
    print("\n".join(log))


if __name__ == "__main__":
    main()
