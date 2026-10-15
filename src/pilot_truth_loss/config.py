"""Frozen Truth-Loss Failure Mode parameters.

Imports shared world / evidence / budget constants from pilot_fi_anchor.
Does NOT modify anchor config.  Pair selection (phase 1) used seeds 1–20;
v2 confirmatory uses independent seeds 21–40 only.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from pilot_fi_anchor.config import (
    ALPHA_EV,
    FAMILY_ORDER,
    M,
    N_CAND,
    PERSIST,
    R,
    SEEDS,
    SIGMA,
    TRUTH_FAMILY,
    TRUTH_PARAMS,
    X0_IDX,
)
from pilot_fi_anchor.evidence_calibration import _neutral_sweep_indices

# --- version ---------------------------------------------------------------
VERSION = "pilot-truth-loss-v0.2.2"
ANCHOR_VERSION = "pilot-v1.1.2-b2-v2"

# --- pair (frozen after phase-1 calibration on seeds 1–20) ---------------
# DGP truth is fixed to anchor hump.  Competitor selected by PC1–PC6 rule;
# pow remains in hypothesis space but is NOT required as wrong lock-in winner.
COMPETITOR_FAMILY = "pow"

# --- calibration (historical; seeds 1–20 only) ------------------------------
PAIR_CALIBRATION_SEEDS = SEEDS
INITIAL_MAX_GAP_SIGMA = 1.0
EXTENDED_TAIL_X_MIN = 5.0
EXTENDED_MIN_TAIL_DIV_SIGMA = 1.5

# --- v1 observed seeds (excluded from v2 confirmatory statistics) ----------
V1_OBSERVED_SEEDS = SEEDS  # seeds 1..20
V1_N_SEEDS = len(V1_OBSERVED_SEEDS)

# --- v2 independent confirmatory population --------------------------------
CONFIRMATORY_SEEDS = tuple(range(21, 41))  # seeds 21..40, n=20
CONFIRMATORY_N_SEEDS = len(CONFIRMATORY_SEEDS)

# --- F2-v2 stability rule --------------------------------------------------
F2_STABILITY_ROUNDS = 5  # final incumbent must hold last 5 rounds

# --- v2 confirmatory gates (frozen) ----------------------------------------
G2_F2V2_FRAC = 0.60  # F2-v2 / F1 on F1 seeds
G3_F3_FRAC = 0.60    # F3 / F1 on F1 seeds
G4_NEUTRAL_TRUTH_EXCLUDED_MAX = 0  # B2-v2 sanity: Neutral truth excluded = 0/N

# --- held-out grid (never used in fit / allocation / elimination) -----------
_HELD_LO = 120
_HELD_HI = 380
_HELD_MOD = 8
_HELD_REM = 3


def held_out_indices() -> tuple[int, ...]:
    blocked = set(X0_IDX) | set(_neutral_sweep_indices())
    return tuple(
        i
        for i in range(N_CAND)
        if i not in blocked
        and _HELD_LO <= i <= _HELD_HI
        and i % _HELD_MOD == _HELD_REM
    )


HELD_OUT_IDX = held_out_indices()

# --- output paths ----------------------------------------------------------
V1_RESULTS_DIR = "outputs/pilot_truth_loss"           # v1 historical (cleared)
V2_RESULTS_DIR = "outputs/pilot_truth_loss_v2"        # v2 formal confirmatory only
V2_DRY_RUN_RESULTS_DIR = "outputs/pilot_truth_loss_v2_dryrun"  # dev dry-run only

# Expected B2-v2 sequential Bonferroni alpha (sanity gate G4)
EXPECTED_ALPHA_EV = 0.05 / (len(FAMILY_ORDER) * R)


def assert_v2_confirmatory_seeds_exact(seeds: tuple[int, ...] | list[int]) -> None:
    """Formal v2 confirmatory must use exactly seeds 21–40 (n=20)."""
    expected = set(CONFIRMATORY_SEEDS)
    got = set(seeds)
    if got != expected:
        missing = sorted(expected - got)
        extra = sorted(got - expected)
        parts = []
        if missing:
            parts.append(f"missing {missing[:5]}{'...' if len(missing) > 5 else ''} ({len(missing)} total)")
        if extra:
            parts.append(f"extra {extra[:5]}{'...' if len(extra) > 5 else ''} ({len(extra)} total)")
        detail = "; ".join(parts) if parts else "wrong seed set"
        raise ValueError(
            f"v2 confirmatory requires exactly seeds {CONFIRMATORY_SEEDS[0]}–"
            f"{CONFIRMATORY_SEEDS[-1]} (n={CONFIRMATORY_N_SEEDS}); {detail}"
        )


def assert_dry_run_seeds(seeds: tuple[int, ...] | list[int]) -> None:
    """Dry-run dev path: subset allowed, but never v1-observed seeds."""
    bad = sorted(set(seeds) & set(V1_OBSERVED_SEEDS))
    if bad:
        raise ValueError(
            f"dry-run must not include v1-observed seeds {bad}"
        )
    if any(s < CONFIRMATORY_SEEDS[0] for s in seeds):
        raise ValueError(
            f"dry-run seeds must be >= {CONFIRMATORY_SEEDS[0]} (fresh population)"
        )


@dataclass(frozen=True)
class TruthLossConfig:
    version: str = VERSION
    anchor_version: str = ANCHOR_VERSION
    truth_family: str = TRUTH_FAMILY
    competitor_family: str = COMPETITOR_FAMILY
    truth_params: dict[str, float] = field(default_factory=lambda: dict(TRUTH_PARAMS))
    pair_calibration_seeds: tuple[int, ...] = PAIR_CALIBRATION_SEEDS
    v1_observed_seeds: tuple[int, ...] = V1_OBSERVED_SEEDS
    confirmatory_seeds: tuple[int, ...] = CONFIRMATORY_SEEDS
    held_out_idx: tuple[int, ...] = HELD_OUT_IDX
    alpha_ev: float = ALPHA_EV
    persist: int = PERSIST
    rounds: int = R
    m_per_round: int = M
    sigma: float = SIGMA
    f2_stability_rounds: int = F2_STABILITY_ROUNDS
    results_dir: str = V2_RESULTS_DIR
    g2_f2v2_frac: float = G2_F2V2_FRAC
    g3_f3_frac: float = G3_F3_FRAC
    g4_neutral_truth_excluded_max: int = G4_NEUTRAL_TRUTH_EXCLUDED_MAX
    dry_run_results_dir: str = V2_DRY_RUN_RESULTS_DIR

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
