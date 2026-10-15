"""CLI.

    python -m pilot_truth_loss --calibrate                 # pair calibration + CAL gates
    python -m pilot_truth_loss --seeds 21..40              # formal v2 confirmatory
    python -m pilot_truth_loss --dry-run --seeds 21        # dev sanity (no gates)
"""

from __future__ import annotations

import argparse
import json

from .confirmatory import run_confirmatory, run_dry_run
from .config import CONFIRMATORY_SEEDS, assert_v2_confirmatory_seeds_exact
from .gates import evaluate_calibration
from .pair_calibration import run_pair_calibration


def _parse_seeds(spec: str) -> tuple[int, ...]:
    if ".." in spec:
        lo, hi = spec.split("..")
        return tuple(range(int(lo), int(hi) + 1))
    if "-" in spec:
        lo, hi = spec.split("-")
        return tuple(range(int(lo), int(hi) + 1))
    return tuple(int(s) for s in spec.split(",") if s.strip())


def main() -> None:
    p = argparse.ArgumentParser(description="Truth-Loss Failure Mode extension (v2)")
    p.add_argument(
        "--calibrate",
        action="store_true",
        help="run phase-1 pair calibration (seeds 1–20; no confirmatory loop)",
    )
    p.add_argument(
        "--seeds",
        default=None,
        help="formal: must be exactly 21..40; dry-run: subset of fresh seeds (>=21)",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="dev sanity path: no G1–G4, non-formal output dir only",
    )
    p.add_argument(
        "--outdir",
        default=None,
        help="override output directory (dry-run cannot use formal v2 dir)",
    )
    p.add_argument(
        "--no-perturb",
        action="store_true",
        help="skip perturbation branches (faster dry-run)",
    )
    args = p.parse_args()

    if args.calibrate:
        cal = run_pair_calibration()
        gates = evaluate_calibration(cal)
        out = {
            "calibration": {k: v for k, v in cal.items() if k != "selection"},
            "selection_summary": {
                "chosen": cal["selection"]["chosen"],
                "reason": cal["selection"]["reason"],
                "ranking": {
                    h: {
                        "structural_ok": ev["structural_ok"],
                        "initial_gap_median": ev["initial_gap_median"],
                    }
                    for h, ev in cal["selection"]["candidates"].items()
                },
            },
            "gates": gates,
            "ready": cal.get("ready") and gates["summary"]["calibration_all_pass"],
        }
        print(json.dumps(out, indent=2))
        if not out["ready"]:
            raise SystemExit(1)
        return

    if args.seeds is None:
        p.print_help()
        print(
            f"\nFormal v2 confirmatory: --seeds {CONFIRMATORY_SEEDS[0]}..{CONFIRMATORY_SEEDS[-1]}"
        )
        print("Dev sanity: --dry-run --seeds 21")
        return

    if args.dry_run:
        result = run_dry_run(
            seeds=_parse_seeds(args.seeds),
            do_perturb=not args.no_perturb,
            outdir=args.outdir,
        )
        print(json.dumps({k: v for k, v in result.items() if k != "records"}, indent=2))
        return

    seeds = _parse_seeds(args.seeds)
    assert_v2_confirmatory_seeds_exact(seeds)
    result = run_confirmatory(
        seeds=seeds,
        do_perturb=not args.no_perturb,
        outdir=args.outdir,
    )
    slim = {
        "n_seeds": result["n_seeds"],
        "runtime_s": result["runtime_s"],
        "outdir": result["outdir"],
        "endpoints": {
            k: v
            for k, v in result["endpoints"].items()
            if k not in ("HO1_per_seed", "F1_per_seed", "F2_v2_per_seed", "F3_per_seed")
        },
        "gates": result["gates"],
    }
    print(json.dumps(slim, indent=2))
    if result["gates"]["summary"].get("killed"):
        raise SystemExit(2)
    if not result["gates"]["summary"]["pass_all"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
