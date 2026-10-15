"""Post-hoc 10/15/20-round sensitivity using existing Native trajectories only.

No experiment imports, reruns, threshold changes or significance tests.
Window: checkpoint-W < iteration <= checkpoint, identical to original code.
"""
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.spatial.distance import cdist

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'cofi_rf_identifiability/stage0_real_rf/native_na_control/runs/paired_support_neutral_confirmatory_v1'
hashes = {}


def read(path):
    raw = path.read_bytes()
    hashes[str(path.relative_to(ROOT))] = hashlib.sha256(raw).hexdigest()
    return raw.decode('utf-8')


joint = json.loads(read(SOURCE / 'joint_summary.json'))
cfg = joint['config']
records, seeds = [], []
for seed in cfg['paired_seeds']:
    folder = SOURCE / f'seed{seed}'
    summary = json.loads(read(folder / 'paired_summary.json'))
    rows = [json.loads(line) for line in read(folder / 'arm_a_native_trajectory.jsonl').splitlines()]
    control = [json.loads(line) for line in read(folder / 'arm_b_support_neutral_trajectory.jsonl').splitlines()]
    assert [r['candidate_id'] for r in rows] == list(range(len(rows)))
    anchors = sorted({r['parent_cell_candidate_id'] for r in control if r['iteration'] == cfg['t0_iteration'] + 1})
    assert len(anchors) == 20
    profiles = np.array([r['vs_z'] for r in rows])
    it = np.array([r['iteration'] for r in rows])
    viable = np.array([r['L_RF'] <= cfg['fixed_viable_sse_cutoff'] for r in rows])
    early = np.flatnonzero((it >= 1) & (it <= cfg['t0_iteration']) & viable)
    normalizer = 3.0 * np.sqrt(profiles.shape[1])
    d0 = cdist(profiles[early], profiles[anchors]) / normalizer
    denominator = early[d0.min(axis=1) <= cfg['physical_coverage_radius']]
    latest = max(summary['matches'], key=lambda m: m['native_iteration'])
    checkpoint = int(latest['native_iteration'])
    valid_ids = np.flatnonzero(viable & (it <= checkpoint))
    # Use the same division-before-distance arithmetic as the original audit.
    near = cdist(profiles[denominator] / 3.0, profiles[valid_ids] / 3.0) / np.sqrt(profiles.shape[1]) <= cfg['physical_coverage_radius']
    lost = {}
    for w in (10, 15, 20):
        lost[w] = ~near[:, it[valid_ids] > checkpoint - w].any(axis=1)
    original_lost = sorted(set(range(len(denominator))) - set(latest['native_retained_ids']))
    assert np.flatnonzero(lost[10]).tolist() == original_lost
    assert int(lost[10].sum()) == summary['native_lost_t0_preservable']
    assert np.all(~lost[20] | lost[15]) and np.all(~lost[15] | lost[10])
    seed_records = []
    for pos, cid in enumerate(denominator):
        hits = it[valid_ids][near[pos]]
        assert len(hits)  # Each early model at least covers itself.
        last = int(hits.max())
        rec = {'seed': seed, 'candidate_id': int(cid), 'checkpoint': checkpoint,
               'last_viable_nearby_round': last, 'consecutive_absent_rounds': checkpoint - last,
               'uncovered': {str(w): bool(lost[w][pos]) for w in (10, 15, 20)}}
        for w in (10, 15, 20):
            assert rec['uncovered'][str(w)] == (checkpoint - last >= w)
        seed_records.append(rec)
    records.extend(seed_records)
    durations = [r['consecutive_absent_rounds'] for r in seed_records if r['uncovered']['10']]
    seeds.append({'seed': seed, 'checkpoint': checkpoint, 'auditable_records': len(denominator),
        'uncovered': {str(w): int(lost[w].sum()) for w in (10, 15, 20)},
        'window_includes_shared_prefix': {str(w): checkpoint - w < cfg['t0_iteration'] for w in (10, 15, 20)},
        'original_lost_duration_min_median_max': [min(durations), float(np.median(durations)), max(durations)]})

original = [r for r in records if r['uncovered']['10']]
assert len(original) == 153
durations = [r['consecutive_absent_rounds'] for r in original]
totals = {str(w): sum(r['uncovered'][str(w)] for r in records) for w in (10, 15, 20)}
common_seeds = [s['seed'] for s in seeds if not s['window_includes_shared_prefix']['20']]
report = {'status': 'POST_HOC_DESCRIPTIVE_SENSITIVITY', 'primary_window_unchanged': 10,
    'windows': [10, 15, 20], 'source_sha256': hashes,
    'auditable_records': len(records), 'uncovered_totals': totals,
    'original_153_remaining_uncovered': {str(w): sum(r['uncovered'][str(w)] for r in original) for w in (10, 15, 20)},
    'original_153_absence_rounds_min_median_max': [min(durations), float(np.median(durations)), max(durations)],
    'common_postfork_only_seeds': common_seeds,
    'common_postfork_only_totals': {str(w): sum(r['uncovered'][str(w)] for r in records if r['seed'] in common_seeds) for w in (10, 15, 20)},
    'limitations': ['Candidate-by-run records are dependent and may share neighbourhoods.',
        'Absence means no nearby viable output, not no allocation or permanent deletion.',
        'Widening windows includes older observations; any decline is not a recovery event.',
        'Shared-prefix flags identify windows including iteration <=10; original counts remain reported without exclusions.'],
    'per_seed': seeds, 'records': records}
output = ROOT / 'analysis/cofi_window_sensitivity.json'
output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k not in ('records', 'source_sha256')}, indent=2))
