# Identifiability Dynamics (Final)

Frozen minimal dynamics for subsequent scientific work.

## Core proposition

Without new discriminatory evidence, if the learner’s current alternative
support recursively determines the next alternative support, then a small
alternative imbalance can switch from **decay** to **amplification**.

Definitions:

```text
q_t = P_t(B)
P_t(A) = 1 - q_t
P_world(A) = P_world(B) = 0.5
```

Recursive map with unbiased rediscovery:

```text
p_B(q) = sigmoid(alpha * logit(q) - beta)
F(q)   = (1-mu) * p_B(q) + mu/2
R_id   = (1-mu) * alpha
```

At `beta=0`, `q*=0.5`:

```text
F'(0.5) = R_id
R_id < 1  → local perturbation decays
R_id > 1  → local perturbation amplifies
R_id = 1  → critical boundary
```

## Theoretical interpretation (locked)

**Layer 1 — Local amplification.**  
`R_id=1` is the local alternative-support amplification threshold
(decay ↔ amplification of small perturbations).

**Layer 2 — Downstream consequence.**  
Once local amplification is active, finite recursive representation can
further reduce alternative entropy / effective alternatives and raise
apparent uniqueness. Terminal collapse is a **downstream consequence** of
recursive local instability — not an independent definition of `R_id=1`.

## Experiments

1. **Deterministic local amplification** — `q0=0.5±ε`, `ε∈{0.001,0.002,0.005}`,
   `λ_emp=(1/K)log(|δ_K|/|δ_0|)` vs `log(R_id)` (`K=5` primary, `K=10` robust).
2. **Threshold / growth-law** — empirical sign-crossing intervals vs
   `α_c=1/(1-μ)`; Pearson/Spearman of `λ_emp` vs `log(R_id)`.
3. **Recursive vs No-recursion** — matched `N,T,seeds,rediscovery`; NR sets
   generation `P(B)=0.5`. Early `D_t`, `A_K=D_K/D_1` plus terminal consequence.
4. **Large-N + bias controls** — `N∈{20,50,100,500,2000}`; `β∈{0,0.01,0.03,0.05}`
   with signed `P_A−P_B` (not absolute asymmetry).

## Main results (verified)

- Below/above `R_id≈1`: deterministic `λ_emp` sign flip; growth-law `r≈1`.
- Theory `α_c` falls in empirical crossing intervals for all six `μ`.
- Above threshold: Recursive early amplification ≫ No-recursion; NR terminal
  collapse ≈ 0.
- Large `N` (500, 2000): Amplification excess remains positive.
- `β=0` already unstable above threshold; mild `β>0` selects direction.

## Controls

| Control | Role |
|--------|------|
| No-recursion | Removes recursive dependence only |
| Large N | Rules out pure small-N drift |
| Mild β | Direction selection, not required for instability |

## Scope limitation

`R_id=1` predicts the **local stability boundary**, not a universal
finite-time terminal-collapse boundary. Finite-time `P_collapse` also depends
on horizon and stochastic dynamics. The stronger claim is **not claimed**
in this package (`Universal_finite_time_collapse_threshold: NOT CLAIMED`).

## Reproduction

```bash
# from repository root
pytest identifiability_dynamics_final/tests -q
python -m identifiability_dynamics_final.run_validation
```

**Provenance**

- Deterministic local metrics: recomputed by `run_validation.py`.
- Early stochastic (`t≤20`): recomputed under the frozen grid/seeds
  (or `--skip-stochastic-resim` to reanalyze
  `outputs/pilot_alt_dynamics/local_amplification/*.csv`).
- Terminal / bias / budget terminal summaries: reanalyzed from verified
  `outputs/pilot_alt_dynamics/*_summary.csv` (full `T=100` 500-seed grids
  are not re-run by default).

Gates: `G1`…`G7` in `gates.py`. No figure-generation code.
