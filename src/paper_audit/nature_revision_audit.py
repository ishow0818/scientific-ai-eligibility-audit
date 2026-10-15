"""Read-only, post-hoc manuscript audit of already saved trajectories.

This script does not refit models, draw new proposals, or alter any registered
endpoint. Its outputs are descriptive sensitivity checks, not confirmatory data.
"""

from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "paper_audit" / "outputs"
ANCHOR = ROOT / "outputs" / "pilot_fi_anchor"
TRUTH_LOSS = ROOT / "outputs" / "pilot_truth_loss_v2"
CAMELS = ROOT / "SBI" / "real_camels_identifiability_micro"
G6 = CAMELS / "truth_grounded" / "extension_g6" / "outputs"
HIGHK = CAMELS / "phase_a_highk" / "outputs" / "he_hi_calibration.json"
PARAMS = ("Omega_m", "sigma_8", "A_SN1", "A_AGN1", "A_SN2", "A_AGN2")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def anchor_audit() -> dict:
    with (ANCHOR / "summary_events.csv").open(newline="", encoding="utf-8") as f:
        events = list(csv.DictReader(f))
    per_seed = {
        seed: read_json(ANCHOR / f"seed_{seed:02d}.json")["arms"]["native"]["rounds"]
        for seed in range(1, 21)
    }
    rows = []
    for event in events:
        seed = int(event["seed"])
        family = event["family"]
        t_elim = int(event["t_elim"])
        rounds = per_seed[seed]
        assert int(rounds[t_elim]["t"]) == t_elim
        assert not rounds[t_elim][family]["excluded"]
        violated = bool(rounds[t_elim][family]["violated"])
        first_violation = next(
            (int(r["t"]) for r in rounds if r[family]["violated"]), None
        )
        rows.append(
            {
                "seed": seed,
                "family": family,
                "t_elim": t_elim,
                "first_violation": first_violation,
                "violation_at_elimination": violated,
                "neutral_retained_at_elimination": event["alive_Neu_at_elim"] == "True",
                "t_excl_two_round": int(event["t_excl_N"])
                if event["t_excl_N"] else None,
                "censored": event["censored_N"] == "True",
            }
        )
    assert len(rows) == 78
    clean = [r for r in rows if not r["violation_at_elimination"]]
    first_hit = [r for r in rows if r["violation_at_elimination"]]
    assert len(clean) == 26 and len(first_hit) == 52
    assert all(r["neutral_retained_at_elimination"] for r in clean)
    assert all(r["first_violation"] == r["t_elim"] for r in first_hit)

    endpoints = read_json(TRUTH_LOSS / "endpoints.json")
    truth_rows = []
    for e in endpoints["F1_per_seed"]:
        seed = int(e["seed"])
        if not (21 <= seed <= 40 and e["f1"]):
            continue
        record = read_json(TRUTH_LOSS / f"seed_{seed:03d}.json")
        t_elim = int(e["t_elim"])
        truth_rows.append(
            {
                "seed": seed,
                "t_elim": t_elim,
                "violation_at_elimination": bool(
                    record["arms"]["native"]["rounds"][t_elim]["hump"]["violated"]
                ),
            }
        )
    assert len(truth_rows) == 4
    return {
        "status": "post_hoc_descriptive_only",
        "primary_endpoint_unchanged": True,
        "events_total": len(rows),
        "first_chi2_violation_at_elimination": len(first_hit),
        "no_chi2_violation_at_elimination": len(clean),
        "no_violation_seed_count": len({r["seed"] for r in clean}),
        "no_violation_neutral_retained": sum(
            r["neutral_retained_at_elimination"] for r in clean
        ),
        "truth_loss_confirmatory_seed_range": [21, 40],
        "truth_loss_f1_rows": truth_rows,
        "rows": rows,
    }


def normalize(raw: np.ndarray, bounds: dict) -> np.ndarray:
    lo = np.array([bounds[k]["min"] for k in PARAMS], dtype=float)
    hi = np.array([bounds[k]["max"] for k in PARAMS], dtype=float)
    return (raw - lo) / (hi - lo)


def camels_audit() -> dict:
    with (G6 / "post_hoc_trajectory_audit_events.csv").open(
        newline="", encoding="utf-8"
    ) as f:
        events = list(csv.DictReader(f))
    catalog = pd.read_parquet(CAMELS.parent / "real_camels_data" / "lh_features_real.parquet")
    highk = read_json(HIGHK)
    r_high = float(highk["tau"])
    rows = []
    for event in events:
        seed = int(event["seed"])
        sim_idx = int(event["sim_idx"])
        loss = int(event["g_loss"])
        base = G6 / f"seed_{seed}"
        bounds = read_json(G6.parent / "splits" / f"seed_{seed}" / "catalog_bounds.json")
        radius = float(read_json(base / "membership_rule.json")["radius_r"])
        member_raw = catalog.loc[catalog["sim_idx"] == sim_idx, PARAMS].to_numpy(dtype=float)
        assert member_raw.shape == (1, 6)
        member_norm = normalize(member_raw, bounds)[0]
        counts = {}
        distances = {}
        for arm in ("native", "neutral"):
            arm_counts = []
            arm_min = []
            for generation in range(7):
                proposals = np.load(
                    base / f"{arm}_run" / f"representation_proposals_g{generation}.npy"
                )
                d = np.linalg.norm(normalize(proposals, bounds) - member_norm, axis=1)
                arm_counts.append(int(np.count_nonzero(d <= radius)))
                arm_min.append(float(d.min()))
            counts[arm] = arm_counts
            distances[arm] = arm_min
        assert counts["native"][loss] == 0
        assert counts["native"][loss - 1] > 0
        assert counts["neutral"][loss] > 0
        rows.append(
            {
                "seed": seed,
                "sim_idx": sim_idx,
                "loss_generation": loss,
                "first_reentry_generation": int(event["first_reentry_g"]),
                "radius": radius,
                "native_counts_within_radius_by_generation": counts["native"],
                "neutral_counts_within_radius_by_generation": counts["neutral"],
                "native_min_distance_by_generation": distances["native"],
                "neutral_min_distance_by_generation": distances["neutral"],
                "highk_D2": float(highk["d2_lh"][sim_idx]),
                "highk_pass": bool(highk["compatible_mask"][sim_idx]),
                "highk_margin": r_high - float(highk["d2_lh"][sim_idx]),
            }
        )
    assert len(rows) == 4
    return {
        "status": "post_hoc_descriptive_only",
        "frozen_posterior_redraw_performed": False,
        "reason": "Only saved proposal arrays, not posterior checkpoints, are present.",
        "events_total": len(rows),
        "unique_sim_idx": sorted({row["sim_idx"] for row in rows}),
        "identity_counts": dict(Counter(row["sim_idx"] for row in rows)),
        "highk_global_admissible": int(highk["H_E_hi_size"]),
        "highk_global_total": len(highk["compatible_mask"]),
        "highk_threshold": r_high,
        "rows": rows,
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    result = {
        "analysis_status": "read_only_offline_post_hoc",
        "anchor": anchor_audit(),
        "camels": camels_audit(),
    }
    path = OUT / "nature_revision_audit.json"
    path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(path)
    print(
        "Anchor:", result["anchor"]["no_chi2_violation_at_elimination"],
        "clean /", result["anchor"]["events_total"], "events"
    )
    for row in result["camels"]["rows"]:
        print(
            "CAMELS:", row["seed"], row["sim_idx"],
            "counts", row["native_counts_within_radius_by_generation"],
            "highk margin", round(row["highk_margin"], 6),
        )


if __name__ == "__main__":
    main()
