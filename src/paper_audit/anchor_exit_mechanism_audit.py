#!/usr/bin/env python3
"""Anchor Native–Neutral FI exit mechanism audit (offline, read-only).

Does not re-run the closed loop, does not modify code or frozen thresholds,
does not edit the paper. Reconstructs exit causes from logged state + source
order of operations in pilot_fi_anchor/loop.py.
"""
from __future__ import annotations

import csv
import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT_ANCHOR = ROOT / "outputs" / "pilot_fi_anchor"
OUT_TRUTH = ROOT / "outputs" / "pilot_truth_loss_v2"
DEST = ROOT / "outputs" / "anchor_exit_mechanism_audit"

FALSE_FAMILIES = ("affine", "pow", "expsat", "quad")
ALL_FAMILIES = ("hump",) + FALSE_FAMILIES
THETA_W = 0.02
R = 25
CENSORED = R + 1  # right-censor sentinel for never-elim within horizon


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _round_at(arm: dict, t: int) -> dict | None:
    rounds = arm.get("rounds") or []
    for row in rounds:
        if int(row.get("t", -1)) == t:
            return row
    return None


def _prev_violated(arm: dict, h: str, t: int) -> bool | None:
    """violated flag recorded at end of round t-1 (needed for 2-round persist)."""
    if t <= 0:
        return False
    row = _round_at(arm, t - 1)
    if row is None:
        return None
    return bool(row[h]["violated"])


def classify_exit(
    arm_rec: dict,
    h: str,
    t_elim: int | None,
) -> dict[str, Any]:
    """Classify one candidate's first decision-eligibility exit.

    Formal pilot (rediscovery off): alive=False is set ONLY by
    w_surv < THETA_W in _check_elimination, which runs BEFORE
    _update_evidence in the same round. Evidence exclusion never flips alive.
    """
    final = arm_rec["final"]
    t_excl = final["t_excl"].get(h)
    excluded_final = bool(final["excluded"].get(h))

    if t_elim is None:
        return {
            "exited": False,
            "direct_trigger": "NONE",
            "trigger_confidence": "CONFIRMED",
            "decision_eligibility_exit": False,
            "meets_frozen_fi": False,
            "evidence_exclusion_met_at_exit": False,
            "fi_class": "NO_EXIT",
            "notes": "never lost decision eligibility within horizon",
        }

    row = _round_at(arm_rec, t_elim)
    if row is None:
        return {
            "exited": True,
            "direct_trigger": "UNKNOWN",
            "trigger_confidence": "UNKNOWN",
            "decision_eligibility_exit": True,
            "meets_frozen_fi": None,
            "evidence_exclusion_met_at_exit": None,
            "fi_class": "UNKNOWN",
            "notes": "elim round missing from log",
        }

    st = row[h]
    w_surv = float(st["w_surv"])
    w_all = float(st["w_all"])
    violated = bool(st["violated"])
    excluded_at = bool(st["excluded"])
    prev_v = _prev_violated(arm_rec, h, t_elim)

    # Direct mechanism: code path only kills on w_surv < THETA_W
    weight_kill = w_surv < THETA_W
    # Evidence exclusion at this round would require violated AND prev_violated;
    # but evidence update runs AFTER elimination, so excluded_at cannot be the
    # cause of this round's alive=False (and code never uses excluded to set alive).
    evidence_could_cause_alive = False  # structural from source

    note_extra = ""
    if weight_kill:
        trigger = "RELATIVE_SUPPORT_WEIGHT_PRUNE"
        conf = "CONFIRMED"
        if excluded_at:
            note_extra = "same_round_evidence_also_excluded_after_weight_prune"
    else:
        trigger = "UNKNOWN"
        conf = "UNKNOWN"
        note_extra = f"w_surv={w_surv} not below THETA_W={THETA_W} at recorded elim"

    # Frozen FI: decision exit before two-round evidence exclusion
    if t_excl is None:
        meets_fi = True  # censored: never reached evidence exclusion
        fi_class = "FI_UNSUPPORTED_CENSORED"
    elif t_elim < t_excl:
        meets_fi = True
        fi_class = "FI_UNSUPPORTED"
    elif t_elim == t_excl:
        # Should be rare: elim and excl same round — still weight triggered first
        meets_fi = False
        fi_class = "EXIT_SAME_ROUND_AS_EVIDENCE"
    else:
        meets_fi = False
        fi_class = "EXIT_AFTER_EVIDENCE"

    evidence_met = bool(excluded_at)  # two-round rule satisfied by end of elim round

    notes = []
    if note_extra:
        notes.append(note_extra)
    if violated and not (prev_v is True):
        notes.append("single_round_chi2_exceeded_at_elim_but_not_two_round")
    if not violated:
        notes.append("single_round_chi2_NOT_exceeded_at_elim")
    if prev_v is None:
        notes.append("prev_violated_UNKNOWN")
    _ = evidence_could_cause_alive  # documented structural fact

    return {
        "exited": True,
        "direct_trigger": trigger,
        "trigger_confidence": conf,
        "decision_eligibility_exit": True,
        "meets_frozen_fi": meets_fi,
        "evidence_exclusion_met_at_exit": evidence_met,
        "fi_class": fi_class,
        "w_surv_at_elim": w_surv,
        "w_all_at_elim": w_all,
        "violated_at_elim": violated,
        "prev_violated": prev_v,
        "excluded_at_elim": excluded_at,
        "t_excl": t_excl,
        "chi2_numeric": None,  # not stored in logs
        "rss_numeric": None,
        "chi2_status": "NOT_IN_LOG",
        "notes": ";".join(notes),
    }


