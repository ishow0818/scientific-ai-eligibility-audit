"""Read-only, post-hoc audit of saved CoFI search opportunities; no simulation imports.

Writes derived JSON only. Parent-neighbourhood allocation is a proxy, not the
probability of reaching a physical neighbourhood through a Voronoi cell.
"""
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.spatial.distance import cdist

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'cofi_rf_identifiability/stage0_real_rf/native_na_control/runs/paired_support_neutral_confirmatory_v1'
OUT = ROOT / 'analysis/cofi_opportunity_audit.json'
inputs = {}


def read(path):
    raw = path.read_bytes()
    inputs[str(path.relative_to(ROOT))] = hashlib.sha256(raw).hexdigest()
    return raw.decode('utf-8')


joint = json.loads(read(SOURCE / 'joint_summary.json'))
cfg = joint['config']
events, seeds = [], []
for seed in cfg['paired_seeds']:
    folder = SOURCE / f'seed{seed}'
    summary = json.loads(read(folder / 'paired_summary.json'))
    arms = {}
    for arm, name in [('native', 'arm_a_native_trajectory.jsonl'), ('control', 'arm_b_support_neutral_trajectory.jsonl')]:
        rows = [json.loads(line) for line in read(folder / name).splitlines()]
        assert [r['candidate_id'] for r in rows] == list(range(len(rows)))
        arms[arm] = {
            'profiles': np.array([r['vs_z'] for r in rows]),
            'it': np.array([r['iteration'] for r in rows]),
            'obj': np.array([r['L_RF'] for r in rows]),
            'parents': np.array([r['parent_cell_candidate_id'] if r['parent_cell_candidate_id'] is not None else -1 for r in rows]),
        }
    a, b = arms['native'], arms['control']
    t0, cutoff, radius = cfg['t0_iteration'], cfg['fixed_viable_sse_cutoff'], cfg['physical_coverage_radius']
    anchors = np.unique(b['parents'][b['it'] == t0 + 1])
    assert len(anchors) == 20
    early = np.flatnonzero((a['it'] >= 1) & (a['it'] <= t0) & (a['obj'] <= cutoff))
    scale = 3.0  # Original S_VS, fixed prior width in km/s.
    dist = cdist(a['profiles'][early] / scale, a['profiles'][anchors] / scale) / np.sqrt(a['profiles'].shape[1])
    denominator = early[dist.min(axis=1) <= radius]
    latest = max(summary['matches'], key=lambda m: m['native_iteration'])
    lost_positions = sorted(set(range(len(denominator))) - set(latest['native_retained_ids']))
    assert len(lost_positions) == summary['native_lost_t0_preservable']
    seed_events = []
    for pos in lost_positions:
        cid = int(denominator[pos])
        event = {'seed': seed, 'candidate_id': cid, 'L_RF': float(a['obj'][cid]), 'arms': {}}
        for arm, data in arms.items():
            checkpoint = int(latest[f'{arm}_iteration'])
            near = cdist(a['profiles'][[cid]] / scale, data['profiles'] / scale)[0] / np.sqrt(data['profiles'].shape[1]) <= radius
            parents = data['parents']
            has_parent = parents >= 0
            assert np.all(data['it'][parents[has_parent]] < data['it'][has_parent])
            parent_near = has_parent & near[np.maximum(parents, 0)]
            per_round = []
            for t in range(t0 + 1, cfg['total_iterations'] + 1):
                mask = data['it'] == t
                assert mask.sum() == cfg['n_samples_per_iteration']
                per_round.append({'round': t,
                    'proposals_from_near_parent': int((mask & parent_near).sum()),
                    'near_proposals_all': int((mask & near).sum()),
                    'near_proposals_viable': int((mask & near & (data['obj'] <= cutoff)).sum())})
            recent = [r for r in per_round if checkpoint - cfg['support_window_iterations'] < r['round'] <= checkpoint]
            later = [r for r in per_round if r['round'] > checkpoint]
            values = {'checkpoint': checkpoint, 'later_rounds_observed': len(later), 'rounds': per_round}
            for key in ['proposals_from_near_parent', 'near_proposals_all', 'near_proposals_viable']:
                values['recent_' + key] = sum(r[key] for r in recent)
                values['later_' + key] = sum(r[key] for r in later)
            if arm == 'native':
                assert values['recent_near_proposals_viable'] == 0
            event['arms'][arm] = values
        assert event['L_RF'] <= cutoff
        events.append(event)
        seed_events.append(event)
    seeds.append({'seed': seed, 'lost_records': len(seed_events),
        'native_checkpoint': latest['native_iteration'], 'control_checkpoint': latest['control_iteration'],
        'recent_native_near_parent_positive': sum(e['arms']['native']['recent_proposals_from_near_parent'] > 0 for e in seed_events),
        'recent_native_near_proposal_positive': sum(e['arms']['native']['recent_near_proposals_all'] > 0 for e in seed_events),
        'later_native_viable_revisit': sum(e['arms']['native']['later_near_proposals_viable'] > 0 for e in seed_events)})
assert len(events) == joint['lost'] == 153
totals = {}
for arm in arms:
    totals[arm] = {key: sum(e['arms'][arm][key] > 0 for e in events) for key in [
        'later_rounds_observed', 'recent_proposals_from_near_parent', 'recent_near_proposals_all',
        'recent_near_proposals_viable', 'later_proposals_from_near_parent',
        'later_near_proposals_all', 'later_near_proposals_viable']}
report = {'status': 'POST_HOC_DESCRIPTIVE_NO_NEW_SIGNIFICANCE_TEST',
    'scope': '153 candidate-by-run records at original latest fit-matched checkpoints; no endpoint changes',
    'limitations': ['Near-parent allocation is not exact physical-neighbourhood probability: Voronoi cells and physical distance differ.',
        'Zero observed allocation or proposals does not establish permanent exclusion or zero future probability.',
        'Events and neighbourhoods overlap; counts are not independent replicates.',
        'Later follow-up lengths depend on original checkpoint; no observations beyond round 50.'],
    'source_sha256': inputs, 'totals_records_with_positive_count': totals, 'per_seed': seeds, 'events': events}
OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
print(json.dumps({'totals': totals, 'per_seed': seeds, 'output': str(OUT)}, indent=2))
