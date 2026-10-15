"""Failure-status score schema must be complete for formal aggregation."""
from __future__ import annotations

from evidence_gated_eligibility.config import (
    FAMILY_ORDER,
    STATUS_ABORT_EMPTY,
    STATUS_DECISION_EMPTY,
    STATUS_OK,
    TRUTH_FAMILY,
)
from evidence_gated_eligibility.loop_ege import _score_arm

REQUIRED = {
    "rmse_eval_noiseless",
    "rmse_with_fail_penalty",
    "primary_status",
    "failure_type",
    "is_failure",
    "truth_selected",
    "truth_excluded_operational",
    "truth_eligibility_lost",
    "n_false_eligible",
    "n_measured",
}


def _pack(status: str, *, excluded_truth: bool = True, n: int = 95, abort=None):
    excluded = {h: True for h in FAMILY_ORDER}
    if not excluded_truth:
        excluded[TRUTH_FAMILY] = False
    eligible = {h: (not excluded[h]) for h in FAMILY_ORDER}
    return {
        "sites": [{"idx": i} for i in range(n)],
        "final": {
            "incumbent": None,
            "incumbent_theta": None,
            "primary_status": status,
            "abort_status": abort,
            "excluded": excluded,
            "eligible": eligible,
            "n_measured": n,
            "arm_theta": {},
        },
    }


def test_decision_empty_has_full_fields():
    sc = _score_arm(_pack(STATUS_DECISION_EMPTY))
    assert set(sc.keys()) == REQUIRED
    assert sc["is_failure"] is True
    assert sc["failure_type"] == STATUS_DECISION_EMPTY
    assert sc["primary_status"] == STATUS_DECISION_EMPTY
    assert sc["rmse_eval_noiseless"] is None
    assert sc["rmse_with_fail_penalty"] is not None
    assert sc["truth_selected"] is False
    assert sc["truth_excluded_operational"] is True
    assert sc["truth_eligibility_lost"] is True
    assert sc["n_false_eligible"] == 0
    assert sc["n_measured"] == 95


def test_abort_empty_has_full_fields():
    sc = _score_arm(_pack(STATUS_OK, abort=STATUS_ABORT_EMPTY, n=40))
    assert set(sc.keys()) == REQUIRED
    assert sc["is_failure"] is True
    assert sc["failure_type"] == STATUS_ABORT_EMPTY
    assert sc["primary_status"] == STATUS_ABORT_EMPTY
    assert sc["rmse_eval_noiseless"] is None
    assert sc["truth_eligibility_lost"] is True
    assert sc["n_measured"] == 40


def test_ok_native_schema_matches():
    pack = {
        "sites": [{"idx": i} for i in range(135)],
        "final": {
            "incumbent": "hump",
            "incumbent_theta": {"A": 8.0, "mu": 4.5, "s": 2.5},
            "primary_status": STATUS_OK,
            "excluded": {h: False for h in FAMILY_ORDER},
            "alive": {h: (h == "hump") for h in FAMILY_ORDER},
            "n_measured": 135,
        },
    }
    sc = _score_arm(pack)
    assert set(sc.keys()) == REQUIRED
    assert sc["is_failure"] is False
    assert sc["failure_type"] is None
    assert sc["rmse_eval_noiseless"] is not None
    assert sc["truth_selected"] is True
    assert sc["truth_eligibility_lost"] is False