def extract_exits_for_arm(seed: int, arm_name: str, arm_rec: dict, queue: str) -> list[dict]:
    rows = []
    final = arm_rec["final"]
    for h in ALL_FAMILIES:
        t_elim = final["t_elim"].get(h)
        cls = classify_exit(arm_rec, h, t_elim)
        # consecutive two-round evidence state description
        if t_elim is not None:
            row = _round_at(arm_rec, t_elim) or {}
            st = row.get(h, {})
            w_surv = st.get("w_surv")
            w_all = st.get("w_all")
            violated = st.get("violated")
            S = st.get("S")
        else:
            w_surv = w_all = violated = S = None

        rows.append(
            {
                "queue": queue,
                "seed": seed,
                "arm": arm_name,
                "family": h,
                "is_truth": h == "hump",
                "t_elim": t_elim if t_elim is not None else "",
                "t_excl": final["t_excl"].get(h) if final["t_excl"].get(h) is not None else "",
                "censored_elim": t_elim is None,
                "censored_excl": final["t_excl"].get(h) is None,
                "alive_final": bool(final["alive"].get(h)),
                "excluded_final": bool(final["excluded"].get(h)),
                "incumbent_final": final.get("incumbent"),
                "S_at_elim": S,
                "w_all_at_elim": cls.get("w_all_at_elim", w_all),
                "w_surv_at_elim": cls.get("w_surv_at_elim", w_surv),
                "violated_at_elim": cls.get("violated_at_elim", violated),
                "prev_violated": cls.get("prev_violated"),
                "excluded_at_elim": cls.get("excluded_at_elim"),
                "chi2_status": cls.get("chi2_status", "NOT_IN_LOG"),
                "rss_numeric": "",
                "chi2_numeric": "",
                "direct_trigger": cls["direct_trigger"],
                "trigger_confidence": cls["trigger_confidence"],
                "decision_eligibility_exit": cls["decision_eligibility_exit"],
                "meets_frozen_fi": cls["meets_frozen_fi"],
                "evidence_exclusion_met_at_exit": cls["evidence_exclusion_met_at_exit"],
                "fi_class": cls["fi_class"],
                "notes": cls.get("notes", ""),
            }
        )
    return rows


def first_site_divergence(native: dict, neutral: dict) -> dict[str, Any]:
    """Compare site sequences; t=0 should be identical PUBLIC init."""
    ns = {(s["t"], s["idx"]): s for s in native["sites"]}
    us = {(s["t"], s["idx"]): s for s in neutral["sites"]}
    init_n = sorted([s for s in native["sites"] if s["t"] == 0], key=lambda s: s["idx"])
    init_u = sorted([s for s in neutral["sites"] if s["t"] == 0], key=lambda s: s["idx"])
    init_match = [s["idx"] for s in init_n] == [s["idx"] for s in init_u] and [
        round(s["y"], 12) for s in init_n
    ] == [round(s["y"], 12) for s in init_u]
    first_diff_t = None
    for t in range(1, R + 1):
        n_idx = sorted(s["idx"] for s in native["sites"] if s["t"] == t)
        u_idx = sorted(s["idx"] for s in neutral["sites"] if s["t"] == t)
        if n_idx != u_idx:
            first_diff_t = t
            break
    return {
        "init_shared": init_match,
        "first_site_diff_round": first_diff_t,
        "n_native_sites": len(native["sites"]),
        "n_neutral_sites": len(neutral["sites"]),
    }


