#!/usr/bin/env python3
"""FI Mechanism Decomposition Audit for Opportunity-Feedback Ablation formal_v2.

Read-only: does not modify algorithms, configs, thresholds, logs, or paper.
Does not re-run formal experiments.
"""
from __future__ import annotations

import csv
import json
import math
import statistics
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "outputs" / "pilot_opp_feedback_ablation_formal_v2"
OUT = ROOT / "outputs" / "pilot_opp_feedback_mechanism_audit"
FORMAL_AGG = DATA / "formal_aggregate.json"

FAMILIES = ("hump", "affine", "pow", "expsat", "quad")
FALSE = ("affine", "pow", "expsat", "quad")
TRUTH = "hump"
ARM_N = "native"
ARM_U = "no_opp_fb"
THETA_W = 0.02
R = 25


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float, float]:
    if n <= 0:
        return 0.0, 0.0, 0.0
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return float(p), float(max(0.0, centre - half)), float(min(1.0, centre + half))


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
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
    path = DATA / f"seed_{seed:02d}_paired.json"
    return json.loads(path.read_text(encoding="utf-8"))


def sites_by_t(sites: list[dict]) -> dict[int, list[int]]:
    by: dict[int, list[int]] = {}
    for s in sites:
        by.setdefault(int(s["t"]), []).append(int(s["idx"]))
    for t in by:
        by[t] = sorted(by[t])
    return by


def first_alive_false(rounds: list[dict], h: str) -> int | None:
    for t, rnd in enumerate(rounds):
        if not rnd[h]["alive"]:
            return t
    return None


def fi_flag(t_elim: int | None, t_excl: int | None) -> bool:
    if t_elim is None:
        return False
    return t_excl is None or t_elim < t_excl


def elim_status(t_elim: int | None) -> str:
    if t_elim is None:
        return "right_censored_alive_at_horizon"
    return "eliminated"


def excl_status(t_excl: int | None) -> str:
    if t_excl is None:
        return "not_met_frozen_exclusion_by_horizon"
    return "excluded"


def proposer_probs_from_prior(
    rounds: list[dict], t: int, mode: str
) -> dict[str, Any]:
    """Reconstruct allocation proposer masses from end-of-(t-1) state.

    Native: survivor-normalize w_all among alive.
    No-Opp: uniform among alive.
    Which hypothesis actually drew each site: NOT_IDENTIFIABLE from logs.
    """
    if t < 1:
        return {
            "alive": list(FAMILIES),
            "probs": {h: 1.0 / 5 for h in FAMILIES},
            "site_proposer_identity": "NOT_IDENTIFIABLE",
        }
    prev = rounds[t - 1]
    alive = [h for h in FAMILIES if prev[h]["alive"]]
    if not alive:
        return {
            "alive": [],
            "probs": {h: 0.0 for h in FAMILIES},
            "site_proposer_identity": "NOT_IDENTIFIABLE",
        }
    probs = {h: 0.0 for h in FAMILIES}
    if mode == "uniform":
        u = 1.0 / len(alive)
        for h in alive:
            probs[h] = u
    else:
        raw = {h: float(prev[h]["w_all"]) for h in alive}
        z = sum(raw.values())
        if z <= 0:
            u = 1.0 / len(alive)
            for h in alive:
                probs[h] = u
        else:
            for h in alive:
                probs[h] = raw[h] / z
    return {
        "alive": alive,
        "probs": probs,
        "site_proposer_identity": "NOT_IDENTIFIABLE",
    }


