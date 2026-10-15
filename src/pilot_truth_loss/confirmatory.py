"""Phase-2 confirmatory runner — imports Anchor loop only; no fork."""

from __future__ import annotations

import json
import os
import time
from typing import Any

from pilot_fi_anchor.loop import run_seed
from pilot_fi_anchor.recorder import _builtin

from .config import (
    CONFIRMATORY_SEEDS,
    V2_DRY_RUN_RESULTS_DIR,
    V2_RESULTS_DIR,
    TruthLossConfig,
    assert_dry_run_seeds,
    assert_v2_confirmatory_seeds_exact,
)
from .gates import evaluate_confirmatory
from .metrics import compute_truth_loss_endpoints


def _run_seeds(
    seed_list: list[int],
    *,
    do_perturb: bool,
    cfg: TruthLossConfig,
) -> tuple[list[dict[str, Any]], float]:
    records: list[dict[str, Any]] = []
    t0 = time.perf_counter()
    for seed in seed_list:
        rec = run_seed(seed, do_perturb=do_perturb)
        record = {
            "seed": seed,
            "version": cfg.version,
            "anchor_version": cfg.anchor_version,
            "truth_family": cfg.truth_family,
            "competitor_family": cfg.competitor_family,
            **rec,
        }
        records.append(record)
    return records, time.perf_counter() - t0


def run_confirmatory(
    seeds: tuple[int, ...] | None = None,
    *,
    do_perturb: bool = True,
    outdir: str | None = None,
) -> dict[str, Any]:
    """Run formal Failure Mode v2 confirmatory (exactly seeds 21–40)."""
    cfg = TruthLossConfig()
    seed_list = list(seeds if seeds is not None else CONFIRMATORY_SEEDS)
    assert_v2_confirmatory_seeds_exact(seed_list)
    out = outdir or cfg.results_dir
    if os.path.normpath(out) == os.path.normpath(V2_DRY_RUN_RESULTS_DIR):
        raise ValueError(
            f"formal confirmatory cannot write to dry-run directory {V2_DRY_RUN_RESULTS_DIR}"
        )
    os.makedirs(out, exist_ok=True)

    records, runtime_s = _run_seeds(seed_list, do_perturb=do_perturb, cfg=cfg)
    for record in records:
        path = os.path.join(out, f"seed_{record['seed']:03d}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(_builtin(record), f, separators=(",", ":"))

    endpoints = compute_truth_loss_endpoints(records)
    endpoints["runtime_s"] = runtime_s
    gates = evaluate_confirmatory(endpoints)

    endpoints_path = os.path.join(out, "endpoints.json")
    gates_path = os.path.join(out, "gates.json")
    with open(endpoints_path, "w", encoding="utf-8") as f:
        json.dump(_builtin(endpoints), f, indent=2)
    with open(gates_path, "w", encoding="utf-8") as f:
        json.dump(_builtin(gates), f, indent=2)

    return {
        "n_seeds": len(seed_list),
        "runtime_s": runtime_s,
        "outdir": out,
        "endpoints": endpoints,
        "gates": gates,
        "records": records,
        "dry_run": False,
    }


def run_dry_run(
    seeds: tuple[int, ...],
    *,
    do_perturb: bool = True,
    outdir: str | None = None,
) -> dict[str, Any]:
    """Dev dry-run: no formal gates, non-formal output directory only."""
    cfg = TruthLossConfig()
    seed_list = list(seeds)
    assert_dry_run_seeds(seed_list)
    out = outdir or cfg.dry_run_results_dir
    if os.path.normpath(out) == os.path.normpath(V2_RESULTS_DIR):
        raise ValueError(
            f"dry-run cannot write to formal confirmatory directory {V2_RESULTS_DIR}"
        )
    os.makedirs(out, exist_ok=True)

    records, runtime_s = _run_seeds(seed_list, do_perturb=do_perturb, cfg=cfg)
    for record in records:
        path = os.path.join(out, f"seed_{record['seed']:03d}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(_builtin(record), f, separators=(",", ":"))

    endpoints = compute_truth_loss_endpoints(records)
    endpoints["runtime_s"] = runtime_s
    summary = {
        "dry_run": True,
        "n_seeds": len(seed_list),
        "runtime_s": runtime_s,
        "outdir": out,
        "endpoints": {
            k: v
            for k, v in endpoints.items()
            if k not in ("HO1_per_seed", "F1_per_seed", "F2_v2_per_seed", "F3_per_seed")
        },
        "note": "dry-run: no G1–G4 gate evaluation; not for confirmatory statistics",
    }
    summary_path = os.path.join(out, "dry_run_summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(_builtin(summary), f, indent=2)

    return {
        **summary,
        "records": records,
    }