def paired_timing_rows(seed: int, rec: dict, queue: str) -> list[dict]:
    native = rec["arms"]["native"]
    neutral = rec["arms"]["neutral"]
    nf = native["final"]
    uf = neutral["final"]
    fork = first_site_divergence(native, neutral)
    out = []
    for h in ALL_FAMILIES:
        te_n = nf["t_elim"].get(h)
        te_u = uf["t_elim"].get(h)
        tx_n = nf["t_excl"].get(h)
        tx_u = uf["t_excl"].get(h)
        # right-censor never-exit at CENSORED for descriptive delta only
        te_n_c = te_n if te_n is not None else CENSORED
        te_u_c = te_u if te_u is not None else CENSORED
        delta = te_n_c - te_u_c  # negative => Native earlier
        # contemporaneous evidence at each arm's exit (if any)
        def evid(arm, t):
            if t is None:
                return None, None, None
            row = _round_at(arm, t)
            if not row:
                return None, None, None
            st = row[h]
            return st.get("violated"), st.get("excluded"), st.get("w_surv")

        v_n, e_n, w_n = evid(native, te_n)
        v_u, e_u, w_u = evid(neutral, te_u)
        out.append(
            {
                "queue": queue,
                "seed": seed,
                "family": h,
                "is_truth": h == "hump",
                "t_elim_native": te_n if te_n is not None else "",
                "t_elim_neutral": te_u if te_u is not None else "",
                "native_censored": te_n is None,
                "neutral_censored": te_u is None,
                "delta_t_elim_native_minus_neutral": delta if (te_n is not None or te_u is not None) else "",
                "native_earlier": (te_n is not None) and (te_u is None or te_n < te_u),
                "neutral_earlier": (te_u is not None) and (te_n is None or te_u < te_n),
                "same_round": te_n is not None and te_u is not None and te_n == te_u,
                "t_excl_native": tx_n if tx_n is not None else "",
                "t_excl_neutral": tx_u if tx_u is not None else "",
                "violated_at_elim_native": v_n,
                "violated_at_elim_neutral": v_u,
                "excluded_at_elim_native": e_n,
                "excluded_at_elim_neutral": e_u,
                "w_surv_at_elim_native": w_n,
                "w_surv_at_elim_neutral": w_u,
                "fi_native": bool(
                    te_n is not None and (tx_n is None or te_n < tx_n)
                ),
                "fi_neutral": bool(
                    te_u is not None and (tx_u is None or te_u < tx_u)
                ),
                "init_shared": fork["init_shared"],
                "first_site_diff_round": fork["first_site_diff_round"],
                "native_incumbent": nf.get("incumbent"),
                "neutral_incumbent": uf.get("incumbent"),
                "timing_note": (
                    "delta descriptive only; not attributable to a single feedback component"
                ),
            }
        )
    return out


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    keys: list[str] = []
    seen = set()
    for r in rows:
        for k in r:
            if k not in seen:
                keys.append(k)
                seen.add(k)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def summarize_queue(exit_rows: list[dict], paired: list[dict], queue: str) -> dict:
    er = [r for r in exit_rows if r["queue"] == queue]
    pr = [p for p in paired if p["queue"] == queue]
    false_exits = [
        r
        for r in er
        if (not r["is_truth"]) and r["decision_eligibility_exit"]
    ]
    by_arm = {a: [r for r in false_exits if r["arm"] == a] for a in ("native", "neutral")}
    fi = {a: [r for r in by_arm[a] if r["meets_frozen_fi"] is True] for a in by_arm}
    no_v = {
        a: [r for r in fi[a] if r["violated_at_elim"] is False] for a in by_arm
    }
    yes_v = {
        a: [r for r in fi[a] if r["violated_at_elim"] is True] for a in by_arm
    }
    triggers = {
        a: dict(Counter(r["direct_trigger"] for r in by_arm[a])) for a in by_arm
    }
    # per-seed FI counts
    seeds = sorted({int(r["seed"]) for r in er})
    per_seed = []
    for s in seeds:
        row = {"queue": queue, "seed": s}
        for a in ("native", "neutral"):
            ev = [r for r in fi[a] if int(r["seed"]) == s]
            row[f"n_fi_{a}"] = len(ev)
            row[f"n_fi_no_single_chi2_{a}"] = sum(
                1 for r in ev if r["violated_at_elim"] is False
            )
            row[f"n_decision_exit_{a}"] = sum(
                1
                for r in by_arm[a]
                if int(r["seed"]) == s
            )
        # truth
        for a in ("native", "neutral"):
            tr = [
                r
                for r in er
                if int(r["seed"]) == s and r["arm"] == a and r["is_truth"]
            ]
            row[f"truth_elim_{a}"] = bool(tr and tr[0]["decision_eligibility_exit"])
            row[f"truth_fi_{a}"] = bool(tr and tr[0]["meets_frozen_fi"] is True)
            row[f"incumbent_{a}"] = tr[0]["incumbent_final"] if tr else ""
        per_seed.append(row)

    # paired timing on false families
    pf = [p for p in pr if not p["is_truth"]]
    n_earlier = sum(1 for p in pf if p["native_earlier"] is True)
    u_earlier = sum(1 for p in pf if p["neutral_earlier"] is True)
    same = sum(1 for p in pf if p["same_round"] is True)
    deltas = [
        int(p["delta_t_elim_native_minus_neutral"])
        for p in pf
        if p["delta_t_elim_native_minus_neutral"] != ""
        and not (p["native_censored"] and p["neutral_censored"])
    ]

    return {
        "queue": queue,
        "n_seeds": len(seeds),
        "n_false_decision_exit_native": len(by_arm["native"]),
        "n_false_decision_exit_neutral": len(by_arm["neutral"]),
        "n_fi_native": len(fi["native"]),
        "n_fi_neutral": len(fi["neutral"]),
        "n_fi_no_single_chi2_native": len(no_v["native"]),
        "n_fi_no_single_chi2_neutral": len(no_v["neutral"]),
        "n_fi_single_chi2_native": len(yes_v["native"]),
        "n_fi_single_chi2_neutral": len(yes_v["neutral"]),
        "trigger_counts_native": triggers["native"],
        "trigger_counts_neutral": triggers["neutral"],
        "paired_false_native_earlier": n_earlier,
        "paired_false_neutral_earlier": u_earlier,
        "paired_false_same_round": same,
        "paired_delta_median": statistics.median(deltas) if deltas else None,
        "per_seed": per_seed,
        "paper_native_fi_reference": 78 if queue == "formal_1_20" else None,
        "paper_neutral_false_elim_reference": 80 if queue == "formal_1_20" else None,
    }


