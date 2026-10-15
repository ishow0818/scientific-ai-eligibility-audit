#!/usr/bin/env python3
"""Pack Opportunity-Feedback Ablation review bundle."""
from __future__ import annotations

import json
import zipfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "pilot_opp_feedback_ablation"
SMOKE = ROOT / "outputs" / "pilot_opp_feedback_ablation_smoke"
ANCHOR = ROOT / "pilot_fi_anchor"
OUT = SMOKE / f"opp_feedback_ablation_bundle_{datetime.now().strftime('%Y%m%d_%H%M')}.zip"

README = """# Opportunity-Feedback Ablation Bundle

## Contents
- `pilot_opp_feedback_ablation/` — full ablation package (code, tests, SOURCE_AUDIT, smoke runner)
- `pilot_fi_anchor/` — native sources involved in allocation (`loop.py` with `_allocate_native` / `w_override`, plus `config.py`, `rng.py`)
- `smoke/` — raw paired trajectories and reports from the 2-seed smoke

## Quick checks
1. Isolation: `python -m pilot_opp_feedback_ablation.tests.test_isolation` (from repo root with this tree laid out, or inspect tests in-place).
2. Native hook: search `loop.py` for `w_override` and `_allocate_native`.
3. Smoke: `smoke/smoke_report.md`, `smoke/seed_01_paired.json`, `smoke/seed_02_paired.json`.
"""


def add_tree(zf: zipfile.ZipFile, src: Path, arc_prefix: str, *, exclude_names: set[str] | None = None) -> int:
    exclude_names = exclude_names or set()
    n = 0
    for p in sorted(src.rglob("*")):
        if not p.is_file():
            continue
        if p.name in exclude_names:
            continue
        if "__pycache__" in p.parts or p.suffix == ".pyc":
            continue
        if p.resolve() == OUT.resolve():
            continue
        rel = p.relative_to(src).as_posix()
        zf.write(p, f"{arc_prefix}/{rel}")
        n += 1
    return n


def main() -> int:
    required = [
        PKG / "loop_ablation.py",
        PKG / "tests" / "test_isolation.py",
        PKG / "SOURCE_AUDIT.md",
        ANCHOR / "loop.py",
        SMOKE / "smoke_report.md",
        SMOKE / "seed_01_paired.json",
        SMOKE / "seed_02_paired.json",
    ]
    missing = [p for p in required if not p.is_file()]
    if missing:
        raise SystemExit(f"missing: {missing}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    manifest = {
        "created": datetime.now().isoformat(timespec="seconds"),
        "bundle": OUT.name,
        "includes": [
            "pilot_opp_feedback_ablation (full)",
            "tests/test_isolation.py (inside package)",
            "SOURCE_AUDIT.md",
            "smoke raw trajectories + report",
            "pilot_fi_anchor loop.py / config.py / rng.py (_allocate_native, w_override)",
        ],
    }
    with zipfile.ZipFile(OUT, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("README.md", README)
        zf.writestr("MANIFEST.json", json.dumps(manifest, indent=2, ensure_ascii=False))
        n_pkg = add_tree(
            zf,
            PKG,
            "pilot_opp_feedback_ablation",
            exclude_names={"pack_bundle.py"},
        )
        # Keep pack_bundle too for reproducibility
        zf.write(PKG / "pack_bundle.py", "pilot_opp_feedback_ablation/pack_bundle.py")
        n_pkg += 1
        for name in ("loop.py", "config.py", "rng.py"):
            zf.write(ANCHOR / name, f"pilot_fi_anchor/{name}")
        n_smoke = add_tree(
            zf,
            SMOKE,
            "smoke",
            exclude_names={OUT.name},
        )
        # Explicit top-level shortcuts requested by user
        zf.write(PKG / "tests" / "test_isolation.py", "tests/test_isolation.py")
        zf.write(PKG / "SOURCE_AUDIT.md", "SOURCE_AUDIT.md")

    print(OUT)
    print(f"size_MB={OUT.stat().st_size / 1024 / 1024:.2f}")
    print(f"package_files≈{n_pkg} smoke_files≈{n_smoke}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
