#!/usr/bin/env python3
"""Dry-run gate for Anchor v2 aligned recoverability."""
from __future__ import annotations

import json
import sys
from pathlib import Path

AV2_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(AV2_ROOT.parent.parent))

from rediscovery_cross.anchor_v2_aligned.analysis import (  # noqa: E402
    load_av2_config,
    paired_pre_first_fi_identical,
    run_anchor_v2_condition,
    verify_reentry_uses_ordinary_criterion,
)
from pilot_fi_anchor.loop import run_seed  # noqa: E402
from pilot_fi_anchor.config import FALSE_FAMILIES, FAMILY_ORDER  # noqa: E402


def main() -> int:
    cfg = load_av2_config()
    seeds = cfg["experiment"]["dry_run_seeds"]
    rows = []
    all_pass = True

    for seed in seeds:
        off0 = run_seed(seed, do_perturb=False, rounds=25, rediscovery_mode="off")
        off1 = run_seed(seed, do_perturb=False, rounds=25, rediscovery_mode="off")
        off_repro = json.dumps(off0, sort_keys=True) == json.dumps(off1, sort_keys=True)

        pre = paired_pre_first_fi_identical(seed)
        on = run_anchor_v2_condition(seed, rediscovery_mode="v2_on", do_perturb=False)
        reentry = verify_reentry_uses_ordinary_criterion(on["record"])

        # OFF absorbing: once dead, stays dead
        off_rec = run_seed(seed, do_perturb=False, rounds=25, rediscovery_mode="off")
        native = off_rec["arms"]["native"]
        absorbing_ok = True
        for h in FALSE_FAMILIES:
            t_elim = native["final"]["t_elim"][h]
            if t_elim is None:
                continue
            traj = [row[h]["alive"] for row in native["rounds"]]
            if any(traj[t] for t in range(t_elim + 1, len(traj))):
                absorbing_ok = False

        # No v1 hypothetical gate in v2
        mode_ok = on["record"]["arms"]["native"]["final"]["rediscovery_mode"] == "v2_on"

        row = {
            "seed": seed,
            "off_reproduces": off_repro,
            "pre_fi_equivalence": pre["pass"],
            "first_fi_matched": pre["first_fi_matched"],
            "reentry_criterion_ok": reentry["pass"],
            "off_absorbing": absorbing_ok,
            "v2_mode": mode_ok,
            "n_reentries": reentry["n_reentries"],
            "pass": all(
                [off_repro, pre["pass"], reentry["pass"], absorbing_ok, mode_ok]
            ),
        }
        rows.append(row)
        all_pass = all_pass and row["pass"]

    out_dir = AV2_ROOT / "outputs" / "dry_run"
    out_dir.mkdir(parents=True, exist_ok=True)
    report = {"all_pass": all_pass, "seeds": rows}
    (out_dir / "dry_run_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