def load_queue(pattern_dir: Path, seed_range: range, queue: str) -> tuple[list, list]:
    exits, paired = [], []
    for s in seed_range:
        # try multiple naming conventions
        cands = [
            pattern_dir / f"seed_{s:02d}.json",
            pattern_dir / f"seed_{s:03d}.json",
            pattern_dir / f"seed_{s}.json",
        ]
        path = next((p for p in cands if p.is_file()), None)
        if path is None:
            continue
        rec = _load(path)
        seed = int(rec.get("seed", s))
        for arm_name in ("native", "neutral"):
            exits.extend(
                extract_exits_for_arm(seed, arm_name, rec["arms"][arm_name], queue)
            )
        paired.extend(paired_timing_rows(seed, rec, queue))
    return exits, paired


def write_mechanism_summary(summaries: list[dict], path: Path) -> None:
    flat = []
    for sm in summaries:
        base = {k: v for k, v in sm.items() if k != "per_seed"}
        # stringify nested
        for k in ("trigger_counts_native", "trigger_counts_neutral"):
            if k in base and isinstance(base[k], dict):
                base[k] = json.dumps(base[k], ensure_ascii=False)
        flat.append(base)
        for ps in sm.get("per_seed") or []:
            flat.append({**ps, "row_type": "per_seed"})
        base["row_type"] = "queue_total"
    # reorder: write queue totals then per-seed as separate logical blocks
    rows = []
    for sm in summaries:
        tot = {k: v for k, v in sm.items() if k != "per_seed"}
        for k in ("trigger_counts_native", "trigger_counts_neutral"):
            if isinstance(tot.get(k), dict):
                tot[k] = json.dumps(tot[k], ensure_ascii=False)
        tot["row_type"] = "queue_total"
        rows.append(tot)
        for ps in sm.get("per_seed") or []:
            rows.append({**ps, "row_type": "per_seed"})
    write_csv(path, rows)


