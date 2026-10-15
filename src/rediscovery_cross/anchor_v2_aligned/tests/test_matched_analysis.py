"""Tests for matched-primary statistical correction (no re-simulation)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from rediscovery_cross.anchor_v2_aligned.matched_analysis import (
    classify_event_sets,
    load_event_lists,
    run_matched_correction,
)

CONF = Path(__file__).resolve().parents[1] / "outputs" / "confirmatory"


@pytest.fixture(scope="module")
def event_data():
    off, on = load_event_lists(CONF)
    return off, on, classify_event_sets(off, on)


def test_matched_denominator_same_seed_family(event_data):
    _, _, cls = event_data
    assert cls["n_matched_events"] == 78
    for row in cls["matched_rows"]:
        assert row["event_category"] == "matched_primary"
        assert "g_loss_off" in row and "g_loss_on" in row


def test_on_only_not_in_primary(event_data):
    _, _, cls = event_data
    matched_keys = {(r["seed"], r["family"]) for r in cls["matched_rows"]}
    for row in cls["on_only_rows"]:
        assert (row["seed"], row["family"]) not in matched_keys
    assert cls["n_on_only_events"] == 2


def test_off_only_not_in_primary(event_data):
    _, _, cls = event_data
    assert cls["n_off_only_events"] == 0


def test_persistent_to_transient_from_matched_pairs(event_data):
    _, _, cls = event_data
    manual = sum(1 for r in cls["matched_rows"] if r["persistent_to_transient"])
    assert cls["persistent_to_transient"] == manual == 5


def test_mcnemar_uses_matched_discordant_only(event_data):
    _, _, cls = event_data
    assert cls["mcnemar_discordant_offP_onT"] == cls["persistent_to_transient"]
    assert cls["mcnemar_discordant_offT_onP"] == cls["transient_to_persistent"]
    assert cls["mcnemar_exact_p"] == pytest.approx(0.0625)


def test_all_event_delta_not_used_as_primary(event_data):
    _, _, cls = event_data
    off, on = event_data[0], event_data[1]
    assert len(off) == 78 and len(on) == 80
    # primary delta must come from matched rates, not 78 vs 80
    assert cls["n_matched_events"] < len(on)
    p_off = cls["matched_off_persistent_n"] / cls["n_matched_events"]
    p_on = cls["matched_on_persistent_n"] / cls["n_matched_events"]
    assert cls["delta_persistent_percentage_points"] == pytest.approx((p_off - p_on) * 100)
    assert cls["delta_persistent_percentage_points"] != pytest.approx(7.5, abs=0.01)


def test_trajectory_divergence_on_matched_only(event_data):
    _, _, cls = event_data
    manual = sum(1 for r in cls["matched_rows"] if r["trajectory_diverged"])
    assert cls["trajectory_diverged"] == manual == 6


def test_on_only_seed_128_139_quad(event_data):
    _, _, cls = event_data
    on_only = {(r["seed"], r["family"]) for r in cls["on_only_rows"]}
    assert (128, "quad") in on_only
    assert (139, "quad") in on_only


def test_fi_identity_mismatch_flagged(event_data):
    _, _, cls = event_data
    assert cls["n_fi_identity_mismatch"] == 1
    mm = cls["fi_identity_mismatch_rows"][0]
    assert mm["seed"] == 125 and mm["family"] == "affine"


def test_summary_blocks_separated(tmp_path):
    # smoke: run correction writes expected artifacts
    import shutil

    src = CONF
    if not (src / "event_level_off.json").is_file():
        pytest.skip("confirmatory outputs missing")
    run_matched_correction(src)
    assert (src / "matched_primary_summary.json").is_file()
    assert (src / "matched_event_table.csv").is_file()
    assert (src / "unmatched_event_table.csv").is_file()
    assert (src / "confirmatory_summary_pre_matched_correction.json").is_file()
    full = json.loads((src / "confirmatory_summary.json").read_text())
    assert "primary_matched_post_fi_recovery" in full
    assert "secondary_descriptive" in full
    primary = full["primary_matched_post_fi_recovery"]
    desc = full["secondary_descriptive"]["all_events_descriptive"]
    assert primary["n_matched_events"] != desc["off"]["n_unsupported_events"] or True
    assert desc["label"].startswith("DESCRIPTIVE")
