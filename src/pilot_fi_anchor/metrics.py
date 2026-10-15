"""Endpoints E1–E3 + secondary metrics (EXPERIMENT_DESIGN.md 10).

Primary FI endpoints:
- E1 (seed-level): >=1 auditable false-family unsupported elimination in Native
- E2 (temporal FI): DeltaT_FI = t_excl^Native - t_elim^Native on same trajectory
- E3 (causal rescue): Native eliminated while Neutral retained at matched time

Censoring: t_excl = None means never excluded within horizon R.  For PASS-A3,
frac(ΔT_FI >= 1) uses **all** unsupported events as denominator; censored
events with R > t_elim + 1 count as gap >= 1.  median_finite_dFI is
descriptive only (finite t_excl events).
"""

from __future__ import annotations

from typing import Any

import numpy as np
from scipy.stats import binomtest

from .config import FALSE_FAMILIES, FAMILY_ORDER, R, PilotConfig


def dFI_ge1(event: dict[str, Any], horizon: int = R) -> bool:
    """Temporal FI gap >= 1 round for an unsupported elimination event."""
    if not event.get("unsupported", False):
        return False
    d = event.get("dFI")
    if d is not None:
        return d >= 1
    if event.get("censored_N") and horizon > event["t_elim"] + 1:
        return True
    return False


def _native_event_row(
    rec: dict[str, Any], h: str, t_elim: int
) -> dict[str, Any]:
    native = rec["arms"]["native"]
    neutral = rec["arms"]["neutral"]
    n_final = native["final"]
    u_final = neutral["final"]
    t_excl_N = n_final["t_excl"][h]
    t_elim_U = u_final["t_elim"][h]
    t_excl_U = u_final["t_excl"][h]
    compat = not native["rounds"][t_elim][h]["excluded"]
    unsupported = compat and (
        t_excl_N is None or t_elim < t_excl_N
    )
    d_fi = (t_excl_N - t_elim) if t_excl_N is not None else None
    return {
        "seed": rec["seed"],
        "family": h,
        "t_elim": t_elim,
        "compat_at_elim": compat,
        "unsupported": unsupported,
        "t_excl_N": t_excl_N,
        "censored_N": t_excl_N is None,
        "dFI": d_fi,
        "t_elim_Neu": t_elim_U,
        "t_excl_Neu": t_excl_U,
        "censored_Neu": t_excl_U is None,
        "alive_Neu_at_elim": (t_elim_U is None) or (t_elim_U > t_elim),
        "dCross": (t_excl_U - t_elim) if t_excl_U is not None else None,
    }


def native_events(
    rec: dict[str, Any], horizon: int = R
) -> list[dict[str, Any]]:
    """Every Native elimination of a false family (event-level audit table)."""
    n_final = rec["arms"]["native"]["final"]
    out = []
    for h in FALSE_FAMILIES:
        t_elim = n_final["t_elim"][h]
        if t_elim is None:
            continue
        row = _native_event_row(rec, h, t_elim)
        row["dFI_ge1"] = dFI_ge1(row, horizon)
        out.append(row)
    return out


def focal_event(rec: dict[str, Any], cfg: PilotConfig) -> dict[str, Any] | None:
    """Representative case only: first false family eliminated in Native."""
    events = native_events(rec, cfg.rounds)
    if not events:
        return None
    victim_row = min(
        events, key=lambda e: (e["t_elim"], FALSE_FAMILIES.index(e["family"]))
    )
    return {
        **victim_row,
        "victim": victim_row["family"],
        "native_final_incumbent": rec["arms"]["native"]["final"]["incumbent"],
        "neutral_final_incumbent": rec["arms"]["neutral"]["final"]["incumbent"],
    }