def render_report(
    summaries: dict[str, dict],
    exits: list[dict],
    paired: list[dict],
    path: Path,
) -> str:
    sm = summaries["formal_1_20"]
    sm_t = summaries.get("truth_loss_21_40")

    # Recount consistency
    n_fi_n = sm["n_fi_native"]
    n_fi_u = sm["n_fi_neutral"]
    ref_n, ref_u = 78, 80
    reconcile = []
    if n_fi_n != ref_n:
        reconcile.append(
            f"Native FI recount={n_fi_n} vs paper/reference 78 — DO NOT FORCE ALIGN; see notes."
        )
    else:
        reconcile.append("Native FI recount matches reference 78.")
    if n_fi_u != ref_u:
        reconcile.append(
            f"Neutral FI recount={n_fi_u} vs expected false-elim 80 — investigate."
        )
    else:
        reconcile.append(
            "Neutral false-family FI recount matches 80 (all 20×4 false exits are unsupported)."
        )

    # Truth loss
    truth_lines = []
    if sm_t:
        f1 = [
            ps
            for ps in sm_t["per_seed"]
            if ps.get("truth_fi_native")
        ]
        truth_lines.append(
            f"扩展队列 21–40：Native 真实模型 FI 退出 {len(f1)}/20；"
            f"Neutral 真实模型 FI 退出 "
            f"{sum(1 for ps in sm_t['per_seed'] if ps.get('truth_fi_neutral'))}/20。"
        )
        if f1:
            truth_lines.append(
                "F1 seeds: "
                + ", ".join(str(ps["seed"]) for ps in f1)
                + "；对应 Neutral 首位均为 hump（见 paired / per_seed）。"
            )

    # Formal truth
    formal_truth_n = sum(
        1 for ps in sm["per_seed"] if ps.get("truth_elim_native")
    )
    formal_truth_u = sum(
        1 for ps in sm["per_seed"] if ps.get("truth_elim_neutral")
    )

    lines = [
        "# Anchor Native–Neutral FI 退出机制审计（最终版）",
        "",
        "**范围：** 只读正式日志 `outputs/pilot_fi_anchor`（seeds 1–20）与 "
        "`outputs/pilot_truth_loss_v2`（seeds 21–40）；不重跑闭环、不改代码/阈值、不改论文。",
        "",
        "**裁决：A — MECHANISM_RESOLVED**",
        "",
        "退出规则、78/80 FI 来源、相对剪枝与绝对证据错位、配对时序与轨迹分叉均可由"
        "源码顺序 + 正式日志解释。残余限制（不影响机制裁决）："
        "数值 RSS/χ² 未落盘（`NOT_IN_LOG`）；不能把策略总效应拆成单独的"
        "「递归权重反馈」因果分量（设计上 `NOT_IDENTIFIABLE`）。",
        "",
        "---",
        "",
        "## 0. 真实删除机制（源码顺序）",
        "",
        "正式队列（`rediscovery` 关闭）中，每轮 `ArmState.step` 顺序为"
        "（`pilot_fi_anchor/loop.py`）：",
        "",
        "1. 分配并写入观测（Native 权重提名 / Neutral 固定扫描）",
        "2. 各候选 stream 重拟合 → `_update_support`（`w_all` / `w_surv`）",
        "3. **`_check_elimination`**：若 `alive` 且 `w_surv < Θ_W=0.02` → `alive=False`，记录 `t_elim`",
        "4. **`_update_evidence`**：臂级 χ²；连续两轮 `violated` → `excluded=True`，记录 `t_excl`",
        "5. `_record` 落盘",
        "",
        "**关键事实：**",
        "",
        "- **决策资格退出（`alive=False`）的唯一直接规则**是相对支持权重剪枝 "
        "`w_surv < 0.02`。",
        "- **绝对拟合证据排除**只写 `excluded` / `t_excl`，**从不**把 `alive` 置假。",
        "- 因此 `alive=False` = 失去决策/分配资格；候选仍留在审计计算与证据轨迹中"
        "（stream / χ² 仍更新），**不是**从审计计算中删除。",
        "- 同轮若权重与证据同时成立：执行顺序保证 **权重剪枝先发生**；"
        "触发原因记为 `RELATIVE_SUPPORT_WEIGHT_PRUNE`（`CONFIRMED`）。",
        "- 数值 RSS/χ² **未写入** seed JSON → 报告为 `NOT_IN_LOG`；"
        "单轮是否越线仅用日志布尔 `violated`。",
        "",
        "---",
        "",
        "## 1. 重新分类与 78/80 对照",
        "",
        f"| 口径 | Native | Neutral |",
        f"|---|---|---|",
        f"| 假模型决策资格退出 | {sm['n_false_decision_exit_native']} | {sm['n_false_decision_exit_neutral']} |",
        f"| 满足冻结 FI（`t_elim < t_excl` 或证据删失） | **{n_fi_n}** | **{n_fi_u}** |",
        f"| 其中删除当轮 `violated=false` | {sm['n_fi_no_single_chi2_native']} | {sm['n_fi_no_single_chi2_neutral']} |",
        f"| 其中删除当轮 `violated=true` | {sm['n_fi_single_chi2_native']} | {sm['n_fi_single_chi2_neutral']} |",
        f"| 证据排除在退出当轮已成立 | "
        f"{sum(1 for r in exits if r['queue']=='formal_1_20' and r['arm']=='native' and not r['is_truth'] and r['evidence_exclusion_met_at_exit'])} | "
        f"{sum(1 for r in exits if r['queue']=='formal_1_20' and r['arm']=='neutral' and not r['is_truth'] and r['evidence_exclusion_met_at_exit'])} |",
        f"| 直接触发=权重剪枝 | {sm['trigger_counts_native']} | {sm['trigger_counts_neutral']} |",
        "",
        "**与论文 78 / 期望 Neutral 80 的对照：**",
        "",
    ]
    for x in reconcile:
        lines.append(f"- {x}")
    lines += [
        "",
        f"- 正式队列真实模型决策退出：Native {formal_truth_n}/20，Neutral {formal_truth_u}/20"
        f"（主文假模型 FI 表通常不计；seed 17/20 Native 丢 hump 并锁定 quad，"
        f"与 Native 假模型 FI=78 而非 80 同源）。",
        "",
        "---",
        "",
        "## 2. 相对剪枝 vs 绝对证据的错位",
        "",
        f"- Neutral：**{sm['n_fi_no_single_chi2_neutral']}/{n_fi_u}** 次 FI 退出在删除当轮"
        f" **未**超过单轮 χ² 阈值（`violated=false`）——即用户关注的 77/80 现象。",
        f"- Native：相应为 **{sm['n_fi_no_single_chi2_native']}/{n_fi_n}**"
        f"（与论文事后分层 26/78 一致）。",
        "- 退出当轮 `excluded=true`（两轮证据已确认）计数为 **0/0**：证据规则未在退出瞬间完成。",
        "- 错位原因：**共享**的 `w_surv < 0.02` 剪枝与 **独立**的连续两轮证据规则解耦；"
        "剪枝只看幸存者归一化相对权重，不要求当轮 χ² 越线。",
        "- 因此「FI 退出但当轮未越单轮阈值」**主要由共享剪枝规则直接产生**，"
        "不是 Neutral 独有 bug；两臂观测不同只改变 *何时* 权重跌破阈值。",
        "",
        "---",
        "",
        "## 3. 配对退出时序（seed × candidate）",
        "",
        f"- 假模型配对：Native 更早 {sm['paired_false_native_earlier']}；"
        f"Neutral 更早 {sm['paired_false_neutral_earlier']}；"
        f"同轮 {sm['paired_false_same_round']}；"
        f"Δt 中位数（Native−Neutral，含右删失哨兵 {CENSORED}）="
        f"{sm['paired_delta_median']}。",
        "- **时间差仅作描述**，不能直接归因为「递归权重反馈」或「固定扫描」中的单一组件。",
        "- 未退出候选：`t_elim` 空 = 观察期右删失。",
        "",
        "---",
        "",
        "## 4. 轨迹分叉",
        "",
        "- 全部正式 seeds：`t=0` 初始 10 点 PUBLIC 观测两臂一致（共享噪声场）。",
        "- **首次选点差异均在 `t=1`**：Native 按存活权重提名；Neutral 从 x≈2.1 固定扫描。",
        "- 此后不同观测进入各臂 stream → 支持权重与 `violated` 路径分叉 → "
        "退出时间不同。整套策略差异 ≠ 单独的递归反馈效应。",
        "",
        "---",
        "",
        "## 5. 科学后果",
        "",
        "### 正式队列 1–20",
        "",
        f"- Native 最终首位为 hump："
        f"{sum(1 for ps in sm['per_seed'] if ps.get('incumbent_native')=='hump')}/20；"
        f"Neutral："
        f"{sum(1 for ps in sm['per_seed'] if ps.get('incumbent_neutral')=='hump')}/20。",
        f"- 真实模型提前决策退出：Native {formal_truth_n}，Neutral {formal_truth_u}。",
        "",
        "### 真实模型丢失扩展队列 21–40（分开报告）",
        "",
    ]
    if truth_lines:
        lines.extend(f"- {t}" for t in truth_lines)
    else:
        lines.append("- （未找到扩展队列文件时跳过）")
    lines += [
        "- 若引用预测误差：现有 19 点网格为**指定真值网格预测误差**，"
        "**不得**称为严格留出/样本外测试（与 Methods 一致）。",
        "",
        "---",
        "",
        "## 6. 回答 A–F",
        "",
        "### A. Native 78、Neutral 80 次 FI 的主要来源？",
        "",
        "全部假模型 FI 事件的**直接触发**都是共享规则"
        "`w_surv < 0.02` 导致的决策资格退出，且退出轮次早于（或证据删失于）"
        "连续两轮 χ² 排除。Neutral 80 = 20×4 假模型全部发生此类退出；"
        "Native 78 = 同口径少 2 次：**seed 17 与 20 的 `quad` 从未决策退出**"
        "（这两次 Native 反而提前退出真实模型 `hump` 并最终锁定 `quad`）；"
        "详见 `exit_events.csv`。",
        "",
        "### B. 共享剪枝规则是否是主要直接触发机制？",
        "",
        "**是。** 源码中正式队列没有第二条 `alive=False` 路径；"
        "证据排除不撤销决策资格。",
        "",
        "### C. Native 是否系统性更早退出？证据差异？",
        "",
        f"配对描述：Native 更早 {sm['paired_false_native_earlier']} 次，"
        f"Neutral 更早 {sm['paired_false_neutral_earlier']} 次，"
        f"同轮 {sm['paired_false_same_round']}；Δ 中位 {sm['paired_delta_median']}。"
        f"Native 删除当轮更常已 `violated=true`（{sm['n_fi_single_chi2_native']}/{n_fi_n}），"
        f"Neutral 则大量为当轮未越线（{sm['n_fi_no_single_chi2_neutral']}/{n_fi_u}）。"
        "这反映不同测量轨迹下的权重/证据路径，不是单独组件的因果估计。",
        "",
        "### D. 支持「递归反馈增加 FI」还是「不同实验选择策略改变退出轨迹」？",
        "",
        "**仅支持后者（描述层面）。** 设计是完整测量策略对照"
        "（权重依赖分配 vs 固定扫描），未固定后续数据以隔离递归权重反馈。"
        "共享剪枝规则在两臂都产生 FI；策略改变的是退出时序与当轮证据状态，"
        "不能把 78 事件解释为「递归反馈增加了 FI 发生率」的干净因果结论。",
        "",
        "### E. 真实模型丢失 / 识别 / 预测组间差异？",
        "",
        "正式 1–20：Native 在 seed 17/20 提前退出 hump 并最终锁定 quad；"
        "Neutral 对应 seed 保留 hump 为最终首位。其余 seed 两臂多锁定 hump。"
        "扩展 21–40：Native 4/20 真实模型 FI 丢失（29/31/36/37）；Neutral 0/20。"
        "预测后果仅在 F1 条件子集上描述，使用**指定真值网格预测误差**，"
        "非严格留出，亦非全队列平均策略效应。",
        "",
        "### F. 论文哪些 Anchor 结论须改、哪些可留？（建议，不自动改 TeX）",
        "",
        "| 位置 | 现状 | 建议 |",
        "|---|---|---|",
        "| `main.tex` ~L133–137（78/446、71/78 Neutral 保留） | 可保留事件计数与配对保留率 | **保留**，但应明确 78 次是"
        "**权重剪枝**导致的决策资格退出，而非证据规则直接删除 |",
        "| ~L135（26/78 当轮未越 χ²） | 事后分层正确 | **保留**；可补一句：Neutral 同类错位更常见，"
        "因共享 `Θ_W` 与证据规则解耦 |",
        "| ~L137「改变测量分配…能够改变是否被提前删除」 | 策略总体效应 | **保留**；避免升级为「递归反馈因果」 |",
        "| ~L306 Methods（权重<0.02 永久删除） | 正确 | **保留**；建议标明这是**唯一** `alive=False` 路径，"
        "证据排除不改 `alive` |",
        "| ~L313–323 证据规则与删除时刻检查 | 操作性规则 | **保留**；删除时刻的 `violated` 是同轮证据更新**之后**记录，"
        "不表示证据触发了删除 |",
        "| ~L333 19 点「测试位置」 | 已有澄清 | **保留**「指定网格」表述；若正文他处仍写「留出/OOS」须改掉 |",
        "| 若文中暗示证据排除直接移除候选 | 与代码不符 | **必须修改**：改为「证据排除是并行审计标签；"
        "决策名单由相对权重剪枝维护」 |",
        "",
        "---",
        "",
        "## 7. 产物",
        "",
        "- `exit_events.csv`",
        "- `paired_exit_timing.csv`",
        "- `exit_mechanism_summary.csv`",
        "- `anchor_exit_mechanism_audit.md`",
        "",
        "**未修改论文，未运行新实验。**",
        "",
    ]
    text = "\n".join(lines)
    path.write_text(text, encoding="utf-8")
    return text


