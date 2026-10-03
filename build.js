const fs=require('fs');const D=require('docx');
const {Document,Packer,Paragraph,TextRun,ImageRun,Table,TableRow,TableCell,WidthType,AlignmentType,BorderStyle,ShadingType,Footer,Header,PageNumber,TabStopType,Tab,LevelFormat,PageBreak}=D;
const LEAD=D.LeaderType?D.LeaderType.DOT:'dot';
const R=JSON.parse(fs.readFileSync('results.json'));const S=R.summary;
const PG=fs.existsSync('pages.json')?JSON.parse(fs.readFileSync('pages.json')):{};
const FONT='Times New Roman',C=AlignmentType.CENTER,J=AlignmentType.JUSTIFIED,TW=9026;
const reg=[];
const CN={};let cn=0;const cite=d=>CN[d]||(CN[d]=++cn);
function runs(t,o={}){const out=[];if(!o.nomap)t=t.replace(/\[(\d+)\]/g,(m,d)=>'['+cite(d)+']');let b=false,i=false;t.split(/(\*\*|__)/).forEach(s=>{if(s==='**')b=!b;else if(s==='__')i=!i;else if(s)out.push(new TextRun({text:s,bold:b||o.bold,italics:i||o.italics,size:o.size||22,font:o.font||FONT,smallCaps:o.sc,color:o.color}));});return out;}
const P=(t,o={})=>new Paragraph({alignment:o.al||J,spacing:{after:o.after??120,before:o.before||0,line:o.line||276},indent:o.indent,keepNext:o.keepNext,children:runs(t,o)});
const H1=(t,pb)=>{reg.push({k:'h',l:1,t});return new Paragraph({heading:'Heading1',pageBreakBefore:!!pb,keepNext:true,children:[new TextRun({text:t,bold:true,size:26,font:FONT})]});};
const H2=t=>{reg.push({k:'h',l:2,t});return new Paragraph({heading:'Heading2',keepNext:true,children:[new TextRun({text:t,bold:true,italics:true,size:23,font:FONT})]});};
const BUL=(t)=>new Paragraph({numbering:{reference:'bul',level:0},alignment:J,spacing:{after:60,line:276},children:runs(t)});
const NUM=(t)=>new Paragraph({numbering:{reference:'num',level:0},alignment:J,spacing:{after:60,line:276},children:runs(t)});
function pngSize(f){const b=fs.readFileSync(f);return [b.readUInt32BE(16),b.readUInt32BE(20)];}
const FORD=['fig1_arch.png','fig16_pipeline.png','fig17_model.png','fig2_flow.png','fig8_concept.png','fig9_geom.png','fig10_landscape.png','fig4_thr_pwr.png','fig6_pareto.png','fig3_learning.png','fig18_learn.png','fig19_regret.png','fig5_lat_fair_mig.png','fig7_sweep.png','fig13_place.png','fig14_theta.png','fig11_box.png','fig15_steady.png','fig12_heat.png','fig20_radar.png'];
const FN=f=>FORD.indexOf(f)+1;const FX=f=>'Fig. '+FN(f);
const TORD=['related','features','hyper','comps','audit','params','mix','metrics','policies','results','stats','bench','steady'];
const TK={'Comparison of Related Approaches':'related','Context Features':'features','Hyperparameters and Defaults':'hyper','Main Components of the Code Base':'comps','Findings of the Prototype Audit':'audit','Simulator Parameters':'params','Simulated Workload Mix (12 Processes)':'mix','Metric Definitions':'metrics','Evaluated Policies':'policies','Mean ± 95% CI over 30 Seeds':'results','Paired Differences (Holm-Adjusted Wilcoxon)':'stats','Computational Cost of One Bandit Update (d = 6)':'bench','Steady-State and Supplementary Results':'steady'};
const TX=k=>'Table '+ROM[TORD.indexOf(k)];
const X=JSON.parse(fs.readFileSync('extra.json'));const v=(p,m)=>S[p][m][0];const X2=JSON.parse(fs.readFileSync('extra2.json'));const sl=(p,a,b)=>(X2.gap[p][b]-X2.gap[p][a])/(b-a);
function FIG(file,w,cap){const fn=FN(file);reg.push({k:'f',n:fn,t:cap});const [pw,ph]=pngSize(file);
 return [new Paragraph({alignment:C,keepNext:true,spacing:{before:120,after:60},children:[new ImageRun({type:'png',data:fs.readFileSync(file),transformation:{width:w,height:Math.round(w*ph/pw)},altText:{title:cap,description:cap,name:file}})]}),
 new Paragraph({alignment:C,spacing:{after:220},indent:{left:300,right:300},children:runs('Fig. '+fn+'. '+cap,{size:19})})];}
const ROM=['I','II','III','IV','V','VI','VII','VIII','IX','X','XI','XII','XIII','XIV','XV'];
function TBL(title,header,rows,widths,o={}){const num=ROM[TORD.indexOf(TK[title])];reg.push({k:'t',n:num,t:title});
 const sum=widths.reduce((a,b)=>a+b,0);const cw=widths.map(w=>Math.round(w*TW/sum));cw[cw.length-1]+=TW-cw.reduce((a,b)=>a+b,0);
 const none={style:BorderStyle.NONE,size:0,color:'FFFFFF'},line={style:BorderStyle.SINGLE,size:6,color:'000000'};
 const cell=(t,i,hd,last,shade)=>new TableCell({width:{size:cw[i],type:WidthType.DXA},margins:{top:40,bottom:40,left:70,right:70},borders:{top:hd?line:none,bottom:(hd||last)?line:none,left:none,right:none},shading:shade?{type:ShadingType.CLEAR,fill:shade,color:'auto'}:undefined,
  children:[new Paragraph({alignment:i===0&&!o.centerFirst?AlignmentType.LEFT:C,children:runs(String(t),{size:o.size||18,bold:hd})})]});
 const trs=[new TableRow({tableHeader:true,children:header.map((h,i)=>cell(h,i,true,false))})];
 rows.forEach((r,ri)=>trs.push(new TableRow({cantSplit:true,children:r.map((c,i)=>cell(c,i,false,ri===rows.length-1,o.shade&&o.shade(ri)))})));
 return [new Paragraph({alignment:C,keepNext:true,spacing:{before:160,after:0},children:runs('TABLE '+num,{size:18})}),
  new Paragraph({alignment:C,keepNext:true,spacing:{after:80},children:runs(title,{size:18,sc:true})}),
  new Table({width:{size:TW,type:WidthType.DXA},columnWidths:cw,rows:trs}),new Paragraph({spacing:{after:160},children:[]})];}
function EQ(t,n){return new Paragraph({tabStops:[{type:TabStopType.CENTER,position:TW/2},{type:TabStopType.RIGHT,position:TW}],spacing:{before:60,after:100},children:[new TextRun({children:[new Tab(),t,new Tab(),'('+n+')'],font:'Cambria Math',size:22})]});}
function ALG(title,lines){const none={style:BorderStyle.NONE,size:0,color:'FFFFFF'},line={style:BorderStyle.SINGLE,size:8,color:'000000'};
 const mk=(ch,top,bot)=>new TableRow({children:[new TableCell({width:{size:TW,type:WidthType.DXA},margins:{top:30,bottom:30,left:100,right:100},borders:{top:top?line:none,bottom:bot?line:none,left:none,right:none},children:ch})]});
 const rows=[mk([new Paragraph({children:runs(title,{bold:true,size:20})})],true,true)];
 rows.push(mk(lines.map((l,i)=>new Paragraph({spacing:{after:30},indent:{left:(l.match(/^ */)[0].length)*180},children:runs((i+1)+':  '+l.trim(),{size:20})})),false,true));
 return [new Table({width:{size:TW,type:WidthType.DXA},columnWidths:[TW],rows}),new Paragraph({spacing:{after:140},children:[]})];}