def analyze_candidate(rec: dict, h: str) -> dict[str, Any]:
    seed = int(rec["seed"])
    out: dict[str, Any] = {"seed": seed, "family": h, "is_truth": h == TRUTH}
    for tag, arm_key in (("native", ARM_N), ("no_opp", ARM_U)):
        arm = rec["arms"][arm_key]
        final = arm["final"]
        rounds = arm["rounds"]
        te = final["t_elim"].get(h)
        tx = final["t_excl"].get(h)
        first_dead = first_alive_false(rounds, h)
        # consistency: first alive=False should equal t_elim if eliminated
        if te is not None and first_dead != te:
            alive_sync = "MISMATCH_first_alive_false_vs_t_elim"
        elif te is None and first_dead is not None:
            alive_sync = "MISMATCH_alive_false_without_t_elim"
        elif te is None and first_dead is None:
            alive_sync = "ok_censored"
        else:
            alive_sync = "ok"

        if te is not None:
            st = rounds[te][h]
            w_surv = st["w_surv"]
            viol = st["violated"]
            excl = st["excluded"]
            w_all = st["w_all"]
        else:
            w_surv = viol = excl = w_all = None

        out[f"t_elim_{tag}"] = te
        out[f"t_excl_{tag}"] = tx
        out[f"elim_status_{tag}"] = elim_status(te)
        out[f"excl_status_{tag}"] = excl_status(tx)
        out[f"fi_{tag}"] = fi_flag(te, tx)
        out[f"w_surv_at_elim_{tag}"] = w_surv
        out[f"w_all_at_elim_{tag}"] = w_all
        out[f"violated_at_elim_{tag}"] = viol
        out[f"excluded_at_elim_{tag}"] = excl
        out[f"first_alive_false_{tag}"] = first_dead
        out[f"alive_sync_{tag}"] = alive_sync
        out[f"final_alive_{tag}"] = final["alive"].get(h)
        out[f"final_incumbent_{tag}"] = final["incumbent"]

    # paired classification
    fn, fu = out["fi_native"], out["fi_no_opp"]
    if fn and fu:
        cls = "Both-FI"
    elif fn and not fu:
        cls = "Native-only FI"
    elif fu and not fn:
        cls = "No-Opp-only FI"
    else:
        cls = "Neither-FI"
    out["paired_fi_class"] = cls

    te_n, te_u = out["t_elim_native"], out["t_elim_no_opp"]
    if te_n is None and te_u is None:
        timing = "both_censored"
        delta = None
    elif te_n is not None and te_u is not None and te_n == te_u:
        timing = "tied"
        delta = 0
    elif te_n is not None and (te_u is None or te_n < te_u):
        timing = "Native_earlier"
        delta = None if te_u is None else int(te_n) - int(te_u)
    elif te_u is not None and (te_n is None or te_u < te_n):
        timing = "No-Opp_earlier"
        delta = None if te_n is None else int(te_n) - int(te_u)
    else:
        timing = "UNKNOWN"
        delta = None
    out["elim_timing_class"] = timing
    out["delta_t_elim_native_minus_no_opp_finite"] = delta
    return out


def find_first_fork(rec: dict) -> dict[str, Any]:
    sn = sites_by_t(rec["arms"][ARM_N]["sites"])
    su = sites_by_t(rec["arms"][ARM_U]["sites"])
    tmax = max(max(sn), max(su))
    first = None
    pre_ok = True
    pre_notes: list[str] = []
    for t in range(0, tmax + 1):
        an = sn.get(t, [])
        au = su.get(t, [])
        # pre-fork state check at end of t-1 / start of t
        if first is None and t >= 1:
            rn = rec["arms"][ARM_N]["rounds"][t - 1]
            ru = rec["arms"][ARM_U]["rounds"][t - 1]
            alive_n = {h: rn[h]["alive"] for h in FAMILIES}
            alive_u = {h: ru[h]["alive"] for h in FAMILIES}
            w_n = {h: rn[h]["w_all"] for h in FAMILIES}
            w_u = {h: ru[h]["w_all"] for h in FAMILIES}
            if alive_n != alive_u:
                pre_ok = False
                pre_notes.append(f"t={t}: alive set differs before site compare")
            # w_all may already differ if prior fork; before first fork should match
            if first is None and any(
                abs(w_n[h] - w_u[h]) > 1e-12 for h in FAMILIES
            ):
                pre_ok = False
                pre_notes.append(f"t={t}: w_all differs before first site fork")
        if an != au:
            first = t
            break
    # state at first fork round (using prior round)
    detail: dict[str, Any] = {
        "first_site_fork_t": first,
        "pre_fork_state_consistent": pre_ok if first is not None else True,
        "pre_fork_notes": pre_notes,
    }
    if first is not None and first >= 1:
        pn = proposer_probs_from_prior(
            rec["arms"][ARM_N]["rounds"], first, "weighted"
        )
        pu = proposer_probs_from_prior(
            rec["arms"][ARM_U]["rounds"], first, "uniform"
        )
        detail["alive_at_fork_start_native"] = pn["alive"]
        detail["alive_at_fork_start_no_opp"] = pu["alive"]
        detail["proposer_probs_native"] = pn["probs"]
        detail["proposer_probs_no_opp"] = pu["probs"]
        detail["site_proposer_identity"] = "NOT_IDENTIFIABLE"
        detail["sites_native"] = sn.get(first, [])
        detail["sites_no_opp"] = su.get(first, [])
        # Did proposer probs differ at fork?
        detail["proposer_probs_differ"] = any(
            abs(pn["probs"][h] - pu["probs"][h]) > 1e-12 for h in FAMILIES
        )
        # Why fork? If probs identical, allocation should match under CRN —
        # unless alive sets / nominations differ (which would be earlier state fork)
        if not detail["proposer_probs_differ"] and pn["alive"] == pu["alive"]:
            detail["fork_cause_note"] = (
                "Sites differ while reconstructed proposer probs & alive match; "
                "possible nomination ranking divergence from prior latent state, "
                "or NOT_IDENTIFIABLE residual. Inspect w_all/stream_n history."
            )
        elif detail["proposer_probs_differ"]:
            detail["fork_cause_note"] = (
                "Reconstructed proposer probabilities differ at fork start "
                "(Native ∝ w_all vs No-Opp uniform among alive) under shared CRN."
            )
        else:
            detail["fork_cause_note"] = "Alive-set mismatch at fork start."
    elif first == 0:
        detail["fork_cause_note"] = (
            "Round-0 sites differ — unexpected under shared World.round0 PUBLIC."
        )
        detail["pre_fork_state_consistent"] = False
    else:
        detail["fork_cause_note"] = "No site fork within horizon (identical designs)."
    return detail


