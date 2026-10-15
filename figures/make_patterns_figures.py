"""Three manuscript figures from frozen records; no fitting or simulation.

PDF/PNG figures and an input-hash manifest are derived outputs only.
"""
from pathlib import Path
import hashlib
import json
import sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Patch
from matplotlib.colors import ListedColormap

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'paper_audit/figures'
HASHES = {}
COL = {'native':'#4C6478', 'open':'#16867A', 'decision':'#BC6A24',
       'full':'#8066AD', 'ink':'#243344', 'muted':'#637282', 'light':'#E8EDF1'}
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,
    'axes.spines.top':False,'axes.spines.right':False,'axes.labelcolor':COL['ink'],
    'text.color':COL['ink'],'axes.titleweight':'bold','pdf.fonttype':42,
    'savefig.facecolor':'white'})

def read(rel):
    p=ROOT/rel; raw=p.read_bytes(); HASHES[rel]=hashlib.sha256(raw).hexdigest()
    return json.loads(raw)

def save(fig,name):
    OUT.mkdir(exist_ok=True,parents=True)
    fig.savefig(OUT/(name+'.pdf'),bbox_inches='tight')
    fig.savefig(OUT/(name+'.png'),dpi=180,bbox_inches='tight')
    plt.close(fig)

def title(ax,text): ax.set_title(text,loc='left',fontsize=11,pad=12)
def box(ax,x,y,w,h,text,fill='#F2F5F7',edge='#CBD4DB',size=10):
    ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle='round,pad=0.012,rounding_size=0.02',
                              fc=fill,ec=edge,lw=1))
    ax.text(x+w/2,y+h/2,text,ha='center',va='center',fontsize=size)
def arrow(ax,a,b,color='#637282'):
    ax.annotate('',xy=b,xytext=a,arrowprops={'arrowstyle':'->','color':color,'lw':1.4})

