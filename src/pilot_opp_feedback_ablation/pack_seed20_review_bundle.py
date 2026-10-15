#!/usr/bin/env python3
"""Pack seed-20 causal-chain review bundle + formal ablation context."""
from __future__ import annotations

import json
import zipfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "pilot_opp_feedback_ablation"
ANCHOR = ROOT / "pilot_fi_anchor"
FORMAL = ROOT / "outputs" / "pilot_opp_feedback_ablation_formal_v2"
CHAIN = FORMAL / "seed20_causal_chain"
OUT = FORMAL / f"seed20_causal_review_bundle_{datetime.now().strftime('%Y%m%d_%H%M')}.zip"

README = """# Seed-20 Opportunity-Feedback Causal Review Bundle

## Contents
1. `pilot_fi_anchor/` — native loop/config + direct deps (allocation, support, prune, evidence order)
2. `pilot_opp_feedback_ablation/` — full ablation package (proposer-weight intervention only)
3. `tests/test_isolation.py` — shortcut copy of CRN / isolation tests
4. `formal/seed_20_paired.json` — raw paired trajectory
5. `seed20_causal_chain/` — causal-chain report, paired round CSV, evidence JSON
6. `formal/` — formal_report.md, verdict.json, paired summary CSVs (20-seed context)

## Suggested checks
- Read `seed20_causal_chain/seed20_causal_chain_report.md` first.
- Cross-check t=2 fork / t=3 elim in `seed_20_paired.json` vs CSV.
- Keep `formal/formal_report.md` in view so seed 20 is not over-generalized.
"""

ANCHOR_FILES = [
    "loop.py",
    "config.py",
    "rng.py",
    "fitting.py",
    "mechanisms.py",
    "world.py",
    "evidence_calibration.py",
    "__init__.py",
]

FORMAL_ROOT_FILES = [
    "formal_report.md",
    "verdict.json",
    "formal_aggregate.json",
    "formal_seed_summary.csv",
    "formal_paired_timing.csv",
    "formal_truth_loss.csv",
    "formal_exit_events.csv",
    "formal_native_reproduction.csv",
    "seed_20_paired.json",
]


def add_tree(zf: zipfile.ZipFile, src: Path, arc_prefix: str) -> int:
    n = 0
    for p in sorted(src.rglob("*")):
        if not p.is_file():
            continue
        if "__pycache__" in p.parts or p.suffix == ".pyc":
            continue
        if p.resolve() == OUT.resolve():
            continue
        # skip large unrelated nested bundles if any
        if p.suffix == ".zip":
            continue
        rel = p.relative_to(src).as_posix()
        zf.write(p, f"{arc_prefix}/{rel}")
        n += 1
    return n


def main() -> int:
    missing = []
    for name in ANCHOR_FILES:
        if not (ANCHOR / name).is_file():
            missing.append(str(ANCHOR / name))
    if not (PKG / "tests" / "test_isolation.py").is_file():
        missing.append(str(PKG / "tests" / "test_isolation.py"))
    if not CHAIN.is_dir():
        missing.append(str(CHAIN))
    for name in FORMAL_ROOT_FILES:
        if not (FORMAL / name).is_file():
            missing.append(str(FORMAL / name))
    if missing:
        raise SystemExit(f"missing required files: {missing}")

    manifest = {
        "created": datetime.now().isoformat(timespec="seconds"),
        "bundle": OUT.name,
        "purpose": "Human review of seed-20 causal instance + 20-seed formal context",
        "includes": [
            "pilot_fi_anchor core sources",
            "pilot_opp_feedback_ablation full package",
            "tests/test_isolation.py",
            "seed_20_paired.json",
            "seed20_causal_chain/",
            "formal_report.md + verdict + paired CSVs",
        ],
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(OUT, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("README.md", README)
        zf.writestr("MANIFEST.json", json.dumps(manifest, indent=2, ensure_ascii=False))
        for name in ANCHOR_FILES:
            zf.write(ANCHOR / name, f"pilot_fi_anchor/{name}")
        n_pkg = add_tree(zf, PKG, "pilot_opp_feedback_ablation")
        zf.write(PKG / "tests" / "test_isolation.py", "tests/test_isolation.py")
        for name in FORMAL_ROOT_FILES:
            zf.write(FORMAL / name, f"formal/{name}")
        n_chain = add_tree(zf, CHAIN, "seed20_causal_chain")

    print(OUT)
    print(f"size_MB={OUT.stat().st_size / 1024 / 1024:.2f}")
    print(f"ablation_files≈{n_pkg} chain_files≈{n_chain}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
