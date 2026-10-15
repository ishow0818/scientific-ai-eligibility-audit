"""Local ON/OFF / identity / isolation verification for five frozen cases."""

from __future__ import annotations

import copy
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from pymatgen.core.composition import Composition

PHASE2D = Path(__file__).resolve().parents[3] / "arrows_phase2d_route_progressive"
PKG = PHASE2D / "source"
sys.path.insert(0, str(PKG))
sys.path.insert(0, str(PKG / "lib"))

import suggest  # noqa: E402
from arrows import exparser  # noqa: E402
from truth_utils import intermediate_fingerprint, precursor_key_to_list, truth_row  # noqa: E402

from verify_store import VerifyStore, precursor_key  # noqa: E402

REDUNDANCY_ATOL = 0.1
LADDER_TEMPS = [600, 700, 800, 900]
REPLACE_PRODUCTS = ["CuO"]
REPLACE_WEIGHTS = [1.0]


def _formula(name: str) -> str:
    return Composition(name).reduced_formula


def parse_node(node: dict[str, Any], target: str) -> dict[str, Any]:
    products = [_formula(p.split("_")[0]) for p in node["products"]]
    wts = list(node["product weight fractions"])
    if np.isclose(sum(wts), 1.0, atol=0.01):
        wts = [100.0 * x for x in wts]
    wts = [float(x) / 100.0 for x in wts]
    target_present = target in products
    target_fraction = float(wts[products.index(target)]) if target_present else 0.0
    return {
        "products": products,
        "weight_fractions": wts,
        "target_present": target_present,
        "target_fraction": target_fraction,
        "pure_target": len(products) == 1 and products[0] == target,
        "fingerprint": intermediate_fingerprint(
            {"products": products, "weight_fractions": wts}
        ),
    }


def serialize_known_interm(known: dict) -> list[dict[str, Any]]:
    rows = []
    for phases, payload in known.items():
        rows.append(
            {
                "phases": list(phases),
                "amounts": [list(map(float, amt)) for amt in payload["Amounts"]],
                "success": bool(payload["Success"]),
            }
        )
    return rows


def _configure(store: VerifyStore, temps: list[int], target: str, precursors: list[str], interm) -> None:
    suggest.increasing_temps = temps
    suggest.exp_data = store.algorithm_view()
    suggest.target_product = target
    suggest.precursors = precursors
    suggest.interm = interm


def wrap_get_products(store: VerifyStore):
    original = exparser.get_products

    def probed(precursors, temperature, exp_data):
        route = precursor_key(precursors)
        tk = f"{int(temperature)} C"
        in_view = bool(exp_data) and route in exp_data and tk in exp_data[route].get("Temperatures", {})
        products, wts = original(precursors, temperature, exp_data)
        store.log_probe(
            route,
            int(temperature),
            caller="exparser.get_products",
            in_view=in_view,
            obtained=products is not None,
        )
        return products, wts

    exparser.get_products = probed
    return original


def restore_get_products(original) -> None:
    exparser.get_products = original


def identity_from_oracle(oracle: dict, case: dict, target: str) -> dict[str, Any]:
    ref = case["reference_route"]
    cand = case["candidate_route"]
    rows = {}
    for route, label in ((ref, "reference"), (cand, "candidate")):
        for t in LADDER_TEMPS:
            row = truth_row(oracle, route, t, target)
            rows[f"{label}_{t}"] = row
    ref600 = rows["reference_600"]
    cand600 = rows["candidate_600"]
    if ref600 is None or cand600 is None:
        raise ValueError(f"{case['case_id']}: missing 600 C truth row")
    ref_ph, ref_w = intermediate_fingerprint(ref600)
    cand_ph, cand_w = intermediate_fingerprint(cand600)
    similar = False
    if ref_ph == cand_ph and len(ref_w) == len(cand_w):
        similar = bool(np.all(np.isclose(ref_w, cand_w, atol=REDUNDANCY_ATOL)))
    ref_high_pure = {
        t: (rows[f"reference_{t}"]["pure_target"] if rows[f"reference_{t}"] else None)
        for t in (700, 800, 900)
    }
    cand900 = rows["candidate_900"]
    return {
        "case_id": case["case_id"],
        "reference_route": ref,
        "candidate_route": cand,
        "ref_600_phases": ";".join(ref_ph),
        "ref_600_weights": ";".join(f"{w:.6f}" for w in ref_w),
        "cand_600_phases": ";".join(cand_ph),
        "cand_600_weights": ";".join(f"{w:.6f}" for w in cand_w),
        "phase_set_equal": ref_ph == cand_ph,
        "weights_exact_equal": ref_ph == cand_ph and ref_w == cand_w,
        "weights_within_atol_0_1": similar,
        "ref_700_pure_target": ref_high_pure[700],
        "ref_800_pure_target": ref_high_pure[800],
        "ref_900_pure_target": ref_high_pure[900],
        "ref_any_highT_pure_target": any(ref_high_pure.values()),
        "cand_900_pure_target": cand900["pure_target"] if cand900 else None,
        "cand_900_products": ";".join(cand900["products"]) if cand900 else "",
        "cand_900_weights": ";".join(f"{w:.6f}" for w in cand900["weight_fractions"]) if cand900 else "",
    }


