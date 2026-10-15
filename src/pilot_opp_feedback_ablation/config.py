"""Frozen smoke settings for opportunity-feedback ablation (do not tune post-hoc)."""

from __future__ import annotations

from pilot_fi_anchor.config import ARM_CODE

# Pre-registered smoke seeds only (not a confirmatory sample).
SMOKE_SEEDS: tuple[int, ...] = (1, 2)

# Formal confirmatory ablation: same seed set as Anchor pilot (1–20).
FORMAL_SEEDS: tuple[int, ...] = tuple(range(1, 21))

# Arm tags in this ablation (Neutral arm is NOT used).
ARM_NATIVE = "native"
ARM_NO_OPP = "no_opp_fb"

# CRN pairing (v0.2): BOTH arms derive allocation RNG from the SAME Native
# arm code so SeedSequence entropy matches formal Native. Each call still
# creates an independent Generator instance (identical initial state).
# Do NOT use Neutral's code (1) or a distinct No-Opp code for allocation.
ALLOC_RNG_ARM_CODE: int = int(ARM_CODE["native"])  # == 0

# Legacy mistaken pairing (v0.1 smoke): No-Opp used code 2. Kept for docs only.
LEGACY_NO_OPP_ALLOC_CODE: int = 2

# v0.1 smoke preserved; v0.2 RNG-fixed smoke writes here without overwrite.
RESULTS_DIR_V1 = "outputs/pilot_opp_feedback_ablation_smoke"
RESULTS_DIR = "outputs/pilot_opp_feedback_ablation_smoke_v2_rng"
FORMAL_RESULTS_DIR = "outputs/pilot_opp_feedback_ablation_formal_v2"

ABLATION_VERSION = "opp-fb-ablation-0.2.0-rng-crn"