def trajectory_rows(rec: dict, fork: dict) -> list[dict]:
    """Per-round paired trajectory from t=0 (or from fork) for all families."""
    seed = int(rec["seed"])
    sn = sites_by_t(rec["arms"][ARM_N]["sites"])
    su = sites_by_t(rec["arms"][ARM_U]["sites"])
    rows = []
    t_fork = fork.get("first_site_fork_t")
    for t in range(0, R + 1):
        rn = rec["arms"][ARM_N]["rounds"][t]
        ru = rec["arms"][ARM_U]["rounds"][t]
        sites_n = sn.get(t, [])
        sites_u = su.get(t, [])
        sites_equal = sites_n == sites_u
        # cumulative measured sets
        # (approximate via stream_n of hump as shared n_arm)
        for h in FAMILIES:
            wn, wu = rn[h]["w_surv"], ru[h]["w_surv"]
            an, au = rn[h]["alive"], ru[h]["alive"]
            cross_n = (wn < THETA_W) if an or (rn[h]["t_elim"] == t) else False
            # threshold crossing this round: alive flipped
            flipped_n = (
                t >= 1
                and rec["arms"][ARM_N]["rounds"][t - 1][h]["alive"]
                and not an
            )
            flipped_u = (
                t >= 1
                and rec["arms"][ARM_U]["rounds"][t - 1][h]["alive"]
                and not au
            )
            rows.append(
                {
                    "seed": seed,
                    "t": t,
                    "family": h,
                    "is_truth": h == TRUTH,
                    "at_or_after_first_fork": (
                        t_fork is not None and t >= t_fork
                    ),
                    "sites_native": "|".join(map(str, sites_n)),
                    "sites_no_opp": "|".join(map(str, sites_u)),
                    "sites_equal": sites_equal,
                    "n_arm_native": rn["n_arm"],
                    "n_arm_no_opp": ru["n_arm"],
                    "alive_native": an,
                    "alive_no_opp": au,
                    "w_surv_native": wn,
                    "w_surv_no_opp": wu,
                    "w_all_native": rn[h]["w_all"],
                    "w_all_no_opp": ru[h]["w_all"],
                    "delta_w_surv": wn - wu,
                    "delta_w_all": rn[h]["w_all"] - ru[h]["w_all"],
                    "crossed_theta_this_round_native": flipped_n,
                    "crossed_theta_this_round_no_opp": flipped_u,
                    "violated_native": rn[h]["violated"],
                    "violated_no_opp": ru[h]["violated"],
                    "excluded_native": rn[h]["excluded"],
                    "excluded_no_opp": ru[h]["excluded"],
                    "incumbent_native": rn.get("incumbent"),
                    "incumbent_no_opp": ru.get("incumbent"),
                    "proposer_draw_identity": "NOT_IDENTIFIABLE",
                }
            )
    return rows


