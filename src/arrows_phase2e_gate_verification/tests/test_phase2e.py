"""Phase-2E local verification tests."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
INP = ROOT.parent / "arrows_phase2d_route_progressive" / "inputs"

sys.path.insert(0, str(ROOT / "scripts"))


@pytest.fixture(scope="module", autouse=True)
def ensure_outputs():
    if not (OUT / "summary.json").exists():
        from run_phase2e import run

        run()


def test_frozen_five_cases_only():
    manifest = list(csv.DictReader((INP / "phase2d_case_manifest.csv").open(encoding="utf-8")))
    assert [r["case_id"] for r in manifest] == ["P2B-01", "P2B-02", "P2B-03", "P2B-04", "P2B-05"]
    table = list(csv.DictReader((OUT / "five_case_verification_table.csv").open(encoding="utf-8")))
    assert [r["case_id"] for r in table] == ["P2B-01", "P2B-02", "P2B-03", "P2B-04", "P2B-05"]


def test_four_unique_candidate_routes():
    s = json.loads((OUT / "summary.json").read_text(encoding="utf-8"))
    assert s["n_unique_candidate_routes"] == 4


def test_on_skips_only_after_gate():
    rows = list(csv.DictReader((OUT / "on_off_contrast.csv").open(encoding="utf-8")))
    for r in rows:
        assert r["gate_ON_check_redundancy"] == "True"
        assert r["gate_ON_skipped"] == "700;800;900"
        assert r["gate_ON_queried"] == "600"


def test_off_queries_high_t():
    rows = list(csv.DictReader((OUT / "on_off_contrast.csv").open(encoding="utf-8")))
    for r in rows:
        assert r["gate_OFF_skipped"] == ""
        assert r["gate_OFF_queried"] == "600;700;800;900"
        assert r["gate_OFF_cand_900_pure"] == "True"
        assert r["stop_caused_by_gate"] == "YES"


def test_isolation_invariant():
    rows = list(csv.DictReader((OUT / "isolation_test.csv").open(encoding="utf-8")))
    for r in rows:
        assert r["baseline_decision"] == r["mask_decision"] == r["replace_decision"] == "True"
        assert r["same_decision"] == "YES"
        assert r["baseline_leakage"] == r["mask_leakage"] == r["replace_leakage"] == "0"


def test_access_log_nonvacuous():
    lines = (OUT / "access_log.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) > 20
    events = [json.loads(x) for x in lines]
    assert any(e["caller"].startswith("reference_ladder") for e in events)
    assert any(e["phase"] == "post_decision" for e in events)
    assert any(e["phase"] == "skipped_by_gate" for e in events)
    decision_hits = [
        e
        for e in events
        if e["hidden_candidate_high_t"] and e["phase"] != "post_decision" and e["obtained_result"]
    ]
    assert decision_hits == []


def test_evidence_language_not_overclaim():
    rows = list(csv.DictReader((OUT / "evidence_audit.csv").open(encoding="utf-8")))
    blob = " ".join(r["claim"] for r in rows).lower()
    assert "no_independent_experimental_exclusion" not in blob
    assert all(r["candidate_highT_unrevealed_at_decision"] == "YES" for r in rows)
    assert all("heuristic" in r["claim"].lower() for r in rows)
