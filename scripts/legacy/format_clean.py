import pandas as pd
import scipy.stats as stats

df = pd.read_csv('results.csv').tail(20)

print('--- METRICS ---')
summary = df.groupby('condition')[['mean_cpu_pct','mean_invol_ctx_switches','jain_fairness_index','heavy_task_completion_time']].agg(['mean', 'std']).round(2)
print(summary.to_csv())

print('\n--- P-VALUES ---')
bandit_invol = df[df['condition'] == 'bandit_adaptive']['mean_invol_ctx_switches']
for c in ['baseline_cfs', 'static_naive', 'heuristic_only']:
    c_invol = df[df['condition'] == c]['mean_invol_ctx_switches']
    if len(c_invol) == len(bandit_invol):
        _, p = stats.ttest_rel(c_invol, bandit_invol)
        print(f'{c}: p={p:.4f}')


