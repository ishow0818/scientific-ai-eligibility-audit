# ARROWS Phase-2E — Frozen 5-case local verification

Local computational checks on the five frozen strict cases only.

Does **not**:
- add physical / wet experiments
- expand the case list
- rerun the historical 87-step campaign
- modify the manuscript
- overwrite Phase-2C / Phase-2D outputs

Reads frozen inputs from `../arrows_phase2d_route_progressive/inputs`.
Uses the publication-era `suggest.check_redundancy` / `update_interm` without changing their scientific logic.

The only control-flow change relative to Phase-2D replay is in **this** verifier:
Gate OFF does not skip 700/800/900°C when the redundancy stop is disabled,
and Gate ON skips those temperatures **only** when `check_redundancy` returns True.
