# Failure Mode v2 — Pre-registration

**Status**: confirmatory population frozen at seeds 21–40 (n=20)  
**Version**: `pilot-truth-loss-v0.2.2`  
**Anchor dependency**: `pilot-v1.1.2-b2-v2` (read-only import of `pilot_fi_anchor.loop.run_seed`)

---

## 0. Historical record — v1 confirmatory (seeds 1–20)

| Item | Value |
|------|-------|
| Version | `pilot-truth-loss-v0.1.1` |
| Seeds | 1–20 (same as Anchor pilot) |
| F1 result | 2/20 unsupported truth elimination |
| F2 result (pow lock-in) | 0/20 |
| F3 result | 2/2 F1 seeds rescued (100%) |
| Gates PASS-T1 (F1 ≥ 4/20) | **FAIL** |
| Gates PASS-T2 (F2 pow ≥ 2/20) | **FAIL** |
| Gates PASS-T3 (F3 ≥ 60%) | **PASS** |
| Overall | **FAIL** under v1 pre-registration |

**Forensic note (seeds 17, 20)**: F1 events were real; Native locked **quad** (not pre-registered competitor pow); HO1 ratios 77.6× and 9.77× on the frozen 19-point held-out grid. These findings motivated **endpoint revision**, not mechanism retuning.

**v2 disposition**: v1 is **not** retroactively re-judged. v2 is an independent confirmatory with **fresh seeds 21–40 (n=20)** and revised F2-v2. v1 outputs were cleared from `outputs/pilot_truth_loss/` and must not enter v2 statistics.

---

## 1. Scientific question (v2)

v2 tests one failure chain:

> **unsupported truth elimination → stable wrong scientific lock-in → downstream prediction failure**

and whether cutting support-dependent allocation (Neutral arm) **blocks** that chain.

### Difference from v1

| Aspect | v1 | v2 |
|--------|----|----|
| F2 wrong lock-in | Must be frozen competitor **pow** | **Any** non-truth family, stably held |
| F2 scope | All confirmatory seeds | **F1 seeds only** |
| F2 stability | Final incumbent only | Final + **last 5 rounds** same wrong incumbent |
| F3 Neutral rescue | Alive at Native t_elim + final truth | **No** Neutral unsupported elim + final truth |
| Confirmatory seeds | 1–20 (observed) | **21–40** (fresh, n=20) |
| Gates | PASS-T1/T2/T3 count thresholds | **G1–G4** (see §6) |

**Unchanged hypothesis**: truth = hump; pow remains in the 5-family pool but is not required to win.

---

## 2. Frozen experimental mechanism (identical to v1 / Anchor)

No parameter changes based on v1 forensic results.

| Component | Frozen value |
|-----------|--------------|
| Truth DGP | hump, θ* = (8, 4.5, 2.5) |
| Hypothesis families | hump, affine, pow, expsat, quad |
| Initial observations | `X0_IDX` (x ∈ [0.5, 2]) |
| Native allocation | support-weighted |
| Neutral allocation | fixed ascending sweep |
| Noise | σ = 0.5, shared init CRN |
| Fitting | stream + arm-wide refit |
| Support | γ = 0.85, `THETA_W = 0.02` |
| Evidence | B2-v2 sequential Bonferroni, α = 0.05/(5·R), PERSIST = 2 |
| Horizon | R = 25 rounds, M = 5 per round |
| Held-out grid | 19 points, idx % 8 == 3, 120 ≤ idx ≤ 380, excluding X0 ∪ NeutralSweep |
| Loop implementation | **`pilot_fi_anchor.loop.run_seed` only** — no fork |

Held-out indices are used **only** for final HO1 evaluation.

---

## 3. Endpoints (frozen)

### F1 — Unsupported truth elimination (Native)

Truth family support-eliminated while evidence-compatible at `t_elim`, with  
`t_elim(truth) < t_excl(truth)`; if no exclusion within horizon, standard censoring applies (`t_excl = null`).

### F2-v2 — Stable wrong lock-in (Native, **F1 seeds only**)

On each F1 seed:

1. Native final incumbent ≠ truth (hump), **and**
2. The **last 5 rounds** (t = R−4 … R) share the **same** non-truth incumbent, equal to the final incumbent.

Wrong family may be **pow, quad, affine, or expsat** — not pre-specified.

### F3 — Neutral causal rescue (F1 seeds only)

For each Native F1 seed, matched Neutral:

1. Does **not** exhibit unsupported truth elimination (same F1 logic on Neutral arm), **and**
2. Final incumbent = truth (hump).

### HO1 — Downstream prediction consequence (descriptive)

On the frozen **19-point held-out grid**, using **final fitted incumbent θ** for Native and Neutral (no θ₀ fallback):

- `native_ho_rmse`, `neutral_ho_rmse`, `ho_rmse_ratio`
- Reported for all confirmatory seeds; median ratio also reported on F2-v2 seeds
- **No pass/fail threshold** in v2 gates

---

## 4. Confirmatory population

| Set | Seeds | Role |
|-----|-------|------|
| v1 observed | 1–20 | **Excluded** from v2 stats, gates, case selection |
| **v2 confirmatory** | **21–40** (exactly) | n = 20 independent seeds; formal run requires `set(seeds) == {21..40}` |
| dry-run | subset of ≥21, no v1 | dev sanity only; **no G1–G4**, non-formal output dir |

---

## 5. Gates (frozen)

| Gate | Rule | Fail action |
|------|------|-------------|
| **G1** | F1 > 0 on v2 population | **KILL** Failure Mode v2 if F1 = 0 |
| **G2** | F2-v2 / F1 ≥ 60% (on F1 seeds) | FAIL |
| **G3** | F3 / F1 ≥ 60% (on F1 seeds) | FAIL |
| **G4** | B2-v2 evidence sanity: α_ev and anchor version unchanged | FAIL |
| DESC-HO1 | descriptive RMSE ratio on F2-v2 seeds | INFO only |

**Retired v1 gates**: F1 ≥ 4/20, pow lock-in ≥ 2/20 — **not used in v2**.

---

## 6. Execution (when authorized)

```bash
python -m pilot_truth_loss --seeds 21..40
# output: outputs/pilot_truth_loss_v2/  (endpoints.json includes neutral_truth_excluded_k)
```

Dry-run (dev sanity, non-statistical):

```bash
python -m pilot_truth_loss --dry-run --seeds 21 --no-perturb
# output: outputs/pilot_truth_loss_v2_dryrun/  (no gates.json)
```

---

## 7. Analysis firewall

- Seeds 1–20: pair calibration + v1 exploratory/confirmatory only.
- Seeds 21–40: v2 confirmatory only.
- No post-hoc gate adjustment from dry-run or v1 forensic.
- No regional HO1 primary endpoint (e.g. x ∈ [7, 9]) — full 19-point grid only.
