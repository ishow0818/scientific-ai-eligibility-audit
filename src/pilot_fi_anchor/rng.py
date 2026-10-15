"""Deterministic RNG derivation for SeedSequence (integers only).

NumPy SeedSequence does not accept string entropy; role tags are frozen
integers documented in EXPERIMENT_DESIGN.md §9.
"""

from __future__ import annotations

import numpy as np

from .config import ARM_CODE, FAMILY_CODE, MASTER_SALT, RNG_ALLOC, RNG_FIT, RNG_NOISE, RNG_PERTURB


def seed_sequence(*parts: int) -> np.random.SeedSequence:
    return np.random.SeedSequence([MASTER_SALT, *parts])


def world_rng(seed: int) -> np.random.Generator:
    return np.random.default_rng(seed_sequence(seed, RNG_NOISE))


def fit_rng(seed: int) -> np.random.Generator:
    """Shared across arms at round 0 so identical PUBLIC streams yield identical fits."""
    return np.random.default_rng(seed_sequence(seed, RNG_FIT))


def alloc_rng(seed: int, arm: str, t: int) -> np.random.Generator:
    return np.random.default_rng(seed_sequence(seed, ARM_CODE[arm], RNG_ALLOC, t))


def fork_rng(rng: np.random.Generator) -> np.random.Generator:
    """Independent fork sharing the current bit-generator state (CRN branches)."""
    bit_gen = type(rng.bit_generator)()
    bit_gen.state = rng.bit_generator.state
    return np.random.Generator(bit_gen)


def perturb_rng(seed: int, arm: str, t: int, family: str) -> np.random.Generator:
    """Legacy role tag; perturbation branches now reuse alloc_rng via fork_rng."""
    return np.random.default_rng(
        seed_sequence(seed, ARM_CODE[arm], RNG_PERTURB, t, FAMILY_CODE[family])
    )
