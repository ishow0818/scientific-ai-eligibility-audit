"""Frozen pilot parameters. Do not tune.

Single source of truth for the False-Identifiability anchor closed-loop pilot.
Any change requires an EXPERIMENT_DESIGN.md version bump and re-review.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

# --- world ---------------------------------------------------------------
X_MIN = 0.0
X_MAX = 10.0
N_CAND = 401                     # candidate grid points (spacing 0.025)
SIGMA = 0.5                      # known observation noise

# eps0 for the shared initial design: fixed seed, shared by EVERY seed/arm,
# so that all seeds fork from bit-identical initial observations.
NOISE_INIT_SEED = 20260921
MASTER_SALT = 2026

# Initial design: 10 grid indices -> x = 0.5, 0.675, ..., 2.0
X0_IDX = (20, 27, 33, 40, 47, 53, 60, 67, 73, 80)

# --- budget --------------------------------------------------------------
R = 25                           # rounds
M = 5                            # new measurements per round
N0 = 10                          # initial observations per arm
SEEDS = tuple(range(1, 21))      # pilot seeds
PILOT_N_SEEDS = len(SEEDS)       # frozen formal pilot size (20)
KILL_B1_MIN = 18                 # Neutral converges to truth: >= 18/20
KILL_B3_MIN = 18                 # round-0 all compatible: >= 18/20

# --- neutral fixed sweep -------------------------------------------------
# Ascending grid indices idx_j = NEUTRAL_J0 + floor(NEUTRAL_SPAN*(j-1)/124),
# j = 1..R*M: x from 2.1 up to 10.0, 5 per round, full-domain coverage.
NEUTRAL_J0 = 84
NEUTRAL_SPAN = 316

# --- algorithmic support --------------------------------------------------
GAMMA = 0.85                     # recency weight on stream log-likelihood
THETA_W = 0.02                   # elimination threshold (survivor-normalized w)

PERSIST = 2                      # consecutive violated rounds confirm exclusion

# --- local perturbation (secondary; pre-registered magnitudes) ------------
DELTA_PERTS = (0.01, 0.025, 0.05)
# Frozen secondary-reporting magnitude (formal pilot; do not tune post-hoc).
DELTA_PERT_PRIMARY = 0.05
DELTA_PERT = DELTA_PERT_PRIMARY  # legacy alias

# --- censoring ------------------------------------------------------------
CENSORED = R + 1                 # sentinel: never excluded within horizon

# --- families -------------------------------------------------------------
TRUTH_FAMILY = "hump"
TRUTH_PARAMS = {"A": 8.0, "mu": 4.5, "s": 2.5}
FALSE_FAMILIES = ("affine", "pow", "expsat", "quad")
FAMILY_ORDER = ("hump", "affine", "pow", "expsat", "quad")

# --- evidence criterion (frozen, independent of support) ------------------
# Sequential Bonferroni: alpha_per_round = 0.05 / (n_families * R) [v1.1.2].
ALPHA_EV = 0.05 / (len(FAMILY_ORDER) * R)

# SeedSequence role tags (integers only; see EXPERIMENT_DESIGN.md §9)
ARM_CODE = {"native": 0, "neutral": 1}
RNG_NOISE = 1
RNG_FIT = 2
RNG_ALLOC = 3
RNG_PERTURB = 4
FAMILY_CODE = {name: i for i, name in enumerate(FAMILY_ORDER)}


@dataclass(frozen=True)
class PilotConfig:
    """Frozen snapshot written into every seed record."""

    x_min: float = X_MIN
    x_max: float = X_MAX
    n_cand: int = N_CAND
    sigma: float = SIGMA
    noise_init_seed: int = NOISE_INIT_SEED
    master_salt: int = MASTER_SALT
    x0_idx: tuple[int, ...] = X0_IDX
    rounds: int = R
    m_per_round: int = M
    n0: int = N0
    seeds: tuple[int, ...] = SEEDS
    neutral_j0: int = NEUTRAL_J0
    neutral_span: int = NEUTRAL_SPAN
    gamma: float = GAMMA
    theta_w: float = THETA_W
    alpha_ev: float = ALPHA_EV
    alpha_ev_legacy: float = 0.05 / 5.0
    persist: int = PERSIST
    delta_pert: float = DELTA_PERT
    delta_pert_primary: float = DELTA_PERT_PRIMARY
    delta_perturbations: tuple[float, ...] = DELTA_PERTS
    censored: int = CENSORED
    truth_family: str = TRUTH_FAMILY
    truth_params: dict[str, float] = field(default_factory=lambda: dict(TRUTH_PARAMS))
    false_families: tuple[str, ...] = FALSE_FAMILIES
    family_order: tuple[str, ...] = FAMILY_ORDER
    results_dir: str = "outputs/pilot_fi_anchor"
    version: str = "pilot-v1.1.2"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
