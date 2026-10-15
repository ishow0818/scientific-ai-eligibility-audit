#!/usr/bin/env python3
"""Read-only evidence-rule sensitivity on frozen Anchor seeds 1–20.

Denominator = frozen primary FI loss events (Native 78 / Neutral 80).
Recomputes only χ² comparator (FWER × persistence); does not alter frozen files.
"""
from __future__ import annotations

import csv
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from pilot_fi_anchor.config import (  # noqa: E402
    ALPHA_EV,
    FAMILY_ORDER,
    FALSE_FAMILIES,
    N_CAND,
    R,
    SIGMA,
    X_MAX,
    X_MIN,
)
from pilot_fi_anchor.evidence_calibration import evidence_crit  # noqa: E402
from pilot_fi_anchor.fitting import fit  # noqa: E402
from pilot_fi_anchor.mechanisms import FAMILIES  # noqa: E402
from pilot_fi_anchor.rng import fit_rng  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "verification" / "evidence_sensitivity"
OUT.mkdir(parents=True, exist_ok=True)

FWER_LEVELS = (0.025, 0.050, 0.100)
PERSIST_LEVELS = (1, 2, 3)
ARMS = ("native", "neutral")
SEEDS = range(1, 21)


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def alpha_for_fwer(fwer: float) -> float:
    return float(fwer) / (len(FAMILY_ORDER) * R)


def x_of(i: int) -> float:
    return float(X_MIN + (X_MAX - X_MIN) * i / (N_CAND - 1))


def load_seed(seed: int) -> dict:
    return json.loads(
        (ROOT / "outputs" / "pilot_fi_anchor" / f"seed_{seed:02d}.json").read_text(
            encoding="utf-8"
        )
    )


def excl_from_stored_violated(rounds: list[dict], persist: int) -> dict[str, int | None]:
    streak = {h: 0 for h in FAMILY_ORDER}
    t_excl: dict[str, int | None] = {h: None for h in FAMILY_ORDER}
    for row in rounds:
        t = int(row["t"])
        for h in FAMILY_ORDER:
            if t_excl[h] is not None:
                continue
            if bool(row[h]["violated"]):
                streak[h] += 1
            else:
                streak[h] = 0
            if streak[h] >= persist:
                t_excl[h] = t
    return t_excl


def recompute_violations_by_round(sites: list[dict], seed: int, alpha: float) -> list[dict[str, bool]]:
    """Return per-round violated flags using original fit_rng CRN."""
    by: dict[int, list[dict]] = {}
    for s in sites:
        by.setdefault(int(s["t"]), []).append(s)
    measured: list[int] = []
    ymap: dict[int, float] = {}
    warm = {h: None for h in FAMILY_ORDER}
    rng = fit_rng(seed)
    out: list[dict[str, bool]] = []
    for t in range(0, R + 1):
        for s in by.get(t, []):
            measured.append(int(s["idx"]))
            ymap[int(s["idx"])] = float(s["y"])
        order = sorted(ymap)
        if not order:
            out.append({h: False for h in FAMILY_ORDER})
            continue
        xs = np.asarray([x_of(i) for i in order], dtype=float)
        ys = np.asarray([ymap[i] for i in order], dtype=float)
        n = len(order)
        flags = {}
        for h in FAMILY_ORDER:
            mech = FAMILIES[h]
            z = fit(mech, xs, ys, warm=warm[h], rng=rng)
            warm[h] = z
            theta = mech.from_fit(z)
            rss = float(np.sum((mech.predict(xs, theta) - ys) ** 2))
            crit = evidence_crit(n, mech.p, alpha=alpha)
            flags[h] = bool(rss / (SIGMA * SIGMA) > crit)
        out.append(flags)
    return out


def excl_from_flags(flags_by_t: list[dict[str, bool]], persist: int) -> dict[str, int | None]:
    streak = {h: 0 for h in FAMILY_ORDER}
    t_excl: dict[str, int | None] = {h: None for h in FAMILY_ORDER}
    for t, flags in enumerate(flags_by_t):
        for h in FAMILY_ORDER:
            if t_excl[h] is not None:
                continue
            if flags[h]:
                streak[h] += 1
            else:
                streak[h] = 0
            if streak[h] >= persist:
                t_excl[h] = t
    return t_excl


