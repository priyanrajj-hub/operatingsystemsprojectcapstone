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
    const demoBanner = $('demoBanner');
    const modeBadge = $('modeBadge');
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
        aizenDataCache = data;
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
        const totDec = (bandit.heuristic_count || 0) + (bandit.bandit_count || 0);
        const hPct = totDec > 0 ? ((bandit.heuristic_count || 0) / totDec * 100).toFixed(0) : 0;
        const bPct = totDec > 0 ? ((bandit.bandit_count || 0) / totDec * 100).toFixed(0) : 0;
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

    function escapeHTML(str) {
        if (str === null || str === undefined) return '';
        return String(str).replace(/[&<>'"]/g, tag => ({
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            "'": '&#39;',
            '"': '&quot;'
        }[tag] || tag));
    }

    function renderTable(procs) {
        tableBody.replaceChildren();
        if (!procs || !procs.length) {
            const tr = document.createElement('tr');
            const td = document.createElement('td');
            td.colSpan = 9;
            td.className = 'table-empty';
            td.textContent = 'Waiting for scheduler data…';
            tr.appendChild(td);
            tableBody.appendChild(tr);
            return;
        }

        const fragment = document.createDocumentFragment();
        procs.forEach(p => {
            const tr = document.createElement('tr');
            const isP = String(p.action || '').includes('P');
            const isBand = String(p.decision_source || '') === 'bandit';
            const reward = parseFloat(p.reward || 0);

            // PID
            const tdPid = document.createElement('td');
            tdPid.textContent = String(p.pid ?? '—');
            tr.appendChild(tdPid);

            // Type
            const tdType = document.createElement('td');
            tdType.textContent = String(p.true_type ?? '—');
            tdType.style.color = isP ? '#00c6ff' : '#a18cd1';
            tr.appendChild(tdType);

            // Routed
            const tdRouted = document.createElement('td');
            const chipAction = document.createElement('span');
            chipAction.className = `chip chip--${isP ? 'p' : 'e'}`;
            chipAction.textContent = String(p.action ?? '—');
            tdRouted.appendChild(chipAction);
            tr.appendChild(tdRouted);

            // Source
            const tdSource = document.createElement('td');
            const chipSrc = document.createElement('span');
            chipSrc.className = `chip chip--${isBand ? 'band' : 'heur'}`;
            chipSrc.textContent = String(p.decision_source ?? '—');
            tdSource.appendChild(chipSrc);
            tr.appendChild(tdSource);

            // CPU %
            const tdCpu = document.createElement('td');
            tdCpu.textContent = `${parseFloat(p.cpu_percent || 0).toFixed(1)}%`;
            tr.appendChild(tdCpu);

            // Vol Ctx
            const tdVol = document.createElement('td');
            tdVol.textContent = parseFloat(p.vol_ctx_rate || 0).toFixed(0);
            tr.appendChild(tdVol);

            // Invol Ctx
            const tdInvol = document.createElement('td');
            tdInvol.textContent = parseFloat(p.invol_ctx_rate || 0).toFixed(0);
            tr.appendChild(tdInvol);

            // UCB
            const tdUcb = document.createElement('td');
            tdUcb.textContent = parseFloat(p.confidence_ucb || 0).toFixed(3);
            tr.appendChild(tdUcb);

            // Reward
            const tdReward = document.createElement('td');
            tdReward.textContent = reward.toFixed(4);
            tdReward.style.color = reward >= 0 ? '#00f2fe' : '#f87171';
            tdReward.style.fontWeight = '700';
            tr.appendChild(tdReward);

            fragment.appendChild(tr);
        });
        tableBody.appendChild(fragment);
    }

    function renderLoadChart(hist) {
        if (!hist.length) return;
        const byTs = {};
        hist.forEach(r => {
            const ts = r.timestamp;
            if (!byTs[ts]) byTs[ts] = { p: [], e: [] };
            const isP = (r.action || '').includes('P');
            const cpu = parseFloat(r.cpu_percent || 0);
            isP ? byTs[ts].p.push(cpu) : byTs[ts].e.push(cpu);
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
    let reconnectDelay = 1000;
    const MAX_RECONNECT_DELAY = 15000;
    let demoMode = false;
    let demoInterval = null;

    function setConnected(connected, isDemo = false) {
        if (connected && !isDemo) {
            demoMode = false;
            if (demoBanner) demoBanner.classList.remove('visible');
            if (modeBadge) {
                modeBadge.textContent = 'LIVE TELEMETRY';
                modeBadge.className = 'badge-live';
            }
            pulseRing.classList.add('active');
            pulseRing.style.background = '#00f2fe';
            pulseRing.style.boxShadow = '0 0 10px #00f2fe';
            statusLabel.textContent = 'Live';
            statusLabel.style.color = '#fff';
        } else if (isDemo) {
            demoMode = true;
            if (demoBanner) demoBanner.classList.add('visible');
            if (modeBadge) {
                modeBadge.textContent = 'DEMO: SIMULATED DATA';
                modeBadge.className = 'badge-demo';
            }
            pulseRing.classList.remove('active');
            pulseRing.style.background = '#f59e0b';
            pulseRing.style.boxShadow = '0 0 10px rgba(245, 158, 11, 0.6)';
            statusLabel.textContent = 'Simulated Demo';
            statusLabel.style.color = '#f59e0b';
        } else {
            if (modeBadge) {
                modeBadge.textContent = 'RECONNECTING...';
                modeBadge.className = 'badge-reconnecting';
            }
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

        // ── CLIENT DEVICE HARDWARE DETECTION ──
        const logicalCores = navigator.hardwareConcurrency || 8;
        const physicalCores = Math.max(1, Math.floor(logicalCores / 2));
        const ramGB = navigator.deviceMemory || 16;
        let pCoresArr = Array.from({ length: physicalCores }, (_, i) => i);
        let eCoresArr = Array.from({ length: logicalCores - physicalCores }, (_, i) => i + physicalCores);

        console.warn(`AI-DAX Lite: Running in SIMULATED DEMO mode (backend unavailable). Client specs: ${logicalCores} Cores, ${ramGB}GB RAM`);

        if (demoInterval) clearInterval(demoInterval);
        demoInterval = setInterval(() => {
            const timeNow = Date.now() / 1000;
            const cpuTotal = 15 + Math.random() * 50;
            const coreData = Array.from({ length: logicalCores }, () => Math.random() * 85);

            const numHeavy = Math.floor(Math.random() * 2) + 2;
            const numLight = 4 - numHeavy;

            decCount += 4;
            const currRegret = Math.max(0.01, Math.random() * 0.1);
            cumulativeRegret += currRegret;

            let mockProcesses = [
                { pid: 1024, action: 'P', decision_source: 'bandit', cpu_percent: 80 + Math.random() * 15, vol_ctx_rate: 12, invol_ctx_rate: 15, confidence_ucb: 1.4, reward: -0.15, true_type: 'Heavy', assigned_cores: `[${pCoresArr.join(', ')}]` },
                { pid: 2048, action: 'P', decision_source: 'bandit', cpu_percent: 85 + Math.random() * 10, vol_ctx_rate: 8, invol_ctx_rate: 10, confidence_ucb: 1.5, reward: -0.10, true_type: 'Heavy', assigned_cores: `[${pCoresArr.join(', ')}]` },
                { pid: 3012, action: 'E', decision_source: 'bandit', cpu_percent: 3 + Math.random() * 5, vol_ctx_rate: 450, invol_ctx_rate: 1, confidence_ucb: 0.3, reward: -0.01, true_type: 'Light', assigned_cores: `[${eCoresArr.join(', ')}]` },
                { pid: 4056, action: 'E', decision_source: 'bandit', cpu_percent: 4 + Math.random() * 4, vol_ctx_rate: 610, invol_ctx_rate: 2, confidence_ucb: 0.4, reward: -0.02, true_type: 'Light', assigned_cores: `[${eCoresArr.join(', ')}]` }
            ];

            const fakeData = {
                system: {
                    cpu_percent_overall: cpuTotal,
                    memory_percent: 32 + Math.random() * 10,
                    cpu_freq_current: 2800 + Math.random() * 500,
                    cpu_count_physical: physicalCores,
                    cpu_count_logical: logicalCores,
                    memory_used_gb: ((32 + Math.random() * 10) / 100 * ramGB).toFixed(1),
                    memory_total_gb: ramGB,
                    cpu_percent_per_core: coreData
                },
                processes: mockProcesses.slice(0, numHeavy + numLight),
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

    function scheduleReconnect() {
        if (reconnectTimer) return;
        reconnectTimer = setTimeout(() => {
            reconnectTimer = null;
            reconnectDelay = Math.min(reconnectDelay * 1.5, MAX_RECONNECT_DELAY);
            connectWS();
        }, reconnectDelay);
    }

    function connectWS() {
        const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const host = window.location.host || '127.0.0.1:8000';
        const wsUrl = `${proto}//${host}/ws/live`;
        try {
            ws = new WebSocket(wsUrl);
        } catch {
            scheduleReconnect();
            return;
        }

        ws.onopen = () => {
            reconnectDelay = 1000;
            if (demoInterval) {
                clearInterval(demoInterval);
                demoInterval = null;
            }
            setConnected(true, false);
            if (reconnectTimer) {
                clearTimeout(reconnectTimer);
                reconnectTimer = null;
            }
        };
        ws.onmessage = (e) => {
            try {
                renderAll(JSON.parse(e.data));
            } catch (err) {
                console.error(err);
            }
        };
        ws.onclose = () => {
            if (!demoMode) setConnected(false, false);
            scheduleReconnect();
        };
        ws.onerror = () => {
            try { ws.close(); } catch {}
        };
    }

    async function poll() {
        if (ws && ws.readyState === WebSocket.OPEN) return;
        try {
            const [liveR, histR] = await Promise.all([
                fetch('/api/live').then(r => {
                    if (!r.ok) throw new Error('Network response not ok');
                    return r.json();
                }),
                fetch('/api/history?limit=100').then(r => r.ok ? r.json() : { history: [] }),
            ]);
            liveR.history_tail = histR.history || [];
            if (demoInterval) {
                clearInterval(demoInterval);
                demoInterval = null;
            }
            renderAll(liveR);
            setConnected(true, false);
        } catch {
            console.warn("Backend API unavailable. Starting explicit DEMO simulation mode.");
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

    // ─────────────────────────────────────────────
    // Jarvis & Aizen Integration
    // ─────────────────────────────────────────────
    let aizenDataCache = null;
    const aizenHealth = $('aizenHealth');
    const aizenProcess = $('aizenProcess');
    const aizenFuture = $('aizenFuture');
    const jarvisBtn = $('jarvisBtn');

    async function fetchAizenInsights(sys, bandit) {
        if (!sys || !sys.cpu_percent_overall) return;
        try {
            const resp = await fetch('/api/aizen', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    cpu_percent_overall: sys.cpu_percent_overall || 0,
                    memory_percent: sys.memory_percent || 0,
                    total_decisions: bandit.total_decisions || 0,
                    regret: bandit.cumulative_regret || 0
                })
            });
            const data = await resp.json();
            if (data.health) aizenHealth.textContent = data.health;
            if (data.process) aizenProcess.textContent = data.process;
            if (data.future) aizenFuture.textContent = data.future;
        } catch (e) {
            console.error("Aizen LLM unavailable", e);
        }
    }

    // Call Aizen every 60 seconds to save API quota
    setInterval(() => {
        if (aizenDataCache && aizenHealth) fetchAizenInsights(aizenDataCache.system, aizenDataCache.bandit);
    }, 60000);
    // Initial call after 2 seconds
    setTimeout(() => {
        if (aizenDataCache && aizenHealth) fetchAizenInsights(aizenDataCache.system, aizenDataCache.bandit);
    }, 2000);

    // Jarvis Multilingual Voice Recognition
    const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (SpeechRec && jarvisBtn) {
        const recognition = new SpeechRec();
        recognition.continuous = false;
        recognition.lang = 'en-US';

        jarvisBtn.addEventListener('click', () => {
            jarvisBtn.classList.add('listening');
            recognition.start();
        });

        recognition.onresult = async (event) => {
            jarvisBtn.classList.remove('listening');
            const query = event.results[0][0].transcript;

            // Extract language from Google Translate Combo
            let userLang = 'English';
            try {
                const gt = document.querySelector('.goog-te-combo');
                if (gt && gt.value) {
                    userLang = gt.options[gt.selectedIndex].text;
                }
            } catch { }

            try {
                const sys = aizenDataCache ? aizenDataCache.system : {};
                const resp = await fetch('/api/jarvis', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        cpu_percent_overall: sys.cpu_percent_overall || 0,
                        memory_percent: sys.memory_percent || 0,
                        total_decisions: 0,
                        regret: 0,
                        voice_query: query,
                        language: userLang
                    })
                });
                const data = await resp.json();

                const synth = window.speechSynthesis;
                const utterThis = new SpeechSynthesisUtterance(data.response);
                synth.speak(utterThis);

                alert("Jarvis (" + userLang + "): " + data.response);

            } catch (e) {
                console.error("Jarvis offline", e);
            }
        };

        recognition.onerror = () => jarvisBtn.classList.remove('listening');
        recognition.onend = () => jarvisBtn.classList.remove('listening');
    }

})();
