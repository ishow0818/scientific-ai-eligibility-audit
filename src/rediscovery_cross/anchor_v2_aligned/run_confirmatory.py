#!/usr/bin/env python3
"""Anchor v2 CAMELS-aligned confirmatory runner — seeds 121–140."""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

AV2_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(AV2_ROOT.parent.parent))

from rediscovery_cross.anchor_v2_aligned.analysis import (  # noqa: E402
    load_av2_config,
    paired_pre_first_fi_identical,
    run_anchor_v2_condition,
    verify_reentry_uses_ordinary_criterion,
)

AV2_OUTPUT = AV2_ROOT / "outputs" / "confirmatory"


def assert_seed_policy(seed: int, cfg: dict) -> None:
    excluded = set()
    for rng in cfg["experiment"]["excluded_seed_ranges"].values():
        if isinstance(rng, list) and len(rng) == 2:
            excluded.update(range(int(rng[0]), int(rng[1]) + 1))
    if seed in excluded:
        raise PermissionError(f"seed {seed} in excluded range")


def run_seed_pair(seed: int, *, skip_if_done: bool = True) -> dict:
    assert_seed_policy(seed, load_av2_config())
    AV2_OUTPUT.mkdir(parents=True, exist_ok=True)
    off_path = AV2_OUTPUT / f"seed_{seed}_off.json"
    on_path = AV2_OUTPUT / f"seed_{seed}_v2_on.json"

    if skip_if_done and off_path.is_file() and on_path.is_file():
        return {"seed": seed, "skipped": True}

    pre = paired_pre_first_fi_identical(seed)
    off = run_anchor_v2_condition(seed, rediscovery_mode="off", do_perturb=False)
    on = run_anchor_v2_condition(seed, rediscovery_mode="v2_on", do_perturb=False)
    reentry = verify_reentry_uses_ordinary_criterion(on["record"])

    payload_off = {k: v for k, v in off.items() if k != "record"}
    payload_on = {k: v for k, v in on.items() if k != "record"}
    payload_off["pre_fi_check"] = pre
    payload_on["pre_fi_check"] = pre
    payload_on["reentry_criterion_audit"] = reentry

    off_path.write_text(json.dumps(payload_off, indent=2), encoding="utf-8")
    on_path.write_text(json.dumps(payload_on, indent=2), encoding="utf-8")
    return {
        "seed": seed,
        "pre_fi_pass": pre["pass"],
        "n_off_events": len(off["events"]),
        "n_on_events": len(on["events"]),
        "n_reentries": reentry["n_reentries"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--skip-analysis", action="store_true")
    args = parser.parse_args()

    cfg = load_av2_config()
    dr = AV2_ROOT / "outputs" / "dry_run" / "dry_run_report.json"
    if not dr.is_file() or not json.loads(dr.read_text()).get("all_pass"):
        print("Dry-run gate failed; run run_dry_run.py first", file=sys.stderr)
        return 1

    seeds = cfg["experiment"]["confirmatory_seeds"]
    if args.seed is not None:
        seeds = [args.seed]

    t0 = time.perf_counter()
    rows = []
    for seed in seeds:
        print(f"Anchor v2 seed {seed}...")
        rows.append(run_seed_pair(seed))

    runtime = time.perf_counter() - t0
    if not args.skip_analysis:
        summary = analyze_confirmatory_from_saved(AV2_OUTPUT, cfg)
        summary["runtime_s"] = runtime
        summary["run_rows"] = rows
        out_path = AV2_OUTPUT / "confirmatory_summary.json"
        # Strip full event lists from summary for cleaner file; save separately
        events_off = summary.pop("off_events", [])
        events_on = summary.pop("on_events", [])
        out_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        (AV2_OUTPUT / "event_level_off.json").write_text(
            json.dumps(events_off, indent=2), encoding="utf-8"
        )
        (AV2_OUTPUT / "event_level_on_v2.json").write_text(
            json.dumps(events_on, indent=2), encoding="utf-8"
        )
        (AV2_OUTPUT / "paired_event_table.json").write_text(
            json.dumps(summary.get("primary", {}).get("paired_event_table", []), indent=2),
            encoding="utf-8",
        )
        print(f"Wrote {out_path}")

    print(json.dumps({"runtime_s": runtime, "n_seeds": len(rows)}, indent=2))
    return 0


def analyze_confirmatory_from_saved(output_root: Path, cfg: dict) -> dict:
    """Aggregate from per-seed JSON without re-running simulations."""
    import json as _json

    from rediscovery_cross.rediscovery import primary_persistence_summary
    from rediscovery_cross.anchor_v2_aligned.analysis import (
        mcnemar_persistent,
        trajectory_divergence_paired,
    )

    pre_loss_rows = []
    off_events = []
    on_events = []
    reentry_checks = []

    for seed in cfg["experiment"]["confirmatory_seeds"]:
        off_path = output_root / f"seed_{seed}_off.json"
        on_path = output_root / f"seed_{seed}_v2_on.json"
        off_data = _json.loads(off_path.read_text(encoding="utf-8"))
        on_data = _json.loads(on_path.read_text(encoding="utf-8"))
        pre_loss_rows.append(off_data.get("pre_fi_check", {}))
        off_events.extend(off_data.get("events", []))
        on_events.extend(on_data.get("events", []))
        reentry_checks.append(on_data.get("reentry_criterion_audit", {}))

    off_sum = primary_persistence_summary(off_events)
    on_sum = primary_persistence_summary(on_events)
    traj = trajectory_divergence_paired(off_events, on_events)

    return {
        "experiment": cfg["experiment"]["name"],
        "version": cfg["experiment"]["version"],
        "n_seeds": len(cfg["experiment"]["confirmatory_seeds"]),
        "pre_loss_equivalence": {
            "n_seeds": len(pre_loss_rows),
            "n_pass": sum(1 for r in pre_loss_rows if r.get("pass")),
            "rows": pre_loss_rows,
        },
        "reentry_criterion_audit": {
            "n_seeds": len(reentry_checks),
            "n_pass": sum(1 for r in reentry_checks if r.get("pass")),
            "total_reentries": sum(r.get("n_reentries", 0) for r in reentry_checks),
        },
        "off": off_sum,
        "on_v2": on_sum,
        "delta_p_persistent": (
            (off_sum["p_persistent_loss"] or 0) - (on_sum["p_persistent_loss"] or 0)
            if off_sum["n_unsupported_events"] and on_sum["n_unsupported_events"]
            else None
        ),
        "primary": traj,
        "mcnemar": mcnemar_persistent(off_events, on_events),
        "off_events": off_events,
        "on_events": on_events,
    }


if __name__ == "__main__":
    sys.exit(main())
