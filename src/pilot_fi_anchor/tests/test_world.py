import numpy as np

from pilot_fi_anchor.config import X0_IDX
from pilot_fi_anchor.world import World


def test_initial_obs_identical_across_seeds():
    y1 = [World(1).y(i) for i in X0_IDX]
    y2 = [World(2).y(i) for i in X0_IDX]
    assert y1 == y2


def test_same_seed_same_field():
    w1, w2 = World(3), World(3)
    assert np.array_equal(w1.noise, w2.noise)


def test_different_seeds_differ_outside_initial():
    w1, w2 = World(4), World(5)
    non_init = [i for i in range(len(w1.grid)) if i not in X0_IDX]
    assert not np.array_equal(w1.noise[non_init], w2.noise[non_init])


def test_initial_indices_on_grid():
    w = World(6)
    assert all(0 <= i < len(w.grid) for i in X0_IDX)
