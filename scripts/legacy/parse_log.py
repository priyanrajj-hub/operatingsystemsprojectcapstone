import re, io, collections

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
    
    print('Condition | Mean CPU % | Invol Ctx/s | Jain Fairness | Heavy Complete(s)')
    print('---|---|---|---|---')
    for cond, trials in data.items():
        if trials:
            means = [sum(x)/len(x) for x in zip(*trials)]
            print(f'{cond} | {means[0]:.2f}% | {means[1]:.2f} | {means[2]:.2f} | {means[3]:.2f}s')

parse()

