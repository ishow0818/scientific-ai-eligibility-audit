"""Aggregation: load seed records -> endpoints -> gates -> summary CSVs."""

from __future__ import annotations

import csv
import json
import os
from typing import Any

from .config import PilotConfig
from .gates import evaluate, format_table, matching_check
from .metrics import compute_endpoints
from .recorder import read_seed


def load_records(outdir: str, seeds: list[int]) -> list[dict[str, Any]]:
    return [read_seed(os.path.join(outdir, f"seed_{s:02d}.json")) for s in seeds]


def _write_csv(path: str, rows: list[dict[str, Any]]) -> None:
    if not rows:
        with open(path, "w", newline="", encoding="utf-8") as f:
            f.write("")
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def analyze(
    outdir: str, seeds: list[int], runtime_s: float | None = None
) -> dict[str, Any]:
    cfg = PilotConfig()
    records = load_records(outdir, seeds)
    endpoints, focals, events, summaries = compute_endpoints(records, cfg, runtime_s)
    matching = matching_check(records)
    endpoints["matching_ok"] = matching["ok"]
    endpoints["matching_detail"] = matching["detail"]
    gates = evaluate(endpoints, matching)

    os.makedirs(outdir, exist_ok=True)
    with open(os.path.join(outdir, "endpoints.json"), "w", encoding="utf-8") as f:
        json.dump(endpoints, f, indent=2)
    with open(os.path.join(outdir, "gates.json"), "w", encoding="utf-8") as f:
        json.dump(gates, f, indent=2)
    _write_csv(os.path.join(outdir, "summary_seeds.csv"), summaries)
    _write_csv(os.path.join(outdir, "summary_focal.csv"), focals)
    _write_csv(os.path.join(outdir, "summary_events.csv"), events)
    gain_rows = [
        {"arm_t": k, **v}
        for k, v in sorted(endpoints["gain_profile"].items())
    ]
    _write_csv(os.path.join(outdir, "summary_gain.csv"), gain_rows)
    gain_delta_rows = [
        {"delta": k, **v}
        for k, v in sorted(
            endpoints.get("gain_by_delta", {}).items(),
            key=lambda x: float(x[0]),
        )
    ]
    _write_csv(os.path.join(outdir, "summary_gain_by_delta.csv"), gain_delta_rows)

    print(format_table(gates))
    return gates