def seed_summary(rec: dict[str, Any], cfg: PilotConfig) -> dict[str, Any]:
    native = rec["arms"]["native"]
    neutral = rec["arms"]["neutral"]
    n_final = native["final"]
    u_final = neutral["final"]
    events = native_events(rec, cfg.rounds)
    unsupported = [e for e in events if e["unsupported"]]
    temporal_fi = [e for e in unsupported if e["dFI_ge1"]]
    rescued = [e for e in unsupported if e["alive_Neu_at_elim"]]
    return {
        "seed": rec["seed"],
        "native_final_incumbent": n_final["incumbent"],
        "neutral_final_incumbent": u_final["incumbent"],
        "neutral_converged": u_final["incumbent"] == "hump",
        "native_final_is_truth": n_final["incumbent"] == "hump",
        "truth_elim_native": n_final["t_elim"]["hump"] is not None,
        "native_truth_excluded": bool(n_final["excluded"]["hump"]),
        "neutral_truth_excluded": bool(u_final["excluded"]["hump"]),
        "n_false_elim_native": len(events),
        "n_unsupported_elim": len(unsupported),
        "has_unsupported_elim": len(unsupported) >= 1,
        "has_temporal_fi": len(temporal_fi) >= 1,
        "n_rescued_unsupported": len(rescued),
        "round0_all_compat": all(
            not native["rounds"][0][h]["violated"] for h in FAMILY_ORDER
        ),
    }


# ----------------------------------------------------------------- aggregate
def _ci(k: int, n: int) -> tuple[float | None, float | None]:
    if n == 0:
        return None, None
    ci = binomtest(k, n).proportion_ci(confidence_level=0.95)
    return float(ci.low), float(ci.high)


