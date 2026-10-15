# Truth-Loss Failure Mode Extension

Sibling of `pilot_fi_anchor/`.  Phase 1 only in v0.1.

## Run

```bash
pytest pilot_truth_loss/tests -q
python -m pilot_truth_loss --calibrate
python -m pilot_truth_loss --seeds 1..20              # phase-2 confirmatory
python -m pilot_truth_loss --seeds 1..20 --no-perturb # faster
```

## Frozen pair (phase 1)

| | |
|---|---|
| Truth | hump |
| Competitor | pow |

See `EXPERIMENT_DESIGN.md` for PC1–PC6 selection rule and phase-2 endpoints.

## Status

Phase-1 **READY**; Phase-2 runner wired (`confirmatory.py`).  
Formal 20-seed **not run** until post-audit approval.
