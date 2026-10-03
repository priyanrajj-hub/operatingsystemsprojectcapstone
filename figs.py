import json, numpy as np, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
plt.rcParams.update({'font.family':'serif','font.serif':['Times New Roman','DejaVu Serif'],'font.size':9,'axes.grid':True,'grid.alpha':.3,'figure.dpi':200})
R=json.load(open('results.json')); S=R['summary']
POL=['Always-P','Always-E','Random','Static-Label','Best-Static','Heuristic','LinUCB-Orig','LinUCB-Perf','LinUCB-Perf+IPC']
SH=['Always-P','Always-E','Random','Static-\nLabel','Best-\nStatic','Heuristic','LinUCB-\nOrig','LinUCB-\nPerf','LinUCB-\nPerf+IPC']
COL=['#d9d9d9','#bdbdbd','#a6a6a6','#8c8c8c','#6e6e6e','#525252','#c6dbef','#6baed6','#08519c']
HAT=['','','','','','','//','xx','']
def box(ax,x,y,w,h,t,fc='#f2f2f2',fs=6.8):
    ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle='round,pad=0.02,rounding_size=0.08',fc=fc,ec='k',lw=.9))
    ax.text(x+w/2,y+h/2,t,ha='center',va='center',fontsize=fs)
def arr(ax,a,b,t=None,rad=0):
    ax.add_patch(FancyArrowPatch(a,b,arrowstyle='-|>',mutation_scale=10,lw=.9,color='k',connectionstyle=f'arc3,rad={rad}'))
    if t: ax.text((a[0]+b[0])/2,(a[1]+b[1])/2+.12,t,fontsize=7,ha='center',style='italic')
# Fig1 architecture
f,ax=plt.subplots(figsize=(6.8,3.6));ax.axis('off');ax.set_xlim(0,13);ax.set_ylim(0,6.3)
box(ax,.3,3.6,3.2,1.3,'Context builder\nx = [1, cpu, vol, invol,\ngroup, (ipc)]',fc='#deebf7')
box(ax,4.9,3.6,3.6,1.3,'LinUCB policy (shared)\n2 arms: P-group / E-group\nSherman\u2013Morrison update',fc='#9ecae1')
box(ax,9.9,3.6,2.8,1.3,'Actuator\nsched_setaffinity()\n(user space, no root)',fc='#deebf7')
box(ax,4.9,5.4,3.6,.8,'Dashboard (FastAPI + WebSocket)',fc='#efedf5')
box(ax,.3,.4,3.2,1.6,'Telemetry\n(psutil, /proc)\nCPU share, ctx-switch\nrates, [IPC]')
box(ax,4.9,.4,7.8,1.6,'Heterogeneous cores running the workload\nP-group (fast, high power)   |   E-group (slower, low power)\nprocesses: CPU-bound, memory-bound, I/O-bound, bursty',fc='#e5f5e0')
box(ax,5.6,2.25,2.2,.8,'Reward  r = s \u2212 \u03bbe',fc='#fdd0a2')
arr(ax,(3.5,4.25),(4.9,4.25));arr(ax,(8.5,4.25),(9.9,4.25),'arm a');arr(ax,(11.3,3.6),(11.3,2.0),'affinity mask')
arr(ax,(4.9,1.2),(3.5,1.2),'');ax.text(4.2,1.4,'measure',fontsize=7,ha='center',style='italic')
arr(ax,(1.9,2.0),(1.9,3.6),'');ax.text(2.0,2.8,'features',fontsize=7,style='italic')
arr(ax,(3.5,1.9),(5.6,2.5));arr(ax,(6.7,3.05),(6.7,3.6));ax.text(6.8,3.25,'update',fontsize=7,style='italic')
arr(ax,(6.7,4.9),(6.7,5.4))
f.savefig('fig1_arch.png',bbox_inches='tight');plt.close()
# Fig2 flowchart
f,ax=plt.subplots(figsize=(4.2,6.0));ax.axis('off');ax.set_xlim(0,6);ax.set_ylim(0,12.4)
st=['Start scheduling cycle (\u0394t = 1 s)','Read per-process telemetry\n(CPU share, ctx switches, IPC)','Build context vector x\u209c','Reward of previous action\nr = s \u2212 \u03bb\u00b7e  (measured)','Update arm: A\u207b\u00b9 \u2190 SM(A\u207b\u00b9, x),  b \u2190 b + r\u00b7x','Score arms \u03b8\u1d43\u1d40x + \u03b1\u221a(x\u1d40A\u207b\u00b9x)\nSelect a\u209c = argmax score','Apply cpu_affinity(mask)\nonly if the arm changed','Log decision, push to dashboard','Sleep until next cycle']
ys=[11.4-1.3*k for k in range(9)]
for t,y in zip(st,ys): box(ax,.9,y,4.6,.85,t,fc='#deebf7' if t.startswith(('Reward','Update')) else '#f2f2f2',fs=7.5)
for k in range(8): arr(ax,(3.2,ys[k]),(3.2,ys[k+1]+.85))
ax.plot([.9,.35,.35],[ys[-1]+.42,ys[-1]+.42,ys[0]+.42],'k',lw=.9);arr(ax,(.35,ys[0]+.42),(.9,ys[0]+.42))
ax.text(.2,6,'repeat',rotation=90,fontsize=7,va='center',style='italic')
f.savefig('fig2_flow.png',bbox_inches='tight');plt.close()
# Fig3 learning dynamics
f,axs=plt.subplots(1,2,figsize=(6.8,2.7),sharex=True)
for ax,k,ti in zip(axs,('fc','fm'),('(a) CPU-bound processes on P-group','(b) Memory-bound processes on E-group')):
    for p,c,ls in (('LinUCB-Orig','#d95f02','--'),('LinUCB-Perf','#6baed6','-.'),('LinUCB-Perf+IPC','#08519c','-')):
        m,s=np.array(R['ts'][p][k][0]),np.array(R['ts'][p][k][1]);ax.plot(m,c=c,ls=ls,lw=1.4,label=p);ax.fill_between(range(len(m)),m-s,m+s,color=c,alpha=.12)
    ax.set_title(ti,fontsize=8.5);ax.set_xlabel('Scheduling cycle (1 s)');ax.set_ylim(-.02,1.05)
