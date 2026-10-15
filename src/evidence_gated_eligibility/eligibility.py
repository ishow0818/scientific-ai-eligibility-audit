"""Eligibility policies and offline Decision-Only selection (no GT / no eval RMSE)."""
from __future__ import annotations

from typing import Any

from pilot_fi_anchor.mechanisms import ALL_FAMILIES

from .config import (
    FAMILY_ORDER,
    STATUS_DECISION_EMPTY,
    STATUS_OK,
)


def require_family_bool_map(d: dict[str, Any], name: str) -> dict[str, bool]:
    """Strict per-family bool map: missing keys raise (no silent defaults)."""
    missing = [h for h in FAMILY_ORDER if h not in d]
    if missing:
        raise KeyError(f"{name} missing families: {missing}")
    return {h: bool(d[h]) for h in FAMILY_ORDER}


def require_family_flag(d: dict[str, Any], h: str, name: str) -> bool:
    """Strict single-family flag lookup."""
    if h not in d:
        raise KeyError(f"{name} missing family {h!r}")
    return bool(d[h])


def require_family_float_map(d: dict[str, Any], name: str) -> dict[str, float]:
    missing = [h for h in FAMILY_ORDER if h not in d]
    if missing:
        raise KeyError(f"{name} missing families: {missing}")
    return {h: float(d[h]) for h in FAMILY_ORDER}


def eligible_not_excluded(excluded: dict[str, bool]) -> list[str]:
    ex = require_family_bool_map(excluded, "excluded")
    return [h for h in FAMILY_ORDER if not ex[h]]


def select_incumbent_by_w_all(
    w_all: dict[str, float],
    excluded: dict[str, bool],
) -> tuple[str | None, str, list[str]]:
    """Original scoring on evidence-eligible set: argmax w_all among not excluded."""
    w = require_family_float_map(w_all, "w_all")
    E = eligible_not_excluded(excluded)
    if not E:
        return None, STATUS_DECISION_EMPTY, E
    h_star = max(E, key=lambda h: w[h])
    return h_star, STATUS_OK, E


def select_incumbent_open_pool(
    w_all: dict[str, float],
) -> tuple[str | None, str, list[str]]:
    """Open Eligibility: argmax w_all among all fitted models (ignore prune & χ²)."""
    w = require_family_float_map(w_all, "w_all")
    E = list(FAMILY_ORDER)
    if not E:
        return None, STATUS_DECISION_EMPTY, E
    h_star = max(E, key=lambda h: w[h])
    return h_star, STATUS_OK, E


def decision_only_gate(native_arm_pack: dict[str, Any]) -> dict[str, Any]:
    """Arm B: offline final decision from Native A pack. Does not alter trajectory."""
    rounds = native_arm_pack["rounds"]
    final = native_arm_pack["final"]
    last = rounds[-1]
    w_all = {h: float(last[h]["w_all"]) for h in FAMILY_ORDER}
    excluded = require_family_bool_map(final["excluded"], "final.excluded")
    alive = require_family_bool_map(final["alive"], "final.alive")
    arm_theta = {h: dict(final["arm_theta"][h]) for h in FAMILY_ORDER}
    incumbent, status, E = select_incumbent_by_w_all(w_all, excluded)
    theta = dict(arm_theta[incumbent]) if incumbent is not None else None
    return {
        "arm_tag": "decision_only",
        "allocation_mode": "offline_reuse_native_trajectory",
        "sites": list(native_arm_pack["sites"]),  # identical references / copies
        "rounds": list(native_arm_pack["rounds"]),
        "final": {
            "incumbent": incumbent,
            "eligible": {h: (h in E) for h in FAMILY_ORDER},
            "excluded": excluded,
            "alive_native": alive,
            "t_elim_native": dict(final["t_elim"]),
            "t_excl": dict(final["t_excl"]),
            "w_all": w_all,
            "arm_theta": arm_theta,
            "incumbent_theta": theta,
            "primary_status": status,
            "decision_rule": "argmax w_all among excluded=False",
        },
        "isolation": {
            "reused_native_sites": True,
            "reused_native_rounds": True,
            "closed_loop_rerun": False,
        },
    }


def open_eligibility_gate(native_arm_pack: dict[str, Any]) -> dict[str, Any]:
    """Post-hoc Open Eligibility: full-pool argmax w_all; ignore prune & excluded."""
    rounds = native_arm_pack["rounds"]
    final = native_arm_pack["final"]
    last = rounds[-1]
    w_all = {h: float(last[h]["w_all"]) for h in FAMILY_ORDER}
    excluded = require_family_bool_map(final["excluded"], "final.excluded")
    alive = require_family_bool_map(final["alive"], "final.alive")
    arm_theta = {h: dict(final["arm_theta"][h]) for h in FAMILY_ORDER}
    incumbent, status, E = select_incumbent_open_pool(w_all)
    theta = dict(arm_theta[incumbent]) if incumbent is not None else None
    return {
        "arm_tag": "open_eligibility",
        "allocation_mode": "offline_reuse_native_trajectory",
        "sites": list(native_arm_pack["sites"]),
        "rounds": list(native_arm_pack["rounds"]),
        "final": {
            "incumbent": incumbent,
            "eligible": {h: (h in E) for h in FAMILY_ORDER},
            "excluded_ignored": excluded,
            "alive_native": alive,
            "t_elim_native": dict(final["t_elim"]),
            "t_excl": dict(final["t_excl"]),
            "w_all": w_all,
            "arm_theta": arm_theta,
            "incumbent_theta": theta,
            "primary_status": status,
            "decision_rule": "argmax w_all among all five fitted models",
        },
        "isolation": {
            "reused_native_sites": True,
            "reused_native_rounds": True,
            "closed_loop_rerun": False,
            "uses_history_prune": False,
            "uses_chi2_exclusion": False,
        },
    }


def assert_excluded_sticky(history_excluded: list[dict[str, bool]]) -> None:
    """Once True, excluded must remain True (no resurrection)."""
    prev = {h: False for h in ALL_FAMILIES}
    for ex in history_excluded:
        for h in ALL_FAMILIES:
            if prev[h] and not ex[h]:
                raise AssertionError(f"excluded resurrected for {h}")
            prev[h] = bool(ex[h])
