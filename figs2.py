import json,csv,numpy as np,matplotlib
matplotlib.use('Agg');import matplotlib.pyplot as plt
plt.rcParams.update({'font.family':'serif','font.serif':['Times New Roman','DejaVu Serif'],'font.size':9,'axes.grid':True,'grid.alpha':.3,'figure.dpi':200})
R=json.load(open('results.json'));E=json.load(open('extra.json'));S=R['summary']
POL=['Always-P','Always-E','Random','Static-Label','Best-Static','Heuristic','LinUCB-Orig','LinUCB-Perf','LinUCB-Perf+IPC']
COL=['#d9d9d9','#bdbdbd','#a6a6a6','#8c8c8c','#6e6e6e','#525252','#c6dbef','#6baed6','#08519c']
# concept table
f,ax=plt.subplots(figsize=(6.8,2.5));ax.axis('off')
cells=[['Supervised learning','Contextual bandit (this work)','Full reinforcement learning'],['Labelled "best core" per process','Reward of the chosen action only','Delayed return over state sequences'],['No ground-truth labels exist','Immediate reward r = s \u2212 \u03bbe','Needs a state-transition model / many samples'],['Offline training, fixed model','Online, O(d\u00b2) update per decision','Neural-network training and inference'],['Cannot adapt to phase changes','Adapts as rewards drift','Adapts, but slowly and at higher cost']]
t=ax.table(cellText=cells[1:],colLabels=cells[0],loc='center',cellLoc='center');t.auto_set_font_size(False);t.set_fontsize(7.6);t.scale(1,2.1)
for (r,c),cell in t.get_celld().items():
    cell.set_edgecolor('#555');
    if r==0: cell.set_facecolor('#d0d0d0');cell.set_text_props(weight='bold')
    elif c==1: cell.set_facecolor('#deebf7')
f.savefig('fig8_concept.png',bbox_inches='tight');plt.close()
# LinUCB geometry (synthetic)
rng=np.random.default_rng(3);xs=np.linspace(0,1,100);f,axs=plt.subplots(1,2,figsize=(6.8,2.7),sharey=True)
def fit(n,tr):
    x=rng.random(n);X=np.c_[np.ones(n),x];y=tr(x)+rng.normal(0,.08,n);A=np.eye(2)+X.T@X;Ai=np.linalg.inv(A);th=Ai@X.T@y;return th,Ai,x,y
for ax,n in zip(axs,(5,60)):
    for tr,c,l in ((lambda x:.30+.30*x,'#08519c','Arm P'),(lambda x:.55-.10*x,'#d95f02','Arm E')):
        th,Ai,x,y=fit(n,tr);Z=np.c_[np.ones(100),xs];m=Z@th;b=1.0*np.sqrt(np.einsum('ij,jk,ik->i',Z,Ai,Z))
        ax.plot(xs,m,c=c,label=l);ax.fill_between(xs,m,m+b,color=c,alpha=.18);ax.scatter(x,y,s=9,c=c,alpha=.6)
    ax.set_xlabel('CPU share c');ax.set_title('(a) 5 samples per arm' if n==5 else '(b) 60 samples per arm',fontsize=8.5)
axs[0].set_ylabel('Predicted reward (line) and UCB (band top)');axs[0].legend(fontsize=7);f.tight_layout();f.savefig('fig9_geom.png');plt.close()
# reward landscape
lam=.5;T=[('CPU-bound',1.0,.55),('Memory-bound',.8,.9),('I/O-bound',.1,.9),('Bursty (active)',.95,.55)]
rp=[1-lam*d*1.0 for _,d,_ in T];re=[s-lam*d*.3 for _,d,s in T]
f,axs=plt.subplots(1,2,figsize=(6.8,2.6));w=.36;xx=np.arange(4)
axs[0].bar(xx-w/2,rp,w,color='#08519c',ec='k',lw=.6,label='P-group');axs[0].bar(xx+w/2,re,w,color='#d9d9d9',ec='k',lw=.6,hatch='//',label='E-group')
axs[1].bar(xx-w/2,[-(0.7*.02+.3*1.0)]*4,w,color='#08519c',ec='k',lw=.6);axs[1].bar(xx+w/2,[-(0.7*.02+.3*.3)]*4,w,color='#d9d9d9',ec='k',lw=.6,hatch='//')
for ax,ti in zip(axs,('(a) Proposed reward r = s \u2212 \u03bbe','(b) Original reward (no contention)')):
    ax.set_xticks(xx);ax.set_xticklabels([t[0] for t in T],fontsize=6.8,rotation=15);ax.set_title(ti,fontsize=8.5);ax.set_ylabel('Expected reward')
