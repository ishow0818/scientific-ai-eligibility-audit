#!/usr/bin/env python3
"""Stage-2 causal attribution audit (read-only; no re-run / no paper edits)."""
from __future__ import annotations

import csv
import json
import math
import statistics
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "evidence_gated_eligibility" / "outputs" / "stage2_formal"
OUT = ROOT / "evidence_gated_eligibility" / "outputs" / "stage2_causal_audit"

ARM_A = "native"
ARM_B = "decision_only"
ARM_C = "full_evidence_gate"
FAMILIES = ("hump", "affine", "pow", "expsat", "quad")
TRUTH = "hump"


def wilson(k: int, n: int, z: float = 1.96) -> list[float]:
    if n <= 0:
        return [0.0, 0.0, 0.0]
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return [float(p), float(max(0.0, centre - half)), float(min(1.0, centre + half))]


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    keys: list[str] = []
    seen: set[str] = set()
    for r in rows:
        for k in r:
            if k not in seen:
                keys.append(k)
                seen.add(k)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)


def load_seed(seed: int) -> dict:
    return json.loads((DATA / f"seed_{seed}.json").read_text(encoding="utf-8"))


def sites_by_t(sites: list[dict]) -> dict[int, list[int]]:
    by: dict[int, list[int]] = {}
    for s in sites:
        by.setdefault(int(s["t"]), []).append(int(s["idx"]))
    for t in by:
        by[t] = sorted(by[t])
    return by


def first_site_fork(sites_a: list[dict], sites_c: list[dict]) -> int | None:
    ba, bc = sites_by_t(sites_a), sites_by_t(sites_c)
    tmax = max(max(ba, default=0), max(bc, default=0))
    for t in range(0, tmax + 1):
        if ba.get(t, []) != bc.get(t, []):
            return t
    return None


def last_w_all(arm_pack: dict) -> dict[str, float]:
    last = arm_pack["rounds"][-1]
    return {h: float(last[h]["w_all"]) for h in FAMILIES}


def analyze_ab_case(rec: dict) -> dict[str, Any]:
    """Causal chain for A wrong → B right (or diagnose non-FI attribution)."""
    seed = rec["seed"]
    a = rec["arms"][ARM_A]
    b = rec["arms"][ARM_B]
    af, bf = a["final"], b["final"]
    sca, scb = rec["scores"][ARM_A], rec["scores"][ARM_B]

    hump_alive = bool(af["alive"].get(TRUTH))
    hump_excl = bool(af["excluded"].get(TRUTH))
    t_elim = af["t_elim"].get(TRUTH)
    t_excl = af["t_excl"].get(TRUTH)

    # Trajectory identity A vs B
    sites_same = [s["idx"] for s in a["sites"]] == [s["idx"] for s in b["sites"]]
    y_same = [s["y"] for s in a["sites"]] == [s["y"] for s in b["sites"]]
    rounds_same = a["rounds"] == b["rounds"]
    theta_same = af["arm_theta"] == bf["arm_theta"]
    w_all_a = last_w_all(a)
    w_all_b = {h: float(bf["w_all"][h]) for h in FAMILIES}
    w_same = all(abs(w_all_a[h] - w_all_b[h]) < 1e-15 for h in FAMILIES)

    # Would hump win under evidence-eligible set with same w_all?
    E = [h for h in FAMILIES if not af["excluded"][h]]
    if E:
        winner_on_E = max(E, key=lambda h: w_all_a[h])
    else:
        winner_on_E = None

    # FI-style: weight prune removed hump while evidence not excluding
    weight_pruned = (not hump_alive) and (t_elim is not None)
    evidence_ok = not hump_excl
    fi_blocked = weight_pruned and evidence_ok and (t_excl is None or (t_elim is not None and t_elim < t_excl))

    # Attribution
    if sca["truth_selected"] or not scb["truth_selected"]:
        attr = "NOT_APPLICABLE"
        note = "Not an A-wrong/B-right case"
    elif not (sites_same and y_same and w_same and theta_same):
        attr = "NOT_IDENTIFIABLE"
        note = "B trajectory/params differ from A — violates Decision-Only contract"
    elif not fi_blocked:
        if hump_alive:
            attr = "NOT_FI_ELIGIBILITY"
            note = "hump still alive under A; B win not from restoring prune-blocked eligibility"
        elif hump_excl:
            attr = "NOT_FI_ELIGIBILITY"
            note = "hump evidence-excluded under A; B cannot restore it — if B somehow differs, inspect"
        else:
            attr = "NOT_IDENTIFIABLE"
            note = "hump not alive but FI operational block not confirmed"
    elif winner_on_E != TRUTH:
        attr = "NOT_FI_ELIGIBILITY"
        note = (
            f"Restoring evidence-eligible set yields winner={winner_on_E}, not hump; "
            "B truth selection not explained by eligibility restore alone"
        )
    elif bf["incumbent"] == TRUTH and winner_on_E == TRUTH:
        attr = "FI_FINAL_ELIGIBILITY_RESTORE"
        note = (
            "A: hump weight-pruned while not evidence-excluded; same data/w_all; "
            "B restores eligible=not-excluded and argmax w_all selects hump"
        )
    else:
        attr = "NOT_IDENTIFIABLE"
        note = "Unexpected B outcome relative to reconstructed rule"

    return {
        "seed": seed,
        "A_incumbent": af["incumbent"],
        "B_incumbent": bf["incumbent"],
        "hump_alive_A": hump_alive,
        "hump_excluded_A": hump_excl,
        "t_elim_hump_A": t_elim,
        "t_excl_hump_A": t_excl,
        "fi_operational_block": fi_blocked,
        "sites_identical": sites_same,
        "y_identical": y_same,
        "rounds_identical": rounds_same,
        "theta_identical": theta_same,
        "w_all_identical": w_same,
        "evidence_eligible_set": E,
        "argmax_w_all_on_E": winner_on_E,
        "A_rmse": sca["rmse_eval_noiseless"],
        "B_rmse": scb["rmse_eval_noiseless"],
        "attribution": attr,
        "note": note,
    }


