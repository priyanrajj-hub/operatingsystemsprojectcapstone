import os

html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI-DAX Lite • CPU Governor</title>
    <meta name="description" content="AI-DAX Lite: Adaptive CPU Governor — Real-time System Monitor">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=Space+Mono:wght@400;700&display=swap" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.4/dist/chart.umd.min.js"></script>
    <link rel="stylesheet" href="style.css">
</head>
<body>
    <div class="ambient-glow glow-1"></div>
    <div class="ambient-glow glow-2"></div>
    <!-- Animated background canvas -->
    <canvas id="bgCanvas"></canvas>

    <header class="header glass-panel">
        <div class="header__left">
            <div class="header__logo">
                <div class="logo-ring">
                    <svg viewBox="0 0 36 36" class="logo-svg">
                        <circle cx="18" cy="18" r="15.5" fill="none" stroke="url(#logoGrad)" stroke-width="2" stroke-dasharray="80 20" class="logo-orbit" />
                        <circle cx="18" cy="18" r="4" fill="#fff" />
                        <defs>
                            <linearGradient id="logoGrad" x1="0" y1="0" x2="1" y2="1">
                                <stop offset="0%" stop-color="#00f2fe" />
                                <stop offset="100%" stop-color="#4facfe" />
                            </linearGradient>
                        </defs>
                    </svg>
                </div>
                <div>
                    <h1 class="header__title">AI-DAX<span class="gradient-text">Lite</span></h1>
                    <p class="header__sub">Adaptive CPU Governor</p>
                </div>
            </div>
        </div>
        <div class="header__right">
            <div class="header__indicator glass-badge">
                <div class="pulse-ring" id="pulseRing"></div>
                <span id="statusLabel">Connecting</span>
            </div>
            <div class="header__clock glass-badge" id="clock">--:--:--</div>
        </div>
    </header>

    <main class="main">
        <section class="section gauges-section">
            <div class="gauge-card glass-panel" id="cpuGaugeCard">
                <div class="gauge-ring-wrap">
                    <svg viewBox="0 0 120 120" class="gauge-svg">
                        <circle cx="60" cy="60" r="52" fill="none" stroke="rgba(255,255,255,0.03)" stroke-width="8" />
                        <circle cx="60" cy="60" r="52" fill="none" stroke="url(#cpuGrad)" stroke-width="8" stroke-dasharray="326.7" stroke-dashoffset="326.7" stroke-linecap="round" class="gauge-arc glow-arc" id="cpuArc" transform="rotate(-90 60 60)" />
                        <defs>
                            <linearGradient id="cpuGrad" x1="0" y1="0" x2="1" y2="1">
                                <stop offset="0%" stop-color="#00c6ff" />
                                <stop offset="100%" stop-color="#0072ff" />
                            </linearGradient>
                        </defs>
                    </svg>
                    <div class="gauge-center">
                        <span class="gauge-value" id="cpuValue">0</span>
                        <span class="gauge-unit">%</span>
                    </div>
                </div>
                <div class="gauge-label">CPU Utilisation</div>
                <div class="gauge-detail" id="cpuDetail">— cores</div>
            </div>

            <div class="gauge-card glass-panel" id="memGaugeCard">
                <div class="gauge-ring-wrap">
                    <svg viewBox="0 0 120 120" class="gauge-svg">
                        <circle cx="60" cy="60" r="52" fill="none" stroke="rgba(255,255,255,0.03)" stroke-width="8" />
                        <circle cx="60" cy="60" r="52" fill="none" stroke="url(#memGrad)" stroke-width="8" stroke-dasharray="326.7" stroke-dashoffset="326.7" stroke-linecap="round" class="gauge-arc glow-arc" id="memArc" transform="rotate(-90 60 60)" />
                        <defs>
                            <linearGradient id="memGrad" x1="0" y1="0" x2="1" y2="1">
                                <stop offset="0%" stop-color="#d4145a" />
                                <stop offset="100%" stop-color="#fbb03b" />
                            </linearGradient>
                        </defs>
                    </svg>
                    <div class="gauge-center">
                        <span class="gauge-value" id="memValue">0</span>
                        <span class="gauge-unit">%</span>
                    </div>
                </div>
                <div class="gauge-label">Memory</div>
                <div class="gauge-detail" id="memDetail">— GB</div>
            </div>

            <div class="info-stack">
                <div class="info-tile glass-panel">
                    <div class="info-tile__header">
                        <div class="info-tile__dot" style="background:#00c6ff; box-shadow: 0 0 10px #00c6ff;"></div>
                        Monitored Processes
                    </div>
                    <div class="info-tile__value" id="procCount">0</div>
                    <div class="info-tile__sub" id="procSplit">—</div>
                </div>
                <div class="info-tile glass-panel">
                    <div class="info-tile__header">
                        <div class="info-tile__dot" style="background:#a18cd1; box-shadow: 0 0 10px #a18cd1;"></div>
                        Decision Engine
                    </div>
                    <div class="info-tile__value" id="engineLabel">—</div>
                    <div class="info-tile__sub" id="engineDetail">—</div>
                </div>
                <div class="info-tile glass-panel">
                    <div class="info-tile__header">
                        <div class="info-tile__dot" style="background:#00f2fe; box-shadow: 0 0 10px #00f2fe;"></div>
                        Regret Tracking
                    </div>
                    <div class="info-tile__value" id="regretValue">0.00</div>
                    <div class="info-tile__sub" id="regretDetail">cumulative</div>
                </div>
            </div>
        </section>

        <section class="section glass-panel">
            <div class="section-head">
                <h2>Core Topology</h2>
                <p>Real-time per-core utilisation heatmap</p>
            </div>
            <div class="core-heatmap" id="coreHeatmap"></div>
        </section>

        <section class="section charts-section">
            <div class="chart-panel glass-panel">
                <div class="section-head">
                    <h2>Load Distribution</h2>
                    <p>P-Core vs E-Core average CPU load over time</p>
                </div>
                <div class="chart-wrap">
                    <canvas id="loadChart"></canvas>
                </div>
            </div>
            <div class="chart-panel chart-panel--narrow glass-panel">
                <div class="section-head">
                    <h2>Learning Curve</h2>
                    <p>Cumulative regret — lower is better</p>
                </div>
                <div class="chart-wrap">
                    <canvas id="regretChart"></canvas>
                </div>
            </div>
        </section>

        <section class="section glass-panel">
            <div class="section-head">
                <h2>Bandit Intelligence</h2>
                <p>LinUCB decision-making breakdown</p>
            </div>
            <div class="bandit-grid">
                <div class="bandit-bar-wrap">
                    <div class="bandit-bar-label">
                        <span>Heuristic fallback</span>
                        <span class="bandit-bar-pct" id="heurPctLabel">0%</span>
                    </div>
                    <div class="bandit-bar-track">
                        <div class="bandit-bar-fill bandit-bar-fill--heur" id="heurBar" style="width:0%; box-shadow: 0 0 10px rgba(161, 140, 209, 0.8);"></div>
                    </div>
                </div>
                <div class="bandit-bar-wrap">
                    <div class="bandit-bar-label">
                        <span>Bandit (LinUCB)</span>
                        <span class="bandit-bar-pct" id="bandPctLabel">0%</span>
                    </div>
                    <div class="bandit-bar-track">
                        <div class="bandit-bar-fill bandit-bar-fill--band" id="bandBar" style="width:0%; box-shadow: 0 0 10px rgba(0, 198, 255, 0.8);"></div>
                    </div>
                </div>
                <div class="bandit-meta">
                    <div><span class="bandit-meta-label">Total Decisions</span><span class="bandit-meta-value glow-text" id="totalDec">0</span></div>
                    <div><span class="bandit-meta-label">α (ctx weight)</span><span class="bandit-meta-value glow-text" id="alphaVal">0.7</span></div>
                    <div><span class="bandit-meta-label">β (energy weight)</span><span class="bandit-meta-value glow-text" id="betaVal">0.3</span></div>
                </div>
            </div>
        </section>

        <section class="section glass-panel">
            <div class="section-head" style="display: flex; justify-content: space-between; align-items: flex-end;">
                <div>
                    <h2>Process Monitor</h2>
                    <p>Live task routing & performance metrics</p>
                </div>
                <button class="reset-btn glass-btn" id="resetBtn">
                    <svg viewBox="0 0 20 20" fill="currentColor" width="14" height="14">
                        <path fill-rule="evenodd" d="M15.312 11.424a5.5 5.5 0 0 1-9.378 2.202l-1.36 1.36A7.002 7.002 0 0 0 17.27 10.5H15.5a.5.5 0 0 0-.188.924zM4.688 8.576a5.5 5.5 0 0 1 9.378-2.202l1.36-1.36A7.002 7.002 0 0 0 2.73 9.5H4.5a.5.5 0 0 0 .188-.924z" clip-rule="evenodd" />
                    </svg>
                    Reset Affinities
                </button>
            </div>
            <div class="table-wrap">
                <table>
                    <thead>
                        <tr>
                            <th>PID</th>
                            <th>Type</th>
                            <th>Routed</th>
                            <th>Source</th>
                            <th>CPU</th>
                            <th>Vol Ctx/s</th>
                            <th>Invol Ctx/s</th>
                            <th>UCB</th>
                            <th>Reward</th>
                        </tr>
                    </thead>
                    <tbody id="tableBody">
                        <tr>
                            <td colspan="9" class="table-empty">Waiting for telemetry…</td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </section>

    </main>

    <footer class="footer">AI-DAX Lite v3 · Premium Glassmorphic Intelligence · Research Prototype</footer>

    <script src="app.js"></script>