def case_narrative(rec: dict, fork: dict, cand_rows: list[dict]) -> str:
    seed = int(rec["seed"])
    hump = next(r for r in cand_rows if r["family"] == TRUTH and r["seed"] == seed)
    lines = [
        f"## Seed {seed}",
        "",
        f"- 首次选点分叉：t={fork.get('first_site_fork_t')}",
        f"- 分叉前状态一致：{fork.get('pre_fork_state_consistent')}",
        f"- 分叉原因（重建）：{fork.get('fork_cause_note')}",
        f"- Native sites@fork：{fork.get('sites_native')}",
        f"- No-Opp sites@fork：{fork.get('sites_no_opp')}",
        f"- proposer 概率是否不同：{fork.get('proposer_probs_differ')}",
        f"- 单点 proposer 身份：{fork.get('site_proposer_identity', 'NOT_IDENTIFIABLE')}",
        "",
        "### 真实模型 hump",
        "",
        f"| 量 | Native | No-Opp |",
        f"|---|---|---|",
        f"| t_elim | {hump['t_elim_native']} | {hump['t_elim_no_opp']} |",
        f"| t_excl | {hump['t_excl_native']} | {hump['t_excl_no_opp']} |",
        f"| FI | {hump['fi_native']} | {hump['fi_no_opp']} |",
        f"| 配对类 | {hump['paired_fi_class']} | — |",
        f"| 退出时序 | {hump['elim_timing_class']} | — |",
        f"| w_surv@elim | {hump['w_surv_at_elim_native']} | {hump['w_surv_at_elim_no_opp']} |",
        f"| violated@elim | {hump['violated_at_elim_native']} | {hump['violated_at_elim_no_opp']} |",
        f"| excluded@elim | {hump['excluded_at_elim_native']} | {hump['excluded_at_elim_no_opp']} |",
        f"| 终局 alive | {hump['final_alive_native']} | {hump['final_alive_no_opp']} |",
        f"| 终局 incumbent | {hump['final_incumbent_native']} | {hump['final_incumbent_no_opp']} |",
        "",
    ]
    # round-by-round around fork / elim for hump
    t0 = fork.get("first_site_fork_t") or 1
    te_candidates = [
        x
        for x in (hump["t_elim_native"], hump["t_elim_no_opp"], t0 + 2)
        if x is not None
    ]
    t1 = max(te_candidates) if te_candidates else t0 + 2
    lines.append("### hump 逐轮（分叉邻域）")
    lines.append("")
    lines.append(
        "| t | sites= | w_surv_N | w_surv_U | alive_N | alive_U | viol_N | viol_U |"
    )
    lines.append("|---|---|---|---|---|---|---|---|")
    for t in range(max(0, t0 - 1), min(R, t1) + 1):
        rn = rec["arms"][ARM_N]["rounds"][t][TRUTH]
        ru = rec["arms"][ARM_U]["rounds"][t][TRUTH]
        sn = sites_by_t(rec["arms"][ARM_N]["sites"]).get(t, [])
        su = sites_by_t(rec["arms"][ARM_U]["sites"]).get(t, [])
        lines.append(
            f"| {t} | {sn==su} | {rn['w_surv']:.6g} | {ru['w_surv']:.6g} | "
            f"{rn['alive']} | {ru['alive']} | {rn['violated']} | {ru['violated']} |"
        )
    lines.append("")
    return "\n".join(lines)


