"""PASS/KILL gates — pre-registered in EXPERIMENT_DESIGN.md 11.

Do not revise thresholds after results exist.  KILL = hard validity gates
(any failure invalidates the pilot); PASS = the scientific claims;
AMBIGUOUS (A1 only) = escalate to a reviewed v2, never silent tuning.
"""

from __future__ import annotations

from typing import Any

from .config import KILL_B1_MIN, KILL_B3_MIN, PILOT_N_SEEDS


def matching_check(records: list[dict[str, Any]]) -> dict[str, Any]:
    """KILL-B4 matching: identical initial observations across arms/seeds and
    identical y for any site measured by both arms of the same seed."""
    ok = True
    detail: list[str] = []
    initial_ref: list[list[float]] | None = None
    for rec in records:
        sites = rec["arms"]
        n0 = [s["y"] for s in sites["native"]["sites"] if s["t"] == 0]
        u0 = [s["y"] for s in sites["neutral"]["sites"] if s["t"] == 0]
        if n0 != u0:
            ok = False
            detail.append(f"seed {rec['seed']}: initial y differ across arms")
        if initial_ref is None:
            initial_ref = n0
        elif n0 != initial_ref:
            ok = False
            detail.append(f"seed {rec['seed']}: initial y differ across seeds")
        y_native = {s["idx"]: s["y"] for s in sites["native"]["sites"]}
        y_neutral = {s["idx"]: s["y"] for s in sites["neutral"]["sites"]}
        shared = set(y_native) & set(y_neutral)
        bad = [i for i in shared if y_native[i] != y_neutral[i]]
        if bad:
            ok = False
            detail.append(f"seed {rec['seed']}: {len(bad)} shared sites disagree")
    return {"ok": ok, "detail": detail}


def evaluate(
    endpoints: dict[str, Any],
    matching: dict[str, Any],
) -> dict[str, Any]:
    gates: dict[str, Any] = {}

    def gate(gid: str, status: str, value: Any, threshold: str, note: str = "") -> None:
        gates[gid] = {
            "status": status, "value": value, "threshold": threshold, "note": note,
        }

    # --- KILL (hard) ------------------------------------------------------
    b1k = endpoints.get("neutral_converged_k")
    b1ok = b1k is not None and b1k >= KILL_B1_MIN
    gate("KILL-B1", "PASS" if b1ok else "FAIL",
         b1k, f">= {KILL_B1_MIN}/{PILOT_N_SEEDS}",
         "Neutral must converge to the truth family (formal 20-seed pilot)")
    b2n = endpoints["neutral_truth_excluded_count"]
    b2x = endpoints["native_truth_excluded_count"]
    b2ok = b2n == 0 and b2x <= 1
    gate("KILL-B2", "PASS" if b2ok else "FAIL",
         f"neutral={b2n}, native={b2x}", "neutral=0, native<=1",
         "truth must not be spuriously evidence-excluded")
    b3k = endpoints.get("round0_all_compat_k")
    b3ok = b3k is not None and b3k >= KILL_B3_MIN
    gate("KILL-B3", "PASS" if b3ok else "FAIL",
         b3k, f">= {KILL_B3_MIN}/{PILOT_N_SEEDS}",
         "all 5 families evidence-compatible at round 0 (under-identification)")
    b4ok = matching["ok"] and endpoints["neutral_max_abs_gain"] < 1e-9
    gate("KILL-B4", "PASS" if b4ok else "FAIL",
         {"matching": matching["ok"], "detail": matching["detail"],
          "neutral_max_abs_gain": endpoints["neutral_max_abs_gain"]},
         "matching OK and neutral gain == 0",
         "arm matching and the zero-gain control")
    b5v = endpoints.get("runtime_s")
    gate("KILL-B5", "PASS" if b5v is not None and b5v <= 3600 else "FAIL",
         b5v, "<= 1 CPU hour", "pilot runtime budget")

    # --- PASS (scientific claims) -----------------------------------------
    k, n = endpoints["E1_seed_k"], endpoints["E1_seed_n"]
    if k >= 8:
        a1 = "PASS"
    elif k <= 2:
        a1 = "FAIL"
    else:
        a1 = "AMBIGUOUS"
    gate("PASS-A1", a1, f"{k}/{n}",
         "PASS>=8, FAIL<=2, else AMBIGUOUS",
         "seed-level unsupported elimination (E1)")
    rv = endpoints["E3_rescue_frac"]
    gate("PASS-A2", "PASS" if rv is not None and rv >= 0.6 else "FAIL",
         rv, ">= 0.60", "causal rescue on unsupported events (E3)")
    fg = endpoints["E2_frac_dFI_ge1"]
    md = endpoints.get("E2_median_finite_dFI")
    a3ok = fg is not None and fg >= 0.6
    gate("PASS-A3", "PASS" if a3ok else "FAIL",
         {"frac_dFI_ge1": fg, "median_finite_dFI": md},
         "frac(ΔT_FI>=1)>=0.60 over all unsupported events",
         "temporal FI within Native (E2); censored counts if R>t_elim+1")
    a4v = endpoints["native_final_truth_frac"]
    gate("DESC-A4", "INFO", a4v,
         "descriptive only (not a PASS gate)",
         "Native final truth recovery rate; FI does not require final error")

    gates["summary"] = {
        "kill_all_pass": all(
            gates[g]["status"] == "PASS" for g in
            ("KILL-B1", "KILL-B2", "KILL-B3", "KILL-B4", "KILL-B5")
        ),
        "pass_all_pass": all(
            gates[g]["status"] == "PASS" for g in
            ("PASS-A1", "PASS-A2", "PASS-A3")
        ),
    }
    return gates


def format_table(gates: dict[str, Any]) -> str:
    lines = ["gate        status      value                          threshold / note"]
    for gid, g in gates.items():
        if gid == "summary":
            continue
        lines.append(
            f"{gid:11s} {g['status']:10s}  {str(g['value'])[:38]:38s}  {g['threshold']}"
        )
    s = gates["summary"]
    lines.append("")
    lines.append(f"KILL all PASS: {s['kill_all_pass']}   PASS all PASS: {s['pass_all_pass']}")
    return "\n".join(lines)
