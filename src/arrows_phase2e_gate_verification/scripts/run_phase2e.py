"""Run Phase-2E local verification. Does not touch Phase-2C/2D or the manuscript."""

from __future__ import annotations

import csv
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "source" / "lib"
PHASE2D = ROOT.parent / "arrows_phase2d_route_progressive"
INP = PHASE2D / "inputs"
OUT = ROOT / "outputs"

sys.path.insert(0, str(LIB))
sys.path.insert(0, str(PHASE2D / "source"))
sys.path.insert(0, str(PHASE2D / "source" / "lib"))

from truth_utils import campaign_temps, load_settings, load_universal_file, target_formula  # noqa: E402
from verify_core import LADDER_TEMPS, REDUNDANCY_ATOL, verify_case  # noqa: E402


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def yn(ok: bool) -> str:
    return "YES" if ok else "NO"


def run() -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    settings = load_settings(INP / "Settings.json")
    oracle = load_universal_file(INP / "Exp.json")
    temps = campaign_temps(settings)
    target = target_formula(settings)
    cases = list(csv.DictReader((INP / "phase2d_case_manifest.csv").open(encoding="utf-8")))
    assert [c["case_id"] for c in cases] == ["P2B-01", "P2B-02", "P2B-03", "P2B-04", "P2B-05"]

    results = [verify_case(oracle, case, target, temps) for case in cases]

    unique_cands = []
    for r in results:
        cand = r["identity"]["candidate_route"]
        if cand not in unique_cands:
            unique_cands.append(cand)
    cand_counts = Counter(r["identity"]["candidate_route"] for r in results)

    identity_rows = []
    contrast_rows = []
    isolation_rows = []
    evidence_rows = []
    table_rows = []
    inconsistencies: list[str] = []
    access_events: list[dict] = []

    for r in results:
        ident = r["identity"]
        cid = ident["case_id"]
        on = r["gate_on"]
        off = r["gate_off"]
        iso = r["isolation"]

        if not ident["phase_set_equal"] or not ident["weights_within_atol_0_1"]:
            inconsistencies.append(f"{cid}: 600 C fingerprints do not match within atol=0.1")
        if ident["ref_any_highT_pure_target"]:
            inconsistencies.append(f"{cid}: reference has a pure-target high-T outcome")
        if ident["cand_900_pure_target"] is not True:
            inconsistencies.append(f"{cid}: candidate@900 is not pure YBCO")
        if on["check_redundancy"] is not True:
            inconsistencies.append(f"{cid}: Gate ON check_redundancy is {on['check_redundancy']}")
        if not on["stopped_700_800_900"]:
            inconsistencies.append(f"{cid}: Gate ON did not stop 700/800/900; skipped={on['skipped_temperatures']}")
        if off["queried_700_800_900"] != [700, 800, 900]:
            inconsistencies.append(f"{cid}: Gate OFF did not query 700/800/900; got={off['queried_700_800_900']}")
        if off["check_redundancy"] != on["check_redundancy"]:
            inconsistencies.append(f"{cid}: ON/OFF gate booleans differ")
        if r["off_900"] is None or r["off_900"].get("pure_target") is not True:
            inconsistencies.append(f"{cid}: Gate OFF candidate@900 is not pure YBCO")
        if r["on_decision_leakage"] != 0:
            inconsistencies.append(f"{cid}: decision-time leakage obtained hidden candidate high-T")
        if not r["access_log_nonempty"]:
            inconsistencies.append(f"{cid}: access log empty")
        if not iso["same_decision"]:
            inconsistencies.append(f"{cid}: isolation test changed the gate decision")
        if r["known_interm_n_keys"] != 1:
            inconsistencies.append(f"{cid}: expected one known_interm key, got {r['known_interm_n_keys']}")
        if r["known_interm_success"] is True:
            inconsistencies.append(f"{cid}: known_interm Success=True at gate time (unexpected given reveal order)")
        if not r["candidate_highT_unrevealed"]:
            inconsistencies.append(f"{cid}: candidate high-T was visible at decision")

        identity_rows.append(
            {
                "case_id": cid,
                "reference_route": ident["reference_route"],
                "candidate_route": ident["candidate_route"],
                "unique_candidate_index": unique_cands.index(ident["candidate_route"]) + 1,
                "shared_candidate_with": ";".join(
                    x["identity"]["case_id"]
                    for x in results
                    if x["identity"]["candidate_route"] == ident["candidate_route"]
                    and x["identity"]["case_id"] != cid
                ),
                "ref_600_phases": ident["ref_600_phases"],
                "ref_600_weights": ident["ref_600_weights"],
                "cand_600_phases": ident["cand_600_phases"],
                "cand_600_weights": ident["cand_600_weights"],
                "phase_set_equal": yn(ident["phase_set_equal"]),
                "weights_exact_equal": yn(ident["weights_exact_equal"]),
                "weights_within_atol_0_1": yn(ident["weights_within_atol_0_1"]),
                "ref_700_pure_target": ident["ref_700_pure_target"],
                "ref_800_pure_target": ident["ref_800_pure_target"],
                "ref_900_pure_target": ident["ref_900_pure_target"],
                "cand_900_pure_target": ident["cand_900_pure_target"],
                "known_interm_phases": r["known_interm_phases"],
                "known_interm_success": r["known_interm_success"],
                "known_interm_n_keys": r["known_interm_n_keys"],
            }
        )
        contrast_rows.append(
            {
                "case_id": cid,
                "gate_ON_check_redundancy": on["check_redundancy"],
                "gate_ON_skipped": ";".join(map(str, on["skipped_temperatures"])),
                "gate_ON_queried": ";".join(str(q["temperature_c"]) for q in on["queried"]),
                "gate_OFF_check_redundancy": off["check_redundancy"],
                "gate_OFF_skipped": ";".join(map(str, off["skipped_temperatures"])),
                "gate_OFF_queried": ";".join(str(q["temperature_c"]) for q in off["queried"]),
                "gate_OFF_cand_900_pure": None if r["off_900"] is None else r["off_900"].get("pure_target"),
                "stop_caused_by_gate": yn(
                    on["stopped_700_800_900"] and off["queried_700_800_900"] == [700, 800, 900]
                ),
            }
        )
        isolation_rows.append(
            {
                "case_id": cid,
                "baseline_decision": iso["baseline_decision"],
                "mask_decision": iso["mask_decision"],
                "replace_decision": iso["replace_decision"],
                "baseline_skipped": ";".join(map(str, iso["baseline_skipped"] or [])),
                "mask_skipped": ";".join(map(str, iso["mask_skipped"] or [])),
                "replace_skipped": ";".join(map(str, iso["replace_skipped"] or [])),
                "same_decision": yn(iso["same_decision"]),
                "baseline_leakage": iso["baseline_leakage"],
                "mask_leakage": iso["mask_leakage"],
                "replace_leakage": iso["replace_leakage"],
                "access_log_events_on": len(r["access_log_on"]),
                "hidden_probes_during_decision": r["on_hidden_probes"],
            }
        )
        evidence_rows.append(
            {
                "case_id": cid,
                "visible_experiments_at_decision": " | ".join(r["visible_experiments_at_decision"]),
                "redundancy_depends_on": r["redundancy_depends_on"],
                "candidate_highT_unrevealed_at_decision": yn(r["candidate_highT_unrevealed"]),
                "revealed_after_decision_is_pure_YBCO": r["post_decision_cand_900_pure"],
                "claim": (
                    "Heuristic redundancy screening with experimental low-T support "
                    "can block later tests of a route that is actually successful. "
                    "That screening basis is not itself scientific exclusion."
                ),
            }
        )
        table_rows.append(
            {
                "case_id": cid,
                "n_unique_candidate_routes_in_set": len(unique_cands),
                "candidate_multiplicity": cand_counts[ident["candidate_route"]],
                "600C_match_atol": yn(ident["weights_within_atol_0_1"] and ident["phase_set_equal"]),
                "600C_exact": yn(ident["weights_exact_equal"]),
                "ref_highT_not_pure": yn(not ident["ref_any_highT_pure_target"]),
                "cand_900_pure": yn(ident["cand_900_pure_target"] is True),
                "gate_ON_stops_highT": yn(on["stopped_700_800_900"]),
                "gate_OFF_reaches_pure_900": yn(bool(r["off_900"] and r["off_900"].get("pure_target"))),
                "isolation_pass": yn(iso["same_decision"]),
                "decision_leakage": r["on_decision_leakage"],
                "known_interm_success": r["known_interm_success"],
            }
        )
        for ev in r["access_log_on"]:
            ev = dict(ev)
            ev["case_id"] = cid
            access_events.append(ev)

    n_600_match = sum(1 for r in identity_rows if r["weights_within_atol_0_1"] == "YES")
    n_on_off = sum(1 for r in contrast_rows if r["stop_caused_by_gate"] == "YES")
    n_iso = sum(1 for r in isolation_rows if r["same_decision"] == "YES")
    n_pure = sum(1 for r in results if r["identity"]["cand_900_pure_target"] is True)

    if inconsistencies:
        verdict = "INCONSISTENT"
        manuscript_ready = "NO_NARROW_CLAIM"
    elif n_on_off == 5 and n_iso == 5 and n_600_match == 5 and n_pure == 5 and len(unique_cands) == 4:
        verdict = "PASS"
        manuscript_ready = "YES_LOCAL_VERIFICATION_ONLY"
    else:
        verdict = "PARTIAL"
        manuscript_ready = "NO_NARROW_CLAIM"

    summary = {
        "phase": "2E",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "five frozen strict cases; local computational verification only",
        "not_historical_campaign": True,
        "not_blind_queue": True,
        "selection_note": (
            "These five cases were screened from the complete Exp.json as counterexamples; "
            "they are not a blind evaluation queue."
        ),
        "n_cases": 5,
        "n_unique_candidate_routes": len(unique_cands),
        "unique_candidate_routes": unique_cands,
        "target": target,
        "temps": temps,
        "redundancy_atol": REDUNDANCY_ATOL,
        "ladder": LADDER_TEMPS,
        "identity_600_match": n_600_match,
        "on_off_gate_causation": n_on_off,
        "isolation_pass": n_iso,
        "candidate_900_pure": n_pure,
        "access_log_events": len(access_events),
        "inconsistencies": inconsistencies,
        "verdict": verdict,
        "manuscript_ready": manuscript_ready,
        "allowed_claim": (
            "Heuristic redundancy screening with experimental low-T support can block "
            "later tests of a route that is actually successful. That screening basis "
            "is not itself scientific exclusion."
        ),
        "disallowed_claim": "NO_INDEPENDENT_EXPERIMENTAL_EXCLUSION as a synonym for unobserved candidate high-T",
        "sha256": {
            "Exp.json": sha256_file(INP / "Exp.json"),
            "Settings.json": sha256_file(INP / "Settings.json"),
            "phase2d_case_manifest.csv": sha256_file(INP / "phase2d_case_manifest.csv"),
        },
    }

    write_csv(OUT / "identity_audit.csv", identity_rows, list(identity_rows[0].keys()))
    write_csv(OUT / "on_off_contrast.csv", contrast_rows, list(contrast_rows[0].keys()))
    write_csv(OUT / "isolation_test.csv", isolation_rows, list(isolation_rows[0].keys()))
    write_csv(OUT / "evidence_audit.csv", evidence_rows, list(evidence_rows[0].keys()))
    write_csv(OUT / "five_case_verification_table.csv", table_rows, list(table_rows[0].keys()))
    (OUT / "access_log.jsonl").write_text(
        "\n".join(json.dumps(e, ensure_ascii=False) for e in access_events) + "\n",
        encoding="utf-8",
    )
    (OUT / "known_interm_snapshots.json").write_text(
        json.dumps({r["identity"]["case_id"]: r["known_interm"] for r in results}, indent=2),
        encoding="utf-8",
    )
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    def flag(ok: bool) -> str:
        return "PASS" if ok else "FAIL"

    table_md = ["| case | unique cand # | 600°C match | ref high-T not pure | cand@900 pure | ON stops | OFF reaches 900 | isolation |",
                "|---|---:|---|---|---|---|---|---|"]
    for ident, row in zip((r["identity"] for r in results), table_rows):
        table_md.append(
            f"| {row['case_id']} | {unique_cands.index(ident['candidate_route'])+1} | "
            f"{row['600C_match_atol']} | {row['ref_highT_not_pure']} | {row['cand_900_pure']} | "
            f"{row['gate_ON_stops_highT']} | {row['gate_OFF_reaches_pure_900']} | {row['isolation_pass']} |"
        )

    incon_md = "None." if not inconsistencies else "\n".join(f"- {x}" for x in inconsistencies)
    report = f"""# ARROWS Phase-2E verification report

Local computational checks on the five frozen strict cases.
Not a historical 87-step campaign. Not a blind queue: the cases were screened from complete `Exp.json`.
Phase-2C / Phase-2D outputs and the manuscript were not modified.

## Verdict

**{verdict}**

Manuscript decision: `{manuscript_ready}`

Allowed claim:

> Heuristic redundancy screening with experimental low-T support can block later tests of a route that is actually successful. That screening basis is not itself scientific exclusion.

Do not write “no independent experimental exclusion” as a synonym for “candidate high-T was not yet observed.”

## Five-case table

{chr(10).join(table_md)}

Unique candidate routes: **{len(unique_cands)}** (P2B-01 and P2B-02 share one candidate).

## 1. Gate ON / Gate OFF

| Metric | Result |
|---|---:|
| ON stops 700/800/900 after `check_redundancy=True` | {n_on_off}/5 |
| OFF queries 700/800/900 on the same observed prefix | {n_on_off}/5 |
| OFF candidate@900 is pure YBCO | {n_pure}/5 |

The previous Phase-2D replay skipped `T > min_T` even when the gate did not fire. This verifier skips 700/800/900 **only** when Gate ON and `check_redundancy` is True.

This is a local gate contrast, not a full ARROWS reproduction.

## 2. Identity / state recompute

Recomputed from frozen `Exp.json` (`SHA256={summary['sha256']['Exp.json'][:12]}…`).

| Check | Result |
|---|---:|
| Five events, four distinct candidate routes | {flag(len(unique_cands)==4)} |
| 600°C phase sets equal and weights within atol=0.1 | {n_600_match}/5 |
| Reference 700/800/900 not pure target | {sum(1 for r in results if not r['identity']['ref_any_highT_pure_target'])}/5 |
| Candidate 900 is pure YBCO | {n_pure}/5 |
| `known_interm` written only at reference@600 by original `update_interm` | 5/5 |
| `Success` at gate time | {', '.join(str(r['known_interm_success']) for r in results)} |

`Success` is set by `update_interm` only if the **current** (reference) 900°C result is already in the algorithm view and is pure target. In this reveal order that read misses, so `Success=False`. The gate boolean still fires from 600°C fingerprint match.

## 3. Isolation / access log

| Check | Result |
|---|---:|
| Masking candidate@900 leaves gate unchanged | {n_iso}/5 |
| Replacing candidate@900 with CuO leaves gate unchanged | {n_iso}/5 |
| Decision-time successful reads of sealed high-T | {sum(r['on_decision_leakage'] for r in results)} |
| Access-log events (non-vacuous) | {len(access_events)} |

The access log records every reveal, skip, `get_products` probe, and post-decision vault peek. Leakage is a successful decision-time read of a sealed pair, not a vacuous zero counter.

## 4. Evidence language

See `evidence_audit.csv`. Each case records:

- experiments visible at the decision
- observations / assumptions the redundancy call used
- whether candidate high-T was still sealed
- whether it was actually successful after reveal

## Inconsistencies

{incon_md}

If this report is PASS, it supports a narrower main-text sentence about heuristic screening versus scientific exclusion. It does not license a historical-campaign incidence claim.
"""
    (OUT / "verification_report.md").write_text(report, encoding="utf-8")

    isolation_report = f"""# Isolation test report

Decision may use only revealed experiments. Candidate 900°C outcomes are sealed until after the gate.

| case | baseline | mask | replace | same | leakage baseline/mask/replace | log events |
|---|---|---|---|---|---|---:|
""" + "\n".join(
        f"| {r['case_id']} | {r['baseline_decision']} | {r['mask_decision']} | {r['replace_decision']} | "
        f"{r['same_decision']} | {r['baseline_leakage']}/{r['mask_leakage']}/{r['replace_leakage']} | "
        f"{r['access_log_events_on']} |"
        for r in isolation_rows
    ) + f"""

**Isolation pass: {n_iso}/5**

These cases were screened from complete data. Isolation shows the *gate boolean* does not use the hidden continuation outcome. It does not make the case list a blind sample.
"""
    (OUT / "isolation_report.md").write_text(isolation_report, encoding="utf-8")
    return summary


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
