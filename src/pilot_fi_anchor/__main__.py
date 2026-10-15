"""CLI entry point.

    python -m pilot_fi_anchor --dry                       # code self-check: 1 seed x 4 rounds, no files
    python -m pilot_fi_anchor --calibrate                 # evidence criterion sanity check
    python -m pilot_fi_anchor --seeds 1..20               # formal pilot (20 seeds x 25 rounds)
    python -m pilot_fi_anchor --seeds 1..20 --no-perturb  # skip perturbation branches (faster)
"""

from __future__ import annotations

import argparse
import os
import time
from typing import Any

from .config import PilotConfig, R, SEEDS
from .loop import run_seed
from .recorder import seed_record, write_seed


def _parse_seeds(spec: str) -> list[int]:
    if ".." in spec:
        lo, hi = spec.split("..")
        return list(range(int(lo), int(hi) + 1))
    if "-" in spec:
        lo, hi = spec.split("-")
        return list(range(int(lo), int(hi) + 1))
    return [int(s) for s in spec.split(",") if s.strip()]


def _print_dry(rec: dict[str, Any]) -> None:
    for kind in ("native", "neutral"):
        rows = rec["arms"][kind]["rounds"]
        print(f"--- {kind} ---")
        for row in rows:
            t = row["t"]
            line = [f"t={t}", f"n={row['n_arm']}", f"inc={row['incumbent']}"]
            for h in ("hump", "affine", "pow", "expsat", "quad"):
                d = row[h]
                line.append(
                    f"{h[:4]}:w={d['w_surv']:.3f}/a={int(d['alive'])}"
                    f"/v={int(d['violated'])}/x={int(d['excluded'])}"
                )
            print("  " + "  ".join(line))
    n_pert = len(rec["perturb"])
    print(f"perturbation records: {n_pert}")


def main() -> None:
    p = argparse.ArgumentParser(description="FI anchor closed-loop pilot")
    p.add_argument("--seeds", default=f"1..{SEEDS[-1]}")
    p.add_argument("--outdir", default=None)
    p.add_argument("--no-perturb", action="store_true")
    p.add_argument("--no-analysis", action="store_true")
    p.add_argument("--dry", action="store_true",
                   help="1 seed x 4 rounds, console only, no files written")
    p.add_argument("--calibrate", action="store_true",
                   help="run evidence criterion calibration (no pilot)")
    args = p.parse_args()

    cfg = PilotConfig()

    if args.calibrate:
        import json

        from .evidence_calibration import run_calibration_batch

        result = run_calibration_batch()
        slim = {k: v for k, v in result.items() if k not in ("per_seed",)}
        print(json.dumps(slim, indent=2))
        if not result["ok"]:
            raise SystemExit(1)
        return

    if args.dry:
        rec = run_seed(1, do_perturb=True, rounds=4)
        _print_dry(rec)
        return

    seeds = _parse_seeds(args.seeds)
    outdir = args.outdir or cfg.results_dir
    t0 = time.perf_counter()
    for s in seeds:
        rec = run_seed(s, do_perturb=not args.no_perturb, rounds=R)
        write_seed(seed_record(s, rec, cfg), os.path.join(outdir, f"seed_{s:02d}.json"))
        print(f"seed {s:2d} done")
    runtime = time.perf_counter() - t0
    print(f"runtime: {runtime:.1f} s for {len(seeds)} seeds")

    if not args.no_analysis:
        from .analysis import analyze

        analyze(outdir, seeds, runtime_s=runtime)


if __name__ == "__main__":
    main()
