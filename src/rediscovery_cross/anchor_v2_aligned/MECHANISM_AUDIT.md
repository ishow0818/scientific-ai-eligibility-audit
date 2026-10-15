# Anchor v2 — Mechanism Audit (CAMELS-aligned recoverability)

## A. State-update audit: can dead alternatives receive current evidence?

**Yes.** Anchor PUBLIC evidence pipeline updates all families each round regardless of `alive`:

- `_ingest`: every measurement enters all hypothesis streams
- `_refit_streams`: all families refit stream parameters
- `_update_support`: `S[h]`, `w_all[h]` updated for all families; only `w_surv[h]` zeroed for dead
- `_update_evidence`: arm-wide chi² updated for all families

No new information or special rules are required for v2 re-entry eligibility.

## B. v2 ON definition (functional mechanism)

**OFF (unchanged):** survivor-normalized `w_surv[h] < THETA_W` → `alive=False` permanently.

**ON v2 (CAMELS-aligned):**

1. **Until first elimination:** identical to OFF (absorbing survivor-normalized elimination).
2. **After first elimination recorded:** each round reconstruct represented set:
   - `alive[h] = (w_all[h] >= THETA_W)` for all alternatives
   - `w_all` is full-pool normalized support from current PUBLIC evidence
   - same numeric threshold `THETA_W` as ordinary representation at t=0 (when w_surv = w_all)
3. **No** `_hypothetical_w_surv`, revival bonus, or special gate.
4. First-loss times (`t_elim`) are frozen at first event (FI definition unchanged).

## C. CAMELS functional alignment

| Layer | CAMELS | Anchor v2 |
|-------|--------|-----------|
| Principle | Reconstruct representation from current posterior/proposals | Reconstruct alive set from current w_all |
| Past loss | Does not permanently ban B_r(θ_i) from pool eligibility | Does not permanently ban alternative from eligibility |
| Criterion | Ordinary membership rule on current state | Ordinary `w_all >= THETA_W` on current state |
| Special revival gate | None | None |

## D. Residual mechanism differences (unavoidable)

1. **State object:** CAMELS uses SNPE posterior + catalog NN membership; Anchor uses stream log-lik support weights.
2. **Eligibility geometry:** CAMELS bans parameter balls; Anchor uses scalar weight threshold on 5 discrete families.
3. **Intervention timing:** v2 switches to reconstruction only after first elimination (to preserve first-FI matching); CAMELS rediscovery is active throughout but pre-loss equivalence holds by construction.

These are representation-medium differences, not an extra Anchor-specific recovery rule.

## E. Pre-loss / first-FI gates

- Pre-loss: OFF vs v2 ON bit-identical through round before first unsupported FI.
- First unsupported FI: matched (seed, family, t_loss) by paired CRN.
- Post-FI: v2 may diverge via reconstruction.