</body>
</html>"""

css_content = """/* AI-DAX Lite v3 - Premium Deep Space Glassmorphism Theme */

:root {
    --bg-base: #02040a;
    --bg-accent: #0f172a;
    
    --glass-bg: rgba(15, 23, 42, 0.4);
    --glass-border: rgba(255, 255, 255, 0.08);
    --glass-highlight: rgba(255, 255, 255, 0.12);
    --glass-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
    
    --text-main: #f8fafc;
    --text-muted: #94a3b8;
    --text-dim: #475569;
    
    --accent-primary: #00c6ff;
    --accent-secondary: #a18cd1;
    --accent-danger: #ff4b2b;
    --accent-success: #00f2fe;

    --font: 'Outfit', -apple-system, sans-serif;
    --mono: 'Space Mono', monospace;
    
    --ease-out: cubic-bezier(0.16, 1, 0.3, 1);
}

* {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
}

body {
    background-color: var(--bg-base);
    color: var(--text-main);
    font-family: var(--font);
    min-height: 100vh;
    overflow-x: hidden;
    line-height: 1.5;
}

/* Ambient glow orbs in the background */
.ambient-glow {
    position: fixed;
    border-radius: 50%;
    filter: blur(120px);
    z-index: 0;
    pointer-events: none;
    opacity: 0.5;
    animation: floatGlow 20s infinite alternate var(--ease-out);
}

