import json,numpy as np,matplotlib
matplotlib.use('Agg');import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch,FancyArrowPatch,Circle
plt.rcParams.update({'font.family':'serif','font.serif':['Times New Roman','DejaVu Serif'],'font.size':9,'axes.grid':True,'grid.alpha':.3,'figure.dpi':200})
R=json.load(open('results.json'));S=R['summary'];E2=json.load(open('extra2.json'))
def box(ax,x,y,w,h,t,fc='#f2f2f2',fs=6.8):
    ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle='round,pad=0.02,rounding_size=0.12',fc=fc,ec='k',lw=.9));ax.text(x+w/2,y+h/2,t,ha='center',va='center',fontsize=fs)
def arr(ax,a,b,rad=0,col='k'):ax.add_patch(FancyArrowPatch(a,b,arrowstyle='-|>',mutation_scale=9,lw=.9,color=col,connectionstyle=f'arc3,rad={rad}'))
# pipeline
f,ax=plt.subplots(figsize=(7.2,3.7));ax.axis('off');ax.set_xlim(0,16);ax.set_ylim(0,8)
A=['1  Telemetry\npsutil, /proc','2  Features\nscale, clip,\nadd bias','3  Model\n\u03b8\u2090 = A\u2090\u207b\u00b9 b\u2090\n(one per arm)','4  UCB score\nmean + bonus','5  Action\nargmax, then\nset CPU affinity','6  Outcome\nCPU share,\nswitches, IPC','7  Reward\nr = s \u2212 \u03bbe','8  Online update\nSherman\u2013\nMorrison']
ax.text(.2,7.55,'A. Online learning loop (one pass per scheduling cycle)',fontsize=8.5,weight='bold')
for i,t in enumerate(A):
    x=.2+i*1.95;box(ax,x,4.9,1.7,1.8,t,fc='#9ecae1' if i in(2,3) else '#deebf7' if i in(6,7) else '#f2f2f2',fs=5.4)
    if i<7:arr(ax,(x+1.7,5.8),(x+1.95,5.8))
arr(ax,(.2+7*1.95+.85,6.7),(.2+2*1.95+.85,6.7),rad=.28);ax.text(8.2,7.15,'learning feedback',fontsize=7,style='italic',ha='center')
B=['Workload\n12 processes,\nphase changes','Simulator\n4 P + 4 E cores\n(Eqs. 7\u20138)','9 policies\n\u00d7 30 seeds','Metrics\nthroughput,\npower, latency','Statistics\nWilcoxon, Holm,\nCohen d\u2082','Figures\nand tables','Report']
ax.text(.2,3.15,'B. Offline evaluation pipeline',fontsize=8.5,weight='bold')
for i,t in enumerate(B):
    x=.2+i*2.25;box(ax,x,.7,2.0,1.8,t,fc='#e5f5e0',fs=5.8)
    if i<6:arr(ax,(x+2.0,1.6),(x+2.25,1.6))
f.savefig('fig16_pipeline.png',bbox_inches='tight');plt.close()
# model internals
f,ax=plt.subplots(figsize=(7.2,3.7));ax.axis('off');ax.set_xlim(-1.5,16);ax.set_ylim(0,8)
nm=['1  (bias)','c  CPU share','v  voluntary','n  involuntary','g  group','q  IPC (opt.)'];ys=np.linspace(7,1,6)
ax.text(1.3,7.75,'Input x (d = 6)',fontsize=8,weight='bold',ha='center')
for y,n in zip(ys,nm):
    ax.add_patch(Circle((2.2,y),.28,fc='#deebf7',ec='k',lw=.9));ax.text(1.8,y,n,ha='right',va='center',fontsize=7)
    for hy in (5.8,2.2):ax.plot([2.48,5.2],[y,hy],c='#bdbdbd',lw=.6,zorder=0)
box(ax,5.2,5.0,3.2,1.6,'Arm P head\n\u03b8\u209a = A\u209a\u207b\u00b9 b\u209a\n(ridge regression)',fc='#9ecae1');box(ax,5.2,1.4,3.2,1.6,'Arm E head\n\u03b8\u2091 = A\u2091\u207b\u00b9 b\u2091\n(ridge regression)',fc='#d9d9d9')
for hy,yy in ((5.8,(6.3,4.9)),(2.2,(2.7,1.3))):
    box(ax,9.2,yy[0]-.4,2.7,.8,'mean  \u03b8\u1d40x',fs=6.2);box(ax,9.2,yy[1]-.4,2.7,.8,'bonus  \u03b1\u221a(x\u1d40A\u207b\u00b9x)',fs=6.2)
    arr(ax,(8.4,hy),(9.2,yy[0]));arr(ax,(8.4,hy),(9.2,yy[1]))
