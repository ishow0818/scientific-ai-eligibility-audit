"""Post-hoc equal-round coverage audit. No simulation, fitting or significance test."""
import hashlib
import json
from pathlib import Path
import numpy as np
from scipy.spatial.distance import cdist

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'cofi_rf_identifiability/stage0_real_rf/native_na_control/runs/paired_support_neutral_confirmatory_v1'
selection_path = ROOT / 'analysis/cofi_window_sensitivity.json'
selection = json.loads(selection_path.read_text(encoding='utf-8'))
for path, digest in selection['source_sha256'].items():
    assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest() == digest, path
cfg = json.loads((SRC/'joint_summary.json').read_text())['config']
series, by_seed = [], []
for seed in cfg['paired_seeds']:
    arms = [[json.loads(x) for x in (SRC/f'seed{seed}'/name).read_text().splitlines()]
            for name in ['arm_a_native_trajectory.jsonl', 'arm_b_support_neutral_trajectory.jsonl']]
    for a,b in zip(arms[0][:3000], arms[1][:3000]):
        for key in ['candidate_id','iteration','parameters','vs_z','L_RF']:
            assert a[key] == b[key], (seed,key)
    ids = [r['candidate_id'] for r in selection['records'] if r['seed']==seed]
    anchors = sorted({r['parent_cell_candidate_id'] for r in arms[1] if r['iteration']==11})
    native = arms[0]
    early = [i for i,r in enumerate(native) if 1<=r['iteration']<=10 and r['L_RF']<=cfg['fixed_viable_sse_cutoff']]
    p = np.array([r['vs_z'] for r in native])
    reconstructed = np.array(early)[(cdist(p[early],p[anchors])/(3*np.sqrt(p.shape[1]))).min(axis=1)<=cfg['physical_coverage_radius']].tolist()
    assert ids == reconstructed
    reference = p[ids]/3
    hits, losses, iterations = [], [], []
    for arm in arms:
        assert [r['candidate_id'] for r in arm] == list(range(len(arm)))
        it=np.array([r['iteration'] for r in arm]); loss=np.array([r['L_RF'] for r in arm])
        assert len(arm)==7000 and all(sum(it==t)==100 for t in range(1,51))
        near=cdist(reference,np.array([r['vs_z'] for r in arm])/3)/np.sqrt(p.shape[1])<=cfg['physical_coverage_radius']
        hit=np.zeros((len(ids),51), dtype=bool)
        for t in range(1,51):
            hit[:,t]=near[:,(it==t)&(loss<=cfg['fixed_viable_sse_cutoff'])].any(axis=1)
        hits.append(hit); losses.append(loss); iterations.append(it)
    local=[]
    for w in [10,15,20]:
        for t in range(10,51):
            states=[h[:,max(1,t-w+1):t+1].any(axis=1) for h in hits]
            a,b=states
            best=[float(l[it<=t].min()) for l,it in zip(losses,iterations)]
            row=dict(seed=seed,window=w,round=t,n=len(ids),evaluations_per_arm=2000+100*t,
                     native_covered=int(a.sum()),control_covered=int(b.sum()),
                     native_fraction=float(a.mean()),control_fraction=float(b.mean()),
                     difference_native_minus_control=float(a.mean()-b.mean()),
                     native_only=int((a&~b).sum()),control_only=int((b&~a).sum()),
                     both=int((a&b).sum()),neither=int((~a&~b).sum()),
                     native_ids=[ids[i] for i in np.flatnonzero(a)],control_ids=[ids[i] for i in np.flatnonzero(b)],
                     native_best_sse=best[0],control_best_sse=best[1],
                     fits_within_5_percent=max(best)/min(best)<=1.05,
                     wholly_postfork=t-w>=10)
            local.append(row)
            if t==10: assert a.all() and b.all()
    series.extend(local)
    endpoint=next(r for r in local if r['window']==10 and r['round']==50)
    diffs=[r['difference_native_minus_control'] for r in local if r['window']==10 and r['round']>=20]
    by_seed.append(dict(seed=seed,n=len(ids),native_final=endpoint['native_covered'],control_final=endpoint['control_covered'],
                        final_difference=endpoint['difference_native_minus_control'],mean_difference_rounds20_50=float(np.mean(diffs)),
                        final_fits_within_5_percent=endpoint['fits_within_5_percent']))

def aggregate(rows):
    d=[r['difference_native_minus_control'] for r in rows]
    return dict(n_seeds=len(rows),denominator=sum(r['n'] for r in rows),
                native_covered=sum(r['native_covered'] for r in rows),control_covered=sum(r['control_covered'] for r in rows),
                mean_seed_difference=float(np.mean(d)),median_seed_difference=float(np.median(d)),
                native_lower=sum(x<0 for x in d),equal=sum(x==0 for x in d),native_higher=sum(x>0 for x in d),
                fits_within_5_percent=sum(r['fits_within_5_percent'] for r in rows))

summary={str(w):{str(t):aggregate([r for r in series if r['window']==w and r['round']==t]) for t in [10,20,30,40,50]} for w in [10,15,20]}
report=dict(status='POST_HOC_DESCRIPTIVE_EQUAL_ROUND_AUDIT',selection='Original 186 t0-preservable candidate-by-run records, not only 153 later-uncovered records',
            source_sha256=selection['source_sha256'],selection_sha256=hashlib.sha256(selection_path.read_bytes()).hexdigest(),
            cutoff=cfg['fixed_viable_sse_cutoff'],radius=cfg['physical_coverage_radius'],summary=summary,per_seed=by_seed,trajectories=series,
            limitations=['Not a replacement for original fit-matched width endpoint; no new significance tests.',
                        'Equal time and budget do not guarantee equal best-fit quality.',
                        'Candidate set is restricted to t0-preservable models and tied to control strata; not global model space.',
                        'Candidates and overlapping windows are dependent; pooled counts are descriptive.',
                        'No nearby viable output is not absence of attempts or permanent deletion.'])
(ROOT/'analysis/cofi_paired_coverage.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(dict(summary=summary,per_seed=by_seed),indent=2))