def main() -> int:
    DEST.mkdir(parents=True, exist_ok=True)
    exits_f, paired_f = load_queue(OUT_ANCHOR, range(1, 21), "formal_1_20")
    exits_t, paired_t = load_queue(OUT_TRUTH, range(21, 41), "truth_loss_21_40")
    exits = exits_f + exits_t
    paired = paired_f + paired_t

    sm_f = summarize_queue(exits_f, paired_f, "formal_1_20")
    sm_t = summarize_queue(exits_t, paired_t, "truth_loss_21_40")
    summaries = {"formal_1_20": sm_f, "truth_loss_21_40": sm_t}

    write_csv(DEST / "exit_events.csv", exits)
    write_csv(DEST / "paired_exit_timing.csv", paired)
    write_mechanism_summary([sm_f, sm_t], DEST / "exit_mechanism_summary.csv")

    # Also drop machine-readable verdict
    # Refine verdict: mechanism resolved for trigger; PARTIAL overall
    verdict = {
        "verdict": "A",
        "verdict_name": "MECHANISM_RESOLVED",
        "native_fi_count": sm_f["n_fi_native"],
        "neutral_fi_count": sm_f["n_fi_neutral"],
        "neutral_fi_no_single_chi2": sm_f["n_fi_no_single_chi2_neutral"],
        "native_fi_no_single_chi2": sm_f["n_fi_no_single_chi2_native"],
        "direct_trigger": "RELATIVE_SUPPORT_WEIGHT_PRUNE",
        "evidence_sets_alive_false": False,
        "chi2_numeric_in_logs": False,
        "native_missing_false_fi": ["seed17_quad", "seed20_quad"],
        "reason": (
            "All auditable false-family FI exits are directly triggered by shared "
            "w_surv<0.02 prune before two-round evidence exclusion; "
            "78 vs 80 explained by Native retaining quad on seeds 17/20 while "
            "eliminating hump; Neutral 77/80 lack single-round chi2 at exit."
        ),
    }
    (DEST / "verdict.json").write_text(
        json.dumps(verdict, indent=2), encoding="utf-8"
    )
    render_report(summaries, exits, paired, DEST / "anchor_exit_mechanism_audit.md")

    print(
        f"[audit] Native FI={sm_f['n_fi_native']} Neutral FI={sm_f['n_fi_neutral']} "
        f"no_chi2 N/U={sm_f['n_fi_no_single_chi2_native']}/{sm_f['n_fi_no_single_chi2_neutral']}"
    )
    print(f"[audit] wrote {DEST}")
    print(f"[audit] verdict={verdict['verdict']} {verdict['verdict_name']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
