"""Unit tests for corrected Anchor offline statistics."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from anchor_corrected_stats import (  # noqa: E402
    FORMAL_DIR,
    TRUTH_DIR,
    build_paired_timing,
    extract_false_fi_events,
    finite_delta,
    is_fi,
    load_json,
    measured_overlap,
    paired_direction,
    prediction_row,
    truth_loss_row,
)
from pilot_truth_loss.config import HELD_OUT_IDX  # noqa: E402


def test_right_censor_not_in_finite_delta():
    assert finite_delta(6, 9) == -3
    assert finite_delta(6, None) is None
    assert finite_delta(None, 9) is None
    assert finite_delta(None, None) is None
    # Must NOT encode censor as 26
    assert finite_delta(6, None) != 6 - 26


def test_paired_direction_definition():
    assert paired_direction(5, 8) == "native_earlier"
    assert paired_direction(8, 5) == "neutral_earlier"
    assert paired_direction(6, 6) == "same_round"
    assert paired_direction(6, None) == "native_earlier"  # Neutral censored → Native earlier
    assert paired_direction(None, 6) == "neutral_earlier"
    assert paired_direction(None, None) == "both_censored"


def test_fi_definition():
    assert is_fi(6, 7) is True
    assert is_fi(6, None) is True
    assert is_fi(7, 7) is False
    assert is_fi(8, 7) is False
    assert is_fi(None, 7) is False


def test_formal_event_counts_78_80_26_77():
    n_fi = u_fi = n_nov = u_nov = 0
    bad_w = 0
    for seed in range(1, 21):
        rec = load_json(FORMAL_DIR / f"seed_{seed:02d}.json")
        for e in extract_false_fi_events("formal_1_20", seed, rec):
            if not e.fi:
                continue
            if e.arm == "native":
                n_fi += 1
                if e.violated_at_elim is False:
                    n_nov += 1
            else:
                u_fi += 1
                if e.violated_at_elim is False:
                    u_nov += 1
            if e.weight_prune_confirmed is False:
                bad_w += 1
    assert (n_fi, u_fi) == (78, 80)
    assert (n_nov, u_nov) == (26, 77)
    assert bad_w == 0


def test_paired_direction_71_7_2():
    n_ear = u_ear = same = both = 0
    for seed in range(1, 21):
        rec = load_json(FORMAL_DIR / f"seed_{seed:02d}.json")
        for row in build_paired_timing("formal_1_20", seed, rec):
            d = row["direction"]
            if d == "native_earlier":
                n_ear += 1
            elif d == "neutral_earlier":
                u_ear += 1
            elif d == "same_round":
                same += 1
            elif d == "both_censored":
                both += 1
    assert (n_ear, u_ear, same) == (71, 7, 2)
    assert n_ear + u_ear + same + both == 80


def test_queues_separated_truth_loss():
    formal = []
    for seed in range(1, 21):
        formal.append(truth_loss_row("formal_1_20", seed, load_json(FORMAL_DIR / f"seed_{seed:02d}.json")))
    ext = []
    for seed in range(21, 41):
        ext.append(
            truth_loss_row(
                "truth_loss_21_40",
                seed,
                load_json(TRUTH_DIR / f"seed_{seed:03d}.json"),
            )
        )
    f_seeds = sorted(r["seed"] for r in formal if r["native_truth_fi"])
    e_seeds = sorted(r["seed"] for r in ext if r["native_truth_fi"])
    assert f_seeds == [17, 20]
    assert e_seeds == [29, 31, 36, 37]
    assert sum(1 for r in formal if r["neutral_truth_fi"]) == 0
    assert sum(1 for r in ext if r["neutral_truth_fi"]) == 0
    # Must not mix into 6/40 as a single confirmatory claim in this module
    assert len(f_seeds) + len(e_seeds) == 6  # arithmetic only; queues stay separate


def test_prediction_grid_overlap_and_naming():
    assert len(HELD_OUT_IDX) == 19
    rec = load_json(FORMAL_DIR / "seed_01.json")
    ov_n = measured_overlap(rec, "native")
    ov_u = measured_overlap(rec, "neutral")
    assert len(ov_u) == 0
    assert len(ov_n) >= 0  # Native may measure grid points
    row = prediction_row("formal_1_20", 1, rec)
    assert row["metric_name"] == "designated_truth_grid_prediction_error"
    assert row["not_strict_holdout"] is True
    assert row["not_oos"] is True
    assert row["status"] == "NOT_IDENTIFIABLE"  # no arm_theta in formal logs

    rec29 = load_json(TRUTH_DIR / "seed_029.json")
    row29 = prediction_row("truth_loss_21_40", 29, rec29)
    assert row29["status"] == "SCORED"
    assert float(row29["rmse_ratio_native_over_neutral"]) > 1.0
    assert int(row29["native_measured_grid_n"]) > 0


def test_rounds_index_matches_t_field():
    """Guard against off-by-one: rounds[t]['t'] == t in formal logs."""
    rec = load_json(FORMAL_DIR / "seed_01.json")
    for arm_name in ("native", "neutral"):
        for row in rec["arms"][arm_name]["rounds"]:
            t = int(row["t"])
            assert rec["arms"][arm_name]["rounds"][t]["t"] == t


def run_all() -> bool:
    tests = [
        test_right_censor_not_in_finite_delta,
        test_paired_direction_definition,
        test_fi_definition,
        test_formal_event_counts_78_80_26_77,
        test_paired_direction_71_7_2,
        test_queues_separated_truth_loss,
        test_prediction_grid_overlap_and_naming,
        test_rounds_index_matches_t_field,
    ]
    failed = 0
    for fn in tests:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"FAIL {fn.__name__}: {type(exc).__name__}: {exc}")
    marker = Path(__file__).resolve().parent / "_anchor_corrected_tests_ok"
    marker.write_text("PASS" if failed == 0 else "FAIL", encoding="utf-8")
    print("ALL PASS" if failed == 0 else f"{failed} FAILED")
    return failed == 0


if __name__ == "__main__":
    raise SystemExit(0 if run_all() else 1)
