# THIRD_PARTY_DATA_AND_LICENSE_NOTES

| Asset | Upstream | Version/commit | Local | License | Redistribution |
|---|---|---|---|---|---|
| Author-generated code | This study | current release | public code package | MIT | YES, subject to MIT; excludes third-party components |
| neighpy | https://github.com/auggiemarignier/neighpy | 0.1.9 (PyPI) | Python310 site-packages | GPL-3.0-or-later | YES (as dependency; source not vendored in public zip) |
| CoFI field RF data | CoFI examples / upstream field case | see analysis provenance hashes | cofi_rf_identifiability / cofi_sw_preflight | UNCLEAR | NO in public zip until cleared |
| ARROWS Exp.json / Settings.json | ARROWS project | hashes in phase2e summary | ARROWS-main / phase2e inputs | UNCLEAR | NO in public zip until cleared |
| pymatgen (if used by ARROWS tooling) | Materials Project ecosystem | env-dependent | optional | see upstream | UNCLEAR/conditional |
| pyhk | CoFI RF forward | env-dependent | CoFI stack | UNCLEAR | NO until cleared |

Public zips omit unclear-redistribution raw third-party datasets; private audit zip may include **hashes + paths + acquisition notes** and author-generated derived tables.


**Scope note:** MIT applies only to author-generated code in this release. It does not relicense third-party dependencies, data, or source material.