def compute_endpoints(
    records: list[dict[str, Any]], cfg: PilotConfig, runtime_s: float | None = None
) -> dict[str, Any]:
    focals = [f for r in records for f in [focal_event(r, cfg)] if f is not None]
    events = [e for r in records for e in native_events(r, cfg.rounds)]
    summaries = [seed_summary(r, cfg) for r in records]
    n_seeds = len(records)

    unsupported_events = [e for e in events if e["unsupported"]]
    event_compat = unsupported_events  # alias: unsupported implies compat at elim

    # E1 primary: seed-level fraction with >=1 unsupported elimination
    e1_seed_k = sum(1 for s in summaries if s["has_unsupported_elim"])
    e1_seed_n = n_seeds
    # E1 secondary: event-level unsupported fraction among auditable eliminations
    e1_event_k, e1_event_n = len(unsupported_events), len(events)

    # E2 temporal FI: DeltaT_FI within Native trajectory
    d_fi_finite = [e["dFI"] for e in unsupported_events if e["dFI"] is not None]
    e2_ge1_k = sum(1 for e in unsupported_events if dFI_ge1(e, cfg.rounds))
    e2_ge1_n = len(unsupported_events)
    d_cross = [e["dCross"] for e in unsupported_events if e["dCross"] is not None]

    # E3 causal rescue on unsupported events (separate endpoint)
    rescued = [e for e in unsupported_events if e["alive_Neu_at_elim"]]

    # secondary descriptive
    n_neutral_converged = sum(1 for s in summaries if s["neutral_converged"])
    n_native_truth_final = sum(1 for s in summaries if s["native_final_is_truth"])
    n_truth_elim_native = sum(1 for s in summaries if s["truth_elim_native"])
    n_round0_ok = sum(1 for s in summaries if s["round0_all_compat"])
    n_neutral_truth_excl = sum(1 for s in summaries if s["neutral_truth_excluded"])
    n_native_truth_excl = sum(1 for s in summaries if s["native_truth_excluded"])

    # local gain profile (secondary; frozen primary reporting delta)
    from .config import DELTA_PERT_PRIMARY, DELTA_PERTS

    gain_primary: dict[tuple[str, int], list[float]] = {}
    gain_by_delta: dict[float, list[float]] = {d: [] for d in DELTA_PERTS}
    neutral_max_abs = 0.0
    for r in records:
        for p in r.get("perturb", []):
            delta = float(p.get("delta", DELTA_PERT_PRIMARY))
            gval = float(p["g"])
            if delta in gain_by_delta:
                gain_by_delta[delta].append(gval)
            if p["arm"] == "neutral":
                neutral_max_abs = max(neutral_max_abs, abs(gval))
            if delta != DELTA_PERT_PRIMARY:
                continue
            key = (p["arm"], p["t"])
            gain_primary.setdefault(key, []).append(gval)
    gain_profile = {
        f"{arm}_t{t}": {"mean_g": float(np.mean(gs)), "n": len(gs)}
        for (arm, t), gs in sorted(gain_primary.items())
    }
    native_gain_mean = float(
        np.mean([g for (arm, _), gs in gain_primary.items() for g in gs if arm == "native"])
    ) if any(arm == "native" for arm, _ in gain_primary) else float("nan")
    gain_delta_summary = {}
    for delta, gs in gain_by_delta.items():
        if not gs:
            continue
        arr = np.array(gs)
        gain_delta_summary[str(delta)] = {
            "mean_g": float(np.mean(arr)),
            "max_abs_g": float(np.max(np.abs(arr))),
            "n": len(gs),
        }

    def med(xs: list[int]) -> float | None:
        return float(np.median(xs)) if xs else None

    endpoints = {
        "n_seeds": n_seeds,
        "runtime_s": runtime_s,
        # E1 primary (seed-level)
        "E1_seed_unsupported_frac": e1_seed_k / e1_seed_n if e1_seed_n else None,
        "E1_seed_k": e1_seed_k,
        "E1_seed_n": e1_seed_n,
        "E1_seed_ci95": _ci(e1_seed_k, e1_seed_n),
        # E1 secondary (event-level)
        "E1_event_unsupported_frac": e1_event_k / e1_event_n if e1_event_n else None,
        "E1_event_k": e1_event_k,
        "E1_event_n": e1_event_n,
        "E1_event_ci95": _ci(e1_event_k, e1_event_n),
        "total_auditable_elim_events": e1_event_n,
        "unsupported_elim_events": e1_event_k,
        # E2 temporal FI (primary gate: frac over all unsupported events)
        "E2_frac_dFI_ge1": e2_ge1_k / e2_ge1_n if e2_ge1_n else None,
        "E2_frac_dFI_ge1_k": e2_ge1_k,
        "E2_frac_dFI_ge1_n": e2_ge1_n,
        "E2_frac_dFI_ge1_ci95": _ci(e2_ge1_k, e2_ge1_n),
        # descriptive: finite t_excl only
        "E2_median_finite_dFI": med(d_fi_finite),
        "E2_n_dFI_finite": len(d_fi_finite),
        "E2_n_dFI_censored": len(unsupported_events) - len(d_fi_finite),
        # E2 supporting cross-arm contrast
        "E2_median_dCross": med(d_cross),
        "E2_n_dCross_finite": len(d_cross),
        "E2_frac_dCross_ge1": (
            np.mean([x >= 1 for x in d_cross]) if d_cross else None
        ),
        # E3 causal rescue (separate)
        "E3_rescue_frac": len(rescued) / len(unsupported_events) if unsupported_events else None,
        "E3_rescue_k": len(rescued),
        "E3_rescue_n": len(unsupported_events),
        "E3_rescue_ci95": _ci(len(rescued), len(unsupported_events)),
        # secondary descriptive
        "neutral_converged_k": n_neutral_converged,
        "neutral_converged_frac": n_neutral_converged / n_seeds if n_seeds else None,
        "native_final_truth_frac": n_native_truth_final / n_seeds if n_seeds else None,
        "truth_elim_native_frac": n_truth_elim_native / n_seeds if n_seeds else None,
        "round0_all_compat_k": n_round0_ok,
        "round0_all_compat_frac": n_round0_ok / n_seeds if n_seeds else None,
        "neutral_truth_excluded_count": n_neutral_truth_excl,
        "native_truth_excluded_count": n_native_truth_excl,
        # gain (secondary only)
        "neutral_max_abs_gain": neutral_max_abs,
        "native_mean_gain": native_gain_mean,
        "gain_profile": gain_profile,
        "gain_delta_primary": DELTA_PERT_PRIMARY,
        "gain_by_delta": gain_delta_summary,
        # legacy focal counts (descriptive only)
        "focal_n": len(focals),
    }
    return endpoints, focals, events, summaries
