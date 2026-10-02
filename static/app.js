/* ═══════════════════════════════════════════════════════════════
   AI-DAX Lite v2 — Dashboard JS
   Animated background • SVG gauges • Core heatmap • Charts
   ═══════════════════════════════════════════════════════════════ */
(() => {
    'use strict';

    // ─────────────────────────────────────────────
    // Animated Background — Subtle Floating Grid
    // ─────────────────────────────────────────────
    const bgCanvas = document.getElementById('bgCanvas');
    const bgCtx = bgCanvas.getContext('2d');
    let particles = [];
    const PARTICLE_COUNT = 50;

    function resizeCanvas() {
        bgCanvas.width = window.innerWidth;
        bgCanvas.height = window.innerHeight;
    }
    window.addEventListener('resize', resizeCanvas);
    resizeCanvas();

    function initParticles() {
        particles = [];
        for (let i = 0; i < PARTICLE_COUNT; i++) {
            particles.push({
                x: Math.random() * bgCanvas.width,
                y: Math.random() * bgCanvas.height,
                vx: (Math.random() - 0.5) * 0.3,
                vy: (Math.random() - 0.5) * 0.3,
                r: Math.random() * 1.5 + 0.5,
                opacity: Math.random() * 0.3 + 0.05,
            });
        }
    }
    initParticles();

    function drawBg() {
        bgCtx.clearRect(0, 0, bgCanvas.width, bgCanvas.height);

        // Draw connection lines
        for (let i = 0; i < particles.length; i++) {
            for (let j = i + 1; j < particles.length; j++) {
                const dx = particles[i].x - particles[j].x;
                const dy = particles[i].y - particles[j].y;
                const dist = Math.sqrt(dx * dx + dy * dy);
                if (dist < 150) {
                    bgCtx.beginPath();
                    bgCtx.moveTo(particles[i].x, particles[i].y);
                    bgCtx.lineTo(particles[j].x, particles[j].y);
                    bgCtx.strokeStyle = `rgba(129, 140, 248, ${0.04 * (1 - dist / 150)})`;
                    bgCtx.lineWidth = 0.5;
                    bgCtx.stroke();
                }
            }
        }

        // Draw & move particles
        for (const p of particles) {
            bgCtx.beginPath();
            bgCtx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
            bgCtx.fillStyle = `rgba(129, 140, 248, ${p.opacity})`;
            bgCtx.fill();

            p.x += p.vx;
            p.y += p.vy;
            if (p.x < 0 || p.x > bgCanvas.width) p.vx *= -1;
            if (p.y < 0 || p.y > bgCanvas.height) p.vy *= -1;
        }

        requestAnimationFrame(drawBg);
    }
    drawBg();

    // ─────────────────────────────────────────────
    // Chart.js Setup
    // ─────────────────────────────────────────────
    Chart.defaults.color = '#52525b';
    Chart.defaults.borderColor = 'rgba(255,255,255,0.04)';
    Chart.defaults.font.family = "'Outfit', sans-serif";
    Chart.defaults.font.weight = 500;

    const loadChart = new Chart(document.getElementById('loadChart').getContext('2d'), {
        type: 'line',
        data: {
            labels: [],
            datasets: [
                {
                    label: 'P-Core (Heavy)',
                    data: [],
                    borderColor: '#00c6ff',
                    backgroundColor: 'rgba(0,198,255,0.06)',
                    fill: true,
                    tension: 0.4,
                    borderWidth: 2,
                    pointRadius: 0,
                    pointHoverRadius: 3,
                },
                {
                    label: 'E-Core (Light)',
                    data: [],
                    borderColor: '#a18cd1',
                    backgroundColor: 'rgba(161,140,209,0.06)',
                    fill: true,
                    tension: 0.4,
                    borderWidth: 2,
                    pointRadius: 0,
                    pointHoverRadius: 3,
                },
            ],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: { duration: 300, easing: 'easeOutQuart' },
            scales: {
                x: { display: true, grid: { display: false }, ticks: { maxTicksLimit: 8, font: { size: 9 } } },
                y: { min: 0, grid: { color: 'rgba(255,255,255,0.02)' }, ticks: { font: { size: 9 } } },
            },
            plugins: {
                legend: { position: 'top', labels: { boxWidth: 10, padding: 16, font: { size: 10, weight: 600 } } },
            },
            interaction: { intersect: false, mode: 'index' },
        },
    });

    const regretChart = new Chart(document.getElementById('regretChart').getContext('2d'), {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'Regret',
                data: [],
                borderColor: '#00f2fe',
                backgroundColor: (ctx) => {
                    const g = ctx.chart.ctx.createLinearGradient(0, 0, 0, 220);
                    g.addColorStop(0, 'rgba(0,242,254,0.1)');
                    g.addColorStop(1, 'rgba(0,242,254,0)');
                    return g;
                },
                fill: true,
                tension: 0.35,
                borderWidth: 2,
                pointRadius: 0,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: { duration: 300 },
            scales: {
                x: { display: false },
                y: { grid: { color: 'rgba(255,255,255,0.02)' }, ticks: { font: { size: 9 } } },
            },
            plugins: { legend: { display: false } },
        },
    });

    // ─────────────────────────────────────────────
    // DOM References
    // ─────────────────────────────────────────────
    const $ = id => document.getElementById(id);

    const cpuArc = $('cpuArc'), memArc = $('memArc');
    const cpuValue = $('cpuValue'), memValue = $('memValue');
    const cpuDetail = $('cpuDetail'), memDetail = $('memDetail');
    const procCount = $('procCount'), procSplit = $('procSplit');
    const engineLabel = $('engineLabel'), engineDetail = $('engineDetail');
    const regretValue = $('regretValue'), regretDetail = $('regretDetail');
    const coreHeatmap = $('coreHeatmap');
    const tableBody = $('tableBody');
    const statusLabel = $('statusLabel'), pulseRing = $('pulseRing');
    const clockEl = $('clock');
    const heurPctLabel = $('heurPctLabel'), bandPctLabel = $('bandPctLabel');
    const heurBar = $('heurBar'), bandBar = $('bandBar');
    const totalDec = $('totalDec'), alphaVal = $('alphaVal'), betaVal = $('betaVal');
    const resetBtn = $('resetBtn');

    const CIRCUMFERENCE = 2 * Math.PI * 52; // ~326.7
    const MAX_CHART = 100;
    let regretHistory = [];

    // ─────────────────────────────────────────────
    // Clock
    // ─────────────────────────────────────────────
    function tick() {
        clockEl.textContent = new Date().toLocaleTimeString('en-GB', { hour12: false });
    }
    setInterval(tick, 1000);
    tick();

    // ─────────────────────────────────────────────
    // Gauge Animation
    // ─────────────────────────────────────────────
    function setGauge(arcEl, valueEl, pct) {
        const offset = CIRCUMFERENCE - (pct / 100) * CIRCUMFERENCE;
        arcEl.style.strokeDashoffset = offset;
        valueEl.textContent = Math.round(pct);
    }

    // ─────────────────────────────────────────────
    // Core Heatmap Color
    // ─────────────────────────────────────────────
    function heatColor(pct) {
        if (pct < 20) return { bg: 'rgba(0,198,255,0.08)', bd: 'rgba(0,198,255,0.1)' };
        if (pct < 40) return { bg: 'rgba(161,140,209,0.12)', bd: 'rgba(161,140,209,0.15)' };
        if (pct < 60) return { bg: 'rgba(0,242,254,0.15)', bd: 'rgba(0,242,254,0.18)' };
        if (pct < 80) return { bg: 'rgba(251,191,36,0.18)', bd: 'rgba(251,191,36,0.22)' };
        return { bg: 'rgba(248,113,113,0.22)', bd: 'rgba(248,113,113,0.28)' };
    }

    // ─────────────────────────────────────────────
    // Render Functions
    // ─────────────────────────────────────────────
    function renderAll(data) {
        const sys = data.system || {};
        const procs = data.processes || [];
        const bandit = data.bandit || {};
        const hist = data.history_tail || [];

        // Gauges
        setGauge(cpuArc, cpuValue, sys.cpu_percent_overall || 0);
        setGauge(memArc, memValue, sys.memory_percent || 0);

        const freqStr = sys.cpu_freq_current ? ` · ${(sys.cpu_freq_current / 1000).toFixed(1)} GHz` : '';
        cpuDetail.textContent = `${sys.cpu_count_physical || '?'} Physical / ${sys.cpu_count_logical || '?'} Logical${freqStr}`;
        memDetail.textContent = `${sys.memory_used_gb || 0} / ${sys.memory_total_gb || 0} GB`;

        // Process tiles
        procCount.textContent = procs.length;
        const hp = procs.filter(p => (p.action || '').includes('P')).length;
        const ep = procs.length - hp;
        procSplit.textContent = `${hp} → P-Core · ${ep} → E-Core`;

        // Engine
        const tot = (bandit.heuristic_count || 0) + (bandit.bandit_count || 0);
        if (tot > 0) {
            const bp = (bandit.bandit_count || 0) / tot * 100;
            engineLabel.textContent = bp > 50 ? 'LinUCB' : 'Heuristic';
            engineDetail.textContent = `${bp.toFixed(0)}% adaptive decisions`;
        } else {
            engineLabel.textContent = 'Cold Start';
            engineDetail.textContent = 'Gathering data…';
        }

        // Regret
        const reg = bandit.cumulative_regret || 0;
        regretValue.textContent = reg.toFixed(2);

        // Bandit bars
        const hPct = bandit.heuristic_pct || 0;
        const bPct = bandit.bandit_pct || 0;
        heurPctLabel.textContent = `${hPct}%`;
        bandPctLabel.textContent = `${bPct}%`;
        heurBar.style.width = `${hPct}%`;
        bandBar.style.width = `${bPct}%`;
        totalDec.textContent = bandit.total_decisions || 0;
        alphaVal.textContent = bandit.alpha_reward || 0.7;
        betaVal.textContent = bandit.beta_reward || 0.3;

        // Core heatmap
        renderCores(sys.cpu_percent_per_core || []);

        // Table
        renderTable(procs);

        // Charts
        renderLoadChart(hist);
        renderRegretChart(reg);
    }

    function renderCores(perCore) {
        if (!perCore.length) return;

        // Only rebuild DOM if core count changed
        if (coreHeatmap.childElementCount !== perCore.length) {
            coreHeatmap.innerHTML = '';
            perCore.forEach((_, i) => {
                const cell = document.createElement('div');
                cell.className = 'core-cell';
                cell.innerHTML = `<span class="core-cell__id">C${i}</span><span class="core-cell__pct">0%</span>`;
                coreHeatmap.appendChild(cell);
            });
        }

        const cells = coreHeatmap.children;
        perCore.forEach((pct, i) => {
            const cell = cells[i];
            if (!cell) return;
            const col = heatColor(pct);
            cell.style.background = col.bg;
            cell.style.borderColor = col.bd;
            cell.querySelector('.core-cell__pct').textContent = `${Math.round(pct)}%`;
        });
    }

    function renderTable(procs) {
        if (!procs || !procs.length) {
            tableBody.innerHTML = '<tr><td colspan="9" class="table-empty">Waiting for scheduler data…</td></tr>';
            return;
        }
        tableBody.innerHTML = procs.map(p => {
            const isP = (p.action || '').includes('P');
            const isBand = (p.decision_source || '') === 'bandit';
            const reward = parseFloat(p.reward || 0);
            const rwdColor = reward >= 0 ? '#00f2fe' : '#f87171';
            return `<tr>
                <td>${p.pid || '—'}</td>
                <td style="color:${isP ? '#00c6ff' : '#a18cd1'}">${p.true_type || '—'}</td>
                <td><span class="chip chip--${isP ? 'p' : 'e'}">${p.action || '—'}</span></td>
                <td><span class="chip chip--${isBand ? 'band' : 'heur'}">${p.decision_source || '—'}</span></td>
                <td>${parseFloat(p.cpu_percent || 0).toFixed(1)}%</td>
                <td>${parseFloat(p.vol_ctx_rate || 0).toFixed(0)}</td>
                <td>${parseFloat(p.invol_ctx_rate || 0).toFixed(0)}</td>
                <td>${parseFloat(p.confidence_ucb || 0).toFixed(3)}</td>
                <td style="color:${rwdColor};font-weight:700">${reward.toFixed(4)}</td>
            </tr>`;
        }).join('');
    }

    function renderLoadChart(hist) {
        if (!hist.length) return;
        const byTs = {};
        hist.forEach(r => {
            const ts = r.timestamp;
            if (!byTs[ts]) byTs[ts] = { p: [], e: [] };
            const cpu = parseFloat(r.cpu_percent || 0);
            (r.action || '').includes('P') ? byTs[ts].p.push(cpu) : byTs[ts].e.push(cpu);
        });
        const keys = Object.keys(byTs).sort().slice(-MAX_CHART);
        const avg = arr => arr.length ? arr.reduce((a, b) => a + b, 0) / arr.length : 0;

        loadChart.data.labels = keys.map(ts => {
            const d = new Date(parseFloat(ts) * 1000);
            return d.toLocaleTimeString('en-GB', { minute: '2-digit', second: '2-digit' });
        });
        loadChart.data.datasets[0].data = keys.map(ts => avg(byTs[ts].p));
        loadChart.data.datasets[1].data = keys.map(ts => avg(byTs[ts].e));
        loadChart.update('none');
    }

    function renderRegretChart(regret) {
        regretHistory.push(regret);
        if (regretHistory.length > MAX_CHART) regretHistory = regretHistory.slice(-MAX_CHART);
        regretChart.data.labels = regretHistory.map((_, i) => i);
        regretChart.data.datasets[0].data = [...regretHistory];
        regretChart.update('none');
    }

    // ─────────────────────────────────────────────
    // Reset Button
    // ─────────────────────────────────────────────
    resetBtn.addEventListener('click', async () => {
        resetBtn.disabled = true;
        const origHTML = resetBtn.innerHTML;
        resetBtn.textContent = 'Resetting…';
        try {
            const r = await fetch('/api/reset', { method: 'POST' });
            const d = await r.json();
            resetBtn.textContent = `✓ ${d.released} released`;
            setTimeout(() => { resetBtn.innerHTML = origHTML; resetBtn.disabled = false; }, 2500);
        } catch {
            resetBtn.textContent = '✗ Failed';
            setTimeout(() => { resetBtn.innerHTML = origHTML; resetBtn.disabled = false; }, 2000);
        }
    });

    // ─────────────────────────────────────────────
    // WebSocket + Fallback Polling + Demo Mock
    // ─────────────────────────────────────────────
    let ws = null;
    let reconnectTimer = null;
    let demoMode = false;
    let demoInterval = null;

    function setConnected(connected, isDemo = false) {
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
            const coreData = Array.from({ length: 8 }, () => Math.random() * 90);

            const numHeavy = Math.floor(Math.random() * 2) + 2;
            const numLight = 4 - numHeavy;

            decCount += 4;
            const currRegret = Math.max(0.01, Math.random() * 0.1);
            cumulativeRegret += currRegret;

            const fakeData = {
                system: {
                    cpu_percent_overall: cpuTotal,
                    memory_percent: 42 + Math.random() * 5,
                    cpu_freq_current: 3100 + Math.random() * 200,
                    cpu_count_physical: 4,
                    cpu_count_logical: 8,
                    memory_used_gb: (6.5 + Math.random() * 0.5).toFixed(1),
                    memory_total_gb: 16.0,
                    cpu_percent_per_core: coreData
                },
                processes: [
                    { pid: 1024, action: 'P', decision_source: 'bandit', cpu_percent: 80 + Math.random() * 15, vol_ctx_rate: 12, invol_ctx_rate: 15, confidence_ucb: 1.4, reward: -0.15, true_type: 'Heavy' },
                    { pid: 2048, action: 'P', decision_source: 'bandit', cpu_percent: 85 + Math.random() * 10, vol_ctx_rate: 8, invol_ctx_rate: 10, confidence_ucb: 1.5, reward: -0.10, true_type: 'Heavy' },
                    { pid: 3012, action: 'E', decision_source: 'bandit', cpu_percent: 3 + Math.random() * 5, vol_ctx_rate: 450, invol_ctx_rate: 1, confidence_ucb: 0.3, reward: -0.01, true_type: 'Light' },
                    { pid: 4056, action: 'E', decision_source: 'bandit', cpu_percent: 4 + Math.random() * 4, vol_ctx_rate: 610, invol_ctx_rate: 2, confidence_ucb: 0.4, reward: -0.02, true_type: 'Light' }
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

            const pCPU = (cpuTotal * 0.8) + (Math.random() * 10);
            const eCPU = (cpuTotal * 0.2) + (Math.random() * 10);
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
        if (window.location.hostname.includes("vercel.app")) {
            console.warn("Vercel deployment detected. Bypassing Serverless frozen state.");
            startDemoSimulation();
            return;
        }

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
                fetch('/api/live').then(r => { if (!r.ok) throw new Error(); return r.json() }),
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
