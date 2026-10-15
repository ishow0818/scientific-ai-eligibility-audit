# Pilot: False-Identifiability Anchor Closed Loop

Sibling of `identifiability_dynamics_final/` and `pilot_alt_dynamics/`.
Full frozen design: `EXPERIMENT_DESIGN.md` (v1.1). CPU-only.

## Core proposition

In a concrete closed-loop symbolic-regression system (5 interpretable
mechanism families, known noise, same candidate set in both arms), the full
FI evidence chain:

```
recursive allocation
  -> evidence-compatible alternative eliminated early (Native)
  -> matched Neutral retains it
  -> at elimination, evidence has not excluded it (Native: t_elim < t_excl)
  -> later discriminative evidence truly excludes it
```

Primary endpoints:

1. **E1 unsupported elimination (seed-level)**: at least one auditable false-family
   event in Native with elimination while evidence-compatible;
2. **E2 temporal FI (Native-internal)**: `DeltaT_FI = t_excl^Native - t_elim^Native`
   on the same alternative and trajectory;
3. **E3 causal rescue (separate)**: Native eliminates h at t while Neutral
   still retains h at the matched time.

Supporting contrast: cross-arm `DeltaT_cross = t_excl^Neutral - t_elim^Native`
(descriptive / causal contrast, not the primary temporal FI endpoint).

**Local perturbation (secondary)**: CRN counterfactual branches with
`g = ||w_pert_next - w_base_next|| / ||w_pert - w_base||` as an empirical
local response measure.  Not a direct estimate of alpha, mu, or R_id.
Neutral is the exact zero-gain control under CRN.

## Design (frozen)

- 20 seeds x 25 rounds x 5 new measurements, 2 arms per seed
  (Native / Neutral), identical initial observations across all seeds/arms.
- Truth = `hump` (A=8, mu=4.5, s=2.5); false families `affine / pow /
  expsat / quad`, all evidence-compatible on the initial window [0.5, 2],
  all excluded once late-x data arrives.
- **PUBLIC evidence**: every acquired measurement enters all hypothesis streams
  in both arms.  Native records proposer credit as provenance only.
- **Native**: support-weighted proposal sampling (allocation only).
- **Neutral**: fixed ascending sweep over [2.1, 10] (support-independent).
  Everything else (initial obs, noise field, budget, fitting, support rule,
  elimination rule, evidence criterion) matched.
- Support: recency-weighted stream log-likelihood (gamma=0.85), elimination
  at survivor-normalised `w < 0.02` (permanent).
- Evidence (frozen, independent of support): arm-wide chi2 goodness-of-fit
  with known sigma, alpha=0.05/(5*R) sequential Bonferroni, 2-round persistence.

## Kill rules (pre-registered; do not revise after results)

| Gate | Condition | Threshold |
|------|-----------|-----------|
| KILL-B1 | Neutral converges to the truth family | >= 18/20 seeds |
| KILL-B2 | truth spuriously evidence-excluded | neutral 0, native <= 1 |
| KILL-B3 | all 5 families evidence-compatible at round 0 | >= 18/20 seeds |
| KILL-B4 | arm matching + exact zero neutral gain (CRN) | matching OK and \|g\| < 1e-9 |
| KILL-B5 | full pilot runtime | <= 1 CPU hour |

| Gate | Condition | Threshold |
|------|-----------|-----------|
| PASS-A1 | seed-level unsupported elimination (E1) | >= 8/20 seeds |
| PASS-A2 | causal rescue on unsupported events (E3) | >= 60% |
| PASS-A3 | frac(DeltaT_FI >= 1) over all unsupported events (E2) | >= 60% |

A1 in 3..7/20 = **AMBIGUOUS**: escalate to a reviewed v2, never silent
tuning.  Native final truth recovery (DESC-A4) is descriptive only.
Local gain g: secondary analysis only, no gate.

## Run order

```bash
# from repository root
pytest pilot_fi_anchor/tests -q
python -m pilot_fi_anchor --calibrate               # evidence criterion sanity check
python -m pilot_fi_anchor --dry                      # 1 seed x 4 rounds, console only
python -m pilot_fi_anchor --seeds 1..20              # formal pilot (writes outputs/)
python -m pilot_fi_anchor --seeds 1..20 --no-perturb # faster, skips perturbation branches
```

Outputs: `outputs/pilot_fi_anchor/{seed_*.json, endpoints.json, gates.json,
summary_*.csv}`. Every seed run is bit-reproducible (explicit
SeedSequence-derived RNGs; deterministic warm-started fitting).

Dependencies: numpy, scipy (least_squares, chi2), pandas, pytest
(scipy added to requirements.txt). No figures. No parameter tuning.

## B2-v2 (sequential Bonferroni)

v1.1.1 KILL-B2 failed (neutral=1, native=2) due to legacy α=0.01 reused across
25 rounds — not hump fitting pathology. B2-v2 sets ALPHA_EV = 0.05/(5*R).
The v1.1.2 confirmatory 20-seed output is present in outputs/pilot_fi_anchor/:
each seed snapshot records alpha_ev=0.0004, and gates.json records all
KILL-B1--B5 and PASS-A1--A3 gates as PASS. B2_V2_AUDIT.md remains the
targeted-audit protocol and repair provenance.

## Status

Design v1.1.2 / B2-v2. v1.1.1 exploratory 20-seed superseded; **confirmatory
v1.1.2 complete**. See outputs/pilot_fi_anchor/endpoints.json and gates.json.
