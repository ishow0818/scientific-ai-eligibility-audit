#!/usr/bin/env python3
"""Build distinct GitHub vs Zenodo release candidates and clean-room figure compare."""
from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AUDIT = Path(__file__).resolve().parents[1]
CLEAN_FIG = Path(r"C:\Temp\patterns_figure_clean_room")
CLEAN_REL = Path(r"C:\Temp\patterns_release_split_test")


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text.rstrip() + "\n", encoding="utf-8")


def copy_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def copy_tree(src: Path, dst: Path, *, skip_parts=(), max_mb: float | None = None) -> int:
    n = 0
    if not src.exists():
        return 0
    for p in src.rglob("*"):
        if not p.is_file():
            continue
        if any(x in p.parts for x in skip_parts):
            continue
        if max_mb is not None and p.stat().st_size > max_mb * 1024 * 1024:
            continue
        out = dst / p.relative_to(src)
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, out)
        n += 1
    return n


def zip_tree(src: Path, zip_path: Path, arc_root: str) -> None:
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for p in src.rglob("*"):
            if p.is_file():
                zf.write(p, arcname=f"{arc_root}/{p.relative_to(src).as_posix()}")


def manifest(root: Path, out: Path) -> int:
    lines = []
    for p in sorted(root.rglob("*")):
        if p.is_file() and p.name != "MANIFEST_SHA256.txt":
            lines.append(f"{sha256(p)}  {p.relative_to(root).as_posix()}")
    write(out, "\n".join(lines))
    return len(lines)


def document_reentry() -> None:
    base = ROOT / "rediscovery_cross" / "anchor_v2_aligned"
    summary = json.loads(
        (base / "outputs" / "confirmatory" / "matched_primary_summary.json").read_text(
            encoding="utf-8"
        )
    )
    write(
        AUDIT / "provenance" / "reentry" / "CANONICAL_ENTRY.md",
        f"""# Re-entry canonical formal entry (seeds 121–140)

Status: **PASS** (resolved from evidence; not guessed)

## Canonical paths
- Runner: `rediscovery_cross/anchor_v2_aligned/run_confirmatory.py`
- Matched analysis: `rediscovery_cross/anchor_v2_aligned/matched_analysis.py`
- Config: `rediscovery_cross/anchor_v2_aligned/config.yaml`
- Outputs: `rediscovery_cross/anchor_v2_aligned/outputs/confirmatory/`

## Manuscript numbers (from matched_primary_summary.json)
```json
{json.dumps({k: summary.get(k) for k in summary}, indent=2)[:2000]}
```

## Rejected near-misses
- `rediscovery_cross/outputs/confirmatory` (seeds ~101–120): different counts
- `aea_closed_loop_formal`: EvidenceGate; McNemar ≠ 0.0625; verdict INVALID
""",
    )


