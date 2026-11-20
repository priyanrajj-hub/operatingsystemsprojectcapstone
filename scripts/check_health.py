import psutil

try:
    print(f"|CPU Utilization: {psutil.cpu_percent(1)}%|")
    mem = psutil.virtual_memory()
    print(f"|RAM Usage: {mem.percent}% ({mem.used / 1024**3:.2f}GB / {mem.total / 1024**3:.2f}GB)|")

    procs = list(psutil.process_iter(["name", "memory_info"]))
    procs.sort(
        key=lambda p: p.info["memory_info"].rss if p.info["memory_info"] else 0, reverse=True
    )

    print("\n|Top 5 RAM Hogs:|")
    for p in procs[:5]:
        print(f" - {p.info['name']}: {p.info['memory_info'].rss / 1024**2:.1f}MB")

except Exception as e:
    print("Error getting health info:", e)
