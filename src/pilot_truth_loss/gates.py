"""Calibration gates (phase 1) and Failure Mode v2 confirmatory gates (G1–G4)."""

from __future__ import annotations

from typing import Any

from pilot_fi_anchor.config import ALPHA_EV, PILOT_N_SEEDS

from .config import (
    ANCHOR_VERSION,
    CONFIRMATORY_N_SEEDS,
    EXPECTED_ALPHA_EV,
    G2_F2V2_FRAC,
    G3_F3_FRAC,
    G4_NEUTRAL_TRUTH_EXCLUDED_MAX,
    TruthLossConfig,
)


def evaluate_calibration(cal: dict[str, Any]) -> dict[str, Any]:
    gates: dict[str, Any] = {}
    sel = cal["selection"]
    seq = cal["sequential_truth_safety"]
    ho = cal["held_out"]

    def gate(gid: str, status: str, value: Any, threshold: str, note: str = "") -> None:
        gates[gid] = {"status": status, "value": value, "threshold": threshold, "note": note}

    gate(
        "CAL-G1",
        "PASS" if sel["chosen"] is not None else "FAIL",
        sel["chosen"],
        "one competitor chosen by PC1–PC6 + min-gap rule",
        "structural pair selection",
    )
    gate(
        "CAL-G2",
        "PASS" if cal.get("frozen_config_match") else "FAIL",
        cal.get("frozen_config_match"),
        "chosen == config.COMPETITOR_FAMILY",
        "config matches rule output (no post-hoc swap)",
    )
    ch = sel["candidates"].get(sel["chosen"], {}) if sel["chosen"] else {}
    gate(
        "CAL-G3",
        "PASS" if ch.get("passes_pc1") else "FAIL",
        {
            "truth_initial_k": ch.get("truth_initial_compatible_k"),
            "comp_initial_k": ch.get("competitor_initial_compatible_k"),
        },
        f"both compatible on initial window all {PILOT_N_SEEDS} seeds",
        "initial compatibility",
    )
    gate(
        "CAL-G4",
        "PASS" if seq.get("ok") else "FAIL",
        seq.get("truth_excluded_k"),
        "truth sequential excluded = 0",
        "Neutral-path truth safety (anchor sequential sim)",
    )
    gate(
        "CAL-G5",
        "PASS" if ch.get("passes_pc3") and ch.get("passes_pc4") else "FAIL",
        {
            "comp_ext_excl_k": ch.get("extended_competitor_excluded_k"),
            "truth_ext_ok_k": ch.get("extended_truth_compatible_k"),
        },
        f"competitor excluded + truth compatible on extended coverage ({PILOT_N_SEEDS} seeds)",
        "extended separability",
    )
    gate(
        "CAL-G6",
        "PASS" if ho.get("ok") else "FAIL",
        ho.get("n_held_out"),
        "held-out grid disjoint and n >= 10",
        "held-out evaluation grid",
    )
    gates["summary"] = {
        "calibration_all_pass": all(
            gates[g]["status"] == "PASS" for g in gates if g.startswith("CAL-")
        ),
        "ready": cal.get("ready", False),
    }
    return gates


def evaluate_evidence_sanity(
    cfg: TruthLossConfig | None = None,
    *,
    neutral_truth_excluded_k: int | None = None,
) -> dict[str, Any]:
    """G4 config + confirmatory Neutral truth exclusion (B2-v2 sanity)."""
    cfg = cfg or TruthLossConfig()
    alpha_ok = abs(cfg.alpha_ev - EXPECTED_ALPHA_EV) < 1e-15
    alpha_matches_anchor = cfg.alpha_ev == ALPHA_EV
    version_ok = cfg.anchor_version == ANCHOR_VERSION
    config_ok = alpha_ok and alpha_matches_anchor and version_ok
    if neutral_truth_excluded_k is None:
        data_ok = None
    else:
        data_ok = neutral_truth_excluded_k <= G4_NEUTRAL_TRUTH_EXCLUDED_MAX
    ok = config_ok and (data_ok is None or data_ok)
    return {
        "ok": ok,
        "config_ok": config_ok,
        "data_ok": data_ok,
        "alpha_ev": cfg.alpha_ev,
        "expected_alpha_ev": EXPECTED_ALPHA_EV,
        "anchor_version": cfg.anchor_version,
        "expected_anchor_version": ANCHOR_VERSION,
        "neutral_truth_excluded_k": neutral_truth_excluded_k,
        "neutral_truth_excluded_max": G4_NEUTRAL_TRUTH_EXCLUDED_MAX,
    }


def evaluate_confirmatory(endpoints: dict[str, Any]) -> dict[str, Any]:
    """Failure Mode v2 confirmatory gates G1–G4."""
    gates: dict[str, Any] = {}
    cfg = TruthLossConfig()

    def gate(gid: str, status: str, value: Any, threshold: str, note: str = "") -> None:
        gates[gid] = {"status": status, "value": value, "threshold": threshold, "note": note}

    f1k = endpoints.get("F1_seed_k", 0)
    f2_frac = endpoints.get("F2_v2_frac")
    f3_frac = endpoints.get("F3_rescue_frac")
    neutral_excl_k = endpoints.get("neutral_truth_excluded_k")
    ev = evaluate_evidence_sanity(cfg, neutral_truth_excluded_k=neutral_excl_k)

    if f1k == 0:
        gate(
            "G1",
            "KILL",
            f1k,
            "> 0",
            "F1 unsupported truth elimination; zero events => Failure Mode v2 KILL",
        )
    else:
        gate(
            "G1",
            "PASS",
            f1k,
            "> 0",
            f"F1 unsupported truth elimination (n={CONFIRMATORY_N_SEEDS} fresh seeds)",
        )

    gate(
        "G2",
        "PASS" if f2_frac is not None and f2_frac >= G2_F2V2_FRAC else "FAIL",
        f2_frac,
        f">= {G2_F2V2_FRAC:.2f} (F2-v2 / F1 on F1 seeds)",
        "stable wrong lock-in on F1 seeds",
    )

    gate(
        "G3",
        "PASS" if f3_frac is not None and f3_frac >= G3_F3_FRAC else "FAIL",
        f3_frac,
        f">= {G3_F3_FRAC:.2f} (F3 / F1 on F1 seeds)",
        "Neutral causal rescue on F1 seeds",
    )

    g4_ok = ev["config_ok"] and ev["data_ok"] is True
    gate(
        "G4",
        "PASS" if g4_ok else "FAIL",
        {
            "alpha_ev": ev["alpha_ev"],
            "anchor_version": ev["anchor_version"],
            "neutral_truth_excluded_k": neutral_excl_k,
        },
        (
            f"B2-v2 alpha={EXPECTED_ALPHA_EV}; "
            f"Neutral truth excluded <= {G4_NEUTRAL_TRUTH_EXCLUDED_MAX}/{CONFIRMATORY_N_SEEDS}"
        ),
        "evidence criterion unchanged + Neutral truth safety in confirmatory data",
    )

    gate(
        "DESC-HO1",
        "INFO",
        endpoints.get("held_out_rmse_ratio_median_f2v2"),
        "descriptive; 19-point held-out RMSE ratio on F2-v2 seeds",
        "downstream prediction consequence (no pass threshold)",
    )

    g1_ok = gates["G1"]["status"] == "PASS"
    gates["summary"] = {
        "pass_all": g1_ok
        and all(gates[g]["status"] == "PASS" for g in ("G2", "G3", "G4")),
        "killed": gates["G1"]["status"] == "KILL",
        "version": cfg.version,
    }
    return gates