.glow-1 {
    top: -10%; left: -5%;
    width: 50vw; height: 50vw;
    background: radial-gradient(circle, rgba(0,198,255,0.15) 0%, rgba(0,0,0,0) 70%);
}

.glow-2 {
    bottom: -10%; right: -5%;
    width: 60vw; height: 60vw;
    background: radial-gradient(circle, rgba(161,140,209,0.1) 0%, rgba(0,0,0,0) 70%);
    animation-delay: -10s;
}

@keyframes floatGlow {
    0% { transform: translate(0, 0) scale(1); }
    100% { transform: translate(30px, 50px) scale(1.1); }
}

#bgCanvas {
    position: fixed;
    inset: 0;
    z-index: 0;
    pointer-events: none;
    opacity: 0.3;
}

/* Glassmorphism Utilities */
.glass-panel {
    background: var(--glass-bg);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    border: 1px solid var(--glass-border);
    box-shadow: var(--glass-shadow);
    border-radius: 20px;
    z-index: 1;
    position: relative;
    transition: transform 0.3s var(--ease-out), border-color 0.3s var(--ease-out), box-shadow 0.3s var(--ease-out);
}

.glass-panel:hover {
    border-color: var(--glass-highlight);
    box-shadow: 0 12px 40px 0 rgba(0, 198, 255, 0.1);
}