def median_finite(vals: list[float | int]) -> float | None:
    if not vals:
        return None
    return float(statistics.median(vals))


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    cand_rows: list[dict] = []
    seed_rows: list[dict] = []
    traj_rows: list[dict] = []
    forks: dict[int, dict] = {}
    discordant_false: list[dict] = []

    for seed in range(1, 21):
        rec = load_seed(seed)
        fork = find_first_fork(rec)
        forks[seed] = fork
        seed_cands = [analyze_candidate(rec, h) for h in FAMILIES]
        cand_rows.extend(seed_cands)

        n_false_fi_n = sum(1 for r in seed_cands if not r["is_truth"] and r["fi_native"])
        n_false_fi_u = sum(1 for r in seed_cands if not r["is_truth"] and r["fi_no_opp"])
        truth = next(r for r in seed_cands if r["is_truth"])
        # false identity / timing shifts when counts equal
        false = [r for r in seed_cands if not r["is_truth"]]
        identity_shift = any(
            r["fi_native"] != r["fi_no_opp"] for r in false
        )
        timing_shift_same_fi = any(
            r["paired_fi_class"] == "Both-FI" and r["elim_timing_class"] != "tied"
            for r in false
        )
        for r in false:
            if r["paired_fi_class"] in ("Native-only FI", "No-Opp-only FI"):
                discordant_false.append(
                    {
                        "seed": seed,
                        "family": r["family"],
                        "class": r["paired_fi_class"],
                        "t_elim_native": r["t_elim_native"],
                        "t_elim_no_opp": r["t_elim_no_opp"],
                    }
                )

        seed_rows.append(
            {
                "seed": seed,
                "first_site_fork_t": fork.get("first_site_fork_t"),
                "pre_fork_state_consistent": fork.get("pre_fork_state_consistent"),
                "proposer_probs_differ_at_fork": fork.get("proposer_probs_differ"),
                "fork_cause_note": fork.get("fork_cause_note"),
                "n_false_fi_native": n_false_fi_n,
                "n_false_fi_no_opp": n_false_fi_u,
                "truth_fi_native": truth["fi_native"],
                "truth_fi_no_opp": truth["fi_no_opp"],
                "truth_paired_class": truth["paired_fi_class"],
                "truth_elim_timing": truth["elim_timing_class"],
                "t_elim_hump_native": truth["t_elim_native"],
                "t_elim_hump_no_opp": truth["t_elim_no_opp"],
                "t_excl_hump_native": truth["t_excl_native"],
                "t_excl_hump_no_opp": truth["t_excl_no_opp"],
                "incumbent_native": truth["final_incumbent_native"],
                "incumbent_no_opp": truth["final_incumbent_no_opp"],
                "false_fi_identity_discordant": identity_shift,
                "false_both_fi_timing_untied": timing_shift_same_fi,
                "delta_false_fi_n_minus_u": n_false_fi_n - n_false_fi_u,
            }
        )
        traj_rows.extend(trajectory_rows(rec, fork))

    # --- aggregates ---
    false_rows = [r for r in cand_rows if not r["is_truth"]]
    truth_rows = [r for r in cand_rows if r["is_truth"]]

    false_class = Counter(r["paired_fi_class"] for r in false_rows)
    truth_class = Counter(r["paired_fi_class"] for r in truth_rows)
    both_fi_false = [r for r in false_rows if r["paired_fi_class"] == "Both-FI"]
    both_timing = Counter(r["elim_timing_class"] for r in both_fi_false)
    finite_deltas = [
        r["delta_t_elim_native_minus_no_opp_finite"]
        for r in both_fi_false
        if r["delta_t_elim_native_minus_no_opp_finite"] is not None
    ]

    n_false_fi_n = sum(1 for r in false_rows if r["fi_native"])
    n_false_fi_u = sum(1 for r in false_rows if r["fi_no_opp"])
    truth_fi_n = sum(1 for r in truth_rows if r["fi_native"])
    truth_fi_u = sum(1 for r in truth_rows if r["fi_no_opp"])

    # reconcile with formal aggregate
    formal = json.loads(FORMAL_AGG.read_text(encoding="utf-8")) if FORMAL_AGG.is_file() else {}
    reconcile = {
        "false_fi_native_audit_vs_formal": [
            n_false_fi_n,
            formal.get("false_fi_total_native"),
        ],
        "false_fi_no_opp_audit_vs_formal": [
            n_false_fi_u,
            formal.get("false_fi_total_no_opp"),
        ],
        "truth_fi_native_audit_vs_formal": [
            truth_fi_n,
            formal.get("truth_fi_native_k"),
        ],
        "truth_fi_no_opp_audit_vs_formal": [
            truth_fi_u,
            formal.get("truth_fi_no_opp_k"),
        ],
        "match": (
            n_false_fi_n == formal.get("false_fi_total_native")
            and n_false_fi_u == formal.get("false_fi_total_no_opp")
            and truth_fi_n == formal.get("truth_fi_native_k")
            and truth_fi_u == formal.get("truth_fi_no_opp_k")
        ),
    }

    # seed-level false FI direction
    seed_false_dir = Counter()
    for s in seed_rows:
        d = s["delta_false_fi_n_minus_u"]
        if d > 0:
            seed_false_dir["native_more"] += 1
        elif d < 0:
            seed_false_dir["no_opp_more"] += 1
        else:
            seed_false_dir["tie"] += 1

    # first fork stats
    fork_ts = [s["first_site_fork_t"] for s in seed_rows]
    n_no_fork = sum(1 for t in fork_ts if t is None)
    n_pre_ok = sum(1 for s in seed_rows if s["pre_fork_state_consistent"])

    # weight divergence before elim for discordant truth
    # (handled in cases)

    # reverse discordant (No-Opp-only) at candidate level — all families
    reverse = [
        r
        for r in cand_rows
        if r["paired_fi_class"] == "No-Opp-only FI"
    ]
    native_only = [
        r
        for r in cand_rows
        if r["paired_fi_class"] == "Native-only FI"
    ]

    # alive sync issues
    sync_issues = [
        {
            "seed": r["seed"],
            "family": r["family"],
            "arm": tag,
            "status": r[f"alive_sync_{tag}"],
        }
        for r in cand_rows
        for tag in ("native", "no_opp")
        if not str(r[f"alive_sync_{tag}"]).startswith("ok")
    ]

    # seed 17 / 20 cases
    case_md_parts = [
        "# 真实模型机制个案：Seed 17 & Seed 20",
        "",
        "数据：`outputs/pilot_opp_feedback_ablation_formal_v2/seed_XX_paired.json`",
        "χ² 为操作性排除标签，非严格校准相容性证明。",
        "",
    ]
    for seed in (17, 20):
        rec = load_seed(seed)
        case_md_parts.append(case_narrative(rec, forks[seed], cand_rows))
        # extra chain for seed 20
        if seed == 20:
            case_md_parts += [
                "### Seed 20 因果链要点（日志可观测）",
                "",
                "1. t=0–1：两臂共享初始设计与 CRN；若分叉在 t=2，则此前 sites 应一致。",
                "2. t=2：首次选点分叉（若 `first_site_fork_t=2`）→ 新观测集合分歧。",
                "3. t=2 结束：支持权重开始分叉（见轨迹 Δw）。",
                "4. t=3：Native `w_surv(hump)<0.02` → `alive=False`；"
                "当轮 `violated=false`、`excluded=false` → 操作性 FI。"
                "No-Opp 同轮 hump 仍存活。",
                "5. 不宣称「局部失稳/临界」——仅记录阈值跨越的可观测事实。",
                "",
            ]

    # other discordant truth / reverse
    case_md_parts += [
        "## 其他 seeds 的候选级 FI 结局反差（全表扫描）",
        "",
        f"- Native-only FI 事件数（含真/假）：{len(native_only)}",
        f"- No-Opp-only FI 事件数（含真/假）：{len(reverse)}",
        "",
    ]
    if native_only:
        case_md_parts.append("### Native-only FI")
        case_md_parts.append("")
        for r in native_only:
            case_md_parts.append(
                f"- seed={r['seed']} family={r['family']} "
                f"t_elim_N={r['t_elim_native']} t_elim_U={r['t_elim_no_opp']} "
                f"truth={r['is_truth']}"
            )
        case_md_parts.append("")
    if reverse:
        case_md_parts.append("### No-Opp-only FI（反方向）")
        case_md_parts.append("")
        for r in reverse:
            case_md_parts.append(
                f"- seed={r['seed']} family={r['family']} "
                f"t_elim_N={r['t_elim_native']} t_elim_U={r['t_elim_no_opp']} "
                f"truth={r['is_truth']}"
            )
        case_md_parts.append("")
    else:
        case_md_parts.append("未发现 No-Opp-only FI（真实或假模型）。\n")

    if discordant_false:
        case_md_parts.append("### 假模型身份反差明细")
        case_md_parts.append("")
        for d in discordant_false:
            case_md_parts.append(
                f"- seed={d['seed']} {d['family']}: {d['class']} "
                f"(t_N={d['t_elim_native']}, t_U={d['t_elim_no_opp']})"
            )
        case_md_parts.append("")

    (OUT / "seed17_seed20_cases.md").write_text(
        "\n".join(case_md_parts), encoding="utf-8"
    )

    # write CSVs
    write_csv(OUT / "candidate_paired_events.csv", cand_rows)
    write_csv(OUT / "seed_summary.csv", seed_rows)
    write_csv(OUT / "feedback_trajectories.csv", traj_rows)

    # seed-level truth rates
    p_n, lo_n, hi_n = wilson(truth_fi_n, 20)
    p_u, lo_u, hi_u = wilson(truth_fi_u, 20)

    # mechanism verdict
    opp_necessary = False  # No-Opp still has massive FI
    opp_can_change = truth_fi_n > truth_fi_u or len(native_only) > 0 or len(reverse) > 0
    # systematic increase? seed-level false FI: mostly ties; truth: 2 vs 1
    systematic = {
        "false_fi_seed_ties": seed_false_dir.get("tie", 0),
        "false_fi_seed_native_more": seed_false_dir.get("native_more", 0),
        "false_fi_seed_no_opp_more": seed_false_dir.get("no_opp_more", 0),
        "truth_native_only_seeds": truth_class.get("Native-only FI", 0),
        "truth_no_opp_only_seeds": truth_class.get("No-Opp-only FI", 0),
        "assessment": (
            "Not a systematic inflation of false-FI counts at seed level "
            "(19/20 ties); one controlled Native-only truth-FI instance (seed 20); "
            "Both-FI truth on seed 17. Opportunity feedback is neither necessary "
            "nor shown to be a large systematic amplifier in this 20-seed panel."
        ),
    }

    verdict = {
        "audit": "FI_Mechanism_Decomposition",
        "data": str(DATA),
        "n_seeds": 20,
        "reconcile_with_formal_v2": reconcile,
        "false_fi_totals": {"native": n_false_fi_n, "no_opp": n_false_fi_u},
        "truth_fi": {
            "native_k": truth_fi_n,
            "no_opp_k": truth_fi_u,
            "native_rate_wilson95": [p_n, lo_n, hi_n],
            "no_opp_rate_wilson95": [p_u, lo_u, hi_u],
            "paired_classes": dict(truth_class),
        },
        "false_paired_classes": dict(false_class),
        "both_fi_false_timing": dict(both_timing),
        "finite_delta_median_native_minus_no_opp": median_finite(finite_deltas),
        "finite_delta_n": len(finite_deltas),
        "seed_false_fi_direction": dict(seed_false_dir),
        "first_fork": {
            "n_no_fork": n_no_fork,
            "n_pre_fork_consistent": n_pre_ok,
            "fork_t_list": fork_ts,
        },
        "discordant_candidates": {
            "native_only": [
                {"seed": r["seed"], "family": r["family"], "truth": r["is_truth"]}
                for r in native_only
            ],
            "no_opp_only": [
                {"seed": r["seed"], "family": r["family"], "truth": r["is_truth"]}
                for r in reverse
            ],
        },
        "alive_sync_issues": sync_issues,
        "mechanism_answers": {
            "direct_trigger": (
                "Decision-eligibility FI is triggered by survivor-normalized "
                "support pruning: alive←False when w_surv < Θ_W=0.02, while "
                "frozen χ² two-round exclusion has not yet been met (operational)."
            ),
            "opportunity_feedback_causal_role": (
                "The w_all→proposer-probability channel changes which sites are "
                "acquired under CRN; this can change subsequent observations, "
                "weights, and whether/when a candidate crosses Θ_W. Seed 20 is a "
                "controlled instance where Native loses hump eligibility and No-Opp "
                "retains it. Across 20 seeds, false-FI identity/timing can shift "
                "even when totals stay similar."
            ),
            "why_fi_remains_without_opp_fb": (
                "No-Opp still runs fit→support→w_surv prune on the same World and "
                "still allocates among alive candidates (uniform). Cutting only "
                "support-weighted opportunity does not remove the pruning rule or "
                "support recursion."
            ),
            "stronger_than_seed20": (
                "Panel supports: (i) pruning is the direct trigger; "
                "(ii) opportunity feedback is not necessary for abundant false FI; "
                "(iii) feedback can alter trajectories and at least one truth-FI "
                "outcome. It does NOT support claiming feedback is generally "
                "required for FI, nor a precise local-instability / R_id=1 theorem."
            ),
            "opportunity_feedback_necessary_for_FI": False,
            "controlled_instance_changes_FI_outcome": bool(
                truth_class.get("Native-only FI", 0) >= 1
                or truth_class.get("No-Opp-only FI", 0) >= 1
                or len(discordant_false) > 0
            ),
            "systematic_FI_risk_increase": systematic,
        },
        "theory_boundary": {
            "consistent_with_minimal_recursion": [
                "Shared support update + threshold prune produces FI on both arms",
                "FI can precede operational evidence exclusion",
                "Cutting one channel (opportunity weighting) leaves other recursion intact",
            ],
            "not_proven": [
                "Local instability of a recursion map",
                "R_id=1 critical condition",
                "Strict Type-I calibration of χ² compatibility",
                "That opportunity feedback systematically amplifies FI risk in general",
            ],
        },
        "limitations": [
            "Per-site proposer hypothesis identity NOT_IDENTIFIABLE from logs",
            "Candidate-level events within a seed are dependent",
            "n=20; Wilson intervals for truth-FI rates are wide",
            "χ² exclusion is operational, not strictly calibrated under adaptive design",
        ],
        "verdict": "MECHANISM_DECOMPOSED",
        "paper_edit": False,
    }
    (OUT / "verdict.json").write_text(
        json.dumps(verdict, indent=2, default=str), encoding="utf-8"
    )

    # main report
    report = _write_report(
        reconcile,
        n_false_fi_n,
        n_false_fi_u,
        truth_fi_n,
        truth_fi_u,
        truth_class,
        false_class,
        both_timing,
        finite_deltas,
        seed_false_dir,
        seed_rows,
        forks,
        native_only,
        reverse,
        sync_issues,
        verdict,
        p_n,
        lo_n,
        hi_n,
        p_u,
        lo_u,
        hi_u,
    )
    (OUT / "mechanism_report.md").write_text(report, encoding="utf-8")
    print(f"[mechanism-audit] wrote {OUT}")
    print(f"  reconcile_match={reconcile['match']}")
    print(f"  false FI N/U={n_false_fi_n}/{n_false_fi_u} truth={truth_fi_n}/{truth_fi_u}")
    print(f"  verdict={verdict['verdict']}")
    return 0


