import pandas as pd
df = pd.read_csv('results.csv')
summary = df.tail(20).groupby('condition')[['mean_cpu_pct','mean_invol_ctx_switches','jain_fairness_index','heavy_task_completion_time']].mean().round(2)
with open('clean_output.txt', 'w') as f:
    f.write(summary.to_markdown())