def frozen_fi_events(rec: dict, arm: str) -> list[tuple[int, str, int]]:
    """(seed, family, t_elim) for false families with FI under frozen primary."""
    final = rec["arms"][arm]["final"]
    seed = int(rec["seed"])
    out = []
    for h in FALSE_FAMILIES:
        te = final["t_elim"].get(h)
        tx = final["t_excl"].get(h)
        if te is None:
            continue
        if tx is None or te < tx:
            out.append((seed, h, int(te)))
    return out


def main() -> int:
    assert abs(ALPHA_EV - alpha_for_fwer(0.05)) < 1e-15

    # --- Primary: 200 stored exclusion times via frozen violated + persist=2 ---
    mismatches = []
    n_ok = 0
    for seed in SEEDS:
        rec = load_seed(seed)
        for arm in ARMS:
            got = excl_from_stored_violated(rec["arms"][arm]["rounds"], persist=2)
            exp = {h: rec["arms"][arm]["final"]["t_excl"].get(h) for h in FAMILY_ORDER}
            for h in FAMILY_ORDER:
                if got[h] == exp[h]:
                    n_ok += 1
                else:
                    mismatches.append(
                        {"seed": seed, "arm": arm, "family": h, "got": got[h], "exp": exp[h]}
                    )
    primary_ok = n_ok == 200

    # Precompute violation streams for each FWER (refit)
    viol_cache: dict[tuple[int, str, float], list[dict[str, bool]]] = {}
    for seed in SEEDS:
        rec = load_seed(seed)
        for arm in ARMS:
            sites = rec["arms"][arm]["sites"]
            for fwer in FWER_LEVELS:
                alpha = alpha_for_fwer(fwer)
                # For frozen FWER=0.05 prefer stored violated flags (exact CRN)
                if abs(fwer - 0.05) < 1e-12:
                    flags = []
                    for row in rec["arms"][arm]["rounds"]:
                        flags.append({h: bool(row[h]["violated"]) for h in FAMILY_ORDER})
                    # Ensure length covers 0..R
                    viol_cache[(seed, arm, fwer)] = flags
                else:
                    viol_cache[(seed, arm, fwer)] = recompute_violations_by_round(
                        sites, seed, alpha
                    )

    expected_table = {
        (0.025, 1, "native"): (27, 16, 27),
        (0.025, 1, "neutral"): (78, 20, 78),
        (0.025, 2, "native"): (78, 20, 27),
        (0.025, 2, "neutral"): (80, 20, 78),
        (0.025, 3, "native"): (78, 20, 27),
        (0.025, 3, "neutral"): (80, 20, 78),
        (0.050, 1, "native"): (26, 15, 26),
        (0.050, 1, "neutral"): (77, 20, 77),
        (0.050, 2, "native"): (78, 20, 26),
        (0.050, 2, "neutral"): (80, 20, 77),
        (0.050, 3, "native"): (78, 20, 26),
        (0.050, 3, "neutral"): (80, 20, 77),
        (0.100, 1, "native"): (26, 15, 26),
        (0.100, 1, "neutral"): (76, 20, 76),
        (0.100, 2, "native"): (78, 20, 26),
        (0.100, 2, "neutral"): (80, 20, 76),
        (0.100, 3, "native"): (78, 20, 26),
        (0.100, 3, "neutral"): (80, 20, 76),
    }

    event_rows = []
    summary_rows = []
    comparisons = []
    n_match = 0

    for fwer in FWER_LEVELS:
        alpha = alpha_for_fwer(fwer)
        for persist in PERSIST_LEVELS:
            for arm in ARMS:
                early = 0
                no_single = 0
                seeds_hit: set[int] = set()
                frozen_denom = 0
                for seed in SEEDS:
                    rec = load_seed(seed)
                    events = frozen_fi_events(rec, arm)
                    frozen_denom += len(events)
                    flags = viol_cache[(seed, arm, fwer)]
                    t_excl = excl_from_flags(flags, persist)
                    for _, h, t_elim in events:
                        tx = t_excl.get(h)
                        is_early = tx is None or t_elim < tx
                        # single-round violation at loss under this FWER stream
                        viol_at_loss = False
                        if 0 <= t_elim < len(flags):
                            viol_at_loss = bool(flags[t_elim][h])
                        if is_early:
                            early += 1
                            seeds_hit.add(seed)
                            if not viol_at_loss:
                                no_single += 1
                        event_rows.append(
                            {
                                "fwer": fwer,
                                "persist": persist,
                                "arm": arm,
                                "seed": seed,
                                "family": h,
                                "t_elim": t_elim,
                                "t_excl_recomputed": tx,
                                "early_exit": is_early,
                                "no_single_round_violation_at_loss": bool(
                                    is_early and not viol_at_loss
                                ),
                            }
                        )
                exp_denom = 78 if arm == "native" else 80
                row = {
                    "fwer": fwer,
                    "persist": persist,
                    "arm": arm,
                    "early_exits": early,
                    "frozen_fi_denominator": frozen_denom,
                    "early_over_loss": f"{early}/{exp_denom}",
                    "seeds_ge1": len(seeds_hit),
                    "seeds_ge1_over_20": f"{len(seeds_hit)}/20",
                    "no_single_round_violation_at_loss": no_single,
                    "alpha_ev": alpha,
                }
                summary_rows.append(row)
                key = (float(fwer), int(persist), arm)
                exp = expected_table[key]
                got = (early, len(seeds_hit), no_single)
                ok = got == exp and frozen_denom == exp_denom
                if ok:
                    n_match += 1
                comparisons.append(
                    {
                        "setting": list(key),
                        "expected": list(exp),
                        "got": list(got),
                        "frozen_denom": frozen_denom,
                        "match": ok,
                    }
                )

    sum_path = OUT / "sensitivity_summary.csv"
    ev_path = OUT / "sensitivity_events.csv"
    with sum_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(summary_rows[0].keys()))
        w.writeheader()
        w.writerows(summary_rows)
    with ev_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(event_rows[0].keys()))
        w.writeheader()
        w.writerows(event_rows)

    status = (
        "PASS"
        if primary_ok and n_match == 18
        else ("PARTIAL" if primary_ok else "FAIL")
    )
    report = {
        "status": status,
        "primary_200_exclusion_times": {
            "n_match": n_ok,
            "n_checked": 200,
            "pass": primary_ok,
            "mismatches": mismatches[:20],
            "method": "stored violated flags + persist=2",
        },
        "table_rows_matched": n_match,
        "table_rows_total": 18,
        "comparisons": comparisons,
        "interpretation": (
            "Supports qualitative robustness that eligibility loss can precede "
            "operational exclusion under neighboring operational choices; does NOT "
            "prove chi-square reference calibration or Type-I/FWER validity under "
            "adaptive nonlinear fitting."
        ),
        "input_hashes": {
            f"outputs/pilot_fi_anchor/seed_{s:02d}.json": sha256(
                ROOT / "outputs" / "pilot_fi_anchor" / f"seed_{s:02d}.json"
            )
            for s in SEEDS
        },
        "script_sha256": sha256(Path(__file__)),
        "outputs": {
            "sensitivity_summary.csv": str(sum_path.relative_to(ROOT)),
            "sensitivity_events.csv": str(ev_path.relative_to(ROOT)),
        },
    }
    (OUT / "sensitivity_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    md = [
        "# Evidence-rule sensitivity report",
        "",
        f"Status: **{status}**",
        "",
        f"- Primary FWER=0.05 / persist=2 exclusion times: {n_ok}/200",
        f"- Manuscript 18-row table: {n_match}/18",
        "",
        report["interpretation"],
        "",
        "## Rows",
        "",
    ]
    for row in summary_rows:
        md.append(
            f"- FWER={row['fwer']} persist={row['persist']} {row['arm']}: "
            f"{row['early_over_loss']}, seeds≥1={row['seeds_ge1_over_20']}, "
            f"no_single={row['no_single_round_violation_at_loss']}"
        )
    (OUT / "sensitivity_report.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": status,
                "primary_200": n_ok,
                "table_match": n_match,
                "mismatched": [c for c in comparisons if not c["match"]],
            },
            indent=2,
        )
    )
    return 0 if status != "FAIL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
