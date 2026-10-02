import re

with open('static/app.js', 'r', encoding='utf-8') as f:
    text = f.read()

prefix = text.split('// ─────────────────────────────────────────────\n    // WebSocket + Fallback Polling')[0]

new_code = """// ─────────────────────────────────────────────
    // WebSocket + Fallback Polling + Demo Mock
    // ─────────────────────────────────────────────
    let ws = null;
    let reconnectTimer = null;
    let demoMode = false;
    let demoInterval = null;

    function setConnected(connected, isDemo=false) {
        if (connected && !isDemo) {
            pulseRing.classList.add('active');
            pulseRing.style.background = '#00f2fe';
            pulseRing.style.boxShadow = '0 0 10px #00f2fe';
            statusLabel.textContent = 'Live';
            statusLabel.style.color = '#fff';
        } else if (isDemo) {
            pulseRing.classList.add('active');
            pulseRing.style.background = '#fbbf24';
            pulseRing.style.boxShadow = '0 0 10px rgba(251, 191, 36, 0.6)';
            statusLabel.textContent = 'Simulation Engine';
            statusLabel.style.color = '#fbbf24';
        } else {
            pulseRing.classList.remove('active');
            pulseRing.style.background = 'var(--text-muted)';
            pulseRing.style.boxShadow = 'none';
            statusLabel.textContent = 'Reconnecting';
            statusLabel.style.color = 'var(--text-muted)';
        }
    }

    function startDemoSimulation() {
        if (demoMode) return;
        demoMode = true;
        setConnected(true, true);
        
        let fakeHist = [];
        let decCount = 450;
        let cumulativeRegret = 1.25;
        
        console.log("AI-DAX Lite fallback: Initializing Demo Simulation Engine");
        
        if (demoInterval) clearInterval(demoInterval);
        demoInterval = setInterval(() => {
            const timeNow = Date.now() / 1000;
            const cpuTotal = 25 + Math.random() * 60;
            const coreData = Array.from({length: 8}, () => Math.random() * 90);
            
            const numHeavy = Math.floor(Math.random() * 2) + 2;
            const numLight = 4 - numHeavy;
            
            decCount += 4;
            const currRegret = Math.max(0.01, Math.random() * 0.1);
            cumulativeRegret += currRegret;
            
            const fakeData = {
                system: {
                    cpu_percent_overall: cpuTotal,
                    memory_percent: 42 + Math.random()*5,
                    cpu_freq_current: 3100 + Math.random()*200,
                    cpu_count_physical: 4,
                    cpu_count_logical: 8,
                    memory_used_gb: (6.5 + Math.random()*0.5).toFixed(1),
                    memory_total_gb: 16.0,
                    cpu_percent_per_core: coreData
                },
                processes: [
                    { pid: 1024, action: 'P', decision_source: 'bandit', cpu_percent: 80 + Math.random()*15, vol_ctx_rate: 12, invol_ctx_rate: 15, confidence_ucb: 1.4, reward: -0.15, true_type: 'Heavy' },
                    { pid: 2048, action: 'P', decision_source: 'bandit', cpu_percent: 85 + Math.random()*10, vol_ctx_rate: 8, invol_ctx_rate: 10, confidence_ucb: 1.5, reward: -0.10, true_type: 'Heavy' },
                    { pid: 3012, action: 'E', decision_source: 'bandit', cpu_percent: 3 + Math.random()*5, vol_ctx_rate: 450, invol_ctx_rate: 1, confidence_ucb: 0.3, reward: -0.01, true_type: 'Light' },
                    { pid: 4056, action: 'E', decision_source: 'bandit', cpu_percent: 4 + Math.random()*4, vol_ctx_rate: 610, invol_ctx_rate: 2, confidence_ucb: 0.4, reward: -0.02, true_type: 'Light' }
                ].slice(0, numHeavy + numLight),
                bandit: {
                    heuristic_count: 50,
                    bandit_count: decCount,
                    cumulative_regret: cumulativeRegret,
                    heuristic_pct: Math.round(50 / (50 + decCount) * 100),
                    bandit_pct: Math.round(decCount / (50 + decCount) * 100),
                    total_decisions: 50 + decCount,
                    alpha_reward: 0.7,
                    beta_reward: 0.3
                }
            };
            
            const pCPU = (cpuTotal * 0.8) + (Math.random()*10);
            const eCPU = (cpuTotal * 0.2) + (Math.random()*10);
            const histEntry = { timestamp: timeNow, cpu_percent: pCPU, action: 'P' };
            const histEntryE = { timestamp: timeNow, cpu_percent: eCPU, action: 'E' };
            fakeHist.push(histEntry);
            fakeHist.push(histEntryE);
            if (fakeHist.length > 200) fakeHist.splice(0, 2);
            
            fakeData.history_tail = fakeHist;
            renderAll(fakeData);
        }, 1500);
    }

    function connectWS() {
        const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
        ws = new WebSocket(`${proto}//${location.host}/ws/live`);

        ws.onopen = () => {
            demoMode = false;
            if (demoInterval) clearInterval(demoInterval);
            setConnected(true);
            if (reconnectTimer) { clearTimeout(reconnectTimer); reconnectTimer = null; }
        };
        ws.onmessage = (e) => {
            try { renderAll(JSON.parse(e.data)); } catch (err) { console.error(err); }
        };
        ws.onclose = () => {
            if (!demoMode) setConnected(false);
            reconnectTimer = setTimeout(connectWS, 4000);
        };
        ws.onerror = () => ws.close();
    }

    async function poll() {
        if (demoMode) return;
        try {
            const [liveR, histR] = await Promise.all([
                fetch('/api/live').then(r => { if(!r.ok) throw new Error(); return r.json() }),
                fetch('/api/history?n=100').then(r => r.json()),
            ]);
            liveR.history_tail = histR.history || [];
            renderAll(liveR);
            setConnected(true);
        } catch {
            console.warn("Backend API unavailable. Starting Vercel Simulation Demo Mode.");
            startDemoSimulation();
        }
    }

    connectWS();
    setTimeout(() => {
        if (!ws || ws.readyState !== WebSocket.OPEN) {
            console.log('WS unavailable, falling back to polling');
            poll();
            setInterval(poll, 1500);
        }
    }, 1500);

})();
"""

final_text = prefix + new_code

with open('static/app.js', 'w', encoding='utf-8') as f:
    f.write(final_text)
