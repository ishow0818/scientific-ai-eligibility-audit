# SCIENTIFIC_RESULT_VERIFICATION — final status

This document records the final Windows-origin reproducibility status after the release cleanup. No frozen scientific output was modified.

| Module | Final status | Verified result / note |
|---|---|---|
| Anchor main (seeds 1–20) | **PASS** | Native alternative FI 78; Neutral 80; 26 no single-round violation at withdrawal; 52 with single-round violation but not two-round exclusion; 15 Native seeds contribute the 26 events; 71/78 paired Neutral candidates remain eligible at the same round. The Windows finalize pass did not independently recompute the risk-record denominator 446; that denominator was independently recomputed in the separate manuscript/frozen-record audit. |
| No-Opp ablation (seeds 1–20) | **PASS** | Frozen formal outputs support Native/No-Opp alternative FI 78/79 and true-model FI 2/1. |
| True-model loss (seeds 21–40) | **PASS** | True-model early withdrawal in seeds 29, 31, 36, and 37 (4/20), matching the manuscript. The historical 19-point RMSE ratios remain descriptive, not a strict common holdout. |
| Final eligibility / Open / Decision-Only / Full Gate (201–240) | **PASS** | Native 37/40; Open 40/40; Decision-Only 39/40; Full Gate 40/40. Read-only recomputation and 44 tests passed. Open differs from Native exactly at seeds 208, 224, 232; Decision differs from Native at 224, 232. Mean RMSE: Native 0.1354327318; Open 0.0846773939; Decision-Only 0.1033417636; Full Gate 0.0829721571. |
| Re-entry (seeds 121–140) | **PASS** | Canonical entry resolved to `rediscovery_cross/anchor_v2_aligned/` (`run_confirmatory.py`, `matched_analysis.py`, `config.yaml`, `outputs/confirmatory/`). Matched events 78; trajectory divergence 6; ON transient/re-entry 5; OFF persistent 78/78; ON persistent 73/78; exact McNemar p=0.0625. |
| Evidence-rule sensitivity | **PASS** | Primary rule (`FWER=0.05`, persistence=2) reproduced 200/200 stored exclusion times exactly. All 18 manuscript sensitivity rows matched. |
| Minimal recursive dynamics | **PASS** | Frozen `final_verdict.json` reports PASS for the local amplification mechanism, theoretical local `R_id` boundary, growth-law correspondence, recursion specificity, large-N persistence, and bias checks. Universal finite-time collapse threshold remains explicitly NOT CLAIMED. |
| CoFI paired coverage (401–410) | **PASS** | W=10 coverage matches manuscript: 186/186, 87/41, 10/64, 0/33, 0/16 for rounds 10/20/30/40/50. `neighpy` version 0.1.9 confirmed on the original Python 3.10 environment. |
| ARROWS Phase-2E | **PASS** | Five fixed cases, four distinct candidate routes, 5/5 gate contrasts; candidate 900°C pure-target outcomes and historical manifest provenance match the frozen audit. |
| Figures | **PASS** | Fig. 1–3 regenerated cleanly; SHA-256 and decoded pixel arrays match exactly; zero differing pixels. |
| Environment provenance | **PASS** | Windows environment snapshots captured; eligibility-intervention environment and separate CoFI Python 3.10/neighpy environment are documented. |
| Third-party raw assets | **PARTIAL** | Redistribution permission is unresolved for some CoFI / ARROWS upstream raw assets. Public payloads omit assets with unclear rights and retain retrieval/provenance notes. |
| GitHub / Zenodo split | **PASS** | Release trees are distinct; GitHub omits large seed JSON, while Zenodo contains frozen seed-level outputs including stage-2 seeds. |

**Final reproducibility status: 12 PASS / 1 PARTIAL / 0 FAIL.**
