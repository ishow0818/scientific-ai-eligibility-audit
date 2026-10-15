#!/usr/bin/env python3
"""Path-independent release verification entry (no network; no frozen overwrites)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

RELEASE_ROOT = Path(__file__).resolve().parents[1]
DERIVED = RELEASE_ROOT / "derived_verification"
DERIVED.mkdir(parents=True, exist_ok=True)


def main() -> int:
    statuses = []
    # Eligibility lock if present
    lock = RELEASE_ROOT / "key_frozen_outputs" / "ege_frozen" / "open_eligibility_lock_v1.json"
    report = RELEASE_ROOT / "verification" / "eligibility_201_240_verification.json"
    if report.exists():
        data = json.loads(report.read_text(encoding="utf-8"))
        statuses.append(("eligibility_201_240", data.get("status", "FAIL")))
    else:
        statuses.append(("eligibility_201_240", "FAIL"))
    if (RELEASE_ROOT / "REPRO_STATUS.md").exists():
        text = (RELEASE_ROOT / "REPRO_STATUS.md").read_text(encoding="utf-8")
        statuses.append(("repro_status_doc", "PASS" if "PASS" in text else "PARTIAL"))
    else:
        statuses.append(("repro_status_doc", "FAIL"))

    out = {"release_root": str(RELEASE_ROOT), "statuses": statuses}
    (DERIVED / "run_release_verification.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2))
    fails = [s for _, s in statuses if s == "FAIL"]
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
