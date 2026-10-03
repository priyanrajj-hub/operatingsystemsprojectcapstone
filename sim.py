import numpy as np, json, time, csv
from scipy import stats
NP_,NE_=4,4; N=12; T=300; STEADY=200
DYN=(1.0,0.30); IDLE=(0.10,0.03)
TYPES=['cpu']*4+['mem']*3+['io']*3+['burst']*2
TI={t:np.array([x==t for x in TYPES]) for t in set(TYPES)}
POL=['Always-P','Always-E','Random','Static-Label','Best-Static','Heuristic','LinUCB-Orig','LinUCB-Perf','LinUCB-Perf+IPC']
def workload(seed):
    r=np.random.default_rng(1000+seed); D=np.zeros((T,N)); S=np.zeros((T,N)); I=np.zeros((T,N))
    for i,ty in enumerate(TYPES):
        if ty=='cpu': D[:,i]=1.0;S[:,i]=0.55;I[:,i]=1.0
        elif ty=='mem': D[:,i]=0.8;S[:,i]=0.90;I[:,i]=0.3
        elif ty=='io': D[:,i]=0.1;S[:,i]=0.90;I[:,i]=0.6
        else:
            t=0;act=bool(r.integers(2))
            while t<T:
                du=int(r.uniform(20,40)); D[t:t+du,i]=0.95 if act else 0.1
                S[t:t+du,i]=0.55 if act else 0.90; I[t:t+du,i]=1.0 if act else 0.6
                t+=du; act=not act
    nz=r.lognormal(0,0.2,(T,N,3)); lz=r.lognormal(0,0.3,(T,N))
    return D,S,I,nz,lz
def outcome(g,d,sE):
    share=np.zeros(N); rho=np.zeros(2); ov=np.zeros(2)
    for k,n in ((0,NP_),(1,NE_)):
        m=g==k; Dg=d[m].sum(); rho[k]=Dg/n
        if Dg>0: share[m]=d[m]*min(1.0,n/Dg); ov[k]=max(0,1-n/Dg)
    sp=np.where(g==0,1.0,sE); prog=share*sp
    bp=min(NP_,d[g==0].sum()); be=min(NE_,d[g==1].sum())
    pw=NP_*IDLE[0]+NE_*IDLE[1]+DYN[0]*bp+DYN[1]*be
    return share,sp,prog,pw,rho,ov
class LinUCB:
    def __init__(s,d,alpha,rng): s.Ai=np.stack([np.eye(d)]*2); s.b=np.zeros((2,d)); s.al=alpha; s.r=rng
    def select(s,x):
        sc=[(s.Ai[a]@s.b[a])@x+s.al*np.sqrt(max(x@s.Ai[a]@x,0)) for a in (0,1)]
        if abs(sc[0]-sc[1])<1e-12: return int(s.r.integers(2))
        return int(np.argmax(sc))
    def update(s,a,x,r):
        Ax=s.Ai[a]@x; s.Ai[a]-=np.outer(Ax,Ax)/(1+x@Ax); s.b[a]+=r*x
def run(pol,seed,lam=0.5,alpha=0.5):
    D,S,I,nz,lz=workload(seed); rp=np.random.default_rng(5000+seed)
    use_ipc=pol.endswith('IPC'); bandit=pol.startswith('LinUCB')
    B=LinUCB(6 if use_ipc else 5,alpha,rp) if bandit else None
    g=np.zeros(N,int) if pol=='Always-P' else np.ones(N,int) if pol=='Always-E' else rp.integers(0,2,N)
    if pol=='Static-Label': g=np.where(TI['io'],1,0)
    if pol=='Best-Static':
        best=-1e9; idx={t:np.where(TI[t])[0] for t in TI}
        import itertools
        for kc,km,ki,b0,b1 in itertools.product(range(5),range(4),range(4),(0,1),(0,1)):
            gg=np.ones(N,int); gg[idx['cpu'][:kc]]=0; gg[idx['mem'][:km]]=0; gg[idx['io'][:ki]]=0; gg[idx['burst'][0]]=b0; gg[idx['burst'][1]]=b1; J=0
            for tt in range(10,T,30):
                sh,sp_,pr,_,_,_=outcome(gg,D[tt],S[tt]);J+=(pr/D[tt]).sum()-lam*(sh*np.where(gg==0,DYN[0],DYN[1])).sum()
            if J>best: best=J;g=gg.copy()
    prog_s=np.zeros(N);d_s=np.zeros(N);pw=[];inv=[];lat=[];mig=0
    fc=np.zeros(T);fm=np.zeros(T);ps=0;ds=0;pws=0;prev_x=None
    for t in range(T):
        d=D[t];share,sp,prog,p,rho,ov=outcome(g,d,S[t])
        cpu=np.clip(share*nz[t,:,0],0,1); vol=(10+300*(1-d))*nz[t,:,1]; iv=(2*d+150*share*ov[g])*nz[t,:,2]
        prog_s+=prog;d_s+=d;pw.append(p);inv.append(iv.mean())
        lat+=list(((1/sp)/(1-0.9*np.minimum(rho[g],1))*lz[t])[TI['io']])
        fc[t]=(g[TI['cpu']]==0).mean(); fm[t]=(g[TI['mem']]==1).mean()
        if t>=STEADY: ps+=prog.sum();ds+=d.sum();pws+=p
        x=np.stack([np.ones(N),cpu,vol/300,np.minimum(iv/100,3),g.astype(float)]+([I[t]] if use_ipc else []),1)
        if bandit and prev_x is not None:
            if pol=='LinUCB-Orig': R=-(0.7*np.minimum(iv/100,3)+0.3*np.where(g==0,1.0,0.3))
            else: R=np.clip(prog/d*nz[t,:,0],0,1.2)-lam*cpu*np.where(g==0,DYN[0],DYN[1])
            for i in range(N): B.update(g[i],prev_x[i],R[i])
        if bandit: gn=np.array([B.select(x[i]) for i in range(N)])
        elif pol=='Random': gn=rp.integers(0,2,N) if t%10==9 else g
        elif pol=='Heuristic': gn=np.where(cpu>0.2,0,1)
        else: gn=g
        mig+=(gn!=g).sum(); prev_x=x; g=gn
    sat=prog_s/d_s
    return dict(thr=prog_s.sum()/d_s.sum(),pwr=float(np.mean(pw)),eff=prog_s.sum()/T/np.mean(pw),lat95=float(np.percentile(lat,95)),
        jain=float(sat.sum()**2/(N*(sat**2).sum())),mig=mig/(N*T/60),inv=float(np.mean(inv)),
        thr_s=ps/ds,pwr_s=pws/(T-STEADY),eff_s=ps/(T-STEADY)/(pws/(T-STEADY)),fc=fc,fm=fm)
