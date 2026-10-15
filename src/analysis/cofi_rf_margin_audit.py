"""Read-only descriptive audit of RF errors for the existing 153 uncovered records."""
import hashlib
import json
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
audit_path = ROOT / 'analysis/cofi_window_sensitivity.json'
audit = json.loads(audit_path.read_text(encoding='utf-8'))
# Verify that the formal sources used to identify candidates have not changed.
for relative, expected in audit['source_sha256'].items():
    assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == expected, relative
source = ROOT / 'cofi_rf_identifiability/stage0_real_rf/native_na_control/runs/paired_support_neutral_confirmatory_v1'
cfg = json.loads((source / 'joint_summary.json').read_text(encoding='utf-8'))['config']
cutoff = cfg['fixed_viable_sse_cutoff']
records = []
for seed in cfg['paired_seeds']:
    rows = [json.loads(line) for line in (source / f'seed{seed}/arm_a_native_trajectory.jsonl').read_text(encoding='utf-8').splitlines()]
    for rec in audit['records']:
        if rec['seed'] != seed or not rec['uncovered']['10']:
            continue
        row = rows[rec['candidate_id']]
        assert row['candidate_id'] == rec['candidate_id']
        loss = row['L_RF']
        records.append(dict(seed=seed, candidate_id=rec['candidate_id'], L_RF=loss,
                            ratio_to_cutoff=loss/cutoff, absolute_margin=cutoff-loss,
                            relative_margin=(cutoff-loss)/cutoff))
assert len(records) == 153
assert len({(r['seed'], r['candidate_id']) for r in records}) == 153

def describe(values):
    q = np.quantile(values, [0, .25, .5, .75, 1], method='linear')
    return dict(zip(['min', 'q25', 'median', 'q75', 'max'], map(float, q)))

report = {
    'status': 'POST_HOC_DESCRIPTIVE_ONLY',
    'cutoff': cutoff,
    'record_count': len(records),
    'all_pass_original_cutoff': all(r['L_RF'] <= cutoff for r in records),
    'L_RF': describe([r['L_RF'] for r in records]),
    'ratio_to_cutoff': describe([r['ratio_to_cutoff'] for r in records]),
    'absolute_margin': describe([r['absolute_margin'] for r in records]),
    'relative_margin': describe([r['relative_margin'] for r in records]),
    'descriptive_bins_not_new_criteria': {
        'within_1_percent_below_cutoff': sum(r['relative_margin'] <= .01 for r in records),
        'within_5_percent_below_cutoff': sum(r['relative_margin'] <= .05 for r in records),
        'at_least_10_percent_below_cutoff': sum(r['relative_margin'] >= .10 for r in records)},
    'per_seed': [dict(seed=s, n=sum(r['seed']==s for r in records),
                      L_RF=describe([r['L_RF'] for r in records if r['seed']==s]),
                      median_ratio=float(np.median([r['ratio_to_cutoff'] for r in records if r['seed']==s])))
                 for s in cfg['paired_seeds']],
    'limitations': ['153 candidate-by-run records are not independent replicates.',
                   'Candidates were originally selected to pass this same fixed-data criterion.',
                   'Margins are descriptive, not confidence levels or evidence of truth.',
                   'No new significance tests, threshold changes or experiments.'],
    'source_sha256': audit['source_sha256'],
    'candidate_selection_audit_sha256': hashlib.sha256(audit_path.read_bytes()).hexdigest(),
    'records': records}
out = ROOT / 'analysis/cofi_rf_margin_audit.json'
out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k not in ('records','source_sha256')}, ensure_ascii=False, indent=2))