def fig3():
    records=[read(f'evidence_gated_eligibility/outputs/stage2_formal/seed_{s}.json') for s in range(201,241)]
    arrays={k:[] for k in ['native','open','decision','full']}; winners=[]
    # Use the unchanged prediction helper solely to evaluate final parameters.
    sys.path.insert(0,str(ROOT))
    from evidence_gated_eligibility.eval_grid import rmse_noiseless,assert_eval_disjoint_from_measurable
    assert_eval_disjoint_from_measurable()
    for d in records:
        a=d['arms']['native'];b=d['arms']['decision_only']
        assert a['sites']==b['sites'] and a['rounds']==b['rounds']
        assert a['final']['arm_theta']==b['final']['arm_theta']
        ws={h:a['rounds'][-1][h]['w_all'] for h in a['final']['arm_theta']}
        h=max(ws,key=ws.get); winners.append(h)
        arrays['open'].append(rmse_noiseless(h,a['final']['arm_theta'][h])[0])
        for short,long in [('native','native'),('decision','decision_only'),('full','full_evidence_gate')]:
            arrays[short].append(d['scores'][long]['rmse_eval_noiseless'])
    arrays={k:np.asarray(v) for k,v in arrays.items()}
    assert all(h=='hump' for h in winners)
    assert np.flatnonzero(abs(arrays['native']-arrays['open'])>1e-12).tolist()==[7,23,31]
    fig=plt.figure(figsize=(10,7.4));gs=fig.add_gridspec(2,3,height_ratios=[1.1,1],hspace=.65,wspace=.42)
    ax=fig.add_subplot(gs[0,:]);title(ax,'A   Fixed Native trajectories: all 40 seeds')
    x=np.arange(201,241)
    for seed in [208,224,232]:
        ax.axvspan(seed-.45,seed+.45,color='#F4EEE5',zorder=0)
        ax.text(seed,.98,str(seed),ha='center',fontsize=8)
    for key,lab,marker,off in [('native','Native: 37/40','o',-.18),('open','Open: 40/40','s',0),('decision','Decision-Only: 39/40','^',.18)]:
        ax.plot(x+off,arrays[key],color=COL[key],marker=marker,ms=3.8,lw=.8,alpha=.9,label=lab)
    ax.set(yscale='log',ylim=(.015,1.2),xlim=(200.3,240.7),xticks=np.arange(201,241,3),xlabel='Paired seed (201-240)',ylabel='Independent-grid RMSE (log scale)')
    ax.legend(loc='lower left',ncol=3,frameon=False,fontsize=8)
    ax.grid(axis='y',alpha=.15)
    ax=fig.add_subplot(gs[1,0]);title(ax,'B   Reopening is sufficient')
    for seed,style in [(224,'-'),(232,'--')]:
        i=seed-201;ys=[arrays[k][i] for k in ['native','open','decision']]
        ax.plot(range(3),ys,style,color=COL['ink'],marker='o',ms=5,label=f'Seed {seed}')
        for j,y in enumerate(ys):ax.text(j,y+(.025 if seed==224 else -.05),f'{y:.3f}',ha='center',fontsize=8)
    ax.set(xticks=range(3),xticklabels=['Native','Open','Decision'],xlim=(-.3,2.3),ylim=(-.03,.93),ylabel='Independent-grid RMSE')
    ax.legend(frameon=False,fontsize=8,loc='upper right')
    ax.text(.5,-.38,'Both seeds: quad → hump\nData, fits and scores unchanged',transform=ax.transAxes,ha='center',fontsize=8)
    ax=fig.add_subplot(gs[1,1]);title(ax,'C   Gate blocks correction')
    ys=[arrays[k][7] for k in ['native','open','decision']]
    ax.bar(range(3),ys,color=[COL[k] for k in ['native','open','decision']],width=.6)
    for j,y in enumerate(ys):ax.text(j,y+.02,f'{y:.3f}',ha='center',fontsize=8)
    ax.set(xticks=range(3),xticklabels=['Native','Open','Decision'],ylim=(0,1.02),ylabel='Independent-grid RMSE')
    ax.text(.5,.94,'Seed 208',transform=ax.transAxes,ha='center',fontsize=9)
    ax.text(.5,-.38,'hump: pruned at 4; excluded at 13\nFinal violation=False; exclusion=True',transform=ax.transAxes,ha='center',fontsize=8)
    ax=fig.add_subplot(gs[1,2]);title(ax,'D   Closed-loop comparison')
    ax.plot([.01,1],[.01,1],color='#AAB4BD',ls='--',lw=1)
    ax.scatter(arrays['native'],arrays['full'],c=COL['full'],s=25,alpha=.75,edgecolors='white',linewidths=.4)
    ax.set(xscale='log',yscale='log',xlim=(.018,1.05),ylim=(.018,1.05),xlabel='Native RMSE',ylabel='Full Gate RMSE')
    ax.text(.04,.96,'Same seeds; new trajectories\n8 better / 5 worse\n27 unchanged',transform=ax.transAxes,va='top',fontsize=8)
    ax.text(.5,-.38,'Full Gate: 40/40 true selections\nNot a fixed-trajectory intervention',transform=ax.transAxes,ha='center',fontsize=8)
    save(fig,'fig3_eligibility_consequences')

def event_rows(arm):
    out=[];retained=0
    for seed in range(1,21):
        rr=read(f'outputs/pilot_fi_anchor/seed_{seed:02}.json')['arms'][arm]['rounds']
        for h in ['affine','pow','expsat','quad']:
            ii=[i for i in range(1,len(rr)) if rr[i-1][h]['alive'] and not rr[i][h]['alive']]
            if not ii:retained+=1;continue
            row=rr[ii[0]];ex=[r['t'] for r in rr if r[h]['excluded']]
            out.append((row['t'],ex[0] if ex else 27,row[h]['violated'],seed,h))
    return out,retained