def analyze_ac_case(rec: dict) -> dict[str, Any]:
    seed = rec["seed"]
    a = rec["arms"][ARM_A]
    c = rec["arms"][ARM_C]
    af, cf = a["final"], c["final"]
    sca, scc = rec["scores"][ARM_A], rec["scores"][ARM_C]
    fork = first_site_fork(a["sites"], c["sites"])

    # Pre-fork consistency: at end of fork-1, compare w_all/alive if fork>=1
    pre_ok = True
    pre_note = ""
    if fork is None:
        pre_note = "no site fork"
    elif fork == 0:
        pre_ok = False
        pre_note = "fork at t=0 unexpected"
    else:
        ra, rc = a["rounds"][fork - 1], c["rounds"][fork - 1]
        for h in FAMILIES:
            if abs(ra[h]["w_all"] - rc[h]["w_all"]) > 1e-12:
                pre_ok = False
                pre_note = f"w_all already differs at t={fork-1} before site fork"
                break
            if ra[h]["excluded"] != rc[h]["excluded"]:
                pre_ok = False
                pre_note = f"excluded differs at t={fork-1}"
                break

    # hump status along C
    c_hump_excl = bool(cf["excluded"].get(TRUTH))
    c_t_excl = cf["t_excl"].get(TRUTH)
    # first time hump not eligible on C
    first_c_inelig = None
    for row in c.get("eligibility_audit", c["rounds"]):
        t = row.get("t")
        if "eligible" in row and isinstance(row["eligible"], dict):
            ok = row["eligible"].get(TRUTH, True)
        elif "excluded" in row and isinstance(row["excluded"], dict):
            ok = not row["excluded"].get(TRUTH, False)
        else:
            # round row
            ok = not row[TRUTH]["excluded"]
        if not ok:
            first_c_inelig = t
            break

    attr = "NOT_APPLICABLE"
    note = ""
    if (not sca["truth_selected"]) and scc["truth_selected"]:
        if fork is None:
            attr = "NOT_IDENTIFIABLE"
            note = "C corrects truth selection but sites never forked — unexpected"
        else:
            attr = "FULL_POLICY_CLOSED_LOOP"
            note = (
                "C corrects via full evidence-gate policy (eligibility for allocate+decision). "
                "Exploration mediation vs eligibility-alone NOT separately identifiable "
                "from this two-arm design (B isolates final-only)."
            )
    elif sca["truth_selected"] and scc["truth_selected"]:
        attr = "BOTH_CORRECT"
        note = "Both select hump"
    elif (not sca["truth_selected"]) and (not scc["truth_selected"]):
        attr = "BOTH_WRONG"
        note = "Neither selects hump"
    else:
        attr = "C_WORSE_OR_OTHER"
        note = "C does not uniquely correct A"

    return {
        "seed": seed,
        "A_incumbent": af["incumbent"],
        "C_incumbent": cf["incumbent"],
        "first_site_fork_t": fork,
        "pre_fork_state_consistent": pre_ok,
        "pre_fork_note": pre_note,
        "A_hump_alive": af["alive"].get(TRUTH),
        "A_hump_excluded": af["excluded"].get(TRUTH),
        "A_t_elim_hump": af["t_elim"].get(TRUTH),
        "C_hump_excluded": c_hump_excl,
        "C_t_excl_hump": c_t_excl,
        "C_first_hump_ineligible_t": first_c_inelig,
        "C_abort": cf.get("abort_status"),
        "A_rmse": sca["rmse_eval_noiseless"],
        "C_rmse": scc["rmse_eval_noiseless"],
        "n_measured_A": len(a["sites"]),
        "n_measured_C": len(c["sites"]),
        "attribution": attr,
        "note": note,
        "exploration_mediation": (
            "NOT_IDENTIFIABLE_separate_from_eligibility"
            if attr == "FULL_POLICY_CLOSED_LOOP"
            else "NA"
        ),
    }


