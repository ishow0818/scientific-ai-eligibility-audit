"""Read-only checks of the original 40 frozen A/B/C records; no new policies."""
from pathlib import Path
import hashlib
import json
import math
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from evidence_gated_eligibility.eval_grid import (  # noqa: E402
    assert_eval_disjoint_from_measurable, rmse_noiseless,
)


def verify():
    assert_eval_disjoint_from_measurable()
    tags = ("native", "decision_only", "full_evidence_gate")
    values = {tag: [] for tag in tags}
    correct = {tag: 0 for tag in tags}
    hashes = {}
    changed = []
    for seed in range(201, 241):
        path = ROOT / f"evidence_gated_eligibility/outputs/stage2_formal/seed_{seed}.json"
        raw = path.read_bytes()
        record = json.loads(raw)
        hashes[str(path.relative_to(ROOT))] = hashlib.sha256(raw).hexdigest()
        assert record["seed"] == seed
        a, b = (record["arms"][tag] for tag in tags[:2])
        assert a["sites"] == b["sites"], (seed, "sites")
        assert a["rounds"] == b["rounds"], (seed, "rounds")
        assert a["final"]["arm_theta"] == b["final"]["arm_theta"], (seed, "fits")
        if a["final"]["incumbent"] != b["final"]["incumbent"]:
            changed.append(seed)
        for tag in tags:
            final = record["arms"][tag]["final"]
            rmse, status = rmse_noiseless(final["incumbent"], final["incumbent_theta"])
            assert status == "OK" and math.isfinite(rmse), (seed, tag)
            assert math.isclose(rmse, record["scores"][tag]["rmse_eval_noiseless"],
                                rel_tol=1e-12, abs_tol=1e-12), (seed, tag, "RMSE")
            values[tag].append(rmse)
            correct[tag] += int(final["incumbent"] == "hump")
    assert list(correct.values()) == [37, 39, 40], correct
    assert changed == [224, 232], changed
    worse = sum(c > a + 1e-12 for a, c in zip(values[tags[0]], values[tags[2]]))
    assert worse == 5, worse
    for rel in ("paper_audit/verify_frozen_eligibility.py",
                "evidence_gated_eligibility/eval_grid.py", "pilot_fi_anchor/mechanisms.py",
                "pilot_fi_anchor/config.py"):
        hashes[rel] = hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()
    return {
        "status": "PASS_FROZEN_RECORD_CHECK_ONLY",
        "scope": "No simulation, fitting, new policy, or ongoing experiment read",
        "n": 40, "correct_selection": correct, "decision_changes": changed,
        "mean_rmse": {t: statistics.mean(values[t]) for t in tags},
        "median_rmse": {t: statistics.median(values[t]) for t in tags},
        "full_gate_rmse_worse_than_native": worse,
        "sha256_at_verification": hashes,
    }


if __name__ == "__main__":
    print(json.dumps(verify(), indent=2, ensure_ascii=False))
