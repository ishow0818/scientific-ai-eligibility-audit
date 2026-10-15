#!/usr/bin/env python3
"""One-shot verification of Native truth mis-exclusions (read-only)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from scipy.stats import chi2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pilot_fi_anchor.config import ALPHA_EV, PERSIST, R, SIGMA, TRUTH_FAMILY
from pilot_fi_anchor.evidence_calibration import evidence_crit
from pilot_fi_anchor.fitting import fit
from pilot_fi_anchor.loop import run_seed
from pilot_fi_anchor.mechanisms import FAMILIES
from pilot_fi_anchor.rng import fit_rng
from pilot_fi_anchor.world import World

FORMAL = ROOT / "outputs" / "pilot_fi_anchor"
OUT = ROOT / "outputs" / "anchor_chi2_reliability_audit"
EXCL_SEEDS = (20, 113, 117)


def sites_by_round(sites: list[dict]) -> list[list[int]]:
    by_t: dict[int, list[int]] = {}
    for s in sites:
        by_t.setdefault(int(s["t"]), []).append(int(s["idx"]))
    tmax = max(by_t)
    return [by_t.get(t, []) for t in range(0, tmax + 1)]


def recompute_hump(seed: int, batches: list[list[int]]) -> list[dict]:
    world = World(seed)
    fr = fit_rng(seed)
    mech = FAMILIES[TRUTH_FAMILY]
    arm_fit = None
    prev_v = False
    measured: list[int] = []
    out = []
    for t, batch in enumerate(batches):
        for idx in batch:
            if idx not in measured:
                measured.append(idx)
        order = sorted(measured)
        xs = np.array([world.x(i) for i in order])
        ys = np.array([world.y(i) for i in order])
        n = len(xs)
        z = fit(mech, xs, ys, warm=arm_fit, rng=fr)
        arm_fit = z
        theta = mech.from_fit(z)
        rss = float(np.sum((mech.predict(xs, theta) - ys) ** 2))
        stat = rss / (SIGMA * SIGMA)
        df = n - mech.p
        crit = evidence_crit(n, mech.p)
        violated = stat > crit
        excluded = bool(violated and prev_v)
        out.append(
            {
                "t": t,
                "n": n,
                "df": df,
                "stat": stat,
                "crit": crit,
                "violated": violated,
                "excluded": excluded,
            }
        )
        prev_v = violated
    return out


def load_or_run(seed: int) -> dict:
    if seed <= 20:
        path = FORMAL / f"seed_{seed:02d}.json"
        return json.loads(path.read_text(encoding="utf-8"))
    # live replay for extra MC seeds
    return run_seed(seed, do_perturb=False, rounds=R)


def summarize_seed(seed: int) -> dict:
    rec = load_or_run(seed)
    native = rec["arms"]["native"]
    final = native["final"]
    rounds = native["rounds"]
    # timeline: elim / first viol / excl relative to alive
    rows = []
    for t, rnd in enumerate(rounds):
        h = rnd["hump"]
        if (
            h.get("violated")
            or h.get("excluded")
            or (h.get("t_elim") is not None and h.get("t_elim") == t)
            or (not h.get("alive") and t <= (h.get("t_elim") or 999) + 2)
        ):
            rows.append(
                {
                    "t": t,
                    "alive": h["alive"],
                    "w_surv": h["w_surv"],
                    "violated": h["violated"],
                    "excluded": h["excluded"],
                    "t_elim": h.get("t_elim"),
                    "t_excl": h.get("t_excl"),
                    "stream_n": h.get("stream_n"),
                    "stat": h.get("stat"),
                    "crit": h.get("crit"),
                }
            )
    t_elim = final["t_elim"]["hump"]
    t_excl = final["t_excl"]["hump"]
    # Did exclusion happen after elimination?
    post_elim_excl = (
        t_elim is not None and t_excl is not None and t_excl > t_elim
    )
    # Evidence continues after prune? Check round after elim still has evidence fields
    evidence_after_elim = None
    if t_elim is not None and t_elim + 1 < len(rounds):
        h1 = rounds[t_elim + 1]["hump"]
        evidence_after_elim = {
            "t": t_elim + 1,
            "alive": h1["alive"],
            "stream_n": h1.get("stream_n"),
            "violated": h1["violated"],
            "excluded": h1["excluded"],
            "has_stat_fields": "stat" in h1 or h1.get("stream_n") is not None,
        }

    # Recompute chi2 from sites to verify logged t_excl
    batches = sites_by_round(native["sites"])
    trace = recompute_hump(seed, batches)
    first_v = next((r["t"] for r in trace if r["violated"]), None)
    first_x = next((r["t"] for r in trace if r["excluded"]), None)
    match = (first_x == t_excl) or (first_x is None and t_excl is None)

    # At t_elim: was excluded already?
    at_elim = None
    if t_elim is not None:
        at_elim = {
            "t": t_elim,
            "alive": rounds[t_elim]["hump"]["alive"],
            "excluded": rounds[t_elim]["hump"]["excluded"],
            "violated": rounds[t_elim]["hump"]["violated"],
            "w_surv": rounds[t_elim]["hump"]["w_surv"],
            "fi_operational": (
                t_elim is not None
                and (t_excl is None or t_elim < t_excl)
                and not rounds[t_elim]["hump"]["excluded"]
            ),
        }

    return {
        "seed": seed,
        "source": "formal_disk" if seed <= 20 else "live_extra_mc",
        "final_excluded": bool(final["excluded"]["hump"]),
        "t_elim": t_elim,
        "t_excl": t_excl,
        "exclusion_after_elim": post_elim_excl,
        "evidence_continues_after_elim": evidence_after_elim,
        "recompute_first_violated": first_v,
        "recompute_first_excluded": first_x,
        "recompute_matches_logged_t_excl": match,
        "at_elim": at_elim,
        "notable_rounds": rows,
        "recompute_around_excl": [
            r
            for r in trace
            if first_x is not None and abs(r["t"] - first_x) <= 2
        ],
    }


def check_impl() -> dict:
    # ALPHA, crit, PERSIST consistency
    n, p = 30, 3
    crit = evidence_crit(n, p)
    expected = float(chi2.ppf(1.0 - ALPHA_EV, n - p))
    # loop source check: evidence over ALL_FAMILIES regardless of alive
    import inspect
    from pilot_fi_anchor.loop import Arm

    src = inspect.getsource(Arm._update_evidence)
    gates_on_alive = "if self.alive" in src or "alive[h]" in src
    return {
        "ALPHA_EV": ALPHA_EV,
        "PERSIST": PERSIST,
        "crit_n30_p3": crit,
        "crit_matches_chi2_ppf": abs(crit - expected) < 1e-12,
        "df_formula": "n - p",
        "evidence_gated_on_alive": gates_on_alive,
        "evidence_loops_all_families": "for h in ALL_FAMILIES" in src,
        "excluded_rule": "violated and prev_violated",
    }


def seed20_t3() -> dict:
    rec = json.loads((FORMAL / "seed_20.json").read_text(encoding="utf-8"))
    native = rec["arms"]["native"]
    h3 = native["rounds"][3]["hump"]
    batches = sites_by_round(native["sites"])
    trace = recompute_hump(20, batches)
    t3 = trace[3]
    return {
        "logged": {
            "alive": h3["alive"],
            "w_surv": h3["w_surv"],
            "violated": h3["violated"],
            "excluded": h3["excluded"],
            "t_elim": h3.get("t_elim"),
            "t_excl": h3.get("t_excl"),
        },
        "recomputed": t3,
        "met_two_round_exclusion_at_t3": bool(t3["excluded"]),
        "fi_t_elim_lt_t_excl": (
            native["final"]["t_elim"]["hump"] is not None
            and native["final"]["t_excl"]["hump"] is not None
            and native["final"]["t_elim"]["hump"]
            < native["final"]["t_excl"]["hump"]
        ),
        "final_t_elim": native["final"]["t_elim"]["hump"],
        "final_t_excl": native["final"]["t_excl"]["hump"],
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    impl = check_impl()
    print("impl:", json.dumps(impl, indent=2))
    details = []
    for s in EXCL_SEEDS:
        print(f"=== seed {s} ===", flush=True)
        d = summarize_seed(s)
        details.append(d)
        print(
            f"  excl={d['final_excluded']} t_elim={d['t_elim']} t_excl={d['t_excl']} "
            f"post_elim={d['exclusion_after_elim']} match={d['recompute_matches_logged_t_excl']}"
        )
        if d["at_elim"]:
            print(f"  at_elim FI_ok={d['at_elim']['fi_operational']} {d['at_elim']}")
    s20 = seed20_t3()
    print("seed20_t3:", json.dumps(s20, indent=2, default=str))

    # Count check vs audit json
    audit = json.loads((OUT / "chi2_reliability_audit.json").read_text(encoding="utf-8"))
    claimed = audit["native_mc"]["excluded_seeds"]
    payload = {
        "count_check": {
            "audit_claimed_excluded_seeds": claimed,
            "verified_seeds": EXCL_SEEDS,
            "count_matches": list(claimed) == list(EXCL_SEEDS),
            "note": (
                "Audit counts final['excluded']['hump'] from formal disk (1-20) "
                "and live run_seed (101-120). Evidence updates ALL families every "
                "round regardless of alive — post-elim background evidence is included."
            ),
        },
        "implementation": impl,
        "exclusion_details": details,
        "seed20_t3": s20,
        "verdict_implication": {
            "counting_bug": False,
            "implementation_bug": not impl["crit_matches_chi2_ppf"]
            or impl["evidence_gated_on_alive"],
            "seed20_fi_still_holds": s20["fi_t_elim_lt_t_excl"]
            and not s20["met_two_round_exclusion_at_t3"],
            "case": (
                "OPERATIONAL_ONLY_calibration_limit"
                if (
                    list(claimed) == list(EXCL_SEEDS)
                    and impl["crit_matches_chi2_ppf"]
                    and not impl["evidence_gated_on_alive"]
                    and s20["fi_t_elim_lt_t_excl"]
                )
                else "NEEDS_CORRECTION"
            ),
        },
    }
    path = OUT / "exclusion_verification.json"
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(f"wrote {path}")
    print("case:", payload["verdict_implication"]["case"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
