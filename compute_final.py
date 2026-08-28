import re, io, collections, json, scipy.stats as stats

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
    
    out_lines = []
    
    out_lines.append('| Condition | Mean CPU Load | Mean Involuntary Context Switches | Jain\\'s Fairness | Heavy Task Completion Time |')
    out_lines.append('|---|---|---|---|---|')
    
    for cond, trials in data.items():
        if trials:
            import numpy as np
            cpu_arr = [x[0] for x in trials]
            ctx_arr = [x[1] for x in trials]
            jain_arr = [x[2] for x in trials]
            time_arr = [x[3] for x in trials]
            
            c_m, c_s = np.mean(cpu_arr), np.std(cpu_arr, ddof=1)
            tx_m, tx_s = np.mean(ctx_arr), np.std(ctx_arr, ddof=1)
            j_m, j_s = np.mean(jain_arr), np.std(jain_arr, ddof=1)
            t_m, t_s = np.mean(time_arr), np.std(time_arr, ddof=1)
            
            out_lines.append(f'| {cond} | {c_m:.1f}% (±{c_s:.1f}) | {tx_m:.1f} (±{tx_s:.1f}) | {j_m:.2f} (±{j_s:.2f}) | {t_m:.1f}s (±{t_s:.1f}) |')
    
    out_lines.append('\n### Paired T-Test (P-values) against bandit_adaptive:')
    if 'bandit_adaptive' in data:
        bandit_trials = data['bandit_adaptive']
        if len(bandit_trials) > 1:
            band_comp = [x[3] for x in bandit_trials]
            band_invo = [x[1] for x in bandit_trials]
            
            for cond in ['baseline_cfs', 'static_naive', 'heuristic_only']:
                if cond in data and len(data[cond]) == len(bandit_trials):
                    cond_comp = [x[3] for x in data[cond]]
                    cond_invo = [x[1] for x in data[cond]]
                    _, p_comp = stats.ttest_rel(cond_comp, band_comp)
                    _, p_invo = stats.ttest_rel(cond_invo, band_invo)
                    
                    out_lines.append(f'- **{cond} vs Bandit**: Completion Time p={p_comp:.4f}, Invol Ctx p={p_invo:.4f}')

    
    with open('notify_message.txt', 'w', encoding='utf-8') as f:
        f.write('\n'.join(out_lines))

parse()

