from pilot_fi_anchor.rng import alloc_rng, fork_rng


def test_fork_rng_produces_identical_draws():
    rng = alloc_rng(7, "native", 3)
    a = fork_rng(rng)
    b = fork_rng(rng)
    draws_a = [a.integers(0, 1000) for _ in range(5)]
    draws_b = [b.integers(0, 1000) for _ in range(5)]
    assert draws_a == draws_b
