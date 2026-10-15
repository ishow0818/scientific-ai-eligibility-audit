# Statistical Endpoint Correction — Anchor v2 Confirmatory

## Problem

The original summary compared:

- OFF: 78 events, 100% persistent
- ON v2: 80 events, 92.5% persistent
- ΔP(persistent) = +7.5 pp (all-event rates)

Because ON/OFF dynamics diverge after the first FI, ON generated **two additional** unsupported FI events (128/quad, 139/quad) with no OFF counterpart. The 78 vs 80 denominators are **not paired** and must not serve as the primary causal recovery comparison.

## Primary endpoint (corrected)

**Denominator:** Matched unsupported FI events where OFF and ON v2 share the same `(seed, family, g_loss)` — i.e. the same first-loss identity.

**Statistics computed on matched set only:**

- Persistent / transient rates (OFF vs ON)
- persistent → transient / transient → persistent
- Trajectory divergence
- ΔP(persistent) in percentage points
- McNemar exact test on discordant matched pairs

**Interpretation tag:** `directionally_consistent_small_effect` when discordance is one-sided (not “statistically significant”).

## Secondary / descriptive blocks

1. **All-event rates (78 vs 80)** — labeled `DESCRIPTIVE — UNMATCHED ALL-EVENT RATE`
2. **ON-only / OFF-only / FI-identity-mismatch** — `POST-INTERVENTION SYSTEM-LEVEL DYNAMICS`
3. **Cross-system table (Anchor v2 vs CAMELS)** — descriptive magnitude only

## Anchor v1 (101–120)

Not pooled with v2. Retained as historical special-threshold probe (0 persistent→transient).

## Primary scientific wording (if numbers confirm)

> Among matched unsupported FI events, aligned recoverability changed 5/N events from persistent to transient; persistence decreased from N/N under OFF to (N−5)/N under ON v2. The paired exact McNemar test gave p=0.0625.

(Do not claim statistical significance.)
