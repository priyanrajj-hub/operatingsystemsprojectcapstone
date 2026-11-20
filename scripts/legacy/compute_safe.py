import re, io, collections, json
import numpy as np
from scipy import stats

def parse():
    log = io.open('eval2.log', 'r', encoding='utf-16-le').read()
    current_cond = None
    data = collections.defaultdict(list)
    for line in log.split('\n'):
        if 'CONDITION:' in line:
            current_cond = line.split('CONDITION:')[-1].strip()
        elif 'Mean CPU:' in line and current_cond:
            m = re.search(r'Mean CPU:\s*([0-9.]+)% \| Mean Invol Ctx:\s*([0-9.]+) \| Jain:\s*([0-9.]+) \| Heavy Comp Time:\s*([0-9.]+)s', line)
            if m:
                data[current_cond].append((float(m.group(1)), float(m.group(2)), float(m.group(3)), float(m.group(4))))
    
    out = []
    out.append('| Condition | Mean CPU Load | Mean Involuntary Context Switches | Jain\\'s Fairness | Heavy Task Completion Time |')
    out.append('|---|---|---|---|---|')
    
    for cond, trials in data.items():
        if trials:
            c_arr = [x[0] for x in trials]
            ix_arr = [x[1] for x in trials]
            j_arr = [x[2] for x in trials]
            t_arr = [x[3] for x in trials]
            
            c_m, c_s = np.mean(c_arr), np.std(c_arr, ddof=1)
            ix_m, ix_s = np.mean(ix_arr), np.std(ix_arr, ddof=1)
            j_m, j_s = np.mean(j_arr), np.std(j_arr, ddof=1)
            t_m, t_s = np.mean(t_arr), np.std(t_arr, ddof=1)
            
            out.append(f'| {cond} | {c_m:.1f}% (±{c_s:.1f}) | {ix_m:.1f} (±{ix_s:.1f}) | {j_m:.2f} (±{j_s:.2f}) | {t_m:.1f}s (±{t_s:.1f}) |')
    
    out.append('\n### Paired T-Tests (vs bandit_adaptive)\n')
    if 'bandit_adaptive' in data:
        band = data['bandit_adaptive']
        if len(band) > 1:
            b_t = [x[3] for x in band]
            b_i = [x[1] for x in band]
            
            for cond in ['baseline_cfs', 'static_naive', 'heuristic_only']:
                if cond in data and len(data[cond]) == len(band):
                    c_t = [x[3] for x in data[cond]]
                    c_i = [x[1] for x in data[cond]]
                    _, p_t = stats.ttest_rel(c_t, b_t)
                    _, p_i = stats.ttest_rel(c_i, b_i)
                    out.append(f'- **{cond}**: Completion Time ={p_t:.4f}$, Involuntary Sw ={p_i:.4f}$')
    else:
        out.append('Error: No bandit_adaptive data found.')

    with open('stats.md', 'w') as f:
        f.write('\\n'.join(out))

parse()

