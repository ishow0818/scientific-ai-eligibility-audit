"""Matched-primary reanalysis for Anchor v2 confirmatory (no re-simulation)."""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from scipy.stats import binomtest

AV2_ROOT = Path(__file__).resolve().parent
CONFIRMATORY_DIR = AV2_ROOT / "outputs" / "confirmatory"


def event_identity_key(ev: dict[str, Any]) -> tuple[int, str, int]:
    """(seed, family, g_loss) — first unsupported FI identity."""
    return (int(ev["seed"]), str(ev["family"]), int(ev["g_loss"]))


def pair_key(ev: dict[str, Any]) -> tuple[int, str]:
    return (int(ev["seed"]), str(ev["family"]))


def load_event_lists(
    confirmatory_dir: Path | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    root = confirmatory_dir or CONFIRMATORY_DIR
    off_path = root / "event_level_off.json"
    on_path = root / "event_level_on_v2.json"
    if off_path.is_file() and on_path.is_file():
        off = json.loads(off_path.read_text(encoding="utf-8"))
        on = json.loads(on_path.read_text(encoding="utf-8"))
        return off, on
    off_events: list[dict] = []
    on_events: list[dict] = []
    for path in sorted(root.glob("seed_*_off.json")):
        off_events.extend(json.loads(path.read_text(encoding="utf-8")).get("events", []))
    for path in sorted(root.glob("seed_*_v2_on.json")):
        on_events.extend(json.loads(path.read_text(encoding="utf-8")).get("events", []))
    return off_events, on_events


def index_by_pair(events: list[dict[str, Any]]) -> dict[tuple[int, str], dict[str, Any]]:
    return {pair_key(e): e for e in events}


def index_by_identity(events: list[dict[str, Any]]) -> dict[tuple[int, str, int], dict[str, Any]]:
    return {event_identity_key(e): e for e in events}


def classify_event_sets(
    off_events: list[dict[str, Any]], on_events: list[dict[str, Any]]
) -> dict[str, Any]:
    off_by = index_by_pair(off_events)
    on_by = index_by_pair(on_events)
    off_ids = index_by_identity(off_events)
    on_ids = index_by_identity(on_events)

    all_pairs = set(off_by) | set(on_by)
    on_only: list[dict] = []
    off_only: list[dict] = []
    fi_identity_mismatch: list[dict] = []
    matched: list[dict] = []

    for key in sorted(all_pairs):
        o = off_by.get(key)
        n = on_by.get(key)
        if o is None and n is not None:
            on_only.append(
                {
                    **n,
                    "unmatched_reason": "ON-only: no OFF counterpart for this (seed, family)",
                    "event_category": "on_only",
                }
            )
            continue
        if n is None and o is not None:
            off_only.append(
                {
                    **o,
                    "unmatched_reason": "OFF-only: no ON v2 counterpart for this (seed, family)",
                    "event_category": "off_only",
                }
            )
            continue
        assert o is not None and n is not None
        g_loss_match = o["g_loss"] == n["g_loss"]
        if not g_loss_match:
            fi_identity_mismatch.append(
                {
                    "seed": key[0],
                    "family": key[1],
                    "off_g_loss": o["g_loss"],
                    "on_g_loss": n["g_loss"],
                    "off_trajectory": o.get("native_trajectory_alive"),
                    "on_trajectory": n.get("native_trajectory_alive"),
                    "off_persistent": o.get("persistent_loss"),
                    "on_persistent": n.get("persistent_loss"),
                    "note": (
                        "Same (seed, family) in both arms but first-loss generation "
                        "differs post-intervention; flagged descriptively, still in "
                        "primary (seed, family) paired denominator per prereg."
                    ),
                    "event_category": "fi_identity_mismatch_within_matched",
                }
            )

        nat_off = o.get("native_trajectory_alive") or ""
        nat_on = n.get("native_trajectory_alive") or ""
        traj_div = nat_off != nat_on
        off_p = bool(o.get("persistent_loss"))
        on_p = bool(n.get("persistent_loss"))
        off_t = bool(o.get("reentered_after_first_loss"))
        on_t = bool(n.get("reentered_after_first_loss"))
        matched.append(
            {
                "seed": key[0],
                "family": key[1],
                "g_loss_off": o["g_loss"],
                "g_loss_on": n["g_loss"],
                "g_loss_match": g_loss_match,
                "event_identity_off": list(event_identity_key(o)),
                "event_identity_on": list(event_identity_key(n)),
                "off_trajectory": nat_off,
                "on_trajectory": nat_on,
                "off_persistent": off_p,
                "on_persistent": on_p,
                "off_transient": off_t,
                "on_transient": on_t,
                "on_reentry_delay": n.get("reentry_delay"),
                "trajectory_diverged": traj_div,
                "trajectory_unchanged": not traj_div,
                "persistent_to_transient": off_p and on_t,
                "transient_to_persistent": off_t and on_p,
                "classification_diverged": off_p != on_p,
                "event_category": "matched_primary",
            }
        )

    n_matched = len(matched)
    off_p_n = sum(1 for r in matched if r["off_persistent"])
    on_p_n = sum(1 for r in matched if r["on_persistent"])
    off_t_n = sum(1 for r in matched if r["off_transient"])
    on_t_n = sum(1 for r in matched if r["on_transient"])
    p2t = sum(1 for r in matched if r["persistent_to_transient"])
    t2p = sum(1 for r in matched if r["transient_to_persistent"])
    traj_div_n = sum(1 for r in matched if r["trajectory_diverged"])

    b = p2t  # OFF persistent, ON transient
    c = t2p  # OFF transient, ON persistent
    mcnemar_p = None
    if b + c > 0:
        mcnemar_p = float(binomtest(min(b, c), b + c, 0.5, alternative="two-sided").pvalue)

    p_off = off_p_n / n_matched if n_matched else None
    p_on = on_p_n / n_matched if n_matched else None
    delta_pp = ((p_off or 0) - (p_on or 0)) * 100 if n_matched else None

    return {
        "n_off_events": len(off_events),
        "n_on_events": len(on_events),
        "n_matched_events": n_matched,
        "n_on_only_events": len(on_only),
        "n_off_only_events": len(off_only),
        "n_fi_identity_mismatch": len(fi_identity_mismatch),
        "matched_off_persistent": f"{off_p_n}/{n_matched}",
        "matched_on_persistent": f"{on_p_n}/{n_matched}",
        "matched_off_transient": f"{off_t_n}/{n_matched}",
        "matched_on_transient": f"{on_t_n}/{n_matched}",
        "matched_off_persistent_n": off_p_n,
        "matched_on_persistent_n": on_p_n,
        "matched_off_transient_n": off_t_n,
        "matched_on_transient_n": on_t_n,
        "p_persistent_off_matched": p_off,
        "p_persistent_on_matched": p_on,
        "p_transient_off_matched": off_t_n / n_matched if n_matched else None,
        "p_transient_on_matched": on_t_n / n_matched if n_matched else None,
        "persistent_to_transient": p2t,
        "transient_to_persistent": t2p,
        "trajectory_diverged": traj_div_n,
        "trajectory_unchanged": n_matched - traj_div_n,
        "fraction_trajectory_diverged": traj_div_n / n_matched if n_matched else None,
        "delta_persistent_percentage_points": delta_pp,
        "mcnemar_discordant_offP_onT": b,
        "mcnemar_discordant_offT_onP": c,
        "mcnemar_n_discordant": b + c,
        "mcnemar_exact_p": mcnemar_p,
        "interpretation_tag": (
            "directionally_consistent_small_effect"
            if b > 0 and c == 0 and mcnemar_p is not None
            else "no_discordant_pairs"
            if b + c == 0
            else "mixed_discordance"
        ),
        "matched_rows": matched,
        "on_only_rows": on_only,
        "off_only_rows": off_only,
        "fi_identity_mismatch_rows": fi_identity_mismatch,
    }


def all_events_descriptive(off_events: list[dict], on_events: list[dict]) -> dict[str, Any]:
    def tallies(ev: list[dict]) -> dict[str, Any]:
        n = len(ev)
        np = sum(1 for e in ev if e.get("persistent_loss"))
        nt = sum(1 for e in ev if e.get("reentered_after_first_loss"))
        return {
            "n_unsupported_events": n,
            "n_persistent_loss": np,
            "n_transient_loss": nt,
            "p_persistent_loss": np / n if n else None,
            "p_transient_loss": nt / n if n else None,
        }

    off_t = tallies(off_events)
    on_t = tallies(on_events)
    return {
        "label": "DESCRIPTIVE — UNMATCHED ALL-EVENT RATE",
        "warning": (
            "Different denominators (OFF vs ON total event counts). "
            "Not valid as primary paired causal recovery effect."
        ),
        "off": off_t,
        "on_v2": on_t,
        "delta_p_persistent_all_events": (
            ((off_t["p_persistent_loss"] or 0) - (on_t["p_persistent_loss"] or 0)) * 100
            if off_t["n_unsupported_events"] and on_t["n_unsupported_events"]
            else None
        ),
    }


def cross_system_descriptive_table() -> dict[str, Any]:
    camels_path = AV2_ROOT.parent / "outputs" / "confirmatory" / "confirmatory_summary.json"
    camels_matched_n = 8
    camels_off_p = 8
    camels_on_p = 1
    camels_recovered = 7
    if camels_path.is_file():
        data = json.loads(camels_path.read_text(encoding="utf-8"))
        c = data.get("camels", {})
        primary = c.get("trajectory_divergence", {})
        camels_matched_n = primary.get("n_matched_events", camels_matched_n)
        off = c.get("off", {})
        on = c.get("on", {})
        camels_off_p = off.get("n_persistent_loss", camels_off_p)
        camels_on_p = on.get("n_persistent_loss", camels_on_p)
        camels_recovered = off.get("n_persistent_loss", 0) - on.get("n_persistent_loss", 0)
        if on.get("n_transient_loss") is not None:
            camels_recovered = on.get("n_transient_loss", camels_recovered)

    return {
        "label": "DESCRIPTIVE cross-system magnitude comparison (not inferential)",
        "note": (
            "Same functional principle permits post-FI recovery in both systems; "
            "magnitude difference is descriptive because representation dynamics differ."
        ),
        "rows": [
            {
                "system": "Anchor v2",
                "matched_FI": None,  # filled by caller
                "OFF_persistent": None,
                "ON_persistent": None,
                "OFF_to_ON_recovered_transient": None,
            },
            {
                "system": "CAMELS",
                "matched_FI": camels_matched_n,
                "OFF_persistent": f"{camels_off_p}/{camels_matched_n}",
                "ON_persistent": f"{camels_on_p}/{camels_matched_n}",
                "OFF_to_ON_recovered_transient": f"{camels_recovered}/{camels_matched_n}",
            },
        ],
    }


def write_csv(rows: list[dict], path: Path) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields: list[str] = []
    for r in rows:
        for k in r:
            if k not in fields:
                fields.append(k)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k) for k in fields})