/* Typography Enhancements */
h1, h2, h3 { font-weight: 700; letter-spacing: -0.02em; }
.gradient-text {
    background: linear-gradient(135deg, #00f2fe 0%, #4facfe 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}

/* Header */
.header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 1rem 2rem;
    margin: 1.5rem auto;
    max-width: 1400px;
    border-radius: 100px;
}

.header__left { display: flex; align-items: center; gap: 1rem; }
.header__logo { display: flex; align-items: center; gap: 1.2rem; }
.logo-ring { position: relative; width: 44px; height: 44px; display: flex; align-items: center; justify-content: center; }
.logo-orbit { transform-origin: center; animation: spin 10s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

.header__title { font-size: 1.3rem; display: flex; gap: 0.3rem;}
.header__sub { font-size: 0.7rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.1em; font-weight: 500; }

.header__right { display: flex; gap: 1rem; align-items: center; }
.glass-badge {
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.06);
    padding: 0.5rem 1rem;
    border-radius: 100px;
    font-size: 0.75rem;
    font-weight: 600;
    display: flex;
    align-items: center;
    gap: 0.6rem;
    backdrop-filter: blur(10px);
}

.pulse-ring {
    width: 8px; height: 8px;
    border-radius: 50%;
    background: var(--text-muted);
}
.pulse-ring.active {
    background: #00f2fe;
    box-shadow: 0 0 10px #00f2fe;
    animation: beat 1.5s ease-out infinite;
}
@keyframes beat { 0% { box-shadow: 0 0 0 0 rgba(0,242,254,0.4); } 100% { box-shadow: 0 0 0 6px rgba(0,242,254,0); } }

#clock { font-family: var(--mono); color: var(--accent-primary); letter-spacing: 0.05em; }

/* Main Layout */
.main {
    max-width: 1400px;
    margin: 0 auto;
    padding: 0 2rem 4rem;
    display: flex;
    flex-direction: column;
    gap: 2rem;
    position: relative;
    z-index: 1;
}

/* Sections */
.section { animation: fadeUp 0.8s var(--ease-out) both; padding: 1.5rem; }
.section:nth-child(1) { animation-delay: 0.1s; }
.section:nth-child(2) { animation-delay: 0.2s; }
.section:nth-child(3) { animation-delay: 0.3s; }
.section:nth-child(4) { animation-delay: 0.4s; }
.section:nth-child(5) { animation-delay: 0.5s; }

@keyframes fadeUp {
    from { opacity: 0; transform: translateY(20px); }
    to { opacity: 1; transform: translateY(0); }
}

.section-head { margin-bottom: 1.25rem; }
.section-head h2 { font-size: 1.1rem; color: #fff; margin-bottom: 0.2rem; }
.section-head p { font-size: 0.75rem; color: var(--text-muted); }

/* Gauges Row */
.gauges-section { display: grid; grid-template-columns: auto auto 1fr; gap: 1.5rem; padding: 0 !important; background: transparent !important; border: none !important; box-shadow: none !important; backdrop-filter: none !important; }
.gauge-card { padding: 1.5rem; display: flex; flex-direction: column; align-items: center; gap: 0.5rem; }
.gauge-ring-wrap { position: relative; width: 110px; height: 110px; }
.gauge-svg { width: 100%; height: 100%; filter: drop-shadow(0 0 8px rgba(0, 198, 255, 0.4)); }
.gauge-arc { transition: stroke-dashoffset 0.8s var(--ease-out); }
.glow-arc { filter: drop-shadow(0 0 4px rgba(255,255,255,0.5)); }
.gauge-center { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; font-family: var(--mono); }
.gauge-value { font-size: 1.5rem; font-weight: 700; color: #fff; }
.gauge-unit { font-size: 0.7rem; color: var(--text-muted); margin-left: 2px; }
.gauge-label { font-size: 0.8rem; font-weight: 600; letter-spacing: 0.05em; text-transform: uppercase; color: var(--text-muted); margin-top: 0.5rem; }
.gauge-detail { font-size: 0.7rem; color: var(--text-dim); }

.info-stack { display: grid; grid-template-columns: repeat(3, 1fr); gap: 1.5rem; }
.info-tile { padding: 1.5rem 1.75rem; display: flex; flex-direction: column; justify-content: center; gap: 0.5rem; }
.info-tile__header { display: flex; align-items: center; gap: 0.5rem; font-size: 0.75rem; font-weight: 600; text-transform: uppercase; color: var(--text-muted); }
.info-tile__dot { width: 8px; height: 8px; border-radius: 50%; }
.info-tile__value { font-family: var(--mono); font-size: 2rem; font-weight: 700; color: #fff; line-height: 1; }
.info-tile__sub { font-size: 0.75rem; color: var(--accent-secondary); }

/* Core Heatmap */
.core-heatmap { display: grid; grid-template-columns: repeat(auto-fill, minmax(64px, 1fr)); gap: 10px; }
.core-cell {
    aspect-ratio: 1;
    border-radius: 12px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 4px;
    font-family: var(--mono);
    font-size: 0.7rem;
    font-weight: 700;
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.05);
    transition: all 0.4s var(--ease-out);
    position: relative;
    overflow: hidden;
}
.core-cell::before {
    content: '';
    position: absolute; inset: 0;
    background: inherit; filter: blur(10px); opacity: 0.5; z-index: -1;
}
.core-cell span:last-child { font-size: 0.6rem; color: var(--text-muted); font-weight: 500; font-family: var(--font); }

/* Charts Row */
.charts-section { display: grid; grid-template-columns: 2fr 1fr; gap: 1.5rem; padding: 0 !important; background: transparent !important; box-shadow: none !important; border: none !important; backdrop-filter: none !important;}
.chart-panel { padding: 1.5rem; }
.chart-wrap { position: relative; height: 260px; }
.chart-wrap canvas { width: 100% !important; height: 100% !important; }

/* Bandit Grid */
.bandit-grid { display: grid; grid-template-columns: 1fr 1fr auto; gap: 2rem; align-items: center; }
.bandit-bar-wrap { display: flex; flex-direction: column; gap: 0.75rem; }
.bandit-bar-label { display: flex; justify-content: space-between; font-size: 0.75rem; font-weight: 600; text-transform: uppercase; color: var(--text-muted); }
.bandit-bar-pct { font-family: var(--mono); font-weight: 700; color: #fff; }
.bandit-bar-track { height: 10px; background: rgba(0,0,0,0.5); border-radius: 10px; overflow: hidden; border: 1px solid rgba(255,255,255,0.05); }
.bandit-bar-fill { height: 100%; border-radius: 10px; transition: width 0.6s var(--ease-out); }
.bandit-bar-fill--heur { background: linear-gradient(90deg, #a18cd1, #fbc2eb); }
.bandit-bar-fill--band { background: linear-gradient(90deg, #00c6ff, #0072ff); }

.bandit-meta { display: flex; flex-direction: column; gap: 1rem; border-left: 1px solid var(--glass-border); padding-left: 2rem; }
.bandit-meta > div { display: flex; justify-content: space-between; gap: 2rem; align-items: center; }
.bandit-meta-label { font-size: 0.65rem; font-weight: 600; text-transform: uppercase; color: var(--text-muted); }
.bandit-meta-value { font-family: var(--mono); font-size: 0.9rem; font-weight: 700; color: #fff; }
.glow-text { text-shadow: 0 0 8px rgba(255,255,255,0.4); }

/* Buttons */
.glass-btn {
    background: rgba(255,75,43,0.1);
    border: 1px solid rgba(255,75,43,0.3);
    color: #ff4b2b;
    padding: 0.5rem 1rem;
    border-radius: 8px;
    font-family: var(--font);
    font-size: 0.75rem;
    font-weight: 600;
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    cursor: pointer;
    transition: all 0.3s var(--ease-out);
    backdrop-filter: blur(5px);
}
.glass-btn:hover { background: rgba(255,75,43,0.2); box-shadow: 0 0 15px rgba(255,75,43,0.4); transform: translateY(-1px); }

/* Table */
.table-wrap { overflow-x: auto; border-radius: 12px; border: 1px solid rgba(255,255,255,0.05); background: rgba(0,0,0,0.2); }
table { width: 100%; border-collapse: collapse; text-align: left; }
th { padding: 1rem; font-size: 0.65rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-muted); border-bottom: 1px solid rgba(255,255,255,0.05); background: rgba(255,255,255,0.02); }
td { padding: 1rem; font-size: 0.8rem; border-bottom: 1px solid rgba(255,255,255,0.02); transition: background 0.2s; }
tbody tr:hover td { background: rgba(255,255,255,0.04); }
.table-empty { text-align: center; color: var(--text-muted); padding: 3rem !important; font-style: italic; }

.chip {
    display: inline-flex; align-items: center; gap: 4px; padding: 2px 10px;
    border-radius: 20px; font-size: 0.65rem; font-weight: 700; text-transform: uppercase;
    font-family: var(--font); letter-spacing: 0.03em;
}
.chip::before { content:''; display:inline-block; width:6px; height:6px; border-radius:50%; }
.chip--heavy { background: rgba(244,114,182,0.1); color: #f472b6; border: 1px solid rgba(244,114,182,0.2); }
.chip--heavy::before { background: currentColor; box-shadow: 0 0 5px currentColor; }
.chip--light { background: rgba(129,140,248,0.1); color: #818cf8; border: 1px solid rgba(129,140,248,0.2); }
.chip--light::before { background: currentColor; box-shadow: 0 0 5px currentColor; }

.val-bad { color: #f87171; text-shadow: 0 0 5px rgba(248,113,113,0.4); }
.val-warn { color: #fbbf24; text-shadow: 0 0 5px rgba(251,191,36,0.4); }
.val-good { color: #34d399; text-shadow: 0 0 5px rgba(52,211,153,0.4); }
.val-mono { font-family: var(--mono); color: #fff; font-weight: 700; }

.footer { text-align: center; padding: 2rem 0; font-size: 0.7rem; color: var(--text-dim); }

/* Scrollbar */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: var(--bg-base); }
::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: rgba(255,255,255,0.2); }
"""

with open("static/index.html", "w", encoding="utf-8") as f:
    f.write(html_content)

with open("static/style.css", "w", encoding="utf-8") as f:
    f.write(css_content)

print("Rewrote index.html and style.css successfully!")