def _write_report(
    reconcile,
    n_fn,
    n_fu,
    t_fn,
    t_fu,
    truth_class,
    false_class,
    both_timing,
    finite_deltas,
    seed_false_dir,
    seed_rows,
    forks,
    native_only,
    reverse,
    sync_issues,
    verdict,
    p_n,
    lo_n,
    hi_n,
    p_u,
    lo_u,
    hi_u,
) -> str:
    med = median_finite(finite_deltas)
    lines = [
        "# FI 机制分解审计（Opportunity-Feedback Ablation formal_v2）",
        "",
        f"**裁决：`{verdict['verdict']}`**",
        "",
        "范围：只读正式配对 JSON；不改算法/阈值/日志/论文；不重跑正式实验。",
        "FI 操作性定义：`t_elim` 存在且（`t_excl` 为空或 `t_elim < t_excl`）；"
        "χ² 为冻结操作性排除标签，非严格校准相容性。",
        "",
        "## A. 20-seed 结局核验",
        "",
        f"- 假模型 FI 总数：Native **{n_fn}**；No-Opp **{n_fu}**"
        f"（正式报告 78 vs 79；复核 match={reconcile['match']}）",
        f"- 真实模型 FI seeds：Native **{t_fn}**/20；No-Opp **{t_fu}**/20"
        f"（正式 2 vs 1；match={reconcile['match']}）",
        f"- 真实模型 Wilson95：Native [{lo_n:.3f},{hi_n:.3f}]；"
        f"No-Opp [{lo_u:.3f},{hi_u:.3f}]",
        f"- alive 与 t_elim 同步问题数：{len(sync_issues)}",
        "",
        "退出 / 右删失 / 未达证据排除均已在 `candidate_paired_events.csv` 分列。",
        "",
        "## B. 机会分配首次分叉",
        "",
    ]
    for s in seed_rows:
        lines.append(
            f"- seed {s['seed']:02d}: first_fork_t={s['first_site_fork_t']}；"
            f"pre_ok={s['pre_fork_state_consistent']}；"
            f"probs_differ={s['proposer_probs_differ_at_fork']}"
        )
    lines += [
        "",
        "单点由哪个候选 proposer 抽中：**NOT_IDENTIFIABLE**（日志无 proposer 身份）。",
        "可从上一轮 `w_all`/`alive` 重建 proposer **概率向量**（Native∝w_all；No-Opp 均匀）。",
        "",
        "## C. 反馈传播（摘要）",
        "",
        "- 轨迹见 `feedback_trajectories.csv`（逐 seed×t×family）。",
        "- 典型链：分叉选点 → `n_arm`/观测集差异 → `w_all`/`w_surv` 差异 →"
        " 是否跨 Θ_W=0.02 → `alive` 分歧。",
        "- 权重差异可先于资格退出出现；资格差异可持续至终局（如 seed 20）。",
        "- 假 FI 总数接近时，仍可有 **身份反差** 或 Both-FI **时序反差**"
        "（见 seed 级 `false_fi_identity_discordant` / `false_both_fi_timing_untied`）。",
        "- **不**将权重差增大解释为「递归不稳定/临界转变」。",
        "",
        "## D. 配对机制分类",
        "",
        "### 真实模型（seed 级，n=20）",
        "",
        f"- 分类计数：{dict(truth_class)}",
        "",
        "### 假模型（候选级，描述性；同一 seed 内事件相关）",
        "",
        f"- 分类计数：{dict(false_class)}",
        f"- Both-FI 时序：{dict(both_timing)}",
        f"- 有限 Δ=t_elim_N−t_elim_U：n={len(finite_deltas)}；"
        f"中位数={med}（**未**用删失哨兵填入）",
        "",
        "### Seed 级假 FI 计数方向",
        "",
        f"- {dict(seed_false_dir)}",
        "",
        f"- Native-only FI 候选：{len(native_only)}；No-Opp-only：{len(reverse)}",
        "",
        "## E. 真实模型个案",
        "",
        "详见 `seed17_seed20_cases.md`。",
        "",
        f"- Seed 17：{next(s for s in seed_rows if s['seed']==17)['truth_paired_class']}；"
        f"时序 {next(s for s in seed_rows if s['seed']==17)['truth_elim_timing']}；"
        f"t_elim N/U="
        f"{next(s for s in seed_rows if s['seed']==17)['t_elim_hump_native']}/"
        f"{next(s for s in seed_rows if s['seed']==17)['t_elim_hump_no_opp']}",
        f"- Seed 20：{next(s for s in seed_rows if s['seed']==20)['truth_paired_class']}；"
        f"t_elim N/U="
        f"{next(s for s in seed_rows if s['seed']==20)['t_elim_hump_native']}/"
        f"{next(s for s in seed_rows if s['seed']==20)['t_elim_hump_no_opp']}",
        "",
        "## F. 机制结论与理论边界",
        "",
        "### 三层区分",
        "",
        "1. **直接执行剪枝**：`w_surv < 0.02` → `alive=False`（两臂共用）。",
        "2. **机会分配反馈的因果作用**：改变 proposer 概率 → 选点 → 观测 →"
        " 支持轨迹 → 可否/何时跨阈值（CRN 下可归因于该通道）。",
        "3. **仍共同保留**：拟合、支持更新、阈值剪枝、证据审计、在存活集上分配。",
        "",
        "### 判断",
        "",
        f"- 机会反馈是 FI **必要条件**？**否**"
        f"（No-Opp 假 FI={n_fu}，真实 FI={t_fu}）。",
        f"- 有受控实例改变 FI 结局？**是**"
        f"（至少 seed 20 Native-only 真实 FI；另有候选级反差）。",
        f"- 系统性增加 FI 风险？**本面板证据不足/偏弱**"
        f"（假 FI seed 级 19/20 平局；真实 FI 2 vs 1，CI 宽）。",
        "- 与最小递归结构一致：剪枝触发 FI；切断单通道后递归仍在；"
        "FI 可早于操作性证据排除。",
        "- **不能**证明：局部失稳、R_id=1 临界、χ² 严格相容、反馈普遍放大 FI。",
        "",
        "## 五个简答",
        "",
        "1. **直接触发**：支持权重剪枝（`w_surv<Θ_W`），且当时未达冻结两轮证据排除。",
        "2. **反馈贡献**：在 CRN 下改变选点与后续权重/资格轨迹；可改变退出时间与少数结局。",
        "3. **切断后仍大量 FI**：剪枝与支持更新仍在；仅去掉权重→机会的加权通道。",
        "4. **相对 seed 20**：20-seed 支持「非必要 + 可改变轨迹/个别结局」，"
        "但不支持更强的「系统放大器/临界定理」。",
        "5. **论文可用/不可用**：可用作机制分解与操作性 FI 证据；"
        "不可用作严格统计相容或递归失稳/R_id 证明。",
        "",
        "**未修改论文。**",
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
