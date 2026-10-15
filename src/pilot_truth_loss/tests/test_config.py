from pilot_fi_anchor.config import TRUTH_FAMILY as ANCHOR_TRUTH
from pilot_fi_anchor.evidence_calibration import _neutral_sweep_indices
from pilot_fi_anchor.config import X0_IDX

from pilot_truth_loss.config import (
    COMPETITOR_FAMILY,
    CONFIRMATORY_SEEDS,
    G2_F2V2_FRAC,
    G3_F3_FRAC,
    HELD_OUT_IDX,
    V1_OBSERVED_SEEDS,
    V2_RESULTS_DIR,
    TruthLossConfig,
    held_out_indices,
)


def test_frozen_pair():
    assert ANCHOR_TRUTH == "hump"
    assert COMPETITOR_FAMILY == "pow"


def test_v2_confirmatory_population():
    assert CONFIRMATORY_SEEDS == tuple(range(21, 41))
    assert not set(V1_OBSERVED_SEEDS) & set(CONFIRMATORY_SEEDS)


def test_held_out_disjoint_from_measured_sets():
    blocked = set(X0_IDX) | set(_neutral_sweep_indices())
    assert not blocked.intersection(HELD_OUT_IDX)
    assert len(HELD_OUT_IDX) >= 10


def test_held_out_rule_stable():
    assert held_out_indices() == HELD_OUT_IDX


def test_config_snapshot():
    cfg = TruthLossConfig()
    assert cfg.competitor_family == "pow"
    assert cfg.anchor_version.startswith("pilot-v1.1.2")
    assert cfg.confirmatory_seeds[0] == 21
    assert cfg.g2_f2v2_frac == G2_F2V2_FRAC
    assert cfg.g3_f3_frac == G3_F3_FRAC
    assert cfg.results_dir == V2_RESULTS_DIR