axs[0].set_ylabel('Fraction of processes');axs[0].legend(fontsize=7,loc='lower right');f.tight_layout();f.savefig('fig3_learning.png');plt.close()
# bars helper
def bars(ax,m,yl,ti,idx=None):
    v=[S[p][m][0] for p in POL];e=[S[p][m][2] for p in POL]
    for i,(a,b,c,h) in enumerate(zip(v,e,COL,HAT)): ax.bar(i,a,yerr=b,color=c,hatch=h,ec='k',lw=.6,capsize=2)
    ax.set_xticks(range(9));ax.set_xticklabels(POL,fontsize=6.3,rotation=45,ha='right');ax.set_ylabel(yl);ax.set_title(ti,fontsize=8.5);ax.grid(axis='x',alpha=0)
f,axs=plt.subplots(1,2,figsize=(6.8,3.3));bars(axs[0],'thr','Normalised throughput','(a) Throughput');bars(axs[1],'pwr','Average power (relative units)','(b) Power');f.tight_layout();f.savefig('fig4_thr_pwr.png');plt.close()
f,axs=plt.subplots(1,3,figsize=(7.2,3.3));bars(axs[0],'lat95','p95 latency (ms)','(a) Interactive tail latency');bars(axs[1],'jain',"Jain's index",'(b) Fairness');bars(axs[2],'mig','Migrations / proc / min','(c) Migration rate');axs[1].set_ylim(.9,1.005);f.tight_layout();f.savefig('fig5_lat_fair_mig.png');plt.close()
OFF={'Always-P':(4,-9),'Always-E':(5,-3),'Random':(-40,-12),'Static-Label':(-30,-11),'Best-Static':(-60,4),'Heuristic':(6,2),'LinUCB-Orig':(5,-10),'LinUCB-Perf':(8,-4),'LinUCB-Perf+IPC':(-82,3)}
f,ax=plt.subplots(figsize=(4.8,3.4))
for i,p in enumerate(POL):
    ax.errorbar(S[p]['pwr'][0],S[p]['thr'][0],xerr=S[p]['pwr'][2],yerr=S[p]['thr'][2],fmt='o' if i<6 else 's',color=COL[i] if i<6 else COL[i],mec='k',ms=6,capsize=2,lw=.8)
    ax.annotate(p,(S[p]['pwr'][0],S[p]['thr'][0]),textcoords='offset points',xytext=OFF[p],fontsize=6.5)
ax.set_xlabel('Average power (relative units)');ax.set_ylabel('Normalised throughput');ax.set_xlim(1.3,6);f.tight_layout();f.savefig('fig6_pareto.png');plt.close()
f,axs=plt.subplots(1,2,figsize=(6.6,2.6))
for ax,key,xl in zip(axs,('lam','alpha'),('Energy weight \u03bb','Exploration coefficient \u03b1')):
    ks=list(R['sweep'][key].keys());xs=[float(k) for k in ks];th=[R['sweep'][key][k][0] for k in ks];pw=[R['sweep'][key][k][1] for k in ks]
    ax.plot(xs,th,'o-',c='#08519c',label='Throughput');ax.set_xlabel(xl);ax.set_ylabel('Normalised throughput',color='#08519c')
    a2=ax.twinx();a2.plot(xs,pw,'s--',c='#d95f02',label='Power');a2.set_ylabel('Power (relative)',color='#d95f02');a2.grid(False)
    if key=='alpha': ax.set_xscale('log')
axs[0].set_title('(a) Sensitivity to \u03bb',fontsize=8.5);axs[1].set_title('(b) Sensitivity to \u03b1',fontsize=8.5);f.tight_layout();f.savefig('fig7_sweep.png');plt.close()
print('figs ok')