def run_matched_correction(confirmatory_dir: Path | None = None) -> dict[str, Any]:
    root = confirmatory_dir or CONFIRMATORY_DIR
    off, on = load_event_lists(root)
    classified = classify_event_sets(off, on)
    all_desc = all_events_descriptive(off, on)
    cross = cross_system_descriptive_table()
    n_m = classified["n_matched_events"]
    cross["rows"][0]["matched_FI"] = n_m
    cross["rows"][0]["OFF_persistent"] = classified["matched_off_persistent"]
    cross["rows"][0]["ON_persistent"] = classified["matched_on_persistent"]
    cross["rows"][0]["OFF_to_ON_recovered_transient"] = (
        f"{classified['persistent_to_transient']}/{n_m}"
    )

    matched_summary = {k: v for k, v in classified.items() if not k.endswith("_rows")}
    system_desc = {
        "post_intervention_system_level_dynamics": {
            "label": "SECONDARY — POST-INTERVENTION SYSTEM-LEVEL DYNAMICS",
            "description": (
                "After first FI, ON/OFF recursive dynamics diverge; ON may generate "
                "additional unsupported FI events with no OFF-matched counterpart."
            ),
            "on_only_events": classified["on_only_rows"],
            "off_only_events": classified["off_only_rows"],
            "fi_identity_mismatch_events": classified["fi_identity_mismatch_rows"],
        },
        "all_events_descriptive": all_desc,
        "cross_system_descriptive": cross,
        "anchor_v1_descriptive_note": {
            "cohort": "seeds 101-120",
            "intervention": "special-threshold _hypothetical_w_surv revival",
            "persistent_to_transient_matched": 0,
            "comparison_note": "Different cohort + intervention; descriptive only, not pooled.",
        },
    }

    # backup original summary
    summary_path = root / "confirmatory_summary.json"
    if summary_path.is_file():
        backup = root / "confirmatory_summary_pre_matched_correction.json"
        if not backup.is_file():
            backup.write_text(summary_path.read_text(encoding="utf-8"), encoding="utf-8")

    # build updated confirmatory summary
    if summary_path.is_file():
        full = json.loads(summary_path.read_text(encoding="utf-8"))
    else:
        full = {}

    full["statistical_correction_version"] = "matched-primary-v1"
    full["primary_matched_post_fi_recovery"] = {
        "label": "PRIMARY — MATCHED POST-FI RECOVERY",
        **matched_summary,
    }
    full["secondary_descriptive"] = system_desc
    full["primary_matched_post_fi_recovery"].pop("interpretation_tag", None)
    matched_summary["interpretation_tag"] = classified.get("interpretation_tag")

    write_csv(classified["matched_rows"], root / "matched_event_table.csv")
    unmatched = classified["on_only_rows"] + classified["off_only_rows"]
    write_csv(unmatched, root / "unmatched_event_table.csv")
    (root / "matched_primary_summary.json").write_text(
        json.dumps(matched_summary, indent=2), encoding="utf-8"
    )
    (root / "system_level_descriptive_summary.json").write_text(
        json.dumps(system_desc, indent=2), encoding="utf-8"
    )
    summary_path.write_text(json.dumps(full, indent=2), encoding="utf-8")

    return {
        "matched_summary": matched_summary,
        "system_descriptive": system_desc,
        "confirmatory_summary": full,
    }


if __name__ == "__main__":
    out = run_matched_correction()
    print(json.dumps(out["matched_summary"], indent=2))