def build_reference_state(
    store: VerifyStore,
    oracle: dict,
    ref_route: str,
    target: str,
    temps: list[int],
) -> tuple[dict, list[dict], str]:
    min_temp = min(temps)
    ref_precursors = precursor_key_to_list(ref_route)
    known_interm: dict = {}
    history: list[dict] = []
    known_after_min: dict | None = None

    for t in LADDER_TEMPS:
        node = store.reveal(ref_route, t, caller=f"reference_ladder@{t}")
        if node is None:
            return {}, history, f"reference@{t} reveal failed"
        parsed = parse_node(node, target)
        phases, wts = parsed["fingerprint"]
        interm_obs = sorted(zip(parsed["products"], parsed["weight_fractions"]))
        if t == min_temp:
            _configure(store, temps, target, ref_precursors, interm_obs)
            redundant_ref = suggest.check_redundancy(phases, wts, known_interm)
            known_interm = suggest.update_interm(
                phases, wts, known_interm, redundant_ref, temps, store.algorithm_view()
            )
            known_after_min = copy.deepcopy(known_interm)
            action = "reference_at_min_T_update_interm"
        else:
            action = "reference_ladder_observe_only"
        history.append(
            {
                "route": ref_route,
                "temperature_c": t,
                "action": action,
                "pure_target": parsed["pure_target"],
                "phases": list(phases),
                "weights": [float(w) for w in wts],
            }
        )
    if known_after_min is None:
        return {}, history, "reference@600 update_interm never executed"
    return known_after_min, history, ""


def run_candidate_branch(
    store: VerifyStore,
    known_interm: dict,
    cand_route: str,
    target: str,
    temps: list[int],
    gate_on: bool,
) -> dict[str, Any]:
    min_temp = min(temps)
    cand_precursors = precursor_key_to_list(cand_route)
    known = copy.deepcopy(known_interm)
    redundant = False
    gate_return = None
    skipped: list[int] = []
    queried: list[dict[str, Any]] = []
    visible_before_gate: list[str] = []

    for t in temps:
        if gate_on and redundant:
            skipped.append(t)
            store.log_skip(cand_route, t, caller="gate_ON_stop")
            continue

        node = store.reveal(cand_route, t, caller=f"candidate_branch_{'ON' if gate_on else 'OFF'}@{t}")
        if node is None:
            queried.append({"temperature_c": t, "status": "MISSING_OR_SEALED"})
            continue
        parsed = parse_node(node, target)
        phases, wts = parsed["fingerprint"]
        interm_obs = sorted(zip(parsed["products"], parsed["weight_fractions"]))
        _configure(store, temps, target, cand_precursors, interm_obs)
        queried.append(
            {
                "temperature_c": t,
                "status": "OBSERVED",
                "pure_target": parsed["pure_target"],
                "phases": list(phases),
                "weights": [float(w) for w in wts],
            }
        )
        if t == min_temp:
            visible_before_gate = sorted(
                f"{route}|{temp} C" for route, temp in store.revealed_pairs
            )
            gate_return = bool(suggest.check_redundancy(phases, wts, known))
            redundant = gate_return
            suggest.update_interm(phases, wts, known, redundant, temps, store.algorithm_view())

    return {
        "gate_on": gate_on,
        "check_redundancy": gate_return,
        "skipped_temperatures": skipped,
        "queried": queried,
        "stopped_700_800_900": skipped == [700, 800, 900],
        "queried_700_800_900": [q["temperature_c"] for q in queried if q["temperature_c"] > min_temp],
        "visible_experiments_at_decision": visible_before_gate,
        "known_interm_after": serialize_known_interm(known),
    }


def isolation_oracle(oracle: dict, cand_route: str, t_high: int, mode: str) -> dict[str, Any]:
    cloned = copy.deepcopy(oracle)
    tk = f"{int(t_high)} C"
    if mode == "mask":
        cloned[cand_route]["Temperatures"].pop(tk, None)
    elif mode == "replace":
        cloned[cand_route]["Temperatures"][tk] = {
            "products": [f"{REPLACE_PRODUCTS[0]}_0"],
            "product weight fractions": REPLACE_WEIGHTS,
            "Experimentally Verified": True,
        }
    return cloned


def run_gate_only(
    oracle: dict,
    case: dict,
    target: str,
    temps: list[int],
    sealed: bool,
) -> dict[str, Any]:
    cand = case["candidate_route"]
    t_high = int(case["candidate_T_high"])
    sealed_pairs = {(cand, t_high)} if sealed else set()
    store = VerifyStore.from_oracle(oracle, sealed_pairs=sealed_pairs)
    original = wrap_get_products(store)
    try:
        known, history, err = build_reference_state(store, oracle, case["reference_route"], target, temps)
        if err:
            return {"error": err, "access_log": [e.as_dict() for e in store.access_log]}
        branch = run_candidate_branch(store, known, cand, target, temps, gate_on=True)
        # ON branch will try to skip 700-900; sealed 900 is never revealed
        return {
            "error": "",
            "check_redundancy": branch["check_redundancy"],
            "skipped": branch["skipped_temperatures"],
            "known_interm": serialize_known_interm(known),
            "visible": branch["visible_experiments_at_decision"],
            "decision_leakage": store.decision_leakage_count,
            "hidden_probes": store.decision_hidden_probes,
            "access_log": [e.as_dict() for e in store.access_log],
            "history": history,
        }
    finally:
        restore_get_products(original)


