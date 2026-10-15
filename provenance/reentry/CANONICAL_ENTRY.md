# Re-entry canonical formal entry (seeds 121–140)

Status: **PASS** (resolved from evidence; not guessed)

## Canonical paths
- Runner: `rediscovery_cross/anchor_v2_aligned/run_confirmatory.py`
- Matched analysis: `rediscovery_cross/anchor_v2_aligned/matched_analysis.py`
- Config: `rediscovery_cross/anchor_v2_aligned/config.yaml`
- Outputs: `rediscovery_cross/anchor_v2_aligned/outputs/confirmatory/`

## Manuscript numbers (from matched_primary_summary.json)
```json
{
  "n_off_events": 78,
  "n_on_events": 80,
  "n_matched_events": 78,
  "n_on_only_events": 2,
  "n_off_only_events": 0,
  "n_fi_identity_mismatch": 1,
  "matched_off_persistent": "78/78",
  "matched_on_persistent": "73/78",
  "matched_off_transient": "0/78",
  "matched_on_transient": "5/78",
  "matched_off_persistent_n": 78,
  "matched_on_persistent_n": 73,
  "matched_off_transient_n": 0,
  "matched_on_transient_n": 5,
  "p_persistent_off_matched": 1.0,
  "p_persistent_on_matched": 0.9358974358974359,
  "p_transient_off_matched": 0.0,
  "p_transient_on_matched": 0.0641025641025641,
  "persistent_to_transient": 5,
  "transient_to_persistent": 0,
  "trajectory_diverged": 6,
  "trajectory_unchanged": 72,
  "fraction_trajectory_diverged": 0.07692307692307693,
  "delta_persistent_percentage_points": 6.41025641025641,
  "mcnemar_discordant_offP_onT": 5,
  "mcnemar_discordant_offT_onP": 0,
  "mcnemar_n_discordant": 5,
  "mcnemar_exact_p": 0.0625,
  "interpretation_tag": "directionally_consistent_small_effect"
}
```

## Rejected near-misses
- `rediscovery_cross/outputs/confirmatory` (seeds ~101–120): different counts
- `aea_closed_loop_formal`: EvidenceGate; McNemar ≠ 0.0625; verdict INVALID