const f3=x=>x.toFixed(3),pm=(a,d=3)=>a[0].toFixed(d)+' ± '+a[2].toFixed(d);
const sg=p=>p<0.001?'***':p<0.01?'**':p<0.05?'*':'ns';
// ---------------- BODY ----------------
const B=[];const add=(...a)=>a.flat().forEach(x=>B.push(x));
add(H1('1. INTRODUCTION',false),H2('1.1 Background and Motivation'),
P('Processor design has moved from many identical cores to heterogeneous multicore chips in which a few fast, power-hungry cores coexist with many slower, energy-frugal ones. The idea was demonstrated architecturally by Kumar et al. [1], who showed that moving programs between cores of different capability can reduce processor power with limited performance loss, and it reached mass-market devices through ARM big.LITTLE [2] and, more recently, hybrid x86 processors with Performance (P) and Efficiency (E) cores. The operating system is responsible for deciding which process runs on which core class, and mainstream kernels address this with fair-share scheduling [4] extended by an energy model for asymmetric CPUs [3].'),
P('Static rules such as “CPU-heavy work goes to the P-cores, everything else to the E-cores” are easy to implement but cannot follow workloads whose behaviour changes over time, and they ignore contention: when twice as many CPU-bound processes exist as P-cores, a rule that keeps all of them on the P-group leaves the E-group idle. Scheduler research has also shown that even mature kernels can leave cores idle while runnable threads wait [5]. A policy that learns from the measured outcome of its own placements is therefore attractive, provided it is cheap enough to run continuously and safe enough to deploy without kernel changes.'),
H2('1.2 Problem Statement'),
P('Given a set of running processes and two core groups with different speed and power, decide at every scheduling cycle which group each process should use so that the system delivers as much useful work as possible per unit of energy, without prior labels of what each process is, without root privileges, and without modifying the kernel. The decision must adapt when a process changes phase (for example, from I/O waiting to computation).'),
H2('1.3 Objectives'),
NUM('Formulate P/E core-group selection as a contextual-bandit problem that can be solved online in user space.'),
NUM('Audit the original AI-DAX Lite prototype and correct its reward signal and evaluation methodology.'),
NUM('Compare the learned policy with simple, heuristic and hindsight-optimal static baselines under a reproducible protocol.'),
NUM('Quantify the contribution of individual design choices (reward, IPC feature, exploration and energy weights) and the computational overhead.'),
H2('1.4 Research Questions'),P('The study is organised around four research questions.'),
BUL('**RQ1.** Does the reward of the original prototype lead the governor to a useful placement policy?'),
BUL('**RQ2.** How close can an online learner come to a hindsight-optimal static partition, and how does it compare with simple rules and random placement?'),
BUL('**RQ3.** Which design choices (reward, IPC feature, energy weight λ, exploration coefficient α) matter most?'),
BUL('**RQ4.** What does the policy cost in migrations, interactive tail latency and computation?'),
H2('1.5 Contributions'),
BUL('A LinUCB-based governor that routes processes between core groups using the sched_setaffinity interface and operating-system telemetry only.'),
BUL('Identification of a failure mode of the original reward (involuntary context switches plus a constant energy proxy) and a replacement reward that combines delivered work and attributed energy.'),
BUL('An ablation showing that a memory-stall/IPC feature makes memory-bound and CPU-bound processes separable and reduces unnecessary migrations by about 80%.'),
BUL('A seeded, open simulator, a hindsight-optimal static baseline, and a statistical protocol (paired Wilcoxon tests with Holm correction) that make the results reproducible.'),
BUL('A FastAPI/WebSocket dashboard and safety mechanisms (PID-reuse guard, atomic logging, affinity reset) for live demonstration.'),
H2('1.6 Code and Deployment Availability'),P('AIZEN is the name used in this report for the improved algorithm and governor built on the AI-DAX Lite prototype of the repository. The source code is available at https://github.com/priyanrajj-hub/operatingsystemsprojectcapstone and the dashboard front end is deployed on Vercel under the project name “operatingsystemsprojectcapstone”. The simulator, figure scripts and raw per-seed data used in this report accompany the submission (Appendix B).'),
H2('1.7 Organisation of the Report'),
P('Section 2 reviews related work. Section 3 presents the proposed methodology. Section 4 describes the implementation, the verification of the prototype, and the simulator. Section 5 reports and analyses the results. Section 6 concludes and lists future work. Appendices A–C give code listings, reproduction instructions and supplementary tables.'));
add(H1('2. LITERATURE SURVEY',true),H2('2.1 Heterogeneous Multicore Processors'),
P('Kumar et al. [1] introduced single-ISA heterogeneous multicore processors and showed, using a thread-to-core assignment that follows program phases, that significant power reductions are possible at modest performance cost. ARM’s big.LITTLE pairs high-performance and high-efficiency cores that share an instruction set [2]. In Linux, Energy Aware Scheduling uses an energy model of the CPU topology to place waking tasks on the core that minimises estimated energy while keeping the CPU capacity sufficient [3]. These mechanisms live inside the kernel and rely on platform-supplied energy models.'),
H2('2.2 General-Purpose Process Scheduling'),
P('The Completely Fair Scheduler allocates CPU time in proportion to weights using virtual runtime ordering [4], and operating-systems textbooks treat it as the canonical fair-share design [15]. Lozi et al. documented performance bugs in the Linux scheduler that left cores idle while threads were waiting [5], which illustrates that placement decisions remain difficult even without heterogeneity. Fairness is commonly summarised with Jain’s index [16], which we also use.'),
H2('2.3 Learning-Based Resource Management'),
P('Quasar uses classification techniques to estimate the resource needs and interference sensitivity of cluster workloads so that quality-of-service targets are met with fewer resources [6]. Decima applies deep reinforcement learning with graph neural networks to schedule data-processing jobs on clusters [7]. Reinforcement learning in general targets sequential decision making with delayed reward [8]; deep variants reached human-level performance in Atari games [27]. Both systems operate at the cluster level; neither addresses per-process core-class selection on a single host.'),
H2('2.4 Contextual Bandits'),
P('When the decision at each step has immediate, measurable feedback and the action set is small, a contextual bandit is a lighter alternative to full reinforcement learning. Auer analysed linear upper-confidence-bound exploration [9]; LinUCB, introduced by Li et al. for news recommendation, maintains a ridge-regression estimate [26] per arm and adds an exploration bonus proportional to the uncertainty of the prediction [10]. Regret analyses for linear payoffs and improved confidence sets are given in [11], [12], and a comprehensive treatment is available in [13]. LinUCB needs only a d×d matrix per arm, which makes it suitable for continuous in-process use.'),
H2('2.5 Tail Latency and Interactive Workloads'),P('For interactive services the high percentiles of latency matter more than the mean, because rare slow responses dominate the experience of the user when many requests are involved [23]. Placing an interactive process on a slower core class or on a crowded core therefore trades energy for tail latency, which is why this report measures the p95 latency of interactive processes separately from throughput.'),
H2('2.6 Summary and Research Gap'),
P(''+TX('related')+' contrasts the surveyed approaches. Kernel mechanisms are hardware-aware but not adaptive to measured outcomes; cluster-level learners are adaptive but operate at a different granularity. What is missing, and what this work explores, is a lightweight, online-learning governor that works at process granularity from user space and whose behaviour can be inspected and reproduced by students and practitioners.'));
add(TBL('Comparison of Related Approaches',['Work','Layer','Method','Learns online','Relation to this work'],[
['Kumar et al. [1]','Architecture','Phase-based thread-to-core migration','No','Motivates P/E routing'],
['big.LITTLE [2]','Hardware/OS','Asymmetric core pairing','No','Target platform class'],
['Linux EAS [3]','Kernel','Energy-model task placement','No','Kernel-level counterpart'],
['CFS [4]','Kernel','Virtual-runtime fair sharing','No','Default baseline'],
['Quasar [6]','Cluster','Classification of resource needs','Partly','Different granularity'],
['Decima [7]','Cluster','Deep RL job scheduling','Yes','Heavier, cluster level'],
['LinUCB [10]','Algorithm','Linear contextual bandit','Yes','Algorithm used here']],[1.5,1.2,2.4,1.1,2.0]));
add(H1('3. PROPOSED METHODOLOGY',true),H2('3.1 System Overview'),
P('AIZEN runs as an ordinary user-space process. Each cycle it reads telemetry of every tracked process, builds a context vector, selects a core group with a LinUCB policy, applies the choice by setting the process’s CPU-affinity mask, and learns from the outcome measured in the next cycle. '+FX('fig1_arch.png')+' shows the architecture and '+FX('fig2_flow.png')+' the control loop.'),
FIG('fig1_arch.png',560,'Architecture of the AIZEN governor: telemetry feeds a context builder; the shared LinUCB policy selects a core group; the actuator applies the affinity mask; the measured outcome yields the reward that updates the policy.'),
P('The machine-learning workflow of AIZEN has two parts ('+FX('fig16_pipeline.png')+'). The online loop (A) runs once per scheduling cycle: telemetry is turned into a scaled feature vector, the two per-arm models score the arms with an upper confidence bound, the chosen core group is applied, and the outcome measured in the next cycle becomes a reward that updates the model in O(d²). The offline pipeline (B) is how the policies are evaluated: a seeded workload runs on the simulated 4P+4E machine under nine policies and 30 seeds, the metrics are summarised, tested statistically and turned into the figures and tables of Section 5.'),
FIG('fig16_pipeline.png',600,'Machine-learning workflow: (A) the online learning loop executed in every scheduling cycle; (B) the offline evaluation pipeline used to produce the results of this report.'),
H2('3.2 Contextual-Bandit Formulation'),
P('For process i at cycle t the context vector is'),
EQ('x = [1, c, v/300, min(n/100, 3), g, q]ᵀ',1),
P('where c is the CPU share obtained in the previous cycle, v and n are the voluntary and involuntary context-switch rates per second, g ∈ {0, 1} is the current group (0 = P, 1 = E), and q is an optional IPC estimate. The constant 1 provides an intercept. There are two arms, a ∈ {P, E}. For each arm the policy keeps a matrix A and a vector b (initialised to the identity and zero) and scores'),
EQ('score(a) = θₐᵀx + α·sqrt(xᵀ Aₐ⁻¹ x),   θₐ = Aₐ⁻¹ bₐ',2),
P('and picks the arm with the larger score; ties are broken at random. After the reward r of the previous action is observed the chosen arm is updated:'),
EQ('Aₐ ← Aₐ + x xᵀ,   bₐ ← bₐ + r x',3),
P('We maintain A⁻¹ directly with the Sherman–Morrison identity [25],'),
EQ('A⁻¹ ← A⁻¹ − (A⁻¹ x xᵀ A⁻¹) / (1 + xᵀ A⁻¹ x)',4),
P('which costs O(d²) per update instead of O(d³) for explicit inversion. One bandit is shared by all processes, so experience from one process informs the others; the cost of sharing is that processes interact through contention, which makes the reward non-stationary (Section 5.10).'),
P(FX('fig17_model.png')+' shows the structure of the model. Six inputs feed two linear heads, one per core group. Each head is a ridge-regression predictor of the reward of its arm together with a covariance matrix that records how well the arm has been explored; the upper confidence bound of an arm is the sum of its predicted reward and an uncertainty bonus, and the arm with the larger bound is chosen. The model has 2 × 6 = 12 weights and two 6 × 6 covariance matrices and no hidden layers, so every weight can be read directly (Section 5.7) and the whole model is updated in microseconds.'),
FIG('fig17_model.png',600,'Structure of the AIZEN model: two linear reward heads with uncertainty bonuses, combined into upper confidence bounds and a greedy arm choice.'),
H2('3.3 Reward Design'),
P('The original prototype used'),
EQ('r = −(0.7 ñ + 0.3 εₐ),   ε_P = 1.0, ε_E = 0.3',5),
P('where ñ is a normalised involuntary-switch rate. The energy term depends only on the chosen arm, and ñ is close to zero whenever there is no contention, so the reward reduces to a constant preference for the E-group irrespective of the work being delivered. We therefore replace it with a service-and-energy reward,'),
EQ('r = s − λ e,   s = delivered work / demanded work,   e = c · π_g',6),
P('where s is the fraction of the process’s demand that was actually served (measurable from retired-instruction counters or, as a proxy, CPU share), e is the CPU share multiplied by the dynamic power π of the group used, and λ = 0.5 is the energy weight. In an uncontended system this gives, for a CPU-bound process, r = 1 − 0.5 = 0.50 on a P-core versus 0.55 − 0.15 = 0.40 on an E-core, so P is preferred; for a memory-bound process (demand 0.8, E-core speed 0.9) it gives 0.60 on P versus 0.78 on E, so E is preferred. Under contention the served fraction drops on an overloaded group, which pushes processes toward the less loaded group and produces load balancing without any process labels.'),
H2('3.4 Control Loop'),
P('Algorithm 1 summarises one scheduling cycle and '+FX('fig2_flow.png')+' shows the same loop as a flowchart. The learning step uses the outcome of the previous cycle, so every update is based on a measured effect of an earlier placement rather than on a heuristic label.'),
ALG('Algorithm 1: AIZEN scheduling cycle',[
'for each tracked process i (validated by PID and creation time):',
'    read telemetry: c, v, n, (q) over the last cycle',
'    build context x as in (1)',
'    if a previous action a′ exists for i:',
'        compute reward r = s − λ e as in (6)',
'        update A⁻¹, b of arm a′ with (3) and (4)',
'    compute score(P), score(E) as in (2)',
'    a ← argmax score (random tie-break)',
'    if a ≠ current group: apply cpu_affinity(mask of a); count a migration',
'    store (a, x) for the next cycle',
'log decisions, publish to dashboard, sleep until next cycle']),
FIG('fig2_flow.png',300,'Flowchart of one scheduling cycle of the governor.'),
H2('3.5 Safety and Robustness'),
P('The governor never needs root privileges because it only changes the affinity of processes owned by the same user. It validates each tracked process by comparing the recorded creation time with the live process to avoid acting on a recycled PID; log files are written atomically through a temporary file and a rename; SIGINT and SIGTERM handlers restore the full CPU set for every tracked process; and the dashboard exposes an emergency-reset endpoint that releases all affinity constraints.'));
add(H2('3.6 Why a Contextual Bandit?'),
P('Three learning paradigms could drive a placement policy ('+FX('fig8_concept.png')+'). Supervised learning requires a label saying which core group was best for each process, but no such ground truth exists because the outcome of the alternative placement is never observed. Full reinforcement learning models the effect of an action on future states and optimises a discounted return, which needs far more samples and heavier models [8], [27]. A contextual bandit sits between them: it learns from the reward of the action that was actually taken, needs no transition model, and its update is a few small matrix operations. Because a placement mostly affects the throughput and energy of the next cycle, ignoring long-term state is an acceptable approximation; the price is that interactions between processes are not modelled explicitly (Section 5.10).'),
FIG('fig8_concept.png',580,'Comparison of learning paradigms for core-group selection; the contextual bandit used in this work (shaded) needs no labels and updates online.'),
P('Exploration is handled by the upper confidence bound. '+FX('fig9_geom.png')+' illustrates the mechanism on synthetic data (it is an illustration, not an experimental result): with few samples the confidence band of each arm is wide, so the arm that currently looks worse may still be tried; as evidence accumulates the bands shrink and the policy settles on the arm with the higher predicted reward, here arm E for a low CPU share and arm P for a high CPU share.'),
FIG('fig9_geom.png',580,'Illustration of upper-confidence-bound exploration on synthetic data: (a) after 5 samples per arm the confidence bands are wide; (b) after 60 samples they have narrowed and the preferred arm depends on the CPU share. Lines are predicted rewards and the top of each band is the UCB.'),
H2('3.7 Context Features'),P(TX('features')+' lists the elements of the context vector in (1) and how they are obtained and scaled.'),
TBL('Context Features',['Feature','Source','Scaling','Purpose'],[
['Bias','constant 1','—','Intercept: baseline reward of an arm'],
['CPU share c','CPU-time delta ÷ Δt (psutil)','clipped to [0, 1]','Demand and service level'],
['Voluntary switches v','/proc counter delta ÷ Δt','÷ 300','I/O-boundness (sleeps often)'],
['Involuntary switches n','/proc counter delta ÷ Δt','÷ 100, clipped to [0, 3]','Contention on the current group'],
['Group g','current affinity class','0 = P, 1 = E','Lets the model value staying put'],
['IPC q (optional)','retired instructions ÷ cycles (performance counters)','as measured','Separates memory-bound from compute-bound']],[1.7,2.8,1.7,2.8],{size:17}),
P('Fixed scales are used instead of running statistics so that a stored context is never re-scaled by later observations. On a real system the IPC feature needs hardware performance counters, which psutil does not provide; in the simulator it stands for any counter-based memory-intensity signal such as stall cycles.'),
H2('3.8 Reward Landscape'),
FIG('fig10_landscape.png',580,'Expected reward of each core group by process type: (a) proposed reward with λ = 0.5; (b) original reward without contention.'),
P(FX('fig10_landscape.png')+'(a) plots the expected reward of (6) for λ = 0.5 in the absence of contention. CPU-bound and bursty-active processes obtain 0.50 and about 0.53 on the P-group but only 0.40 and 0.41 on the E-group; memory-bound processes obtain 0.78 on E against 0.60 on P; I/O-bound processes are almost indifferent (0.95 against 0.89). The learned policy therefore only has to discover the sign of these differences. '+FX('fig10_landscape.png')+'(b) shows the original reward in the same situation: with ñ ≈ 0.02 it gives −0.31 on P and −0.10 on E for every process type, so the E-group is always preferred and nothing rewards giving a process the speed it needs.'),
H2('3.9 Hyperparameters and Complexity'),
TBL('Hyperparameters and Defaults',['Parameter','Default','Range / note'],[
['Exploration coefficient α','0.5','swept 0.05–2.0'],['Energy weight λ','0.5','swept 0.1–1.2'],['Ridge regulariser','1.0 (A initialised to I)','fixed'],['Cycle length Δt','1 s','fixed'],['Arms','2 (P-group, E-group)','fixed'],['Feature dimension d','5 (6 with IPC)','fixed'],['Tie-breaking','uniform random','fixed'],['Bandit sharing','one bandit for all processes','per-PID bandit left for future work']],[3,3,3]),
P('Each decision costs two matrix–vector products and one quadratic form per arm, O(d²); each update is one rank-one correction, also O(d²). Memory per bandit is 2(d² + d) numbers (84 for d = 6), independent of the number of decisions, and a single shared bandit serves all processes.'));
add(H1('4. IMPLEMENTATION',true),H2('4.1 Software Stack and Code Organisation'),
P('The prototype is written in Python 3. Process telemetry and affinity control use psutil [14], numerical work uses NumPy and SciPy, and the dashboard is a FastAPI application with a REST interface and a WebSocket stream consumed by an HTML/JavaScript front end. '+TX('comps')+' lists the main components.'),
TBL('Main Components of the Code Base',['File','Role'],[
['ai_scheduler.py','LinUCB bandit, telemetry, reward, affinity actuation, bandit statistics'],
['workload_generator.py','Spawns CPU-bound and I/O-bound worker processes (infinite or finite jobs)'],
['evaluate.py','Four-condition native evaluation harness (CFS, static, heuristic, bandit)'],
['main.py, static/','FastAPI REST/WebSocket backend and dashboard front end'],
['sim.py (new)','Seeded heterogeneous-core simulator and all policies; writes results and raw data'],
['figs.py (new)','Generates every figure used in this report from the simulator output']],[2,6]),
H2('4.2 Telemetry and Actuation'),
P('For each tracked process the governor reads CPU times, voluntary and involuntary context-switch counters, and the current affinity mask; the counters are exposed through /proc [22]. Rates are computed as differences between consecutive cycles. A persistent process handle must be kept between cycles, because the CPU-percentage routine of psutil returns a meaningless zero on the first call of a new handle. Actuation uses the CPU-affinity call [21] with the mask of the P-group (lower half of the logical CPUs by default or the sysfs-reported P-cores where available) or the E-group.'),
H2('4.3 Workload Generator'),
P('The generator starts a configurable mix of CPU-bound workers (prime computation) and I/O-bound workers (small file writes and reads separated by sleeps). Each process registers its PID, type label and creation time in a tracking file that the scheduler and the dashboard read. A finite mode makes jobs terminate so that completion time can be measured.'),
H2('4.4 Dashboard'),
P('The dashboard shows per-process placement, reward and bandit statistics, system CPU health and a reset button. The backend reads the scheduler’s CSV log and statistics file once per second and pushes them over a WebSocket.'),
H2('4.5 Verification of the Prototype'),
P('Before using the native harness for the evaluation we inspected its source and output and found four issues that make its numbers unsuitable as evidence: (i) the archived native results show zero involuntary context switches, zero heavy-task completion time and undefined p-values in every condition, so no effect can be measured from them; (ii) the bandit condition of the harness creates a new process handle in every cycle, so the CPU-share feature is read from a first-call handle; (iii) the heuristic-only condition measures metrics over a different, shorter window than the other conditions; and (iv) the static-naive condition reads each process’s ground-truth type from the tracking file, so it is an oracle rather than a naive rule. These findings are the reason the quantitative evaluation in this report is performed on a simulator with explicit assumptions, and they define the corrections needed for a native Linux re-run (Section 6).'),
P(TX('audit')+' collects the findings of the audit in one place, with the evidence and the corrective action adopted in this report.'),
TBL('Findings of the Prototype Audit',['ID','Finding','Evidence','Consequence','Corrective action'],[
['A1','Archived native results are degenerate','final_results.txt: involuntary switches 0.00, heavy completion 0.00, p-values undefined in every condition','No effect can be measured or claimed','Re-run on Linux with oversubscribed cores; report all metrics'],
['A2','Heavy workers appear unmeasured','Mean CPU of about 0.4–0.9% although CPU-bound workers were launched','Experiment effectively measured idle I/O workers','Verify worker liveness; log samples per process'],
['A3','CPU share read from a fresh handle each cycle','Scheduler and harness create a new psutil handle per cycle; first call returns 0.0','CPU feature constant; heuristic degenerates to the E-group','Keep one handle per PID across cycles'],
['A4','Heuristic condition measured over a different window','evaluate.py: control phase unmeasured; metrics taken afterwards for at most 10 s','Conditions not comparable','Identical measurement window for all conditions'],
['A5','“Static-naive” baseline uses ground-truth labels','Type read from the tracking file','Oracle, not naive','Rename; add label-free baselines'],
['A6','Reward and regret ill-posed','Energy term depends only on the arm; both arms scored with the same observed involuntary rate','Policy reduces to “prefer E”; regret not counterfactual','Reward (6); simulation-based true regret'],
['A7','Dashboard hardening','Unauthenticated reset endpoint; README suggests binding to 0.0.0.0; log truncated to 300 lines','Exposure on shared networks; no raw data retained','Local-only binding, token, append-only raw log'],
['A8','Repository hygiene','Temporary and log files committed; no tests; no standard licence file','Hard to reproduce and reuse','Clean tree, tests, CI, explicit licence']],[0.6,2.2,3.2,2.2,2.6],{size:15}),
H2('4.6 Heterogeneous-Core Simulator'),
P('The development machine has no hybrid CPU, so the evaluation uses a discrete-time simulator whose cycle length equals the governor’s one-second period. A machine has n_P = 4 P-cores and n_E = 4 E-cores. Process i has a demand d_i (fraction of one P-core it wants) and a relative speed σ_i on the E-group (1.0 on P). If D_g is the total demand placed on group g with n_g cores, each process receives'),
EQ('share_i = d_i · min(1, n_g / D_g),   progress_i = share_i · σ_i,g',7),
P('so an overloaded group serves only part of the demand. System power is'),
EQ('Power = Σ_g [ n_g π_idle,g + π_dyn,g · min(n_g, D_g) ]',8),
P('Involuntary context switches follow 2d + 150 · share · (1 − n_g/D_g) per second and voluntary switches 10 + 300(1 − d), both with multiplicative log-normal noise (σ = 0.2). The tail latency of an interactive process is (1/σ) / (1 − 0.9 · min(ρ_g, 1)) milliseconds with log-normal noise (σ = 0.3), where ρ_g = D_g / n_g. '+TX('params')+' lists the parameters and '+TX('mix')+' the workload mix, which is deliberately oversubscribed: the mean total demand is about 7.7 P-core equivalents against four P-cores. All values are modelling assumptions chosen to resemble a hybrid processor and are not measurements.'),
TBL('Simulator Parameters',['Parameter','Value'],[
['Cores','4 P-cores (speed 1.0), 4 E-cores'],
['Dynamic power per busy core','P = 1.00, E = 0.30 (relative units)'],
['Idle power per core','P = 0.10, E = 0.03'],
['Cycle / episode','1 s / 300 cycles; first 200 cycles used for steady-state figures'],
['Telemetry noise','log-normal, σ = 0.2 (counters), σ = 0.3 (latency)'],
['Bandit','shared LinUCB, ridge 1, α = 0.5, λ = 0.5, random tie-break'],
['Seeds','30 independent seeds (0–29), common random numbers across policies']],[3,5]),
TBL('Simulated Workload Mix (12 Processes)',['Type','Count','Demand','E-core speed','IPC feature'],[
['CPU-bound','4','1.00','0.55','1.0'],
['Memory-bound','3','0.80','0.90','0.3'],
['I/O-bound (interactive)','3','0.10','0.90','0.6'],
['Bursty (phase-changing)','2','0.95 / 0.10 (20–40 s phases)','0.55 / 0.90','1.0 / 0.6']],[2.3,1,2.6,1.4,1.4]),
H2('4.7 Reproduction'),
P('The experiment is reproduced with “python sim.py” (about three minutes on one core; writes results.json and raw_per_seed.csv) followed by “python figs.py”. Every number and figure in Section 5 is produced by these two scripts; the seeds are fixed.'));
add(H2('4.8 Deployment and Availability'),P('The source repository is https://github.com/priyanrajj-hub/operatingsystemsprojectcapstone and the dashboard front end is also deployed on Vercel (project “operatingsystemsprojectcapstone”). Because the governor changes CPU affinity through operating-system calls, it only affects processes on the machine where it runs; a hosted page cannot govern a remote host, so the Python backend must be started locally for live operation and the hosted page serves as a demonstration of the interface. The simulator, the figure scripts and the raw per-seed data used in this report accompany the submission so that every number can be regenerated.'));
// Table V policies
add(H1('5. RESULTS AND ANALYSIS',true),H2('5.1 Experimental Setup and Metrics'),
P('Nine policies are compared ('+TX('policies')+'). Best-Static is a strong reference: it exhaustively searches all static assignments (using the symmetry between processes of the same type) for the one that maximises the same service-minus-energy objective on sampled time steps, so it uses knowledge of the workload that the online policies do not have. Metrics per episode (defined in '+TX('metrics')+') are normalised throughput (progress divided by demand), average power, efficiency (work per unit power), p95 latency of the interactive I/O processes, Jain’s fairness index [16] of per-process satisfaction, and migrations per process per minute. Results are means over 30 seeds with 95% confidence intervals. Differences are tested with paired Wilcoxon signed-rank tests [17], Holm-corrected [18] across the five planned comparisons, and effect sizes are reported as paired Cohen’s d_z [19].'),
TBL('Metric Definitions',['Metric','Definition','Better'],[
['Normalised throughput','Σ progress ÷ Σ demand over the episode','higher'],['Average power','Mean over cycles of (8)','lower'],['Efficiency','Mean total progress per cycle ÷ mean power','higher'],['p95 latency','95th percentile of the latency of interactive (I/O-bound) processes','lower'],['Jain’s index','(Σ s)² ÷ (N Σ s²) of per-process satisfaction s','higher'],['Migrations','Group changes per process per minute','lower'],['Involuntary switches','Mean per process per second','lower']],[2.2,4.8,1.2],{size:17}),
TBL('Evaluated Policies',['Policy','Description','Knowledge used'],[
['Always-P / Always-E','All processes on one group','None'],
['Random','Re-draw each process’s group every 10 cycles','None'],
['Static-Label','Heavy types to P, I/O to E (README rule)','True process type'],
['Best-Static','Best fixed assignment found by exhaustive search','Types, demand profile (oracle)'],
['Heuristic','P if CPU share > 20%, else E (README cold-start rule)','CPU share'],
['LinUCB-Orig','LinUCB with the original reward (5)','psutil telemetry'],
['LinUCB-Perf','AIZEN without IPC: LinUCB with reward (6)','psutil telemetry'],
['LinUCB-Perf+IPC','AIZEN (proposed): LinUCB with reward (6) and the IPC feature','Telemetry + IPC']],[2.1,4,2.3]),
H2('5.2 Overall Performance'));
const POL=['Always-P','Always-E','Random','Static-Label','Best-Static','Heuristic','LinUCB-Orig','LinUCB-Perf','LinUCB-Perf+IPC'];
add(TBL('Mean ± 95% CI over 30 Seeds',['Policy','Throughput','Power','Efficiency','p95 lat. (ms)','Jain','Migr./proc/min'],
POL.map(p=>[p,pm(S[p].thr),pm(S[p].pwr,2),pm(S[p].eff),pm(S[p].lat95,2),pm(S[p].jain),pm(S[p].mig,2)]),[2,1.5,1.3,1.5,1.4,1.2,1.4],{size:16,shade:i=>i>=6?'EAF1FB':null}),
P(''+TX('results')+' and '+FX('fig4_thr_pwr.png')+' show the main outcome. LinUCB-Perf+IPC delivers 0.827 normalised throughput, 46% more than the README heuristic (0.565), 13% more than random placement (0.731) and 9% more than the same bandit without the IPC feature (0.758). It reaches 95% of the throughput of the hindsight-optimal Best-Static partition (0.870) at 2.4% lower power (5.30 versus 5.43). The label-based and heuristic rules deliver only 0.55–0.57 because they keep the E-group almost idle while the P-group is oversubscribed, which is exactly the contention situation that motivates learning.'),
FIG('fig4_thr_pwr.png',580,'Normalised throughput (a) and average power (b) of the nine policies (mean and 95% CI over 30 seeds).'),
P('Efficiency taken alone is misleading: Always-E has the highest efficiency (1.575) but delivers only 0.349 of the demanded work. '+FX('fig6_pareto.png')+' therefore shows the throughput–power trade-off. LinUCB-Perf+IPC lies on the upper-right frontier together with Best-Static, whereas LinUCB-Orig sits at low power and low throughput: with the original reward the bandit saves 31% power relative to LinUCB-Perf but loses 22% of the throughput, confirming the failure mode analysed in Section 3.3.'),
FIG('fig6_pareto.png',390,'Throughput–power trade-off; points show the mean over 30 seeds with 95% CI bars.'),
H2('5.3 Learning Dynamics'),
P(''+FX('fig3_learning.png')+' shows how placements evolve. With the IPC feature the policy places memory-bound processes on the E-group almost immediately (fraction near 1.0 within about ten cycles) and keeps roughly 90% of the CPU-bound processes on the P-group after about thirty cycles; the remaining share moves to the E-group when the P-group is saturated, which is the load-balancing behaviour of Section 3.3. Without the IPC feature the policy cannot tell memory-bound from CPU-bound processes using CPU share and context-switch rates alone, so only about 60–70% of memory-bound processes end up on the E-group and placements keep oscillating (12.1 migrations per process per minute versus 2.4 with IPC). The original reward keeps fewer than half of the CPU-bound processes on the P-group, in line with its low throughput.'),
FIG('fig3_learning.png',590,'Placement over time (mean ± 1 s.d. over 30 seeds): (a) fraction of CPU-bound processes on the P-group; (b) fraction of memory-bound processes on the E-group.'),
P(FX('fig18_learn.png')+' shows the normalised throughput per cycle (10-cycle moving average, mean over 20 seeds) and '+FX('fig19_regret.png')+' the cumulative throughput shortfall relative to Best-Static. This shortfall is a pseudo-regret, not the formal regret of the bandit, but it shows whether learning closes the gap. With IPC, the shortfall of AIZEN grows by '+sl('LinUCB-Perf+IPC',0,99).toFixed(3)+' per cycle in cycles 1–100 and by '+sl('LinUCB-Perf+IPC',199,299).toFixed(3)+' per cycle in cycles 200–300. The corresponding figures are '+sl('LinUCB-Perf',0,99).toFixed(3)+' and '+sl('LinUCB-Perf',199,299).toFixed(3)+' without IPC, '+sl('LinUCB-Orig',0,99).toFixed(3)+' and '+sl('LinUCB-Orig',199,299).toFixed(3)+' for the original reward, and '+sl('Heuristic',0,99).toFixed(3)+' and '+sl('Heuristic',199,299).toFixed(3)+' for the README heuristic, which does not learn.'),
FIG('fig18_learn.png',540,'Normalised throughput per scheduling cycle (10-cycle moving average, mean over 20 seeds).'),
FIG('fig19_regret.png',540,'Cumulative throughput shortfall relative to Best-Static (mean over 20 seeds).'),
H2('5.4 Statistical Analysis'));
const L=['Perf+IPC vs Best-Static','Perf+IPC vs Heuristic','Perf+IPC vs Random','Perf vs Orig','Perf+IPC vs Perf'];
const stRows=L.map((l,i)=>[l].concat([['thr',3],['pwr',2],['eff',3],['lat95',2]].map(([m,d])=>{const r=R.stats[m][i];return (r[2]>=0?'+':'')+r[2].toFixed(d)+' (d_z='+r[3].toFixed(1)+') '+sg(r[5]);})));
add(TBL('Paired Differences (Holm-Adjusted Wilcoxon)',['Comparison','Δ Throughput','Δ Power','Δ Efficiency','Δ p95 latency (ms)'],stRows,[2.2,1.9,1.7,1.9,2.1],{size:16}),
P(''+TX('stats')+' lists the paired differences (*** p < 0.001, ** p < 0.01, * p < 0.05, ns = not significant after Holm correction). All throughput, power and efficiency differences are significant. The IPC feature gives a significant gain over the telemetry-only bandit, and the corrected reward significantly improves throughput over the original reward. The only latency difference that is not significant is Perf+IPC versus Best-Static (+1.07 ms). Because the seeds vary only the workload phases and measurement noise within one fixed model, these tests quantify consistency inside the simulator and should not be read as evidence about real hardware.'),
H2('5.5 Latency, Fairness and Migration'),
FIG('fig5_lat_fair_mig.png',600,'Interactive tail latency (a), Jain’s fairness index (b) and migration rate (c) of the nine policies.'),
P(''+FX('fig5_lat_fair_mig.png')+' shows tail latency, fairness and migration rate. Fairness is highest for LinUCB-Perf+IPC among the policies that use both core groups (Jain 0.997). The learned policies have a higher tail latency for the interactive I/O processes (13.2 ms for Perf+IPC; 17.8 ms for Orig) than Static-Label and Heuristic (about 2 ms). The reason is the same as for their low throughput: those two rules park the interactive processes on a nearly empty E-group, whereas the learned policies use all eight cores and therefore share cores with heavier processes. The reward (6) contains no latency term and the interactive processes have small demand, so their latency has little influence on learning. This is a real limitation and the main motivation for the latency-aware reward proposed in Section 6.'),
H2('5.6 Sensitivity and Overhead'),
FIG('fig7_sweep.png',560,'Sensitivity of LinUCB-Perf+IPC (15 seeds per point) to the energy weight λ (a) and the exploration coefficient α (b).'),
P(''+FX('fig7_sweep.png')+'(a) shows that λ acts as a power–performance knob: for λ ≤ 0.5 throughput stays at 0.825–0.828 with power about 5.3, while λ = 0.8 gives 0.618 throughput at 3.74 power and λ = 1.2 gives 0.417 at 2.29, so an operator can move along the frontier without retraining the method. '+FX('fig7_sweep.png')+'(b) shows that the policy is robust to the exploration coefficient: throughput stays between 0.812 and 0.828 for α from 0.05 to 2.0 and is highest at α = 0.5, the default.'),
...TBL('Computational Cost of One Bandit Update (d = 6)',['Method','Time per update (µs)','Complexity'],[
['Sherman–Morrison (used)',R.bench.sm_us.toFixed(2),'O(d²)'],['Explicit matrix inversion',R.bench.inv_us.toFixed(2),'O(d³)']],[3,2.5,2]),
P(''+TX('bench')+' reports the measured cost of one update on a single core. At d = 6 the two methods are comparable (the O(d²) advantage appears only for larger feature vectors), and both are several orders of magnitude below the one-second control period, so the learning overhead is negligible for twelve processes.'),
H2('5.7 Policy Behaviour and Interpretability'),
P(FX('fig13_place.png')+' shows the fraction of time each process type spends on the P-group (mean over 10 seeds). The hindsight-optimal Best-Static places the memory-bound processes entirely on the E-group, three of the four CPU-bound processes and 90% of the bursty ones on P, and mostly keeps the I/O-bound ones on E. LinUCB-Perf+IPC reproduces this pattern without any labels: '+Math.round(100*X.place['LinUCB-Perf+IPC'].cpu)+'% of the CPU-bound and '+Math.round(100*X.place['LinUCB-Perf+IPC'].burst)+'% of the bursty placements are on P, memory-bound processes stay on E ('+Math.round(100*X.place['LinUCB-Perf+IPC'].mem)+'% on P), and I/O-bound processes are split ('+Math.round(100*X.place['LinUCB-Perf+IPC'].io)+'% on P) because their reward is nearly indifferent. LinUCB-Perf without IPC cannot separate CPU-bound from memory-bound processes and spreads both ('+Math.round(100*X.place['LinUCB-Perf'].cpu)+'% and '+Math.round(100*X.place['LinUCB-Perf'].mem)+'% on P). LinUCB-Orig sends nearly everything to E ('+Math.round(100*X.place['LinUCB-Orig'].cpu)+'% of the CPU-bound on P, the other types at or below '+Math.round(100*X.place['LinUCB-Orig'].burst)+'%), as predicted by the reward analysis of Section 3.8.'),
FIG('fig13_place.png',400,'Fraction of time each process type spends on the P-group under each policy (mean over 10 seeds).'),
P(FX('fig14_theta.png')+' shows the weights learned by the shared bandit of one seed (features as in '+TX('features')+'). The IPC weight is the clearest signal: it is '+X.theta[0][5].toFixed(2)+' for the P arm but '+X.theta[1][5].toFixed(2)+' for the E arm, so a high IPC lowers the predicted reward of the E-group by about '+(X.theta[0][5]-X.theta[1][5]).toFixed(2)+' relative to P, which is the rule “compute-bound processes need the fast cores”. The intercept of the E arm ('+X.theta[1][0].toFixed(2)+') exceeds that of the P arm ('+X.theta[0][0].toFixed(2)+'), reflecting the energy saving available to processes that tolerate the slower cores. The involuntary-switch weights are almost identical for both arms ('+X.theta[0][3].toFixed(2)+' and '+X.theta[1][3].toFixed(2)+'), so contention alone does not favour one group, and the CPU-share weight is negative for E ('+X.theta[1][1].toFixed(2)+') and near zero for P ('+X.theta[0][1].toFixed(2)+'). These values come from a single seed and serve interpretation, not population estimates.'),
FIG('fig14_theta.png',380,'Weights learned by the shared LinUCB-Perf+IPC bandit for each arm at the end of one 300-cycle episode (seed 0).'),
H2('5.8 Distribution Across Seeds and Steady State'),
P(FX('fig11_box.png')+' shows the spread of throughput and efficiency over the 30 seeds. The 95% confidence half-width of the throughput of LinUCB-Perf+IPC is '+f3(S['LinUCB-Perf+IPC'].thr[2])+', against '+f3(S['LinUCB-Orig'].thr[2])+' for LinUCB-Orig and '+f3(S['LinUCB-Perf'].thr[2])+' for LinUCB-Perf, so its advantage is consistent across seeds rather than driven by a few of them. All averages so far include the learning phase. '+FX('fig15_steady.png')+' restricts them to the last 100 cycles: the throughput of LinUCB-Perf+IPC is '+f3(v('LinUCB-Perf+IPC','thr_s'))+' there against '+f3(v('LinUCB-Perf+IPC','thr'))+' over all cycles, and the shortfall relative to Best-Static is '+(100*(1-v('LinUCB-Perf+IPC','thr_s')/v('Best-Static','thr_s'))).toFixed(1)+'% in steady state against '+(100*(1-v('LinUCB-Perf+IPC','thr')/v('Best-Static','thr'))).toFixed(1)+'% over the whole episode.'),
FIG('fig11_box.png',560,'Distribution over 30 seeds of normalised throughput (a) and efficiency (b); boxes show the interquartile range and whiskers the extremes up to 1.5 times the interquartile range.'),
FIG('fig15_steady.png',560,'Normalised throughput (a) and efficiency (b) over all 300 cycles versus the last 100 cycles.'),
P(FX('fig12_heat.png')+' condenses all metrics. No policy is best in every column: Best-Static leads in throughput, Always-E in power and efficiency, and the label-based and heuristic rules in interactive latency, while the learned policy with IPC combines high throughput with moderate power and a low migration rate.'),
FIG('fig12_heat.png',520,'Mean value of every metric for every policy; shading indicates relative rank within each column (darker is better, with lower-is-better metrics reversed).'),
P(FX('fig20_radar.png')+' shows the same information as a radar chart for five policies; each axis is scaled so that the outer ring is the best policy on that metric. The enclosed area is '+X2.radar_area['Best-Static'].toFixed(2)+' for Best-Static, '+X2.radar_area['LinUCB-Perf+IPC'].toFixed(2)+' for AIZEN with IPC, '+X2.radar_area['Random'].toFixed(2)+' for Random, '+X2.radar_area['LinUCB-Orig'].toFixed(2)+' for LinUCB-Orig and '+X2.radar_area['Heuristic'].toFixed(2)+' for the README heuristic; a larger area means a better balance over the seven metrics.'),
FIG('fig20_radar.png',380,'Radar chart of seven normalised metrics for five policies (outer ring = best policy on that metric).'),
H2('5.9 Answers to the Research Questions'),
BUL('**RQ1.** No. With reward (5) the policy behaves as “prefer E”: its throughput is '+f3(v('LinUCB-Orig','thr'))+' against '+f3(v('LinUCB-Perf','thr'))+' with reward (6), a loss of '+(100*(1-v('LinUCB-Orig','thr')/v('LinUCB-Perf','thr'))).toFixed(0)+'%, and only '+Math.round(100*X.place['LinUCB-Orig'].cpu)+'% of the CPU-bound processes are placed on P.'),
BUL('**RQ2.** The IPC-enabled policy reaches '+f3(v('LinUCB-Perf+IPC','thr'))+', which is '+(100*v('LinUCB-Perf+IPC','thr')/v('Best-Static','thr')).toFixed(0)+'% of Best-Static ('+f3(v('Best-Static','thr'))+'), '+(100*(v('LinUCB-Perf+IPC','thr')/v('Heuristic','thr')-1)).toFixed(0)+'% above the README heuristic and '+(100*(v('LinUCB-Perf+IPC','thr')/v('Random','thr')-1)).toFixed(0)+'% above random placement.'),
BUL('**RQ3.** The reward matters most (+'+(100*(v('LinUCB-Perf','thr')/v('LinUCB-Orig','thr')-1)).toFixed(0)+'% throughput from (5) to (6)), followed by the IPC feature (+'+(100*(v('LinUCB-Perf+IPC','thr')/v('LinUCB-Perf','thr')-1)).toFixed(0)+'%). The energy weight λ moves the operating point along the throughput–power frontier, whereas α has only a minor effect.'),
BUL('**RQ4.** The IPC policy migrates '+v('LinUCB-Perf+IPC','mig').toFixed(1)+' times per process per minute (against '+v('LinUCB-Perf','mig').toFixed(1)+' without IPC), its interactive p95 latency is '+v('LinUCB-Perf+IPC','lat95').toFixed(1)+' ms against about 2 ms for the label-based rules, and one bandit update takes about '+R.bench.sm_us.toFixed(0)+' µs.'),
H2('5.10 Discussion and Threats to Validity'),
BUL('**Simulation, not hardware.** The core speeds, power values, IPC feature and latency model are assumptions. Absolute numbers will differ on a real hybrid CPU; the qualitative findings (reward matters, IPC separates process types, learned policies balance load) need confirmation on Linux hybrid hardware with measured energy.'),
BUL('**Oracle gap.** Best-Static, which knows the workload in advance, is still 5% better in throughput. The online policy pays for learning and for re-evaluating placements every cycle.'),
BUL('**Interaction between processes.** One shared bandit makes decisions for processes that compete for the same cores, so the reward of one process depends on the others’ actions; the bandit assumption of independent rounds is only approximate.'),
BUL('**Metric choice.** The service term uses delivered work divided by demand, which the simulator knows exactly; on a real system it must be estimated from retired-instruction counters or CPU share.'),
BUL('**Statistics.** Seeds share one model, so significance indicates consistency within the model only.'));
add(H1('6. CONCLUSION',true),
P('This report presented AIZEN, a user-space contextual-bandit governor that chooses between P-core and E-core groups for each process from operating-system telemetry. Auditing the prototype showed that its reward, which combines involuntary context switches with a constant energy proxy, drives the policy toward low power without regard to delivered work, and that the native evaluation artefacts could not support any claim. Replacing the reward with a service-minus-energy signal and adding an IPC feature produced a policy that, in a calibrated 4P+4E simulation with 30 seeds, achieves 0.827 normalised throughput: 46% above the README heuristic, 13% above random placement and 95% of a hindsight-optimal static partition, with about 2.4 migrations per process per minute and a negligible computational cost. The energy weight gives a simple control over the power–performance trade-off.'),
P('The main limitations are the simulated platform and the higher tail latency of interactive processes. **Future work** includes (i) re-running the study on Linux with a hybrid CPU, measuring energy with RAPL and IPC with performance counters, and reading run-queue delay from the kernel to add a latency term to the reward; (ii) a corrected native harness that keeps persistent process handles, measures all conditions over identical windows and uses oblivious baselines; (iii) change-point detection such as CUSUM [20] to discount stale statistics when a process changes phase; (iv) a switching-cost penalty and minimum dwell time to avoid thrashing; and (v) comparison with Thompson sampling [24] and with the Linux energy-aware scheduler.'));
const REFS=[
'R. Kumar, K. I. Farkas, N. P. Jouppi, P. Ranganathan, and D. M. Tullsen, “Single-ISA heterogeneous multi-core architectures: The potential for processor power reduction,” in Proc. 36th Annu. IEEE/ACM Int. Symp. Microarchitecture (MICRO), 2003, pp. 81–92.',
'P. Greenhalgh, “big.LITTLE processing with ARM Cortex-A15 & Cortex-A7,” ARM Ltd., White Paper, Sep. 2011.',
'“Energy Aware Scheduling,” Linux Kernel Documentation. [Online]. Available: https://docs.kernel.org/scheduler/sched-energy.html',
'C. S. Pabla, “Completely fair scheduler,” Linux Journal, no. 184, Aug. 2009.',
'J.-P. Lozi, B. Lepers, J. Funston, F. Gaud, V. Quéma, and A. Fedorova, “The Linux scheduler: A decade of wasted cores,” in Proc. 11th Eur. Conf. Computer Systems (EuroSys), 2016, Art. no. 1.',
'C. Delimitrou and C. Kozyrakis, “Quasar: Resource-efficient and QoS-aware cluster management,” in Proc. 19th Int. Conf. Architectural Support for Programming Languages and Operating Systems (ASPLOS), 2014, pp. 127–144.',
'H. Mao, M. Schwarzkopf, S. B. Venkatakrishnan, Z. Meng, and M. Alizadeh, “Learning scheduling algorithms for data processing clusters,” in Proc. ACM SIGCOMM, 2019, pp. 270–288.',
'R. S. Sutton and A. G. Barto, Reinforcement Learning: An Introduction, 2nd ed. Cambridge, MA, USA: MIT Press, 2018.',
'P. Auer, “Using confidence bounds for exploitation-exploration trade-offs,” J. Mach. Learn. Res., vol. 3, pp. 397–422, 2002.',
'L. Li, W. Chu, J. Langford, and R. E. Schapire, “A contextual-bandit approach to personalized news article recommendation,” in Proc. 19th Int. Conf. World Wide Web (WWW), 2010, pp. 661–670.',
'W. Chu, L. Li, L. Reyzin, and R. E. Schapire, “Contextual bandits with linear payoff functions,” in Proc. 14th Int. Conf. Artificial Intelligence and Statistics (AISTATS), 2011, pp. 208–214.',
'Y. Abbasi-Yadkori, D. Pál, and C. Szepesvári, “Improved algorithms for linear stochastic bandits,” in Advances in Neural Information Processing Systems (NeurIPS), vol. 24, 2011.',
'T. Lattimore and C. Szepesvári, Bandit Algorithms. Cambridge, U.K.: Cambridge Univ. Press, 2020.',
'G. Rodola, “psutil: Cross-platform library for process and system monitoring in Python,” GitHub repository. [Online]. Available: https://github.com/giampaolo/psutil',
'A. Silberschatz, P. B. Galvin, and G. Gagne, Operating System Concepts, 10th ed. Hoboken, NJ, USA: Wiley, 2018.',
'R. K. Jain, D.-M. W. Chiu, and W. R. Hawe, “A quantitative measure of fairness and discrimination for resource allocation in shared computer systems,” Digital Equipment Corp., Tech. Rep. DEC-TR-301, 1984.',
'F. Wilcoxon, “Individual comparisons by ranking methods,” Biometrics Bulletin, vol. 1, no. 6, pp. 80–83, 1945.',
'S. Holm, “A simple sequentially rejective multiple test procedure,” Scand. J. Statist., vol. 6, no. 2, pp. 65–70, 1979.',
'J. Cohen, Statistical Power Analysis for the Behavioral Sciences, 2nd ed. Hillsdale, NJ, USA: Lawrence Erlbaum, 1988.',
'E. S. Page, “Continuous inspection schemes,” Biometrika, vol. 41, no. 1/2, pp. 100–115, 1954.',
'Linux man-pages project, “sched_setaffinity(2): set and get a thread’s CPU affinity mask,” Linux Programmer’s Manual. [Online]. Available: https://man7.org/linux/man-pages/man2/sched_setaffinity.2.html',
'“proc(5): process information pseudo-filesystem,” Linux Programmer’s Manual. [Online]. Available: https://man7.org/linux/man-pages/man5/proc.5.html',
'J. Dean and L. A. Barroso, “The tail at scale,” Commun. ACM, vol. 56, no. 2, pp. 74–80, 2013.',
'W. R. Thompson, “On the likelihood that one unknown probability exceeds another in view of the evidence of two samples,” Biometrika, vol. 25, no. 3/4, pp. 285–294, 1933.',
'J. Sherman and W. J. Morrison, “Adjustment of an inverse matrix corresponding to a change in one element of a given matrix,” Ann. Math. Statist., vol. 21, no. 1, pp. 124–127, 1950.',
'A. E. Hoerl and R. W. Kennard, “Ridge regression: Biased estimation for nonorthogonal problems,” Technometrics, vol. 12, no. 1, pp. 55–67, 1970.',
'V. Mnih et al., “Human-level control through deep reinforcement learning,” Nature, vol. 518, pp. 529–533, 2015.'];
const POL2=['Always-P','Always-E','Random','Static-Label','Best-Static','Heuristic','LinUCB-Orig','LinUCB-Perf','LinUCB-Perf+IPC'];
const CODE=ls=>ls.map(l=>new Paragraph({spacing:{after:0,line:240},shading:{type:ShadingType.CLEAR,fill:'F2F2F2',color:'auto'},children:[new TextRun({text:l===''?' ':l,font:'Courier New',size:16})]}));
add(H1('APPENDIX A: KEY CODE LISTINGS',true),P('The listings are taken from the simulator (sim.py) that produced the results of Section 5. They show the bandit (Sherman–Morrison form), the two reward functions and the contention model.'),
H2('A.1 LinUCB with Sherman–Morrison update'),
CODE(['class LinUCB:','    def __init__(s, d, alpha, rng):','        s.Ai = np.stack([np.eye(d)] * 2)   # A^-1 of each arm','        s.b = np.zeros((2, d)); s.al = alpha; s.r = rng','    def select(s, x):','        sc = [(s.Ai[a] @ s.b[a]) @ x + s.al * np.sqrt(max(x @ s.Ai[a] @ x, 0))','              for a in (0, 1)]','        if abs(sc[0] - sc[1]) < 1e-12: return int(s.r.integers(2))','        return int(np.argmax(sc))','    def update(s, a, x, r):             # rank-one update, O(d^2)','        Ax = s.Ai[a] @ x','        s.Ai[a] -= np.outer(Ax, Ax) / (1 + x @ Ax)','        s.b[a] += r * x']),
H2('A.2 Reward functions'),
CODE(['# proposed reward, Eq. (6): served fraction of demand minus attributed energy','sat = np.clip(prog / d * noise, 0, 1.2)','R = sat - lam * cpu * np.where(g == 0, 1.0, 0.30)      # lam = 0.5','# original prototype reward, Eq. (5)','R_orig = -(0.7 * np.minimum(invol / 100, 3) + 0.3 * np.where(g == 0, 1.0, 0.3))']),
H2('A.3 Contention model'),
CODE(['for k, n in ((0, NP), (1, NE)):                # P-group, E-group','    m = (g == k); Dg = d[m].sum()','    if Dg > 0: share[m] = d[m] * min(1.0, n / Dg)  # Eq. (7)','speed = np.where(g == 0, 1.0, sigma_E); prog = share * speed','power = NP*IDLE_P + NE*IDLE_E + DYN_P*min(NP, D_P) + DYN_E*min(NE, D_E)   # Eq. (8)']),
H1('APPENDIX B: REPRODUCTION INSTRUCTIONS',true),P('All results can be regenerated on any machine with Python 3 and the packages below. The seeds are fixed, so repeated runs give identical numbers.'),
CODE(['pip install numpy scipy matplotlib psutil','python sim.py            # about 3 min on one core: results.json, raw_per_seed.csv','python extra.py          # per-type placement and learned weights: extra.json','python figs.py && python figs2.py   # all figures used in this report']),
P('The files results.json and raw_per_seed.csv contain the per-policy summaries and the per-seed values behind every table and figure, and extra.json contains the data for the placement heat map and the learned weights.',{before:120}),
H1('APPENDIX C: SUPPLEMENTARY RESULTS',true),P(TX('steady')+' lists the steady-state results (cycles 200–300) and the involuntary-switch rate of every policy.'),
TBL('Steady-State and Supplementary Results',['Policy','Throughput (steady)','Power (steady)','Efficiency (steady)','Efficiency (all)','Invol. switches / s'],POL2.map(p=>[p,pm(S[p].thr_s),pm(S[p].pwr_s,2),pm(S[p].eff_s),pm(S[p].eff),pm(S[p].inv,2)]),[2,1.7,1.5,1.7,1.5,1.5],{size:16}));
reg.push({k:'h',l:1,t:'REFERENCES'});
add(new Paragraph({heading:'Heading1',pageBreakBefore:true,keepNext:true,children:[new TextRun({text:'REFERENCES',bold:true,size:26,font:FONT})]}));
Object.keys(CN).sort((a,b)=>CN[a]-CN[b]).forEach(k=>add(new Paragraph({alignment:AlignmentType.LEFT,spacing:{after:70,line:252},tabStops:[{type:TabStopType.LEFT,position:500}],indent:{left:500,hanging:500},children:[new TextRun({children:['['+CN[k]+']',new Tab(),REFS[k-1]],size:20,font:FONT})]})));
// ------------- FRONT MATTER -------------
function ABB(){const rows=[['P-core / E-core','Performance core / Efficiency core'],['CFS','Completely Fair Scheduler'],['EAS','Energy Aware Scheduling'],['UCB','Upper confidence bound'],['LinUCB','Linear contextual bandit with UCB exploration'],['SM','Sherman–Morrison rank-one inverse update'],['IPC','Instructions per cycle'],['RQ','Research question'],['CI','Confidence interval'],['d_z','Paired Cohen’s effect size'],['PID','Process identifier'],['RAPL','Running Average Power Limit (Intel energy counters)'],['p95','95th percentile']];
const line={style:BorderStyle.SINGLE,size:6,color:'000000'},none={style:BorderStyle.NONE,size:0,color:'FFFFFF'};const cw=[2600,TW-2600];
const mk=(r,hd,last)=>new TableRow({children:r.map((t,i)=>new TableCell({width:{size:cw[i],type:WidthType.DXA},margins:{top:50,bottom:50,left:80,right:80},borders:{top:hd?line:none,bottom:(hd||last)?line:none,left:none,right:none},children:[new Paragraph({children:runs(t,{size:21,bold:hd})})]}))});
return new Table({width:{size:TW,type:WidthType.DXA},columnWidths:cw,rows:[mk(['Abbreviation','Meaning'],true,false),...rows.map((r,i)=>mk(r,false,i===rows.length-1))]});}
const pg=k=>String(PG[k]??'0');
const cen=(t,o={})=>new Paragraph({alignment:C,spacing:{after:o.after??120,before:o.before||0},children:runs(t,o)});
const FM=[];
FM.push(cen('AMRITA VISHWA VIDYAPEETHAM',{bold:true,size:32,before:200}),cen('Amrita School of Engineering, Chennai',{size:26}),cen('Department of Electronics and Communication Engineering',{size:24,after:500}),
cen('AIZEN ALGORITHM REPORT',{bold:true,size:30,after:80}),cen('OPERATING SYSTEMS CAPSTONE PROJECT',{bold:true,size:24,after:500}),
cen('AIZEN: A Contextual-Bandit Algorithm for Routing Processes Between Performance and Efficiency Core Groups in User Space',{bold:true,size:36,after:600}));
const nb={style:BorderStyle.NONE,size:0,color:'FFFFFF'},nbs={top:nb,bottom:nb,left:nb,right:nb};
const ac=(t,w,b)=>new TableCell({width:{size:w,type:WidthType.DXA},borders:nbs,margins:{top:60,bottom:60,left:80,right:80},children:[new Paragraph({alignment:C,children:runs(t,{size:24,bold:b})})]});
FM.push(new Table({width:{size:TW,type:WidthType.DXA},columnWidths:[1700,1700,3000,2626],rows:[
 new TableRow({children:[ac('Author',1700,true),ac('Role',1700,true),ac('Roll Number',3000,true),ac('Programme',2626,true)]}),
 new TableRow({children:[ac('Priyanraj',1700),ac('Main author',1700),ac('CH.EN.U4CCE25020',3000),ac('B.Tech CCE',2626)]}),
 new TableRow({children:[ac('Naveen',1700),ac('Co-author',1700),ac('CH.EN.U4CCE25014',3000),ac('B.Tech CCE',2626)]})]}),
cen('',{after:500}),cen('Submitted to: Dr. Dasari Naga Vinod',{size:24,after:80}),cen('Submission deadline: 10 October 2026',{size:24,after:80}),cen('October 2026',{size:24}));
FM.push(new Paragraph({children:[new PageBreak()]}));
const tocLine=(t,p,ind,b)=>new Paragraph({tabStops:[{type:TabStopType.RIGHT,position:TW,leader:LEAD}],spacing:{after:70},indent:{left:ind},children:[new TextRun({children:[t,new Tab(),p],font:FONT,size:22,bold:b})]});
FM.push(cen('TABLE OF CONTENTS',{bold:true,size:26,after:200}),tocLine('List of Abbreviations',pg('fm:ABBR'),0,true),tocLine('Abstract',pg('h:ABSTRACT'),0,true));
reg.filter(r=>r.k==='h'&&r.l>0).forEach(r=>FM.push(tocLine(r.t,pg('h:'+r.t),r.l===1?0:400,r.l===1)));
FM.push(new Paragraph({children:[new PageBreak()]}),cen('TABLE OF FIGURES & TABLES',{bold:true,size:26,after:200}),new Paragraph({spacing:{after:100},children:runs('List of Figures',{bold:true})}));
reg.filter(r=>r.k==='f').sort((a,b)=>a.n-b.n).forEach(r=>FM.push(tocLine('Fig. '+r.n+'. '+(r.t.length>88?r.t.slice(0,85)+'…':r.t),pg('f:'+r.n),0,false)));
FM.push(new Paragraph({spacing:{before:200,after:100},children:runs('List of Tables',{bold:true})}));
reg.filter(r=>r.k==='t').sort((a,b)=>ROM.indexOf(a.n)-ROM.indexOf(b.n)).forEach(r=>FM.push(tocLine('Table '+r.n+'. '+r.t,pg('t:'+r.n),0,false)));
FM.push(new Paragraph({children:[new PageBreak()]}),cen('LIST OF ABBREVIATIONS',{bold:true,size:26,after:200}),ABB(),new Paragraph({children:[new PageBreak()]}),new Paragraph({heading:'Heading1',alignment:C,keepNext:true,children:[new TextRun({text:'ABSTRACT',bold:true,size:26,font:FONT})]}),
P('Modern processors increasingly combine fast, power-hungry Performance (P) cores with slower, energy-frugal Efficiency (E) cores, yet a general-purpose scheduler must decide where each process should run with little knowledge of what it will do next. This report presents AIZEN, a user-space governor that treats the choice between the P-core group and the E-core group as a contextual-bandit problem solved with LinUCB. In every one-second cycle the governor builds a context vector for each process from operating-system telemetry (CPU share, voluntary and involuntary context-switch rates, current placement and, optionally, an IPC estimate), selects a core group with an upper-confidence-bound rule, applies it through the CPU-affinity interface, and learns from a measured reward. We audit the original prototype, show that a reward made of involuntary context switches and a constant energy proxy drives the policy toward low power at the expense of throughput, and replace it with a service-minus-energy reward. Because the development machine has neither a hybrid CPU nor trustworthy involuntary-switch counters, the quantitative evaluation uses a calibrated discrete-time simulator of a 4P+4E processor running twelve processes for 300 cycles over 30 seeds. The proposed policy (AIZEN with the IPC feature, labelled LinUCB-Perf+IPC in the tables) reaches 0.827 normalised throughput, 46% above the README heuristic (0.565), 13% above random placement (0.731) and within 5% of a hindsight-optimal static partition (0.870) that must know every process type in advance, at 5.30 relative power units. Adding an IPC feature reduces migrations from 12.1 to 2.4 per process per minute. The study also exposes a limitation: the tail latency of interactive processes is higher (13.2 ms versus about 2 ms for label-based routing), which motivates a latency-aware reward. Code, raw per-seed data and figures are provided for reproduction.',{before:100}),
P('**Index Terms**—heterogeneous multicore, CPU scheduling, contextual bandit, LinUCB, energy efficiency, operating systems.',{before:100}));
reg.push({k:'h',l:0,t:'ABSTRACT'});
fs.writeFileSync('reg.json',JSON.stringify(reg));
const HDR=()=>new Header({children:[new Paragraph({alignment:AlignmentType.RIGHT,children:runs('AIZEN Algorithm Report — Operating Systems Capstone',{size:18,italics:true})})]});
const FTR=()=>new Footer({children:[new Paragraph({alignment:C,children:[new TextRun({children:[PageNumber.CURRENT],size:20,font:FONT})]})]});
const doc=new Document({creator:'Priyanraj; Naveen',title:'AIZEN Algorithm Report',
 styles:{default:{document:{run:{font:FONT,size:22}}},paragraphStyles:[
  {id:'Heading1',name:'Heading 1',basedOn:'Normal',next:'Normal',quickFormat:true,run:{size:26,bold:true,font:FONT,color:'000000'},paragraph:{spacing:{before:300,after:120},outlineLevel:0}},
  {id:'Heading2',name:'Heading 2',basedOn:'Normal',next:'Normal',quickFormat:true,run:{size:23,bold:true,italics:true,font:FONT,color:'000000'},paragraph:{spacing:{before:200,after:80},outlineLevel:1}}]},
 numbering:{config:[{reference:'bul',levels:[{level:0,format:LevelFormat.BULLET,text:'•',alignment:AlignmentType.LEFT,style:{paragraph:{indent:{left:540,hanging:270}}}}]},
  {reference:'num',levels:[{level:0,format:LevelFormat.DECIMAL,text:'%1.',alignment:AlignmentType.LEFT,style:{paragraph:{indent:{left:540,hanging:300}}}}]}]},
 sections:[{properties:{titlePage:true,page:{size:{width:11906,height:16838},margin:{top:1440,right:1440,bottom:1440,left:1440},pageNumbers:{start:1,formatType:D.NumberFormat.LOWER_ROMAN}}},headers:{default:HDR(),first:new Header({children:[new Paragraph('')]})},footers:{default:FTR(),first:new Footer({children:[new Paragraph('')]})},children:FM},
 {properties:{page:{size:{width:11906,height:16838},margin:{top:1440,right:1440,bottom:1440,left:1440},pageNumbers:{start:1,formatType:D.NumberFormat.DECIMAL}}},headers:{default:HDR()},footers:{default:FTR()},children:B}]});
Packer.toBuffer(doc).then(b=>{fs.writeFileSync('AIZEN_Algorithm_Report.docx',b);console.log('docx ok',b.length);});
