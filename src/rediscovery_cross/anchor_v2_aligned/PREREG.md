# Anchor Rediscovery v2 — CAMELS-aligned Recoverability (Prereg v2.0.0)

## Scientific question

Does CAMELS-aligned re-entry accessibility alter post-FI persistence in Anchor?

Shared principle: *Representation is reconstructed from the current state rather than irreversibly inherited from past elimination.*

## Cohort (frozen)

- **Confirmatory:** seeds **121–140**, N=20
- **Dry-run:** seeds 921, 922
- **Excluded:** pilot 1–20, v1 101–120, CAMELS 47–91

## Intervention

| Arm | Mechanism |
|-----|-----------|
| OFF | Formal Anchor hard elimination (unchanged) |
| ON v2 | After first elimination: `alive[h] = w_all[h] >= THETA_W` each round |

**Not used:** v1 `_hypothetical_w_surv >= THETA_W` special revival gate.

## Gates

1. Pre-first-FI bit-identical (OFF vs v2 ON)
2. First unsupported FI matched (family, t_loss)
3. Re-entry criterion audit: `w_all >= THETA_W` only

## Endpoints

**Primary:** post-FI trajectory divergence (matched unsupported FI events)

**Secondary:** P(persistent|OFF) vs P(persistent|ON-v2), re-entry delay, paired event table, McNemar (if discordant pairs exist)

## Relation to v1

v1 (101–120) retained as special-threshold probe; **not pooled** with v2.