def verify_case(oracle: dict, case: dict, target: str, temps: list[int]) -> dict[str, Any]:
    identity = identity_from_oracle(oracle, case, target)
    cand = case["candidate_route"]
    t_high = int(case["candidate_T_high"])
    sealed = {(cand, t_high)}

    store_on = VerifyStore.from_oracle(oracle, sealed_pairs=sealed)
    orig = wrap_get_products(store_on)
    try:
        known, hist, err = build_reference_state(store_on, oracle, case["reference_route"], target, temps)
        if err:
            raise RuntimeError(err)
        known_snapshot = serialize_known_interm(known)
        success_flags = [row["success"] for row in known_snapshot]
        on_branch = run_candidate_branch(store_on, known, cand, target, temps, gate_on=True)
        hidden_node = store_on.peek_after_decision(cand, t_high, caller="post_decision_oracle")
        hidden_parsed = parse_node(hidden_node, target) if hidden_node else None
        on_log = [e.as_dict() for e in store_on.access_log]
        on_leakage = store_on.decision_leakage_count
        on_hidden_probes = store_on.decision_hidden_probes
        visible = on_branch["visible_experiments_at_decision"]
    finally:
        restore_get_products(orig)

    store_off = VerifyStore.from_oracle(oracle, sealed_pairs=set())
    orig = wrap_get_products(store_off)
    try:
        known_off, _, err = build_reference_state(store_off, oracle, case["reference_route"], target, temps)
        if err:
            raise RuntimeError(err)
        off_branch = run_candidate_branch(store_off, known_off, cand, target, temps, gate_on=False)
        off_900 = next((q for q in off_branch["queried"] if q["temperature_c"] == 900), None)
    finally:
        restore_get_products(orig)

    iso_base = run_gate_only(oracle, case, target, temps, sealed=True)
    iso_mask = run_gate_only(isolation_oracle(oracle, cand, t_high, "mask"), case, target, temps, sealed=True)
    iso_replace = run_gate_only(isolation_oracle(oracle, cand, t_high, "replace"), case, target, temps, sealed=True)
    isolation_same = (
        iso_base.get("check_redundancy") == iso_mask.get("check_redundancy") == iso_replace.get("check_redundancy")
        and iso_base.get("skipped") == iso_mask.get("skipped") == iso_replace.get("skipped")
        and iso_base.get("decision_leakage", 1) == 0
        and iso_mask.get("decision_leakage", 1) == 0
        and iso_replace.get("decision_leakage", 1) == 0
    )

    known_key = known_snapshot[0]["phases"] if known_snapshot else []
    known_success = known_snapshot[0]["success"] if known_snapshot else None

    return {
        "identity": identity,
        "known_interm": known_snapshot,
        "known_interm_n_keys": len(known_snapshot),
        "known_interm_phases": ";".join(known_key),
        "known_interm_success": known_success,
        "known_interm_success_source": (
            "update_interm at reference@600 using algorithm_view only; "
            "Success=True only if reference@900 already revealed and pure"
        ),
        "visible_experiments_at_decision": visible,
        "redundancy_depends_on": (
            "known_interm from reference@600 observed phases/weights; "
            f"np.isclose(..., atol={REDUNDANCY_ATOL}); Success flag does not change the boolean"
        ),
        "candidate_highT_unrevealed": f"{cand}|{t_high} C" not in visible,
        "gate_on": on_branch,
        "gate_off": off_branch,
        "post_decision_cand_900_pure": hidden_parsed["pure_target"] if hidden_parsed else None,
        "on_decision_leakage": on_leakage,
        "on_hidden_probes": on_hidden_probes,
        "access_log_on": on_log,
        "access_log_nonempty": len(on_log) > 0,
        "isolation": {
            "baseline_decision": iso_base.get("check_redundancy"),
            "mask_decision": iso_mask.get("check_redundancy"),
            "replace_decision": iso_replace.get("check_redundancy"),
            "baseline_skipped": iso_base.get("skipped"),
            "mask_skipped": iso_mask.get("skipped"),
            "replace_skipped": iso_replace.get("skipped"),
            "same_decision": isolation_same,
            "baseline_leakage": iso_base.get("decision_leakage"),
            "mask_leakage": iso_mask.get("decision_leakage"),
            "replace_leakage": iso_replace.get("decision_leakage"),
            "baseline_hidden_probes": iso_base.get("hidden_probes"),
        },
        "history": hist,
        "off_900": off_900,
        "success_flags_at_gate": success_flags,
    }