for cy,l in ((5.6,'UCB\u209a'),(2.0,'UCB\u2091')):
    ax.add_patch(Circle((12.75,cy),.38,fc='#fff2cc',ec='k',lw=.9));ax.text(12.75,cy,'+',ha='center',va='center',fontsize=11);ax.text(12.75,cy+.6,l,ha='center',fontsize=7.5)
    arr(ax,(11.9,cy+.7 if cy>3 else cy+.3),(12.4,cy+.12));arr(ax,(11.9,cy-.7),(12.4,cy-.12))
box(ax,13.7,3.1,2.1,1.5,'argmax\n(random\ntie-break)',fc='#fdd0a2',fs=6.4);arr(ax,(13.15,5.6),(13.9,4.6));arr(ax,(13.15,2.0),(13.9,3.1))
ax.text(14.75,5.0,'action a \u2208 {P, E}',ha='center',fontsize=7.5,style='italic');ax.text(6.8,7.75,'Two linear models (no hidden layers)',fontsize=8,weight='bold',ha='center');ax.text(14.75,7.75,'Decision',fontsize=8,weight='bold',ha='center')
f.savefig('fig17_model.png',bbox_inches='tight');plt.close()
# learning curve + gap
POLS=[('LinUCB-Orig','#d95f02','--'),('LinUCB-Perf','#6baed6','-.'),('LinUCB-Perf+IPC','#08519c','-'),('Best-Static','k',':'),('Heuristic','#7f7f7f','-'),('Random','#bdbdbd','-')]
mv=lambda a,w=10:np.convolve(a,np.ones(w)/w,mode='valid')
f,ax=plt.subplots(figsize=(6.4,3.0))
for p,c,ls in POLS:ax.plot(range(9,300),mv(E2['tr'][p]),c=c,ls=ls,lw=1.5,label=p)
ax.set_xlabel('Scheduling cycle (1 s)');ax.set_ylabel('Normalised throughput');ax.legend(fontsize=6.8,ncol=2,loc='lower right');f.tight_layout();f.savefig('fig18_learn.png');plt.close()
f,ax=plt.subplots(figsize=(6.4,3.0))
for p,c,ls in [x for x in POLS if x[0]!='Best-Static']:ax.plot(E2['gap'][p],c=c,ls=ls,lw=1.5,label=p)
ax.set_xlabel('Scheduling cycle (1 s)');ax.set_ylabel('Cumulative shortfall vs Best-Static');ax.legend(fontsize=6.8,loc='upper left');f.tight_layout();f.savefig('fig19_regret.png');plt.close()
# radar
Mt=[('thr','Throughput',1),('eff','Efficiency',1),('pwr','Power',-1),('lat95','Latency',-1),('jain','Fairness',1),('mig','Migrations',-1),('inv','Invol. sw.',-1)]
POL=['Always-P','Always-E','Random','Static-Label','Best-Static','Heuristic','LinUCB-Orig','LinUCB-Perf','LinUCB-Perf+IPC']
V=np.array([[S[p][m][0] for m,_,_ in Mt] for p in POL]);Z=np.zeros_like(V)
for j,(m,_,sg) in enumerate(Mt):c=V[:,j]*sg;Z[:,j]=(c-c.min())/(c.max()-c.min()+1e-12)
n=len(Mt);ang=np.linspace(0,2*np.pi,n,endpoint=False);areas={}
f=plt.figure(figsize=(4.8,4.2));ax=f.add_subplot(111,polar=True)
for p,c,ls in [('LinUCB-Perf+IPC','#08519c','-'),('Best-Static','k',':'),('Heuristic','#7f7f7f','-'),('Random','#bdbdbd','-'),('LinUCB-Orig','#d95f02','--')]:
    z=Z[POL.index(p)];ax.plot(np.r_[ang,ang[0]],np.r_[z,z[0]],c=c,ls=ls,lw=1.5,label=p);areas[p]=float(.5*np.sin(2*np.pi/n)*np.sum(z*np.roll(z,-1)))
ax.set_xticks(ang);ax.set_xticklabels([m[1] for m in Mt],fontsize=7.5);ax.set_yticklabels([]);ax.set_ylim(0,1.05);ax.legend(fontsize=6.8,loc='upper center',bbox_to_anchor=(.5,-.08),ncol=3);f.tight_layout();f.savefig('fig20_radar.png');plt.close()
E2['radar_area']=areas;json.dump(E2,open('extra2.json','w'));print(areas)
