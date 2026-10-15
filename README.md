# Reproducibility materials for "Algorithmic Elimination and Evidential Exclusion in Scientific AI"

This repository contains the MIT-licensed, author-generated code and verification
materials for the manuscript **"Algorithmic Elimination and Evidential Exclusion in
Scientific AI"** (Zhipeng Zhang, Kai Li, Wenting Ma, Meng Guo, Lei Yang; China Mobile
Research Institute).

It is the GitHub half of a split release:

| Component | Location | Content |
|---|---|---|
| Code, configs, verification scripts, figures | **this repository** | author-generated code (MIT) |
| Frozen seed-level outputs and large JSON records | Zenodo archive (reserved DOI, see [below](#zenodo-data-archive)) | archival frozen data |
| Private Windows reproducibility audit | not published | internal audit trail |

## Zenodo data archive

Frozen experimental outputs and derived reproducibility artifacts are archived on Zenodo.

Reserved DOI: https://doi.org/10.5281/zenodo.23395190

The DOI becomes active when the Zenodo record is published.

The two public trees are intentionally distinct: this repository intentionally omits
large seed-level JSON payloads (those are in the Zenodo deposit), and both public
payloads omit third-party raw data whose redistribution rights are unclear (see
[Third-party assets](#third-party-assets)).

## Repository contents

| Path | Content |
|---|---|
| `src/` | Experiment and analysis source: evidence-gated eligibility, anchor pilot, truth-loss pilot, opportunity-feedback ablation, re-entry confirmatory run (`rediscovery_cross`), CoFI analyses, ARROWS Phase-2E gate verification, minimal recursive dynamics, manuscript audit scripts |
| `figures/` | Manuscript figures (Fig. 1–3 PNG) and the figure-generation script `make_patterns_figures.py` |
| `release_tools/` | Verification and release tooling (frozen-output checks, evidence-sensitivity replay, eligibility-core verification, release build/split) |
| `summaries/` | Frozen summary tables and reports for the headline experiments |
| `verification/` | Verification records (anchor modules, eligibility seeds 201–240, evidence-rule sensitivity) |
| `provenance/` | Provenance records: ARROWS manifests, CoFI `neighpy` environment, canonical re-entry entry point |
| `environment/` | Python environment snapshots (`requirements.txt`, `pip_freeze.txt`, `pip_list.txt`) |
| `MANIFEST_SHA256.txt` | SHA-256 manifest of this payload as packaged (220 files) |
| `CITATION.cff` | Citation metadata |

## Reproducibility status

Final status after the release audit: **12 PASS / 1 PARTIAL / 0 FAIL**
(see `REPRO_STATUS.md` and `SCIENTIFIC_RESULT_VERIFICATION.md` for the full table).

Highlights, all reproduced from frozen records and read-only recomputation:

- **Anchor main** (seeds 1–20): Native alternative FI 78 vs. Neutral 80; 26 seeds show no single-round violation at withdrawal.
- **Final eligibility** (seeds 201–240): Native 37/40; Open 40/40; Decision-Only 39/40; Full Gate 40/40.
- **Re-entry** (seeds 121–140, preregistered): 78 matched events, 6 trajectory divergences, 5 re-entry events; exact McNemar p = 0.0625.
- **Evidence-rule sensitivity**: primary rule reproduced 200/200 stored exclusion times; all 18 manuscript sensitivity rows matched.
- **CoFI paired coverage** (seeds 401–410, W=10): 186/186, 87/41, 10/64, 0/33, 0/16 for rounds 10/20/30/40/50.
- **Figures 1–3**: clean-room regeneration matched the frozen PNGs with zero differing pixels.

The single PARTIAL item is a **third-party raw-data redistribution-rights issue**
(CoFI field RF inputs, ARROWS `Exp.json`/`Settings.json`), not a scientific-result
inconsistency.

## Verifying this release

```bash
# 1. Integrity of the packaged payload (220 files)
shasum -a 256 -c MANIFEST_SHA256.txt        # macOS / Linux
# sha256sum -c MANIFEST_SHA256.txt          # GNU coreutils

# 2. Read-only verification of frozen anchor outputs
python release_tools/verify_anchor_frozen.py

# 3. Read-only verification of the eligibility core (seeds 201–240)
python release_tools/verify_eligibility_core.py
```

Note on `MANIFEST_SHA256.txt`: it documents the release payload **as packaged**.
`README.md` was added after packaging as documentation and is not a manifest entry.

## Environment

- Primary eligibility/audit environment: Python 3.12.10, NumPy 2.5.0, SciPy 1.17.1
  (see `environment/pip_freeze.txt`).
- CoFI nearest-neighbour search additionally uses
  [`neighpy`](https://github.com/auggiemarignier/neighpy) **0.1.9** (GPL-3.0-or-later)
  on a Python 3.10 environment; see `provenance/cofi/NEIGHPY_PROVENANCE.md`.

Frozen scientific outputs were never modified by verification runs; fresh reruns must
be written outside the frozen output directories.

## Third-party assets

Third-party raw data with unclear redistribution permission is **not included** in this
repository. Retrieval instructions and expected hashes are in
`THIRD_PARTY_RETRIEVAL.md` and `THIRD_PARTY_DATA_AND_LICENSE_NOTES.md`. Upstream
acknowledgements: [CoFI](https://github.com/inlab-geo/cofi),
[ARROWS](https://github.com/njszym/ARROWS), [neighpy](https://github.com/auggiemarignier/neighpy).

## License

Author-generated code in this repository is released under the
[MIT License](LICENSE) — Copyright (c) 2026 Zhipeng Zhang.

The MIT license applies only to author-generated code. It does **not** relicense
third-party dependencies, datasets, or source materials.

## Citation

If you use this software or the associated reproducibility materials, please cite the
associated manuscript (see `CITATION.cff`). Corresponding author: Zhipeng Zhang
(`zzp_zzp2002@aliyun.com`).
