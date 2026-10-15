#!/usr/bin/env python3
"""Read-only verification of eligibility seeds 201–240 + Open Eligibility lock."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AUDIT_VER = Path(__file__).resolve().parents[1] / "verification"
AUDIT_VER.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(ROOT))

from evidence_gated_eligibility.config import FORMAL_SEEDS  # noqa: E402
from evidence_gated_eligibility.open_eligibility_posthoc import (  # noqa: E402
    LOCK_PATH,
    aggregate,
    analyze_seed,
    assert_against_lock,
)


def main() -> int:
    rows = [analyze_seed(s) for s in FORMAL_SEEDS]
    agg = aggregate(rows)
    lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
    lock_ok = True
    lock_err = None
    try:
        assert_against_lock(rows, agg, lock)
    except Exception as e:  # noqa: BLE001
        lock_ok = False
        lock_err = str(e)

    fg_truth = 0
    fg_rmse: list[float] = []
    a_minus_c = {"better": 0, "worse": 0, "same": 0}
    for s in FORMAL_SEEDS:
        rec = json.loads(
            (ROOT / f"evidence_gated_eligibility/outputs/stage2_formal/seed_{s}.json")
            .read_text(encoding="utf-8")
        )
        sca = rec["scores"]["native"]
        scc = rec["scores"]["full_evidence_gate"]
        fg_truth += int(scc["truth_selected"])
        fg_rmse.append(float(scc["rmse_eval_noiseless"]))
        da = float(sca["rmse_with_fail_penalty"]) - float(scc["rmse_with_fail_penalty"])
        if da > 0:
            a_minus_c["better"] += 1
        elif da < 0:
            a_minus_c["worse"] += 1
        else:
            a_minus_c["same"] += 1

    out = {
        "module": "final_eligibility_open_decision_fullgate",
        "method": "readonly_recompute_from_stage2_formal",
        "lock_ok": lock_ok,
        "lock_error": lock_err,
        "truth_selected": {
            "native": agg["native"]["truth_selected_k"],
            "open": agg["open_eligibility"]["truth_selected_k"],
            "decision_only": agg["decision_only"]["truth_selected_k"],
            "full_gate": fg_truth,
        },
        "rmse_mean": {
            "native": agg["native"]["rmse_finite_mean"],
            "open": agg["open_eligibility"]["rmse_finite_mean"],
            "decision_only": agg["decision_only"]["rmse_finite_mean"],
            "full_gate": sum(fg_rmse) / len(fg_rmse),
        },
        "rmse_median": {
            "native": agg["native"]["rmse_finite_median"],
            "open": agg["open_eligibility"]["rmse_finite_median"],
            "decision_only": agg["decision_only"]["rmse_finite_median"],
        },
        "selection_diff": agg["selection_diff"],
        "full_gate_vs_native_rmse": a_minus_c,
        "expected": {
            "native": 37,
            "open": 40,
            "decision_only": 39,
            "full_gate": 40,
            "open_ne_native": [208, 224, 232],
            "decision_ne_native": [224, 232],
            "full_gate_better_worse_same": [8, 5, 27],
        },
    }
    ok = (
        lock_ok
        and out["truth_selected"]["native"] == 37
        and out["truth_selected"]["open"] == 40
        and out["truth_selected"]["decision_only"] == 39
        and out["truth_selected"]["full_gate"] == 40
        and out["selection_diff"]["open_ne_native"] == [208, 224, 232]
        and out["selection_diff"]["decision_ne_native"] == [224, 232]
        and a_minus_c == {"better": 8, "worse": 5, "same": 27}
    )
    out["status"] = "PASS" if ok else "FAIL"
    path = AUDIT_VER / "eligibility_201_240_verification.json"
    path.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
