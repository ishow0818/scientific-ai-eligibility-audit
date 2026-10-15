# WINDOWS_REPRO_AUDIT_SUMMARY — final post-cleanup status

## Final status

**12 PASS / 1 PARTIAL / 0 FAIL**

No conflict with the manuscript's scientific results was identified. Frozen scientific outputs and `main.tex` were not modified during release cleanup.

## Resolved items

1. **Re-entry — PASS**
   - Canonical entry: `rediscovery_cross/anchor_v2_aligned/`
   - Runner: `run_confirmatory.py`
   - Matched analysis: `matched_analysis.py`
   - Formal outputs: `outputs/confirmatory/`
   - Seeds: 121–140
   - Matched events: 78
   - Trajectory divergence: 6
   - Re-entry/transient under ON: 5/78
   - Persistent absence: OFF 78/78; ON 73/78
   - Exact event-level McNemar p = 0.0625 (descriptive; same-seed events are not treated as independent).

2. **Evidence-rule sensitivity — PASS**
   - Frozen primary rule (`FWER=0.05`, persistence=2): **200/200 stored exclusion times reproduced exactly**.
   - Manuscript sensitivity grid: **18/18 rows matched**.
   - Outputs are under `verification/evidence_sensitivity/`.

3. **Figures — PASS**
   - Fig. 1–3 regenerated in a clean directory.
   - File SHA-256 values matched the frozen manuscript PNGs.
   - Decoded pixel arrays matched exactly.
   - Differing pixels: 0 for all three figures.

4. **GitHub / Zenodo split — PASS**
   - Trees are distinct.
   - GitHub candidate contains code/configuration/small summaries and omits large seed JSON.
   - Zenodo candidate contains frozen seed-level outputs including stage-2 seeds.

## Previously confirmed scientific results

- Anchor main: Native alternative FI = 78; Neutral = 80; withdrawal-round split = 26/52; 71/78 paired Neutral retained at the same round.
- Final eligibility: Native 37/40; Open Eligibility 40/40; Decision-Only 39/40; Full Gate 40/40.
- Open Eligibility changes exactly seeds 208, 224, and 232 relative to Native.
- CoFI W=10 coverage: round 10 = 186/186, round 20 = 87/41, round 30 = 10/64, round 40 = 0/33, round 50 = 0/16.
- ARROWS Phase-2E: 5 fixed cases, 4 distinct candidate routes, 5/5 gating contrasts.
- Exact `neighpy` provenance recovered: version 0.1.9 on the original Python 3.10 installation used for CoFI search.
- Historical ARROWS manifest hash referenced by Phase-2E was recovered and matched.

## Remaining PARTIAL

Only **third-party raw-data redistribution rights** remain unresolved for some CoFI / ARROWS upstream assets. Those raw assets remain excluded from public release candidates unless redistribution permission is confirmed. This does not alter the frozen derived results used by the manuscript.

## Author decisions still required before public release

- Select the license for author-generated code / outputs, subject to author and institutional approval.
- Decide whether any third-party raw assets may be redistributed after checking their upstream licenses/permissions.
