import os
import sys
import time
import json
import psutil
import tempfile
import warnings
from collections import deque
from sklearn.ensemble import RandomForestClassifier

# Suppress sklearn warnings about lack of feature names
warnings.filterwarnings('ignore')

LOG_FILE = 'scheduler_log.csv'
PID_FILE = 'pids.txt'

class AIScheduler:
    def __init__(self):
        self.p_cores, self.e_cores = self.detect_cores()
        self.history = {}
        
        # Classifier Setup: Lightweight RandomForest
        self.clf = RandomForestClassifier(n_estimators=10, max_depth=3)
        self.training_data_x = []
        self.training_data_y = [] # 0: Heavy, 1: Light
        self.model_fitted = False
        
    def detect_cores(self):
        """Attempts to read hardware topology. Falls back cleanly."""
        p_cores, e_cores = [], []
        try:
            import glob
            core_types = glob.glob("/sys/devices/system/cpu/cpu*/topology/core_type")
            for file in core_types:
                cpu_id = int(file.split('cpu')[1].split('/')[0])
                with open(file, 'r') as f:
                    c_type = int(f.read().strip())
                if c_type == 0: p_cores.append(cpu_id)
                elif c_type == 1: e_cores.append(cpu_id)
                
            if p_cores and e_cores:
                print(f"[SYSFS] Detected P-cores: {p_cores}, E-cores: {e_cores}")
                return p_cores, e_cores
        except Exception:
            pass
            
        # Fallback 1: Try to detect via max CPU frequency (P-cores are typically faster)
        try:
            import glob
            freqs = {}
            freq_files = glob.glob("/sys/devices/system/cpu/cpu*/cpufreq/cpuinfo_max_freq")
            for file in freq_files:
                cpu_id = int(file.split('cpu')[1].split('/')[0])
                with open(file, 'r') as f:
                    freqs[cpu_id] = int(f.read().strip())
            
            if freqs:
                unique_freqs = sorted(list(set(freqs.values())), reverse=True)
                if len(unique_freqs) > 1:
                    threshold = (unique_freqs[0] + unique_freqs[-1]) / 2
                    p_cores = [c for c, f in freqs.items() if f > threshold]
                    e_cores = [c for c, f in freqs.items() if f <= threshold]
                    print(f"[FREQ FALLBACK] Detected P-cores: {p_cores}, E-cores: {e_cores}")
                    return p_cores, e_cores
        except Exception:
            pass
            
        print("[FALLBACK] Hardware topology undetectable. Splitting adjacent cores 50/50.")
        total = os.cpu_count() or 4
        half = total // 2
        return list(range(half)), list(range(half, total))

    def get_active_pids(self):
        """Reads target PIDs safely and checks lifecycle bounds."""
        active = []
        try:
            with open(PID_FILE, 'r') as f:
                for line in f:
                    if not line.strip(): continue
                    try:
                        data = json.loads(line)
                        pid = data['pid']
                        start_time = data['start_time']
                        
                        p = psutil.Process(pid)
                        
                        # Security boundary: Only act on processes we own, and verify PID has not been 
                        # recycled by cross-checking process creation time against the recorded spawn time.
                        if p.create_time() == start_time and p.username() == psutil.Process().username():
                            active.append((pid, data['type']))
                    except Exception as e:
                        print("Exception in get_active_pids:", e)
                        continue
        except FileNotFoundError:
            pass
        return active

    def run(self):
        print("[SCHEDULER] Starting AI Scheduler loop...")
        while True:
            cycle_start = time.time()
            active = self.get_active_pids()
            rows = []
            
            for pid, true_type in active:
                try:
                    p = psutil.Process(pid)
                    # Non-blocking CPU measurement after first call
                    cpu = p.cpu_percent(interval=0.0) 
                    ctx = p.num_ctx_switches()
                    
                    if pid not in self.history:
                        p.cpu_percent(interval=None) # Initialize psutil CPU baseline measurement
                        self.history[pid] = {'vol': ctx.voluntary, 'time': cycle_start}
                        continue
                        
                    dt = cycle_start - self.history[pid]['time']
                    if dt <= 0: continue
                    vol_rate = (ctx.voluntary - self.history[pid]['vol']) / dt
                    
                    self.history[pid]['vol'] = ctx.voluntary
                    self.history[pid]['time'] = cycle_start
                    
                    # Track inference latency
                    t0_inf = time.time()
                    features = [cpu, vol_rate]
                    
                    # --- Bootstrapping Heuristic ---
                    # High CPU + Low Context Switches = Heavy Loop
                    # This must exist as a fallback due to the cold-start problem (ML model has no labels at boot).
                    heur_class = 'Heavy' if (cpu > 20 and vol_rate < 500) else 'Light'
                    
                    # Online Training Collection (Labels generated by heuristic initially)
                    self.training_data_x.append(features)
                    self.training_data_y.append(0 if heur_class == 'Heavy' else 1)
                    
                    # Memory cap on online training dataset size
                    if len(self.training_data_x) > 1000:
                        self.training_data_x = self.training_data_x[-1000:]
                        self.training_data_y = self.training_data_y[-1000:]
                        
                    final_class = heur_class
                    mode = 'Heuristic'
                    confidence = 1.0
                    
                    # Transition to ML strategy once enough data is captured
                    if len(self.training_data_x) > 50:
                        if not self.model_fitted:
                            self.clf.fit(self.training_data_x, self.training_data_y)
                            self.model_fitted = True
                        try:
                            probs = self.clf.predict_proba([features])[0]
                            pred_idx = probs.argmax()
                            confidence = probs[pred_idx]
                            final_class = 'Heavy' if pred_idx == 0 else 'Light'
                            mode = 'RandomForest'
                        except Exception:
                            pass
                            
                    latency = (time.time() - t0_inf) * 1000
                    
                    # --- Core Enforcement ---
                    target_cores = self.p_cores if final_class == 'Heavy' else self.e_cores
                    try:
                        # Utilizing psutil cpu_affinity over raw os.sched_setaffinity for OS cross-compatibility safety checks
                        p.cpu_affinity(target_cores)
                    except (psutil.NoSuchProcess, psutil.AccessDenied, AttributeError):
                        pass 
                        
                    rows.append(f"{cycle_start},{pid},{true_type},{final_class},\"{target_cores}\",{confidence:.2f},{cpu:.1f},{latency:.2f},{mode}\n")
                    
                except Exception as e:
                     # Process may have vanished just in this exact millisecond window
                    print("Exception in run loop:", e, type(e))
                    pass
                    
            if rows:
                log_lines = []
                if os.path.exists(LOG_FILE):
                    try:
                        with open(LOG_FILE, 'r') as f:
                            log_lines = f.readlines()[-300:] # Cap dashboard lookback to 300 logs
                    except:
                        pass
                log_lines.extend(rows)
                
                # --- Atomic Logging ---
                # We write to a temporary file in the local directory and use os.replace
                # This guarantees that the stream reader (the Streamlit dashboard) never reads a partially written row.
                dir_name = os.path.dirname(os.path.abspath(LOG_FILE)) or '.'
                tmp_fd, tmp_path = tempfile.mkstemp(dir=dir_name)
                with os.fdopen(tmp_fd, 'w') as f:
                    if not log_lines or not log_lines[0].startswith("timestamp"):
                        f.write("timestamp,pid,true_type,classification,assigned_cores,confidence,cpu_percent,latency_ms,mode\n")
                    for line in log_lines:
                        if line.startswith("timestamp"): continue
                        f.write(line)
                os.replace(tmp_path, LOG_FILE)
                
            time.sleep(1.0)

if __name__ == '__main__':
    scheduler = AIScheduler()
    
    def shutdown_handler(signum, frame):
        """Fallback cleanup ensures no artificial core starvation if terminated."""
        print("\n[SCHEDULER] Shutting down. Resetting all affinities...")
        active = scheduler.get_active_pids()
        total_cores = os.cpu_count() or 4
        all_cores = list(range(total_cores))
        for pid, _ in active:
            try:
                p = psutil.Process(pid)
                p.cpu_affinity(all_cores)
            except:
                pass
        sys.exit(0)
        
    import signal
    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)
    
    scheduler.run()