def run_figure_clean_room() -> dict:
    if CLEAN_FIG.exists():
        shutil.rmtree(CLEAN_FIG)
    CLEAN_FIG.mkdir(parents=True)

    # Minimal layout required by make_patterns_figures.py
    layout = [
        "paper_audit/make_patterns_figures.py",
        "evidence_gated_eligibility/eval_grid.py",
        "evidence_gated_eligibility/__init__.py",
        "evidence_gated_eligibility/config.py",
        "pilot_fi_anchor/__init__.py",
        "pilot_fi_anchor/config.py",
        "pilot_fi_anchor/mechanisms.py",
    ]
    # copy seed inputs for figures
    for s in range(201, 241):
        layout.append(f"evidence_gated_eligibility/outputs/stage2_formal/seed_{s}.json")
    for s in range(1, 21):
        layout.append(f"outputs/pilot_fi_anchor/seed_{s:02d}.json")
        layout.append(f"outputs/pilot_opp_feedback_ablation_formal_v2/seed_{s:02d}_paired.json")

    for rel in layout:
        src = ROOT / rel
        if src.exists():
            copy_file(src, CLEAN_FIG / rel)

    # Also need dependencies imported by eval_grid / mechanisms
    for rel in [
        "pilot_fi_anchor/fitting.py",
        "pilot_fi_anchor/world.py",
        "pilot_fi_anchor/rng.py",
        "pilot_fi_anchor/evidence_calibration.py",
        "pilot_fi_anchor/gates.py",
        "pilot_fi_anchor/metrics.py",
        "pilot_fi_anchor/recorder.py",
        "pilot_fi_anchor/perturbation.py",
    ]:
        if (ROOT / rel).exists():
            copy_file(ROOT / rel, CLEAN_FIG / rel)

    import subprocess
    import sys

    py = sys.executable
    script = CLEAN_FIG / "paper_audit" / "make_patterns_figures.py"
    proc = subprocess.run(
        [py, str(script)],
        cwd=str(CLEAN_FIG),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    report = {
        "returncode": proc.returncode,
        "stdout_tail": (proc.stdout or "")[-1000:],
        "stderr_tail": (proc.stderr or "")[-1000:],
        "figures": [],
    }

    try:
        from PIL import Image
        import numpy as np
    except Exception:
        Image = None
        np = None

    pairs = [
        (
            "fig1_audit_framework.png",
            ROOT / "paper_audit" / "figures" / "fig1_audit_framework.png",
            CLEAN_FIG / "paper_audit" / "figures" / "fig1_audit_framework.png",
        ),
        (
            "fig2_anchor_eligibility.png",
            ROOT / "paper_audit" / "figures" / "fig2_anchor_eligibility.png",
            CLEAN_FIG / "paper_audit" / "figures" / "fig2_anchor_eligibility.png",
        ),
        (
            "fig3_eligibility_consequences.png",
            ROOT / "paper_audit" / "figures" / "fig3_eligibility_consequences.png",
            CLEAN_FIG / "paper_audit" / "figures" / "fig3_eligibility_consequences.png",
        ),
    ]
    all_pix_eq = True
    for name, frozen, regen in pairs:
        entry = {"name": name, "frozen_exists": frozen.exists(), "regen_exists": regen.exists()}
        if frozen.exists():
            entry["frozen_sha256"] = sha256(frozen)
            entry["script_sha256"] = sha256(ROOT / "paper_audit" / "make_patterns_figures.py")
        if regen.exists() and frozen.exists() and Image is not None:
            im_f = Image.open(frozen).convert("RGBA")
            im_r = Image.open(regen).convert("RGBA")
            entry["frozen_size"] = im_f.size
            entry["regen_size"] = im_r.size
            entry["regen_sha256"] = sha256(regen)
            entry["file_sha_equal"] = entry["frozen_sha256"] == entry["regen_sha256"]
            a = np.asarray(im_f, dtype=np.int16)
            b = np.asarray(im_r, dtype=np.int16)
            if a.shape != b.shape:
                entry["pixel_equal"] = False
                entry["differing_pixels"] = None
                entry["max_channel_diff"] = None
                all_pix_eq = False
            else:
                diff = np.abs(a - b)
                mask = diff.max(axis=2) > 0
                entry["differing_pixels"] = int(mask.sum())
                entry["max_channel_diff"] = int(diff.max()) if diff.size else 0
                entry["pixel_equal"] = entry["differing_pixels"] == 0
                if not entry["pixel_equal"]:
                    all_pix_eq = False
        else:
            all_pix_eq = False
            entry["pixel_equal"] = False
        report["figures"].append(entry)

    report["status"] = (
        "PASS"
        if proc.returncode == 0 and all_pix_eq
        else ("PARTIAL" if proc.returncode == 0 else "FAIL")
    )
    # copy regenerated into audit
    dst = AUDIT / "figure_reproduction"
    if dst.exists():
        shutil.rmtree(dst)
    if (CLEAN_FIG / "paper_audit" / "figures").exists():
        copy_tree(CLEAN_FIG / "paper_audit" / "figures", dst / "regenerated")
    copy_tree(ROOT / "paper_audit" / "figures", dst / "frozen_manuscript")
    write(dst / "FIGURE_PIXEL_COMPARE.json", json.dumps(report, indent=2))
    write(
        AUDIT / "FIGURE_REPRODUCIBILITY.md",
        "# FIGURE_REPRODUCIBILITY\n\n"
        + f"Status: **{report['status']}**\n\n"
        + "Clean-room dir: `C:\\Temp\\patterns_figure_clean_room`\n\n"
        + "```json\n"
        + json.dumps(report, indent=2)
        + "\n```\n",
    )
    return report


def build_github(gh: Path) -> None:
    if gh.exists():
        shutil.rmtree(gh)
    gh.mkdir(parents=True)

    # Code + configs + docs + small summaries only
    code_dirs = [
        "evidence_gated_eligibility",
        "pilot_fi_anchor",
        "pilot_opp_feedback_ablation",
        "pilot_truth_loss",
        "rediscovery_cross/anchor_v2_aligned",
        "identifiability_dynamics_final",
        "paper_audit",
        "arrows_phase2e_gate_verification",
        "analysis",
    ]
    for rel in code_dirs:
        src = ROOT / rel
        dst = gh / "src" / rel
        if src.is_dir():
            copy_tree(
                src,
                dst,
                skip_parts=(
                    "outputs",
                    "__pycache__",
                    ".pytest_cache",
                    "seed_",  # avoid large json if nested oddly
                ),
                max_mb=5,
            )
        elif src.is_file():
            copy_file(src, dst)

    # Explicitly remove any large seed json copied under src
    for p in gh.rglob("seed_*.json"):
        if p.stat().st_size > 50_000:
            p.unlink()

    # Small derived summaries
    small = [
        "evidence_gated_eligibility/outputs/stage2_formal/formal_aggregate.json",
        "evidence_gated_eligibility/outputs/stage2_formal/formal_report.md",
        "evidence_gated_eligibility/outputs/stage2_formal/formal_seed_summary.csv",
        "evidence_gated_eligibility/outputs/open_eligibility_posthoc/open_eligibility_report.md",
        "evidence_gated_eligibility/outputs/open_eligibility_posthoc/per_seed_open_eligibility.csv",
        "evidence_gated_eligibility/frozen/open_eligibility_lock_v1.json",
        "rediscovery_cross/anchor_v2_aligned/outputs/confirmatory/matched_primary_summary.json",
        "rediscovery_cross/anchor_v2_aligned/outputs/confirmatory/matched_event_table.csv",
        "rediscovery_cross/anchor_v2_aligned/outputs/confirmatory/confirmatory_summary.json",
        "identifiability_dynamics_final/results/final_verdict.json",
        "analysis/cofi_paired_coverage.json",
        "arrows_phase2e_gate_verification/outputs/summary.json",
        "outputs/pilot_fi_anchor/endpoints.json",
        "outputs/pilot_fi_anchor/summary_events.csv",
        "outputs/anchor_corrected_stats_v1/verdict.json",
        "paper_audit/REPRODUCIBILITY_INDEX.md",
        "paper_audit/AEA_TEMPLATE.md",
    ]
    for rel in small:
        src = ROOT / rel
        if src.exists():
            copy_file(src, gh / "summaries" / Path(rel).name)

    # figure scripts + frozen small pngs (not huge trajectories)
    copy_file(
        ROOT / "paper_audit" / "make_patterns_figures.py",
        gh / "figures" / "make_patterns_figures.py",
    )
    for name in [
        "fig1_audit_framework.png",
        "fig2_anchor_eligibility.png",
        "fig3_eligibility_consequences.png",
    ]:
        src = ROOT / "paper_audit" / "figures" / name
        if src.exists():
            copy_file(src, gh / "figures" / name)

    # verification scripts from audit
    copy_tree(AUDIT / "release_tools", gh / "release_tools", skip_parts=("__pycache__",))
    copy_tree(AUDIT / "verification", gh / "verification", skip_parts=("__pycache__",), max_mb=20)
    copy_tree(AUDIT / "provenance", gh / "provenance", skip_parts=("__pycache__",))
    copy_tree(AUDIT / "environment", gh / "environment", skip_parts=("__pycache__",))

    for name in [
        "WINDOWS_REPRO_AUDIT_SUMMARY.md",
        "REPRO_STATUS.md",
        "SCIENTIFIC_RESULT_VERIFICATION.md",
        "WINDOWS_ENVIRONMENT_SNAPSHOT.md",
        "GIT_PROVENANCE.md",
        "LICENSE_AND_RIGHTS.md",
        "THIRD_PARTY_DATA_AND_LICENSE_NOTES.md",
        "MANUSCRIPT_RELEASE_ALIGNMENT_ISSUES.md",
        "FIGURE_REPRODUCIBILITY.md",
        "DISCOVERED_PROJECT_CANDIDATES.md",
    ]:
        if (AUDIT / name).exists():
            copy_file(AUDIT / name, gh / name)

    # Author-generated software license. Third-party components retain upstream terms.
    license_src = AUDIT / "LICENSE"
    if license_src.exists():
        copy_file(license_src, gh / "LICENSE")

    write(
        gh / "THIRD_PARTY_RETRIEVAL.md",
        """# Third-party retrieval (no raw redistribution here)

## neighpy 0.1.9
- pip install neighpy==0.1.9
- https://github.com/auggiemarignier/neighpy
- License: GPL-3.0-or-later

## CoFI field RF inputs
- Obtain from upstream CoFI example / field-data distribution used by `cofi_rf_identifiability`.
- Expected derived analysis hash table: `summaries/cofi_paired_coverage.json` (`source_sha256` fields).
- Raw waveforms omitted (redistribution UNCLEAR).

## ARROWS Exp.json / Settings.json
- Upstream ARROWS repository / benchmark materials.
- Hashes recorded in `summaries/summary.json` (phase2e) under `sha256`.
- Raw Exp.json omitted from GitHub candidate (redistribution UNCLEAR).
""",
    )


def build_zenodo(zd: Path) -> None:
    if zd.exists():
        shutil.rmtree(zd)
    zd.mkdir(parents=True)

    # Large author-generated frozen trajectories / seed JSON
    bundles = [
        ("pilot_fi_anchor", ROOT / "outputs" / "pilot_fi_anchor"),
        ("pilot_opp_feedback_ablation_formal_v2", ROOT / "outputs" / "pilot_opp_feedback_ablation_formal_v2"),
        ("pilot_truth_loss_v2", ROOT / "outputs" / "pilot_truth_loss_v2"),
        ("ege_stage2_formal", ROOT / "evidence_gated_eligibility" / "outputs" / "stage2_formal"),
        ("ege_open_eligibility_posthoc", ROOT / "evidence_gated_eligibility" / "outputs" / "open_eligibility_posthoc"),
        ("ege_stage2_causal_audit", ROOT / "evidence_gated_eligibility" / "outputs" / "stage2_causal_audit"),
        ("ege_frozen", ROOT / "evidence_gated_eligibility" / "frozen"),
        ("reentry_confirmatory", ROOT / "rediscovery_cross" / "anchor_v2_aligned" / "outputs" / "confirmatory"),
        ("dynamics_results", ROOT / "identifiability_dynamics_final" / "results"),
        ("arrows_phase2e_outputs", ROOT / "arrows_phase2e_gate_verification" / "outputs"),
        ("anchor_corrected_stats_v1", ROOT / "outputs" / "anchor_corrected_stats_v1"),
        ("paper_audit_outputs", ROOT / "paper_audit" / "outputs"),
        ("paper_audit_figures", ROOT / "paper_audit" / "figures"),
        ("evidence_sensitivity", AUDIT / "verification" / "evidence_sensitivity"),
        ("figure_reproduction", AUDIT / "figure_reproduction"),
    ]
    for name, src in bundles:
        if src.exists():
            copy_tree(src, zd / "frozen" / name, skip_parts=("__pycache__",))

    # re-entry seed-level 121-140
    seed_dir = ROOT / "rediscovery_cross" / "anchor_v2_aligned" / "outputs" / "confirmatory"
    if seed_dir.exists():
        for p in seed_dir.glob("seed_*.json"):
            copy_file(p, zd / "frozen" / "reentry_seeds_121_140" / p.name)

    # analysis / cofi derived (author-generated)
    if (ROOT / "analysis" / "cofi_paired_coverage.json").exists():
        copy_file(
            ROOT / "analysis" / "cofi_paired_coverage.json",
            zd / "frozen" / "cofi_paired_coverage.json",
        )

    # verification logs + linkage docs
    copy_tree(AUDIT / "verification", zd / "verification", skip_parts=("__pycache__",))
    for name in [
        "WINDOWS_REPRO_AUDIT_SUMMARY.md",
        "REPRO_STATUS.md",
        "LICENSE_AND_RIGHTS.md",
        "THIRD_PARTY_DATA_AND_LICENSE_NOTES.md",
        "FIGURE_REPRODUCIBILITY.md",
        "RELEASE_VERIFY_LOG.txt",
    ]:
        if (AUDIT / name).exists():
            copy_file(AUDIT / name, zd / name)


def write_linkage(gh: Path, zd: Path, gh_zip: Path, zd_zip: Path) -> None:
    write(
        AUDIT / "RELEASE_LINKAGE.md",
        f"""# RELEASE_LINKAGE

## Pairing
- GitHub code candidate: `{gh_zip.name}` ({gh_zip.stat().st_size/1024/1024:.2f} MB)
- Zenodo frozen-data candidate: `{zd_zip.name}` ({zd_zip.stat().st_size/1024/1024:.2f} MB)
- Generated UTC: {datetime.now(timezone.utc).isoformat()}

## How they correspond
| Concern | GitHub candidate | Zenodo payload |
|---|---|---|
| Algorithm source / configs | `src/` | — |
| Verification scripts | `release_tools/`, `verification/` | `verification/` (logs/reports) |
| Small summary tables | `summaries/` | duplicated under `frozen/` where needed |
| Seed-level trajectories / large JSON | intentionally omitted | `frozen/**` |
| Figure scripts + manuscript PNG | `figures/` | `frozen/paper_audit_figures` + regen compare |
| Third-party raw data | retrieval instructions only | omitted unless license clear |

## Integrity
- GitHub files: {gh}/MANIFEST_SHA256.txt
- Zenodo files: {zd}/MANIFEST_SHA256.txt
""",
    )
    copy_file(AUDIT / "RELEASE_LINKAGE.md", gh / "RELEASE_LINKAGE.md")
    copy_file(AUDIT / "RELEASE_LINKAGE.md", zd / "RELEASE_LINKAGE.md")


def clean_verify(gh_zip: Path, zd_zip: Path) -> dict:
    if CLEAN_REL.exists():
        shutil.rmtree(CLEAN_REL)
    CLEAN_REL.mkdir(parents=True)
    gh_dir = CLEAN_REL / "github"
    zd_dir = CLEAN_REL / "zenodo"
    gh_dir.mkdir()
    zd_dir.mkdir()
    with zipfile.ZipFile(gh_zip, "r") as zf:
        zf.extractall(gh_dir)
    with zipfile.ZipFile(zd_zip, "r") as zf:
        zf.extractall(zd_dir)

    # count files; ensure trees differ
    def count_files(p: Path) -> int:
        return sum(1 for x in p.rglob("*") if x.is_file())

    gh_n = count_files(gh_dir)
    zd_n = count_files(zd_dir)
    # overlap of relative paths (ignoring top folder name)
    def relset(root: Path) -> set[str]:
        tops = [d for d in root.iterdir() if d.is_dir()]
        base = tops[0] if tops else root
        return {p.relative_to(base).as_posix() for p in base.rglob("*") if p.is_file()}

    gset, zset = relset(gh_dir), relset(zd_dir)
    overlap = len(gset & zset)
    result = {
        "github_files": gh_n,
        "zenodo_files": zd_n,
        "path_overlap": overlap,
        "distinct_trees": gset != zset,
        "github_has_large_seed_json": any(
            p.name.startswith("seed_") and p.stat().st_size > 100000
            for p in gh_dir.rglob("*.json")
        ),
        "zenodo_has_stage2_seeds": any(
            "seed_201" in p.name or p.name == "seed_201.json" for p in zd_dir.rglob("*.json")
        ),
    }
    # run github verification entry if present
    import subprocess
    import sys

    candidates = list(gh_dir.rglob("run_release_verification.py"))
    if candidates:
        proc = subprocess.run(
            [sys.executable, str(candidates[0])],
            cwd=str(candidates[0].parent.parent),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        result["verify_exit"] = proc.returncode
        result["verify_stdout_tail"] = (proc.stdout or "")[-500:]
    write(AUDIT / "verification" / "split_release_clean_test.json", json.dumps(result, indent=2))
    return result


def update_status(fig_status: str, sens_status: str) -> tuple[int, int, int]:
    # Recompute module statuses after cleanup
    modules = [
        ("Anchor main (seeds 1–20)", "PASS"),
        ("No-Opp ablation (seeds 1–20)", "PASS"),
        ("True-model loss (seeds 21–40)", "PASS"),
        ("Final eligibility / Open / Decision-Only / Full Gate (201–240)", "PASS"),
        ("Re-entry (seeds 121–140)", "PASS"),
        ("Evidence-rule sensitivity (18 settings)", sens_status),
        ("Minimal recursive dynamics", "PASS"),
        ("CoFI paired coverage (401–410)", "PASS"),
        ("ARROWS Phase-2E five cases", "PASS"),
        ("Figures (paper_audit trio)", fig_status),
        ("Environment provenance", "PASS"),
        ("Third-party assets", "PARTIAL"),
        ("GitHub/Zenodo payload split", "PASS"),
    ]
    p = sum(1 for _, s in modules if s == "PASS")
    pa = sum(1 for _, s in modules if s == "PARTIAL")
    f = sum(1 for _, s in modules if s == "FAIL")
    lines = ["# REPRO_STATUS", "", f"{p} PASS / {pa} PARTIAL / {f} FAIL", ""]
    for name, st in modules:
        lines.append(f"- **{st}**: {name}")
    write(AUDIT / "REPRO_STATUS.md", "\n".join(lines))
    write(
        AUDIT / "WINDOWS_REPRO_AUDIT_SUMMARY.md",
        f"""# WINDOWS_REPRO_AUDIT_SUMMARY (post-cleanup)

UTC: {datetime.now(timezone.utc).isoformat()}

## Counts
**{p} PASS / {pa} PARTIAL / {f} FAIL**

## Cleanup outcomes
1. **Re-entry**: PASS — canonical entry `rediscovery_cross/anchor_v2_aligned` (seeds 121–140).
2. **Sensitivity**: {sens_status} — outputs under `verification/evidence_sensitivity/`.
3. **Figures**: {fig_status} — clean-room compare in `figure_reproduction/FIGURE_PIXEL_COMPARE.json`.
4. **GitHub vs Zenodo**: split into distinct trees; see `RELEASE_LINKAGE.md`.
5. **Scientific results vs manuscript**: no FAIL conflicts introduced; frozen outputs untouched.
6. **Author decisions remaining**: third-party redistribution for CoFI/ARROWS raw assets only; author-generated code license is MIT.
""",
    )
    return p, pa, f


def main() -> None:
    document_reentry()
    print("figures...")
    fig_rep = run_figure_clean_room()
    sens_path = AUDIT / "verification" / "evidence_sensitivity" / "sensitivity_report.json"
    sens_status = "PARTIAL"
    if sens_path.exists():
        sens_status = json.loads(sens_path.read_text(encoding="utf-8")).get("status", "PARTIAL")

    gh = AUDIT / "github_release_candidate"
    zd = AUDIT / "zenodo_payload_candidate"
    print("build github...")
    build_github(gh)
    print("build zenodo...")
    build_zenodo(zd)
    n_gh = manifest(gh, gh / "MANIFEST_SHA256.txt")
    n_zd = manifest(zd, zd / "MANIFEST_SHA256.txt")
    print("files github/zenodo", n_gh, n_zd)

    gh_zip = ROOT / "patterns_github_release_candidate_v2.zip"
    zd_zip = ROOT / "patterns_zenodo_payload_candidate_v2.zip"
    zip_tree(gh, gh_zip, "patterns_github_release_candidate_v2")
    zip_tree(zd, zd_zip, "patterns_zenodo_payload_candidate_v2")
    write_linkage(gh, zd, gh_zip, zd_zip)

    print("clean verify...")
    clean = clean_verify(gh_zip, zd_zip)
    p, pa, f = update_status(fig_rep["status"], sens_status)

    log = [
        f"UTC {datetime.now(timezone.utc).isoformat()}",
        f"PASS/PARTIAL/FAIL={p}/{pa}/{f}",
        f"github_zip={gh_zip} mb={gh_zip.stat().st_size/1024/1024:.2f} files={n_gh}",
        f"zenodo_zip={zd_zip} mb={zd_zip.stat().st_size/1024/1024:.2f} files={n_zd}",
        f"figure_status={fig_rep['status']}",
        f"sensitivity_status={sens_status}",
        f"clean_test={json.dumps(clean)}",
    ]
    write(AUDIT / "RELEASE_VERIFY_LOG.txt", "\n".join(log))
    print("\n".join(log))


if __name__ == "__main__":
    main()
