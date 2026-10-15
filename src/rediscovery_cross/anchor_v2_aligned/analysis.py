"""Anchor v2 CAMELS-aligned recoverability — analysis."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from scipy.stats import binomtest

from pilot_fi_anchor.config import FALSE_FAMILIES, FAMILY_ORDER, R, THETA_W
from pilot_fi_anchor.loop import run_seed
from pilot_fi_anchor.metrics import native_events
from rediscovery_cross.anchor_analysis import classify_anchor_events, family_alive_trajectory
from rediscovery_cross.rediscovery import analyze_trajectory_after_first_loss, primary_persistence_summary

AV2_ROOT = Path(__file__).resolve().parent


def load_av2_config(path: Path | None = None) -> dict[str, Any]:
    with open(path or AV2_ROOT / "config.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def run_anchor_v2_condition(
    seed: int,
    *,
    rediscovery_mode: str,
    rounds: int = R,
    do_perturb: bool = False,
) -> dict[str, Any]:
    rec = run_seed(seed, do_perturb=do_perturb, rounds=rounds, rediscovery_mode=rediscovery_mode)
    events = classify_anchor_events(rec, horizon=rounds)
    for ev in events:
        ev["rediscovery_mode"] = rediscovery_mode
    return {
        "system": "anchor_v2",
        "seed": seed,
        "rediscovery_mode": rediscovery_mode,
        "record": rec,
        "events": events,
        "summary": primary_persistence_summary(events),
        "reentry_audit": rec["arms"]["native"]["final"].get("reentry_audit", []),
    }


def first_unsupported_fi(rec: dict[str, Any], *, horizon: int = R) -> dict[str, Any] | None:
    unsup = [e for e in native_events(rec, horizon) if e["unsupported"]]
    if not unsup:
        return None
    return min(unsup, key=lambda e: (e["t_elim"], FALSE_FAMILIES.index(e["family"])))


def paired_pre_first_fi_identical(seed: int, *, rounds: int = R) -> dict[str, Any]:
    """OFF vs v2 ON identical through round before first unsupported FI."""
    off = run_seed(seed, do_perturb=False, rounds=rounds, rediscovery_mode="off")
    on = run_seed(seed, do_perturb=False, rounds=rounds, rediscovery_mode="v2_on")
    fi_off = first_unsupported_fi(off, horizon=rounds)
    fi_on = first_unsupported_fi(on, horizon=rounds)

    if fi_off is None:
        compare_through = rounds
    else:
        compare_through = max(0, fi_off["t_elim"] - 1)

    def snap(rec: dict[str, Any], t: int) -> dict[str, Any]:
        row = rec["arms"]["native"]["rounds"][t]
        return {
            "n_arm": row["n_arm"],
            "alive": {h: row[h]["alive"] for h in FAMILY_ORDER},
            "w_all": {h: row[h]["w_all"] for h in FAMILY_ORDER},
            "w_surv": {h: row[h]["w_surv"] for h in FAMILY_ORDER},
            "sites": [s for s in rec["arms"]["native"]["sites"] if s["t"] <= t],
        }

    pre_identical = all(snap(off, t) == snap(on, t) for t in range(compare_through + 1))
    fi_matched = (
        fi_off is None
        and fi_on is None
        or (
            fi_off is not None
            and fi_on is not None
            and fi_off["family"] == fi_on["family"]
            and fi_off["t_elim"] == fi_on["t_elim"]
        )
    )
    return {
        "seed": seed,
        "first_unsupported_fi_off": fi_off,
        "first_unsupported_fi_on": fi_on,
        "compare_through_round": compare_through,
        "pre_fi_identical": pre_identical,
        "first_fi_matched": fi_matched,
        "pass": pre_identical and fi_matched,
    }


def verify_reentry_uses_ordinary_criterion(rec: dict[str, Any]) -> dict[str, Any]:
    audit = rec["arms"]["native"]["final"].get("reentry_audit", [])
    violations = []
    for entry in audit:
        w = entry["eligibility_quantity"]
        th = entry["ordinary_threshold"]
        if w < th - 1e-12:
            violations.append(entry)
        if entry.get("criterion") != "w_all >= THETA_W":
            violations.append({"error": "wrong criterion", **entry})
    return {"n_reentries": len(audit), "violations": violations, "pass": not violations}


def trajectory_divergence_paired(
    off_events: list[dict[str, Any]], on_events: list[dict[str, Any]]
) -> dict[str, Any]:
    off_by = {(e["seed"], e["family"]): e for e in off_events}
    matched = traj_diff = class_diff = 0
    persistent_to_transient = transient_to_persistent = 0
    paired_rows: list[dict[str, Any]] = []

    for e in on_events:
        key = (e["seed"], e["family"])
        o = off_by.get(key)
        if o is None:
            continue
        matched += 1
        nat_on = e.get("native_trajectory_alive") or e.get("native_trajectory")
        nat_off = o.get("native_trajectory_alive") or o.get("native_trajectory")
        td = nat_on != nat_off
        cd = e.get("persistent_loss") != o.get("persistent_loss")
        if td:
            traj_diff += 1
        if cd:
            class_diff += 1
        if o.get("persistent_loss") and e.get("reentered_after_first_loss"):
            persistent_to_transient += 1
        if o.get("reentered_after_first_loss") and e.get("persistent_loss"):
            transient_to_persistent += 1
        paired_rows.append(
            {
                "seed": e["seed"],
                "family": e["family"],
                "g_loss": e["g_loss"],
                "off_trajectory": nat_off,
                "on_trajectory": nat_on,
                "off_persistent": o.get("persistent_loss"),
                "on_persistent": e.get("persistent_loss"),
                "off_transient": o.get("reentered_after_first_loss"),
                "on_transient": e.get("reentered_after_first_loss"),
                "on_reentry_delay": e.get("reentry_delay"),
                "trajectory_diverged": td,
                "classification_diverged": cd,
            }
        )

    return {
        "n_matched_FI_events": matched,
        "n_trajectory_diverged": traj_diff,
        "fraction_trajectory_diverged": traj_diff / matched if matched else None,
        "n_persistent_classification_diff": class_diff,
        "persistent_to_transient": persistent_to_transient,
        "transient_to_persistent": transient_to_persistent,
        "paired_event_table": paired_rows,
    }


def mcnemar_persistent(off_events: list[dict], on_events: list[dict]) -> dict[str, Any] | None:
    off_by = {(e["seed"], e["family"]): e for e in off_events}
    b = c = 0  # off persistent/on transient; off transient/on persistent
    for e in on_events:
        o = off_by.get((e["seed"], e["family"]))
        if o is None:
            continue
        op, tp = bool(o.get("persistent_loss")), bool(e.get("persistent_loss"))
        if op and not tp:
            b += 1
        if not op and tp:
            c += 1
    if b + c == 0:
        return {"n_discordant": 0, "p_value": None}
    result = binomtest(min(b, c), b + c, 0.5, alternative="two-sided")
    return {"b_off_p_on_t": b, "c_off_t_on_p": c, "n_discordant": b + c, "p_value": float(result.pvalue)}


def analyze_confirmatory(output_root: Path, cfg: dict | None = None) -> dict[str, Any]:
    cfg = cfg or load_av2_config()
    pre_loss_rows = []
    off_events: list[dict] = []
    on_events: list[dict] = []
    reentry_checks = []

    for seed in cfg["experiment"]["confirmatory_seeds"]:
        pre = paired_pre_first_fi_identical(seed)
        pre_loss_rows.append(pre)
        off = run_anchor_v2_condition(seed, rediscovery_mode="off", do_perturb=False)
        on = run_anchor_v2_condition(seed, rediscovery_mode="v2_on", do_perturb=False)
        off_events.extend(off["events"])
        on_events.extend(on["events"])
        reentry_checks.append(verify_reentry_uses_ordinary_criterion(on["record"]))

    off_sum = primary_persistence_summary(off_events)
    on_sum = primary_persistence_summary(on_events)
    traj = trajectory_divergence_paired(off_events, on_events)

    return {
        "experiment": cfg["experiment"]["name"],
        "version": cfg["experiment"]["version"],
        "n_seeds": len(cfg["experiment"]["confirmatory_seeds"]),
        "pre_loss_equivalence": {
            "n_seeds": len(pre_loss_rows),
            "n_pass": sum(1 for r in pre_loss_rows if r["pass"]),
            "rows": pre_loss_rows,
        },
        "reentry_criterion_audit": {
            "n_seeds": len(reentry_checks),
            "n_pass": sum(1 for r in reentry_checks if r["pass"]),
            "total_reentries": sum(r["n_reentries"] for r in reentry_checks),
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


def load_v1_summary_for_comparison() -> dict[str, Any] | None:
    p = AV2_ROOT.parent / "outputs" / "confirmatory" / "confirmatory_summary.json"
    if not p.is_file():
        return None
    data = json.loads(p.read_text(encoding="utf-8"))
    return data.get("anchor")
