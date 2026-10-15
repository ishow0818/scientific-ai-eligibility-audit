"""Frozen Stage-1 constants for Evidence-Gated Eligibility (no threshold tuning)."""
from __future__ import annotations

from pilot_fi_anchor.config import (
    FAMILY_ORDER,
    FALSE_FAMILIES,
    M,
    MASTER_SALT,
    N0,
    N_CAND,
    R,
    RNG_ALLOC,
    THETA_W,
    TRUTH_FAMILY,
)

EGE_VERSION = "ege-stage2-0.1.0"
EVAL_PROTOCOL_VERSION = "ege-eval-midpoints-v1"

# Allocation CRN: same construction as formal Native (arm code 0)
ALLOC_ARM_CODE = 0

ARM_NATIVE = "native"
ARM_DECISION_ONLY = "decision_only"
ARM_FULL_GATE = "full_evidence_gate"

# Smoke only (Stage 1). Formal queue reserved — do not run here.
SMOKE_SEEDS = (1001, 1002, 1003)
FORMAL_SEEDS = tuple(range(201, 241))
REPRO_SEEDS = (1, 3, 20)

STATUS_OK = "OK"
STATUS_DECISION_EMPTY = "DECISION_EMPTY"
STATUS_ABORT_EMPTY = "ABORT_EMPTY_ELIGIBLE"
STATUS_ABORT_ZERO_MASS = "ABORT_ZERO_WEIGHT_MASS"

EXPECTED_N_MEASURED = N0 + R * M  # 135

__all__ = [
    "EGE_VERSION",
    "EVAL_PROTOCOL_VERSION",
    "ALLOC_ARM_CODE",
    "ARM_NATIVE",
    "ARM_DECISION_ONLY",
    "ARM_FULL_GATE",
    "SMOKE_SEEDS",
    "FORMAL_SEEDS",
    "REPRO_SEEDS",
    "STATUS_OK",
    "STATUS_DECISION_EMPTY",
    "STATUS_ABORT_EMPTY",
    "STATUS_ABORT_ZERO_MASS",
    "EXPECTED_N_MEASURED",
    "FAMILY_ORDER",
    "FALSE_FAMILIES",
    "TRUTH_FAMILY",
    "THETA_W",
    "R",
    "M",
    "N0",
    "N_CAND",
    "MASTER_SALT",
    "RNG_ALLOC",
]