axs[0].legend(fontsize=7,loc='lower left');f.tight_layout();f.savefig('fig10_landscape.png');plt.close()
# boxplots
rows=list(csv.DictReader(open('raw_per_seed.csv')));f,axs=plt.subplots(1,2,figsize=(6.8,3.2))
for ax,m,yl in zip(axs,('thr','eff'),('Normalised throughput','Efficiency (work / power)')):
    d=[[float(r[m]) for r in rows if r['policy']==p] for p in POL];bp=ax.boxplot(d,patch_artist=True,widths=.6,medianprops=dict(color='k'),flierprops=dict(markersize=2))
    for b,c in zip(bp['boxes'],COL): b.set_facecolor(c)
    ax.set_xticks(range(1,10));ax.set_xticklabels(POL,rotation=45,ha='right',fontsize=6.3);ax.set_ylabel(yl)
f.tight_layout();f.savefig('fig11_box.png');plt.close()
# multi-metric heatmap
Mt=[('thr','Throughput',1),('eff','Efficiency',1),('pwr','Power',-1),('lat95','p95 latency',-1),('jain','Fairness',1),('mig','Migrations',-1),('inv','Invol. ctx/s',-1)]
V=np.array([[S[p][m][0] for m,_,_ in Mt] for p in POL]);Z=np.zeros_like(V)
for j,(m,_,sg) in enumerate(Mt):
    c=V[:,j]*sg;Z[:,j]=(c-c.min())/(c.max()-c.min()+1e-12)
f,ax=plt.subplots(figsize=(6.6,3.4));ax.imshow(Z,cmap='Blues',vmin=0,vmax=1.15,aspect='auto');ax.grid(False)
ax.set_xticks(range(len(Mt)));ax.set_xticklabels([n for _,n,_ in Mt],fontsize=7.5);ax.set_yticks(range(9));ax.set_yticklabels(POL,fontsize=7.5)
for i in range(9):
    for j in range(len(Mt)): ax.text(j,i,f'{V[i,j]:.2f}' if Mt[j][0]!='mig' else f'{V[i,j]:.1f}',ha='center',va='center',fontsize=7,color='w' if Z[i,j]>.6 else 'k')
f.tight_layout();f.savefig('fig12_heat.png');plt.close()
# placement heatmap
ty=['cpu','mem','io','burst'];V=np.array([[E['place'][p][t] for t in ty] for p in POL])
f,ax=plt.subplots(figsize=(5.2,3.3));im=ax.imshow(V,cmap='Greys',vmin=0,vmax=1,aspect='auto');ax.grid(False)
ax.set_xticks(range(4));ax.set_xticklabels(['CPU-bound','Memory-bound','I/O-bound','Bursty']);ax.set_yticks(range(9));ax.set_yticklabels(POL,fontsize=7.5)
for i in range(9):
    for j in range(4): ax.text(j,i,f'{V[i,j]:.2f}',ha='center',va='center',fontsize=7.5,color='w' if V[i,j]>.55 else 'k')
cb=f.colorbar(im,ax=ax,fraction=.04);cb.set_label('Fraction of time on P-group',fontsize=7.5);f.tight_layout();f.savefig('fig13_place.png');plt.close()
# theta
fn=['bias','CPU share','voluntary','involuntary','group','IPC'];th=np.array(E['theta']);f,ax=plt.subplots(figsize=(5.6,2.7));x=np.arange(6)
ax.bar(x-.18,th[0],.36,color='#08519c',ec='k',lw=.6,label='\u03b8 (P arm)');ax.bar(x+.18,th[1],.36,color='#d9d9d9',ec='k',lw=.6,hatch='//',label='\u03b8 (E arm)')
ax.set_xticks(x);ax.set_xticklabels(fn,fontsize=7.5);ax.set_ylabel('Learned weight');ax.legend(fontsize=7);ax.axhline(0,c='k',lw=.6);f.tight_layout();f.savefig('fig14_theta.png');plt.close()
# steady vs overall
f,axs=plt.subplots(1,2,figsize=(6.8,3.0));xx=np.arange(9)
for ax,(a,b),yl in zip(axs,(('thr','thr_s'),('eff','eff_s')),('Normalised throughput','Efficiency')):
    ax.bar(xx-.2,[S[p][a][0] for p in POL],.4,color='#bdbdbd',ec='k',lw=.5,label='All 300 cycles');ax.bar(xx+.2,[S[p][b][0] for p in POL],.4,color='#08519c',ec='k',lw=.5,label='Cycles 200\u2013300')
    ax.set_xticks(xx);ax.set_xticklabels(POL,rotation=45,ha='right',fontsize=6.3);ax.set_ylabel(yl)
axs[0].legend(fontsize=6.8);f.tight_layout();f.savefig('fig15_steady.png');plt.close()
print('ok')