def fig2():
    fig=plt.figure(figsize=(10,7.6));gs=fig.add_gridspec(2,2,hspace=.68,wspace=.34)
    fig.text(.125,.99,'A   Eligibility loss precedes operational exclusion in both strategies',fontsize=11,fontweight='bold')
    for col,arm in enumerate(['native','neutral']):
        ax=fig.add_subplot(gs[0,col]);rows,retained=event_rows(arm)
        ax.set_title(arm.capitalize()+' | seeds 1-20',loc='left',fontsize=9,fontweight='normal',pad=12)
        # Deterministic small offsets separate ties without modifying source times.
        groups={}
        for x,y,v,seed,h in rows:groups.setdefault((x,y,v),[]).append((seed,h))
        for (x,y,v),members in groups.items():
            for i,_ in enumerate(members):
                dx=((i%5)-min(4,len(members)-1)/2)*.11
                dy=(i//5)*.13
                ax.scatter(x+dx,y+dy,color=COL['decision'] if v else COL['open'],s=22,
                           marker='^' if y==27 else 'o',alpha=.8,edgecolors='white',linewidths=.25)
        ax.plot([0,25],[0,25],ls='--',color='#AAB4BD',lw=1)
        ax.text(17,15,'Equal times',fontsize=8,rotation=35,color=COL['muted'])
        ax.axhline(26,color='#CCD3D9',lw=.8)
        ax.set(xlim=(0,26),ylim=(0,29),xticks=[0,5,10,15,20,25],yticks=[0,5,10,15,20,25,27],yticklabels=['0','5','10','15','20','25','>25'],xlabel='First eligibility loss (round)',ylabel='First operational exclusion (round)')
        nv=sum(not r[2] for r in rows);vi=len(rows)-nv;ce=sum(r[1]==27 for r in rows)
        ax.text(.97,.07,f'{len(rows)} early exits; {retained} never exited\nAt loss: {nv} below / {vi} above single threshold\n{ce} exclusion times right-censored',transform=ax.transAxes,ha='right',va='bottom',fontsize=8)
    fig.text(.5,.49,'At loss:  green = no single-round violation;  orange = violation without two-round exclusion.\nTriangles: no exclusion by round 25. Coincident observations are slightly offset.',ha='center',fontsize=8,color=COL['muted'])
    ax=fig.add_subplot(gs[1,0]);title(ax,'B   True-model trajectory | seed 20')
    d=read('outputs/pilot_opp_feedback_ablation_formal_v2/seed_20_paired.json')
    for arm,col,label in [('native',COL['native'],'Native'),('no_opp_fb',COL['open'],'No-Opp')]:
        rr=d['arms'][arm]['rounds'];ts=[r['t'] for r in rr]
        ax.plot(ts,[r['hump']['w_all'] for r in rr],color=col,lw=1.7,label=label)
    ax.axvline(3,color=COL['native'],ls='--',lw=1);ax.axvline(7,color=COL['decision'],ls=':',lw=1.3)
    ax.text(3.3,.85,'Native loses eligibility: 3',fontsize=8)
    ax.text(7.3,.70,'Operational exclusion: 7',fontsize=8,color=COL['decision'])
    ax.set(xlabel='Round',ylabel='hump full-pool weight',ylim=(-.04,1.06),xlim=(0,25))
    ax.legend(frameon=False,loc='lower right',fontsize=8)
    ax.text(.5,-.40,'Full-pool weight is not the pruning weight.\nPruning uses surviving-pool weight < 0.02.\nNo-Opp retains hump throughout.',transform=ax.transAxes,ha='center',fontsize=8)
    ax=fig.add_subplot(gs[1,1]);title(ax,'C   Paired ablation | seeds 1-20')
    mat=[];totals=[]
    for arm in ['native','no_opp_fb']:
        row=[];nfalse=0
        for seed in range(1,21):
            rr=read(f'outputs/pilot_opp_feedback_ablation_formal_v2/seed_{seed:02}_paired.json')['arms'][arm]['rounds']
            flags={}
            for h in ['hump','affine','pow','expsat','quad']:
                flags[h]=any(rr[i-1][h]['alive'] and not rr[i][h]['alive'] and not rr[i][h]['excluded'] for i in range(1,len(rr)))
            row.append(int(flags['hump']));nfalse+=sum(flags[h] for h in flags if h!='hump')
        mat.append(row);totals.append(nfalse)
    assert totals==[78,79] and list(map(sum,mat))==[2,1]
    ax.imshow(mat,aspect='auto',cmap=ListedColormap(['#E8EDF1',COL['native']]),vmin=0,vmax=1,extent=(.5,20.5,1.5,-.5))
    for r in range(2):
        for c in range(20):ax.text(c+1,r,str(mat[r][c]),ha='center',va='center',fontsize=7,color='white' if mat[r][c] else '#84919D')
    ax.set(xticks=range(1,21),yticks=[0,1],yticklabels=['Native','No-Opp'],xlabel='Paired seed');ax.tick_params(axis='x',labelsize=7)
    ax.text(.5,-.40,'True-model FI: 2/20 vs 1/20 (1 = event)\nAlternative-model FI events: 78 vs 79\nNo evidence of a general risk increase',transform=ax.transAxes,ha='center',fontsize=8)
    save(fig,'fig2_anchor_eligibility')

def fig1():
    fig,axs=plt.subplots(3,1,figsize=(10,7.5),gridspec_kw={'height_ratios':[1.2,.85,1.2]})
    fig.subplots_adjust(hspace=.42)
    for ax in axs:ax.set(xlim=(0,1),ylim=(-.04,1));ax.axis('off')
    ax=axs[0];title(ax,'A   The same retained candidate can have different evidential status')
    box(ax,.02,.30,.19,.35,'Initially eligible\nA and B')
    box(ax,.35,.59,.29,.30,'Evidence excludes B',fill='#E4F1ED')
    box(ax,.35,.08,.29,.30,'Algorithm removes B\nEvidence has not excluded B',fill='#FCF0E2')
    box(ax,.77,.59,.21,.30,'Eligible: A\nNot excluded: A',fill='#E4F1ED')
    box(ax,.77,.08,.21,.30,'Eligible: A\nNot excluded: A, B',fill='#FCF0E2')
    arrow(ax,(.22,.53),(.34,.74));arrow(ax,(.22,.43),(.34,.23));arrow(ax,(.66,.74),(.75,.74));arrow(ax,(.66,.23),(.75,.23))
    ax.text(.77,0,'Operational FI for B',fontsize=9,color=COL['decision'])
    ax=axs[1];title(ax,'B   One possible feedback pathway - not a necessary cause of FI')
    box(ax,.03,.35,.24,.42,'Current candidate state')
    box(ax,.38,.35,.24,.42,'Next research opportunities')
    box(ax,.73,.35,.24,.42,'Updated candidate state')
    arrow(ax,(.28,.56),(.36,.56));arrow(ax,(.63,.56),(.71,.56))
    ax.plot([.85,.85,.15],[.32,.19,.19],color=COL['muted'],lw=1.3)
    arrow(ax,(.15,.19),(.15,.32))
    ax.text(.5,.01,'Local amplification does not guarantee candidate withdrawal',ha='center',fontsize=9)
    ax=axs[2];title(ax,'C   AEA: state audit → event history → optional consequence test')
    box(ax,.02,.45,.22,.38,'Define audit set\nand eligibility function')
    box(ax,.34,.45,.29,.38,'Compare eligibility with\ncontemporaneous evidence\nReport rule reliability',size=9)
    box(ax,.74,.45,.24,.38,'If history is available:\nverify the exit event',size=9)
    arrow(ax,(.25,.64),(.32,.64));arrow(ax,(.65,.64),(.72,.64))
    box(ax,.34,.00,.29,.27,'Insufficient information:\nNOT_DETERMINABLE',fill='#FCF0E2',size=9)
    arrow(ax,(.485,.43),(.485,.30))
    box(ax,.74,.00,.24,.27,'If fits and scores exist:\nfixed-data eligibility test',fill='#E4F1ED',size=9)
    arrow(ax,(.86,.43),(.86,.30))
    ax.text(.02,.09,'No automatic claim of\nerror or unique truth',fontsize=9,color=COL['muted'])
    save(fig,'fig1_audit_framework')

if __name__=='__main__':
    if '--fig2-only' in sys.argv:
        fig2()
    else:
        fig3();fig2();fig1()
    HASHES['paper_audit/make_patterns_figures.py']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    manifest='fig2_revision_inputs.json' if '--fig2-only' in sys.argv else 'patterns_figure_inputs.json'
    (OUT/manifest).write_text(json.dumps({'scope':'Frozen-record plotting only; no new experiments','sha256':HASHES},indent=2),encoding='utf-8')
    print('Requested figures generated; all source-count assertions passed.')
