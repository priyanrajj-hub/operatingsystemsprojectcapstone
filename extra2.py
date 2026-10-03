import json,numpy as np
src=open('sim.py').read(); head=src[:src.index("M=['thr'")]
for a,b in [("prog_s=np.zeros(N);d_s=np.zeros(N);","TR=[];prog_s=np.zeros(N);d_s=np.zeros(N);"),("prog_s+=prog;d_s+=d;","prog_s+=prog;d_s+=d;TR.append(prog.sum()/d.sum());"),("return dict(thr=","return dict(tr=TR,thr=")]:
    assert a in head; head=head.replace(a,b)
exec(head)
TRS={p:np.array([run(p,s)['tr'] for s in range(20)]) for p in POL}
out={'tr':{p:TRS[p].mean(0).tolist() for p in POL},'gap':{p:np.cumsum(TRS['Best-Static']-TRS[p],1).mean(0).tolist() for p in POL}}
json.dump(out,open('extra2.json','w'));print('ok')
