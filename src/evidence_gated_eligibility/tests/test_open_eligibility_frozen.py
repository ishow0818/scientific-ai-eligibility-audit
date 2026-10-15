"""Lock Open Eligibility post-hoc conclusions for seeds 201–240."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from evidence_gated_eligibility.config import FAMILY_ORDER, FORMAL_SEEDS
from evidence_gated_eligibility.eligibility import (
    require_family_bool_map,
    require_family_flag,
    select_incumbent_by_w_all,
    select_incumbent_open_pool,
)
from evidence_gated_eligibility.open_eligibility_posthoc import (
    LOCK_PATH,
    aggregate,
    analyze_seed,
    assert_against_lock,
    open_eligibility_from_native,
)

ROOT = Path(__file__).resolve().parents[1]
STAGE2 = ROOT / "outputs" / "stage2_formal"


def test_strict_excluded_alive_raise_on_missing():
    complete = {h: False for h in FAMILY_ORDER}
    require_family_bool_map(complete, "excluded")
    with pytest.raises(KeyError, match="missing families"):
        require_family_bool_map({"hump": False}, "excluded")
    with pytest.raises(KeyError, match="missing family"):
        require_family_flag({"hump": True}, "quad", "alive")


def test_select_incumbent_requires_complete_w_all():
    excluded = {h: False for h in FAMILY_ORDER}
    with pytest.raises(KeyError, match="w_all"):
        select_incumbent_by_w_all({"hump": 1.0}, excluded)
    with pytest.raises(KeyError, match="w_all"):
        select_incumbent_open_pool({"hump": 1.0})


def test_frozen_lock_file_present():
    assert LOCK_PATH.is_file(), f"missing lock: {LOCK_PATH}"
    lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
    assert lock["lock_version"] == "open-eligibility-lock-v1"
    assert lock["n"] == 40
    assert lock["seeds"] == list(FORMAL_SEEDS)
    assert len(lock["per_seed"]) == 40


@pytest.mark.parametrize("seed", list(FORMAL_SEEDS))
def test_per_seed_winners_params_rmse_locked(seed: int):
    lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
    exp = next(x for x in lock["per_seed"] if int(x["seed"]) == seed)
    row = analyze_seed(seed)
    atol = float(lock["rmse_atol"])

    assert row["native_incumbent"] == exp["native_incumbent"]
    assert row["open_incumbent"] == exp["open_incumbent"]
    assert row["decision_only_incumbent"] == exp["decision_only_incumbent"]
    assert row["native_truth"] == exp["native_truth"]
    assert row["open_truth"] == exp["open_truth"]
    assert row["decision_truth"] == exp["decision_truth"]
    assert row["open_winner_excluded_by_evidence"] == exp[
        "open_winner_excluded_by_evidence"
    ]
    assert row["open_winner_pruned_by_history"] == exp["open_winner_pruned_by_history"]

    # Parameter / score reuse from Native
    assert row["theta_reused_from_native"] is True
    assert row["w_all_reused_from_native"] is True
    assert row["open_incumbent_theta"] == exp["open_incumbent_theta"]
    native = json.loads((STAGE2 / f"seed_{seed}.json").read_text(encoding="utf-8"))
    af = native["arms"]["native"]["final"]
    assert row["open_incumbent_theta"] == af["arm_theta"][row["open_incumbent"]]

    for key in ("native_rmse", "open_rmse", "decision_rmse"):
        assert abs(float(row[key]) - float(exp[key])) <= atol

    pack = open_eligibility_from_native(native["arms"]["native"])
    assert pack["final"]["incumbent"] == exp["open_incumbent"]
    assert pack["final"]["incumbent_theta"] == exp["open_incumbent_theta"]


def test_aggregate_and_full_lock_contract():
    lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
    rows = [analyze_seed(s) for s in FORMAL_SEEDS]
    agg = aggregate(rows)
    assert_against_lock(rows, agg, lock)

    exp = lock["aggregate"]
    assert exp["native_truth_selected_k"] == 37
    assert exp["open_truth_selected_k"] == 40
    assert exp["decision_truth_selected_k"] == 39
    assert exp["open_ne_native"] == [208, 224, 232]
    assert exp["open_ne_decision"] == [208]
    assert exp["decision_ne_native"] == [224, 232]
    assert exp["open_winner_evidence_excluded_k"] == 1
    assert exp["open_winner_history_pruned_k"] == 3