M=['thr','pwr','eff','lat95','jain','mig','inv','thr_s','pwr_s','eff_s']
SE=30; res={p:[run(p,s) for s in range(SE)] for p in POL}
out={'summary':{},'ts':{},'stats':{},'sweep':{}}
for p in POL:
    out['summary'][p]={}
    for m in M:
        v=np.array([r[m] for r in res[p]]); ci=stats.t.ppf(.975,SE-1)*v.std(ddof=1)/np.sqrt(SE)
        out['summary'][p][m]=[float(v.mean()),float(v.std(ddof=1)),float(ci)]
    out['ts'][p]={k:[np.mean([r[k] for r in res[p]],0).tolist(),np.std([r[k] for r in res[p]],0).tolist()] for k in ('fc','fm')}
pairs=[('LinUCB-Perf+IPC','Best-Static'),('LinUCB-Perf+IPC','Heuristic'),('LinUCB-Perf+IPC','Random'),('LinUCB-Perf','LinUCB-Orig'),('LinUCB-Perf+IPC','LinUCB-Perf')]
for m in ('thr','pwr','eff','lat95'):
    ps=[];rows=[]
    for a,b in pairs:
        x=np.array([r[m] for r in res[a]]);y=np.array([r[m] for r in res[b]]);df=x-y
        try: pv=stats.wilcoxon(x,y).pvalue
        except Exception: pv=1.0
        rows.append([a,b,float(df.mean()),float(df.mean()/df.std(ddof=1)) if df.std()>0 else 0.0,float(pv)]);ps.append(pv)
    o=np.argsort(ps);adj=[0]*len(ps);run_max=0
    for k,ix in enumerate(o): run_max=max(run_max,min(1,(len(ps)-k)*ps[ix]));adj[ix]=run_max
    for r,a in zip(rows,adj): r.append(float(a))
    out['stats'][m]=rows
SW=15
out['sweep']['lam']={str(l):[float(np.mean([run('LinUCB-Perf+IPC',s,lam=l)[k] for s in range(SW)])) for k in ('thr','pwr','eff')] for l in (0.1,0.3,0.5,0.8,1.2)}
out['sweep']['alpha']={str(a):[float(np.mean([run('LinUCB-Perf+IPC',s,alpha=a)[k] for s in range(SW)])) for k in ('thr','pwr','eff')] for a in (0.05,0.2,0.5,1.0,2.0)}
r=np.random.default_rng(0);d=6;A=np.eye(d)+0.1;x=r.random(d);Ai=np.linalg.inv(A);n=20000
t0=time.perf_counter()
for _ in range(n): Ax=Ai@x;Ai=Ai-np.outer(Ax,Ax)/(1+x@Ax)
t1=time.perf_counter()
for _ in range(n): A=A+np.outer(x,x);np.linalg.inv(A)
t2=time.perf_counter()
out['bench']={'sm_us':(t1-t0)/n*1e6,'inv_us':(t2-t1)/n*1e6}
json.dump(out,open('results.json','w'))
with open('raw_per_seed.csv','w',newline='') as f:
    w=csv.writer(f);w.writerow(['policy','seed']+M)
    for p in POL:
        for s,rr in enumerate(res[p]): w.writerow([p,s]+[round(rr[m],5) for m in M])
for p in POL: print(p.ljust(16),' '.join(f"{m}={out['summary'][p][m][0]:.3f}" for m in ('thr','pwr','eff','lat95','jain','mig','inv','eff_s')))
for m in ('eff','thr','pwr','lat95'):
    for r_ in out['stats'][m]: print(m,r_[0][:14],'vs',r_[1][:14],f"d={r_[2]:+.3f} dz={r_[3]:+.2f} padj={r_[5]:.4f}")
print(out['sweep']);print(out['bench'])
