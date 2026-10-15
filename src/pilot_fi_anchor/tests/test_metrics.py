from pilot_fi_anchor.config import PilotConfig
from pilot_fi_anchor.loop import run_seed
from pilot_fi_anchor.metrics import (
    compute_endpoints,
    dFI_ge1,
    focal_event,
    native_events,
    seed_summary,
)


def test_endpoints_use_seed_level_e1():
    rec = run_seed(3, do_perturb=False, rounds=8)
    endpoints, focals, events, summaries = compute_endpoints([rec], PilotConfig())
    assert "E1_seed_k" in endpoints
    assert "E1_focal_k" not in endpoints
    assert endpoints["E1_seed_n"] == 1
    assert endpoints["gain_delta_primary"] == 0.05
    assert "gain_by_delta" in endpoints


def test_dfi_on_native_trajectory():
    events = native_events(run_seed(4, do_perturb=False, rounds=10))
    for e in events:
        if e["dFI"] is not None:
            assert e["dFI"] == e["t_excl_N"] - e["t_elim"]


def test_dfi_ge1_censored_with_horizon():
    censored = {
        "unsupported": True,
        "dFI": None,
        "censored_N": True,
        "t_elim": 5,
    }
    assert dFI_ge1(censored, horizon=25)
    assert not dFI_ge1(censored, horizon=6)  # R > t_elim+1 required
    finite = {"unsupported": True, "dFI": 4, "censored_N": False, "t_elim": 5}
    assert dFI_ge1(finite, horizon=25)


def test_dfi_ge1_frac_denominator_all_unsupported():
    endpoints, _, events, _ = compute_endpoints([], PilotConfig())
    assert endpoints["E2_frac_dFI_ge1"] is None

    mock_unsupported = [
        {"unsupported": True, "dFI": None, "censored_N": True, "t_elim": 5},
        {"unsupported": True, "dFI": 0, "censored_N": False, "t_elim": 8},
    ]
    k = sum(1 for e in mock_unsupported if dFI_ge1(e, 25))
    n = len(mock_unsupported)
    assert k == 1
    assert n == 2


def test_seed_summary_horizon_matches_compute_endpoints():
    from dataclasses import replace

    rec = run_seed(3, do_perturb=False, rounds=25)
    cfg = replace(PilotConfig(), rounds=25)
    _, _, _, summaries = compute_endpoints([rec], cfg)
    direct = seed_summary(rec, cfg)
    assert summaries[0]["has_temporal_fi"] == direct["has_temporal_fi"]
    assert summaries[0]["has_unsupported_elim"] == direct["has_unsupported_elim"]


def test_focal_is_descriptive_only():
    rec = run_seed(5, do_perturb=False, rounds=10)
    focal = focal_event(rec, PilotConfig())
    summary = seed_summary(rec, PilotConfig())
    if focal is not None:
        assert "victim" in focal
        assert "dFI" in focal
    assert "has_unsupported_elim" in summary
