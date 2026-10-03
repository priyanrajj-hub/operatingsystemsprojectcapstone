import json,numpy as np
src=open('sim.py').read(); head=src[:src.index("M=['thr'")]
for a,b in [("fm[t]=(g[TI['mem']]==1).mean()","fm[t]=(g[TI['mem']]==1).mean(); PT+=(g==0)"),("fc=np.zeros(T);fm=np.zeros(T);","fc=np.zeros(T);fm=np.zeros(T);PT=np.zeros(N);"),("return dict(thr=","return dict(B=B,pt=PT/T,thr=")]:
    assert a in head; head=head.replace(a,b)
exec(head)
place={}
for p in POL:
    acc={t:[] for t in ['cpu','mem','io','burst']}
    for s in range(10):
        r=run(p,s)
        for t in acc: acc[t].append(r['pt'][TI[t]].mean())
    place[p]={t:float(np.mean(v)) for t,v in acc.items()}
B=run('LinUCB-Perf+IPC',0)['B']; th=[(B.Ai[a]@B.b[a]).tolist() for a in (0,1)]
json.dump({'place':place,'theta':th},open('extra.json','w'))
for p in POL: print(p.ljust(16),{k:round(v,2) for k,v in place[p].items()})
print([round(x,3) for x in th[0]],[round(x,3) for x in th[1]])