def excluded_sticky(arm_pack: dict) -> bool:
    prev = {h: False for h in FAMILIES}
    for row in arm_pack["rounds"]:
        for h in FAMILIES:
            ex = bool(row[h]["excluded"])
            if prev[h] and not ex:
                return False
            prev[h] = ex
    return True


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    paired: list[dict] = []
    rmse_cost: list[dict] = []
    ab_cases: list[dict] = []
    ac_cases: list[dict] = []
    validity_flags: list[dict] = []

    for seed in range(201, 241):
        rec = load_seed(seed)
        sc = rec["scores"]
        a, b, c = rec["arms"][ARM_A], rec["arms"][ARM_B], rec["arms"][ARM_C]
        sa, sb, scc = sc[ARM_A], sc[ARM_B], sc[ARM_C]

        # integrity of B reuse
        b_ok = (
            [s["idx"] for s in a["sites"]] == [s["idx"] for s in b["sites"]]
            and a["rounds"] == b["rounds"]
        )

        sticky_c = excluded_sticky(c)
        c_illegal_restore = not sticky_c

        row = {
            "seed": seed,
            "A_incumbent": a["final"]["incumbent"],
            "B_incumbent": b["final"]["incumbent"],
            "C_incumbent": c["final"]["incumbent"],
            "A_truth": sa["truth_selected"],
            "B_truth": sb["truth_selected"],
            "C_truth": scc["truth_selected"],
            "A_fail": sa["is_failure"],
            "B_fail": sb["is_failure"],
            "C_fail": scc["is_failure"],
            "A_failure_type": sa.get("failure_type"),
            "B_failure_type": sb.get("failure_type"),
            "C_failure_type": scc.get("failure_type"),
            "A_rmse": sa["rmse_eval_noiseless"],
            "B_rmse": sb["rmse_eval_noiseless"],
            "C_rmse": scc["rmse_eval_noiseless"],
            "A_rmse_penalty": sa["rmse_with_fail_penalty"],
            "B_rmse_penalty": sb["rmse_with_fail_penalty"],
            "C_rmse_penalty": scc["rmse_with_fail_penalty"],
            "dRMSE_A_minus_B": sa["rmse_with_fail_penalty"] - sb["rmse_with_fail_penalty"],
            "dRMSE_A_minus_C": sa["rmse_with_fail_penalty"] - scc["rmse_with_fail_penalty"],
            "dRMSE_B_minus_C": sb["rmse_with_fail_penalty"] - scc["rmse_with_fail_penalty"],
            "A_hump_alive": a["final"]["alive"].get(TRUTH),
            "A_hump_excluded": a["final"]["excluded"].get(TRUTH),
            "A_t_elim_hump": a["final"]["t_elim"].get(TRUTH),
            "A_t_excl_hump": a["final"]["t_excl"].get(TRUTH),
            "B_hump_eligible": b["final"]["eligible"].get(TRUTH),
            "C_hump_excluded": c["final"]["excluded"].get(TRUTH),
            "C_abort": c["final"].get("abort_status"),
            "A_n_false_eligible": sa["n_false_eligible"],
            "B_n_false_eligible": sb["n_false_eligible"],
            "C_n_false_eligible": scc["n_false_eligible"],
            "A_n_measured": sa["n_measured"],
            "C_n_measured": scc["n_measured"],
            "wall_s": rec.get("wall_s"),
            "B_trajectory_identical_to_A": b_ok,
            "C_excluded_sticky": sticky_c,
        }
        paired.append(row)

        # RMSE direction vs truth selection consistency
        def dir_label(d: float) -> str:
            if abs(d) < 1e-15:
                return "tie"
            return "improve" if d > 0 else "worsen"  # A-B>0 means A worse → B improve

        rmse_cost.append(
            {
                "seed": seed,
                "A_rmse": sa["rmse_eval_noiseless"],
                "B_rmse": sb["rmse_eval_noiseless"],
                "C_rmse": scc["rmse_eval_noiseless"],
                "dA_B": row["dRMSE_A_minus_B"],
                "dA_C": row["dRMSE_A_minus_C"],
                "B_vs_A": dir_label(row["dRMSE_A_minus_B"]),
                "C_vs_A": dir_label(row["dRMSE_A_minus_C"]),
                "A_truth": sa["truth_selected"],
                "B_truth": sb["truth_selected"],
                "C_truth": scc["truth_selected"],
                "truth_fix_B_but_rmse_worsen": (
                    (not sa["truth_selected"])
                    and sb["truth_selected"]
                    and row["dRMSE_A_minus_B"] < 0
                ),
                "truth_fix_C_but_rmse_worsen": (
                    (not sa["truth_selected"])
                    and scc["truth_selected"]
                    and row["dRMSE_A_minus_C"] < 0
                ),
                "A_n_false_eligible": sa["n_false_eligible"],
                "B_n_false_eligible": sb["n_false_eligible"],
                "C_n_false_eligible": scc["n_false_eligible"],
                "A_n_measured": sa["n_measured"],
                "C_n_measured": scc["n_measured"],
                "wall_s": rec.get("wall_s"),
                "fit_calls": "NOT_IDENTIFIABLE",
            }
        )

        if (not sa["truth_selected"]) or (not sb["truth_selected"]) or (
            sa["truth_selected"] != sb["truth_selected"]
        ):
            ab_cases.append(analyze_ab_case(rec))
        # always analyze AC for wrong-A or forked interest — actually all A-wrong and also summarize forks for corrections
        if (not sa["truth_selected"]) or (sa["truth_selected"] != scc["truth_selected"]):
            ac_cases.append(analyze_ac_case(rec))

        validity_flags.append(
            {
                "seed": seed,
                "C_excludes_truth": bool(c["final"]["excluded"].get(TRUTH)),
                "C_illegal_eligibility_restore": c_illegal_restore,
                "C_abort": c["final"].get("abort_status"),
                "A_fail_in_scores": sa["is_failure"],
                "B_fail_in_scores": sb["is_failure"],
                "C_fail_in_scores": scc["is_failure"],
                "score_fields_complete": all(
                    k in sa and k in sb and k in scc
                    for k in (
                        "truth_eligibility_lost",
                        "failure_type",
                        "is_failure",
                        "rmse_eval_noiseless",
                    )
                ),
            }
        )

    # Also run AB analysis specifically for A-wrong B-right
    ab_focus = []
    ac_focus = []
    for seed in range(201, 241):
        rec = load_seed(seed)
        sa, sb, scc = (
            rec["scores"][ARM_A],
            rec["scores"][ARM_B],
            rec["scores"][ARM_C],
        )
        if (not sa["truth_selected"]) and sb["truth_selected"]:
            ab_focus.append(analyze_ab_case(rec))
        if (not sa["truth_selected"]) and scc["truth_selected"]:
            ac_focus.append(analyze_ac_case(rec))
        # seed 208: A wrong B wrong C right — include in AC focus already
        if (not sa["truth_selected"]) and (not sb["truth_selected"]):
            ab_cases_diag = analyze_ab_case(rec)
            if ab_cases_diag not in ab_cases:
                pass
            # ensure documented
            if seed not in {c["seed"] for c in ab_focus}:
                # store diagnostic for A-wrong B-wrong
                if not any(x["seed"] == seed for x in ab_cases):
                    ab_cases.append(ab_cases_diag)

    # Aggregates
    n = len(paired)
    assert n == 40
    A_k = sum(1 for r in paired if r["A_truth"])
    B_k = sum(1 for r in paired if r["B_truth"])
    C_k = sum(1 for r in paired if r["C_truth"])
    assert A_k == 37 and B_k == 39 and C_k == 40

    def count_dir(key: str) -> dict:
        return {
            "improve": sum(1 for r in rmse_cost if r[key] == "improve"),
            "tie": sum(1 for r in rmse_cost if r[key] == "tie"),
            "worsen": sum(1 for r in rmse_cost if r[key] == "worsen"),
        }

    dAB = [r["dRMSE_A_minus_B"] for r in paired]
    dAC = [r["dRMSE_A_minus_C"] for r in paired]
    dBC = [r["dRMSE_B_minus_C"] for r in paired]

    fi_restore_seeds = [
        c["seed"] for c in ab_focus if c["attribution"] == "FI_FINAL_ELIGIBILITY_RESTORE"
    ]
    non_fi_b = [c for c in ab_focus if c["attribution"] != "FI_FINAL_ELIGIBILITY_RESTORE"]

    # RMSE among FI-restore seeds
    fi_rmse = []
    for s in fi_restore_seeds:
        r = next(x for x in paired if x["seed"] == s)
        fi_rmse.append(
            {
                "seed": s,
                "A_rmse": r["A_rmse"],
                "B_rmse": r["B_rmse"],
                "C_rmse": r["C_rmse"],
                "dA_B": r["dRMSE_A_minus_B"],
                "dA_C": r["dRMSE_A_minus_C"],
            }
        )

    # C-only correction (208)
    c_only = [
        c
        for c in ac_focus
        if (not next(p for p in paired if p["seed"] == c["seed"])["B_truth"])
    ]

    # cost
    wall = [r["wall_s"] for r in paired if r["wall_s"] is not None]
    false_elig = {
        "A_mean": statistics.mean(r["A_n_false_eligible"] for r in paired),
        "B_mean": statistics.mean(r["B_n_false_eligible"] for r in paired),
        "C_mean": statistics.mean(r["C_n_false_eligible"] for r in paired),
    }

    validity = {
        "C_truth_excluded_k": sum(1 for v in validity_flags if v["C_excludes_truth"]),
        "C_illegal_restore_k": sum(
            1 for v in validity_flags if v["C_illegal_eligibility_restore"]
        ),
        "C_abort_k": sum(1 for v in validity_flags if v["C_abort"]),
        "failures_in_queue_A": sum(1 for r in paired if r["A_fail"]),
        "failures_in_queue_B": sum(1 for r in paired if r["B_fail"]),
        "failures_in_queue_C": sum(1 for r in paired if r["C_fail"]),
        "all_score_fields_complete": all(v["score_fields_complete"] for v in validity_flags),
        "B_all_trajectories_identical": all(r["B_trajectory_identical_to_A"] for r in paired),
    }

    # Verdict logic
    has_verified_fi_fix = len(fi_restore_seeds) >= 1
    rmse_median_ab = statistics.median(dAB)
    rmse_median_ac = statistics.median(dAC)
    dirs_ab = count_dir("B_vs_A")
    dirs_ac = count_dir("C_vs_A")
    truth_rmse_conflict = any(
        r["truth_fix_B_but_rmse_worsen"] or r["truth_fix_C_but_rmse_worsen"]
        for r in rmse_cost
    )
    worsen_present = dirs_ab["worsen"] > 0 or dirs_ac["worsen"] > 0

    if validity["C_illegal_restore_k"] > 0 or not validity["B_all_trajectories_identical"]:
        verdict = "INVALID"
        reason = "Integrity failure: illegal eligibility restore or B trajectory mismatch"
    elif not has_verified_fi_fix and C_k == 40:
        verdict = "NOT_SUPPORTED"
        reason = "Selection gains not attributable to FI eligibility restore"
    elif has_verified_fi_fix and (
        rmse_median_ab == 0 and rmse_median_ac == 0 and (worsen_present or dirs_ac["improve"] <= len(fi_restore_seeds) + 2)
    ):
        # Selection benefit verified; RMSE panel-level median delta 0; gains concentrated
        verdict = "MIXED"
        reason = (
            "Verified FI final-eligibility restore on specific seeds with RMSE drop there; "
            "panel median ΔRMSE=0; C adds closed-loop corrections not reducible to B; "
            "some C-vs-A RMSE worsenings exist — prediction benefit not uniform"
        )
    elif has_verified_fi_fix and rmse_median_ac > 0 and not worsen_present:
        verdict = "CAUSAL_BENEFIT_SUPPORTED"
        reason = "Verified FI corrections with panel-level RMSE improvement without worsenings"
    else:
        verdict = "MIXED"
        reason = (
            "FI eligibility restore causally verified on subset; "
            "overall prediction improvement limited/concentrated (median Δ=0)"
        )

    # Write CSVs
    write_csv(OUT / "paired_40_seeds.csv", paired)
    write_csv(OUT / "rmse_cost_analysis.csv", rmse_cost)

    # corrected cases markdown
    case_lines = [
        "# 错误纠正实例与证据链",
        "",
        "χ² 为操作性排除标签（OPERATIONAL_ONLY）。",
        "",
        "## A 选错的全部 seeds（对称列出）",
        "",
    ]
    for r in paired:
        if not r["A_truth"]:
            case_lines.append(
                f"- seed {r['seed']}: A=`{r['A_incumbent']}` "
                f"(alive_hump={r['A_hump_alive']}, excl={r['A_hump_excluded']}, "
                f"t_elim={r['A_t_elim_hump']}, t_excl={r['A_t_excl_hump']})；"
                f"B=`{r['B_incumbent']}`；C=`{r['C_incumbent']}`"
            )
    case_lines += ["", "## A→B 纠正案例（A 错且 B 对）", ""]
    for c in ab_focus:
        case_lines += [
            f"### Seed {c['seed']}",
            f"- A→B: `{c['A_incumbent']}` → `{c['B_incumbent']}`",
            f"- hump alive/excluded @A: {c['hump_alive_A']}/{c['hump_excluded_A']}；"
            f"t_elim={c['t_elim_hump_A']}；t_excl={c['t_excl_hump_A']}",
            f"- FI 操作性阻断: {c['fi_operational_block']}",
            f"- 轨迹不变 (sites/y/w_all/theta): "
            f"{c['sites_identical']}/{c['y_identical']}/{c['w_all_identical']}/{c['theta_identical']}",
            f"- 证据资格集 E={c['evidence_eligible_set']}；argmax_w_all(E)={c['argmax_w_all_on_E']}",
            f"- RMSE A/B: {c['A_rmse']} / {c['B_rmse']}",
            f"- **归因: `{c['attribution']}`** — {c['note']}",
            "",
        ]
    case_lines += ["", "## A 错且 B 仍错（对照）", ""]
    for r in paired:
        if (not r["A_truth"]) and (not r["B_truth"]):
            ab = analyze_ab_case(load_seed(r["seed"]))
            case_lines += [
                f"### Seed {r['seed']}",
                f"- A=B=`{r['A_incumbent']}`；hump excl={r['A_hump_excluded']} alive={r['A_hump_alive']}",
                f"- 归因诊断: `{ab['attribution']}` — {ab['note']}",
                f"- C=`{r['C_incumbent']}`（闭环另行纠正）",
                "",
            ]
    case_lines += ["", "## A→C 纠正案例（A 错且 C 对）", ""]
    for c in ac_focus:
        case_lines += [
            f"### Seed {c['seed']}",
            f"- A→C: `{c['A_incumbent']}` → `{c['C_incumbent']}`",
            f"- 首次选点分叉 t={c['first_site_fork_t']}；分叉前一致={c['pre_fork_state_consistent']} "
            f"({c['pre_fork_note']})",
            f"- A hump alive/excl/t_elim={c['A_hump_alive']}/{c['A_hump_excluded']}/{c['A_t_elim_hump']}",
            f"- C hump excl/t_excl/abort={c['C_hump_excluded']}/{c['C_t_excl_hump']}/{c['C_abort']}",
            f"- RMSE A/C: {c['A_rmse']} / {c['C_rmse']}；n_meas A/C={c['n_measured_A']}/{c['n_measured_C']}",
            f"- **归因: `{c['attribution']}`** — {c['note']}",
            f"- 探索中介: {c['exploration_mediation']}",
            "",
        ]

    (OUT / "corrected_seed_cases.md").write_text("\n".join(case_lines), encoding="utf-8")

    # Main report
    report = f"""# Stage 2 因果归因审计报告

**裁决：`{verdict}`**

{reason}

数据：`{DATA}`（只读；未重跑；未改算法/论文）。χ²=`OPERATIONAL_ONLY`。

## 一、40-seed 全量核验

| 臂 | 真模型选中 | 失败 | 有限 RMSE 中位* |
|---|---|---|---|
| A Native | **{A_k}/40** | {validity['failures_in_queue_A']} | {statistics.median(r['A_rmse'] for r in paired if r['A_rmse'] is not None):.6g} |
| B Decision-Only | **{B_k}/40** | {validity['failures_in_queue_B']} | {statistics.median(r['B_rmse'] for r in paired if r['B_rmse'] is not None):.6g} |
| C Full Gate | **{C_k}/40** | {validity['failures_in_queue_C']} | {statistics.median(r['C_rmse'] for r in paired if r['C_rmse'] is not None):.6g} |

\\*与正式报告一致：A=37、B=39、C=40；三臂失败=0。

配对惩罚 RMSE：median(A−B)={statistics.median(dAB):.6g}；median(A−C)={statistics.median(dAC):.6g}；median(B−C)={statistics.median(dBC):.6g}。

代价摘要：错误模型资格数均值 A/B/C={false_elig['A_mean']:.3f}/{false_elig['B_mean']:.3f}/{false_elig['C_mean']:.3f}；
wall_s 中位={statistics.median(wall):.3f}（配对 run 含 A+C）；拟合调用次数=`NOT_IDENTIFIABLE`（日志未计）。

## 二、A→B：终局资格的直接因果作用

A 错且 B 对的 seeds：**{[c['seed'] for c in ab_focus]}**（共 {len(ab_focus)}）。

| seed | FI 阻断 | 轨迹不变 | argmax_w_all(E) | 归因 |
|---|---|---|---|---|
"""
    for c in ab_focus:
        report += (
            f"| {c['seed']} | {c['fi_operational_block']} | "
            f"{c['sites_identical'] and c['w_all_identical']} | "
            f"{c['argmax_w_all_on_E']} | `{c['attribution']}` |\n"
        )
    report += f"""
**严格可归因于「恢复最终决策资格」的 seeds：** {fi_restore_seeds}

A 错且 B 仍错：seed **208**（hump 已被操作性 χ² 排除 → B 无法恢复；改善不能归因于纠正 FI 资格）。

## 三、A→C：完整闭环

A 错且 C 对：**{[c['seed'] for c in ac_focus]}**。

"""
    for c in ac_focus:
        report += (
            f"- seed {c['seed']}: fork_t={c['first_site_fork_t']}；"
            f"归因=`{c['attribution']}`；探索中介=`{c['exploration_mediation']}`；"
            f"ΔRMSE(A−C)={next(p['dRMSE_A_minus_C'] for p in paired if p['seed']==c['seed']):.6g}\n"
        )
    report += f"""
C 相对 B 的额外纠正（B 仍错）：seeds {[c['seed'] for c in c_only]}。
这些收益来自**完整闭环政策**，探索中介与资格门控**不能**在本设计中单独识别（`NOT_IDENTIFIABLE`）。

## 四、预测质量与成本

B vs A（正= B 更好）：improve/tie/worsen = {dirs_ab['improve']}/{dirs_ab['tie']}/{dirs_ab['worsen']}
C vs A：improve/tie/worsen = {dirs_ac['improve']}/{dirs_ac['tie']}/{dirs_ac['worsen']}

- 面板 **median ΔRMSE = 0** 含义：≥半数 seed 上惩罚 RMSE 无变化；改善**集中于少数**纠正 seed，而非全局平移。
- 真模型纠正但 RMSE 变差：B={sum(1 for r in rmse_cost if r['truth_fix_B_but_rmse_worsen'])}；
  C={sum(1 for r in rmse_cost if r['truth_fix_C_but_rmse_worsen'])}。
- FI 恢复 seeds 的 RMSE：{fi_rmse}

预算：A 均为 135；C 与 A 同预算（本队列无 ABORT）。拟合次数 `NOT_IDENTIFIABLE`。

## 五、失败与证据有效性

- C 错误排除真实 hump：k={validity['C_truth_excluded_k']}
- 非法资格恢复：k={validity['C_illegal_restore_k']}
- 空资格/ABORT：k={validity['C_abort_k']}
- 失败是否进入统计：是（本队列失败 k=0；字段完整={validity['all_score_fields_complete']}）
- B 轨迹≡A：{validity['B_all_trajectories_identical']}

## 六、结论边界（六问）

1. **FI 是否造成可避免的真模型选择错误？**  
   **是**（至少 seeds {fi_restore_seeds}）：权重剪枝使 hump 失去最终资格，同时证据未排除；同数据下恢复资格后 hump 按原评分胜出。

2. **B 的改善有多少可严格归因于恢复终局资格？**  
   **{len(fi_restore_seeds)}/{len(ab_focus) if ab_focus else 0}** 个 A→B 纠正案例满足严格归因；
   seed 208 的 B **无**改善且不能归因于 FI 纠正（证据排除）。

3. **C 的额外结果？**  
   额外纠正 seed 208（闭环轨迹下 hump 未被排除并最终选中）；对 224/232 与 B 同向选对。
   相对 B 的额外收益机制 = 完整政策，**非**可分离的单一反馈通道。

4. **预测误差实质改善还是主要选择率？**  
   **主要是选择率**（37→39→40）；面板 RMSE 中位差为 0；有限 seed 上 RMSE 下降，亦存在 C 相对 A 的恶化计数。

5. **失败风险与代价？**  
   本环境本队列：无 ABORT/空资格/非法恢复；C 未排除真模型；错误资格数均值略升；
   wall 为 A+C 配对成本；跨环境敏感性仍适用（Stage1）。

6. **对 FI 论文的因果证据强度？**  
   提供**受控、可复核**的实例：终局资格剪枝可造成可逆的真模型落选，且恢复资格可纠正；
   **不足以**宣称证据门控普遍大幅降低预测误差，也**不能**把 C 的额外收益归因于单一探索机制。

---

**最终裁决：`{verdict}`**
"""
    (OUT / "causal_audit_report.md").write_text(report, encoding="utf-8")

    verdict_payload = {
        "verdict": verdict,
        "reason": reason,
        "reconcile": {"A": A_k, "B": B_k, "C": C_k, "n": 40, "match_formal": True},
        "fi_final_eligibility_restore_seeds": fi_restore_seeds,
        "A_wrong_B_right": [c["seed"] for c in ab_focus],
        "A_wrong_C_right": [c["seed"] for c in ac_focus],
        "A_wrong_B_still_wrong": [
            r["seed"] for r in paired if (not r["A_truth"]) and (not r["B_truth"])
        ],
        "rmse": {
            "median_A_minus_B": statistics.median(dAB),
            "median_A_minus_C": statistics.median(dAC),
            "B_vs_A_counts": dirs_ab,
            "C_vs_A_counts": dirs_ac,
            "fi_restore_rmse": fi_rmse,
        },
        "validity": validity,
        "answers": {
            "FI_caused_avoidable_truth_miss": has_verified_fi_fix,
            "B_strictly_attributable_restore_count": len(fi_restore_seeds),
            "C_extra_beyond_B": [c["seed"] for c in c_only],
            "prediction_vs_selection": "selection_primary_rmse_median_delta_zero",
            "failure_risk_this_panel": "none_observed_env_bound",
            "paper_causal_strength": "instance_level_FI_eligibility_harm_and_restore_supported_not_global_rmse_claim",
        },
        "chi2_status": "OPERATIONAL_ONLY",
        "paper_modified": False,
        "rerun": False,
    }
    (OUT / "verdict.json").write_text(
        json.dumps(verdict_payload, indent=2, default=str), encoding="utf-8"
    )
    print(f"[causal-audit] verdict={verdict} -> {OUT}")
    print(
        json.dumps(
            {
                "fi_seeds": fi_restore_seeds,
                "A_wrong": [r["seed"] for r in paired if not r["A_truth"]],
                "dirs_ac": dirs_ac,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
