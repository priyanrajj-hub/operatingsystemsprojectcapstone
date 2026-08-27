import multiprocessing
import time
import os
import json
import signal
import sys
import tempfile
import psutil

PID_FILE = 'pids.txt'

def heavy_worker():
    """Simulates CPU-bound work using a prime calculation loop."""
    while True:
        primes = []
        for possiblePrime in range(2, 5000):
            is_prime = True
            for num in range(2, possiblePrime):
                if possiblePrime % num == 0:
                    is_prime = False
                    break
            if is_prime:
                primes.append(possiblePrime)

def light_worker():
    """Simulates I/O-bound work with small file writes/reads and sleeps."""
    temp_file = tempfile.mktemp()
    while True:
        with open(temp_file, 'w') as f:
            f.write("a" * 1024 * 10)
        time.sleep(0.5)
        with open(temp_file, 'r') as f:
            f.read()
        time.sleep(0.5)

workers = []

def cleanup(signum=None, frame=None):
    """Gracefully terminates worker processes on exit."""
    print("\n[WORKLOAD GENERATOR] Stopping workers...")
    for w in workers:
        w.terminate()
        w.join()
    if os.path.exists(PID_FILE):
        try: 
            os.remove(PID_FILE)
        except: 
            pass
    sys.exit(0)

if __name__ == '__main__':
    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)
    
    N_HEAVY = 2
    M_LIGHT = 2
    
    # Initialize the tracking file.
    with open(PID_FILE, 'w') as f:
        pass
        
    print("[WORKLOAD GENERATOR] Spawning processes...")
    
    for i in range(N_HEAVY + M_LIGHT):
        w_type = 'Heavy' if i < N_HEAVY else 'Light'
        target = heavy_worker if w_type == 'Heavy' else light_worker
        p = multiprocessing.Process(target=target)
        p.start()
        workers.append(p)
        
        # Save exact creation time for robust PID-reuse validation
        start_time = psutil.Process(p.pid).create_time()
        with open(PID_FILE, 'a') as f:
            f.write(json.dumps({'pid': p.pid, 'type': w_type, 'start_time': start_time}) + '\n')
            
    print(f"[WORKLOAD GENERATOR] Running {N_HEAVY} Heavy and {M_LIGHT} Light processes.")
    
    try:
        # Keep main process alive to maintain workers
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        cleanup()
