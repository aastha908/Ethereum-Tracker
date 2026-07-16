import argparse
import json
import os
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict
from urllib.parse import parse_qs, urlparse

from comparison.report import generate_report, load_report


HOST = "127.0.0.1"
REPORTS_DIR = os.path.join(os.path.dirname(__file__), "reports")


def build_html_page() -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Milestone 5 Comparison Dashboard</title>
  <style>
    :root {{
      --bg: #f8f9fb;
      --paper: #ffffff;
      --ink: #182026;
      --muted: #5a6673;
      --line: #d8dfe6;
      --accent: #0f4c81;
      --accent-soft: #e8f1f9;
      --warm: #7a4e2f;
      --shadow: 0 8px 24px rgba(16, 24, 32, 0.08);
    }}

    * {{ box-sizing: border-box; }}

    body {{
      margin: 0;
      font-family: "Palatino Linotype", Palatino, "Book Antiqua", serif;
      color: var(--ink);
      background:
        linear-gradient(0deg, rgba(255, 255, 255, 0.92), rgba(255, 255, 255, 0.92)),
        repeating-linear-gradient(
          0deg,
          rgba(15, 76, 129, 0.03) 0,
          rgba(15, 76, 129, 0.03) 1px,
          transparent 1px,
          transparent 26px
        ),
        linear-gradient(130deg, #eef3f8 0%, #f6f7f9 45%, #ece8e2 100%);
      min-height: 100vh;
    }}

    .shell {{
      max-width: 1360px;
      margin: 0 auto;
      padding: 28px 22px 40px;
    }}

    .hero,
    .section-card {{
      background: var(--paper);
      border: 1px solid var(--line);
      border-radius: 18px;
      box-shadow: var(--shadow);
      padding: 26px 24px;
      margin-bottom: 22px;
    }}

    h1 {{
      margin: 0 0 8px;
      font-size: clamp(1.8rem, 2.8vw, 2.7rem);
      letter-spacing: -0.01em;
    }}

    h2 {{
      margin: 0;
      font-size: 1.32rem;
    }}

    h3 {{
      margin: 14px 0 6px;
      font-size: 1.02rem;
      font-family: "Helvetica Neue", "Segoe UI", sans-serif;
      letter-spacing: 0.03em;
      text-transform: uppercase;
      color: var(--accent);
      font-weight: 700;
    }}

    p, li {{
      color: var(--muted);
      line-height: 1.58;
    }}

    .hero p,
    .section-card p {{
      margin-top: 8px;
      margin-bottom: 0;
    }}

    .section-head {{
      display: grid;
      gap: 6px;
      margin-bottom: 14px;
      padding-bottom: 12px;
      border-bottom: 1px solid var(--line);
    }}

    .section-tag {{
      display: inline-block;
      width: fit-content;
      font-family: "Helvetica Neue", "Segoe UI", sans-serif;
      font-size: 0.74rem;
      font-weight: 700;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: var(--accent);
      background: var(--accent-soft);
      border: 1px solid rgba(15, 76, 129, 0.2);
      border-radius: 999px;
      padding: 4px 10px;
    }}

    .paper-note {{
      margin-top: 12px;
      padding: 12px 14px;
      border-left: 4px solid var(--warm);
      background: rgba(122, 78, 47, 0.06);
      border-radius: 8px;
      font-size: 0.95rem;
    }}

    .method-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
      gap: 14px;
      margin-top: 16px;
    }}

    .method-box {{
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 12px;
      background: #fcfdff;
    }}

    .meta-grid,
    .stats-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap: 16px;
      margin-top: 16px;
    }}

    .stat-box {{
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 14px;
      background: #fdfefe;
      min-height: 148px;
    }}

    .label {{
      font-family: "Helvetica Neue", "Segoe UI", sans-serif;
      font-size: 0.72rem;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.07em;
      color: var(--muted);
      margin-bottom: 8px;
    }}

    .value {{
      font-size: 0.96rem;
      color: var(--ink);
      font-family: Consolas, "Courier New", monospace;
      word-break: break-word;
      line-height: 1.45;
    }}

    .metrics-lines {{
      display: grid;
      gap: 4px;
      margin-top: 8px;
      font-family: Consolas, "Courier New", monospace;
      font-size: 0.88rem;
      color: #24303b;
    }}

    .comparison-note {{
      margin-top: 14px;
      padding: 12px 14px;
      border-radius: 10px;
      border: 1px solid rgba(15, 76, 129, 0.24);
      background: var(--accent-soft);
      color: #123650;
      line-height: 1.5;
    }}

    .reorg-list {{
      margin: 8px 0 0 0;
      padding-left: 18px;
    }}

    table {{
      width: 100%;
      border-collapse: collapse;
      margin-top: 16px;
      background: #fdfefe;
      border-radius: 12px;
      overflow: hidden;
      border: 1px solid var(--line);
    }}

    th, td {{
      border-bottom: 1px solid var(--line);
      padding: 10px 12px;
      text-align: left;
      font-size: 0.9rem;
    }}

    th {{
      background: #f2f6fa;
      font-weight: 700;
      font-family: "Helvetica Neue", "Segoe UI", sans-serif;
    }}

    .mode-chip {{
      display: inline-block;
      margin-top: 10px;
      padding: 6px 10px;
      border-radius: 999px;
      border: 1px solid rgba(15, 76, 129, 0.22);
      background: var(--accent-soft);
      font-size: 0.86rem;
      color: #123650;
    }}

    .mode-controls {{
      display: flex;
      gap: 12px;
      align-items: center;
      flex-wrap: wrap;
      margin-top: 12px;
    }}

    .mode-button,
    .mode-select {{
      border: 1px solid rgba(15, 76, 129, 0.25);
      background: #f6fafe;
      color: #123650;
      border-radius: 999px;
      padding: 8px 12px;
      font: inherit;
    }}

    .mode-button {{
      cursor: pointer;
    }}

    .mode-button.active {{
      background: var(--accent-soft);
      border-color: rgba(15, 76, 129, 0.4);
      color: #10324a;
      font-weight: 700;
    }}

    .mode-select {{
      display: none;
      min-width: 260px;
    }}

    .muted {{
      color: var(--muted);
      font-size: 0.88rem;
      line-height: 1.45;
    }}

    @media (max-width: 780px) {{
      .shell {{
        padding: 16px 12px 26px;
      }}

      .hero,
      .section-card {{
        padding: 18px 14px;
        border-radius: 14px;
      }}

      .stats-grid,
      .meta-grid {{
        grid-template-columns: 1fr;
      }}

      .mode-controls {{
        gap: 8px;
      }}
    }}
  </style>
</head>
<body>
  <div class="shell">
    <section class="hero">
      <h1>Milestone 5 Network Comparison Dashboard</h1>
      <p>Empirical side-by-side analysis of tracker outputs from Ethereum mainnet and a private PoS testnet.</p>
      <div class="mode-chip" id="modeBadge">Mode: Live</div>
      <div class="mode-controls">
        <button class="mode-button active" id="liveModeBtn" type="button">Live</button>
        <button class="mode-button" id="frozenModeBtn" type="button">Frozen Report</button>
        <select class="mode-select" id="reportSelect"></select>
      </div>
      <div class="meta-grid" id="windowMeta"></div>
      <div class="method-grid">
        <div class="method-box">
          <div class="label">Method</div>
          <div class="muted">Metrics are computed from persisted tracker events in SQLite and re-evaluated per request in live mode.</div>
        </div>
        <div class="method-box">
          <div class="label">Notation</div>
          <div class="muted">Each metric card states formula and unit. Distribution summaries report n, mean, median, p90, p99, std, min, and max.</div>
        </div>
        <div class="method-box">
          <div class="label">Interpretation</div>
          <div class="muted">H1 targets fidelity, H2 targets integrity, and H3 targets lifecycle behavior under different load profiles.</div>
        </div>
      </div>
    </section>

    <section class="section-card">
      <div class="section-head">
        <span class="section-tag">Hypothesis H1</span>
        <h2>Protocol Fidelity (should closely match)</h2>
        <p>Evaluates whether testnet consensus and block-production behavior follows mainnet-like protocol timing characteristics.</p>
      </div>
      <div class="comparison-note" id="h1Method"></div>
      <h3>Block Production Timing</h3>
      <div class="stats-grid" id="h1BlockInterval"></div>
      <div class="comparison-note" id="h1Comparison"></div>
      <h3>Finality Behavior</h3>
      <div class="stats-grid" id="h1Extra"></div>
    </section>

    <section class="section-card">
      <div class="section-head">
        <span class="section-tag">Hypothesis H2</span>
        <h2>Chain Integrity</h2>
        <p>Evaluates operational stability using missed-slot frequency and observed reorganization events.</p>
      </div>
      <p><strong>Formula:</strong> missed_rate = missed_slots / total_slots. <strong>Unit:</strong> ratio in [0,1].</p>
      <h3>Missed Slot Diagnostics</h3>
      <div class="stats-grid" id="h2Missed"></div>
      <h3>Reorganization Events</h3>
      <div id="h2Reorgs"></div>
    </section>

    <section class="section-card">
      <div class="section-head">
        <span class="section-tag">Hypothesis H3</span>
        <h2>Transaction Lifecycle (expected to diverge)</h2>
        <p>Compares inclusion, confirmation, and finalization timings while accounting for throughput and injector-driven traffic differences.</p>
      </div>
      <div class="comparison-note" id="h3Method"></div>
      <h3>Inclusion Latency</h3>
      <div class="stats-grid" id="h3Inclusion"></div>
      <h3>Finalization Latency</h3>
      <div class="stats-grid" id="h3Finalization"></div>
      <h3>Confirmation Milestones</h3>
      <table>
        <thead>
          <tr>
            <th>Milestone</th>
            <th>Mainnet Mean Seconds</th>
            <th>Testnet Mean Seconds</th>
          </tr>
        </thead>
        <tbody id="milestoneTable"></tbody>
      </table>
      <h3>Gas Utilization</h3>
      <div class="stats-grid" id="h3Gas"></div>
    </section>
  </div>

  <script>
    let currentMode = "live";
    let selectedReportFilename = "";
    let refreshTimer = null;

    function safeText(value) {{
      if (value === null || value === undefined) return "insufficient data";
      if (typeof value === "number") return Number.isFinite(value) ? value.toFixed(4) : "insufficient data";
      if (value === "") return "insufficient data";
      return String(value);
    }}

    function safeNumber(value) {{
      if (value === null || value === undefined) return null;
      const parsed = Number(value);
      return Number.isFinite(parsed) ? parsed : null;
    }}

    function statsSummaryHtml(title, stats, formula, unit) {{
      const s = stats || {{}};
      return `
        <div class="stat-box">
          <div class="label">${{title}}</div>
          <div class="metrics-lines">
            <div>n = ${{safeText(s.n)}}</div>
            <div>mean = ${{safeText(s.mean)}} | median = ${{safeText(s.median)}}</div>
            <div>p90 = ${{safeText(s.p90)}} | p99 = ${{safeText(s.p99)}}</div>
            <div>std = ${{safeText(s.stddev)}} | min = ${{safeText(s.min)}} | max = ${{safeText(s.max)}}</div>
          </div>
          <div class="value" style="margin-top: 8px;">f(x): ${{formula}}</div>
          <div class="muted">unit: ${{unit}}</div>
        </div>
      `;
    }}

    function scalarMetricHtml(title, scalar, details, formula, unit) {{
      return `
        <div class="stat-box">
          <div class="label">${{title}}</div>
          <div class="value">${{safeText(scalar)}}</div>
          <div class="muted" style="margin-top: 6px;">${{details}}</div>
          <div class="muted"><strong>Formula:</strong> ${{formula}}</div>
          <div class="muted"><strong>Unit:</strong> ${{unit}}</div>
        </div>
      `;
    }}

    function updateModeBadge() {{
      const badge = document.getElementById("modeBadge");
      if (currentMode === "live") {{
        badge.textContent = "Mode: Live";
        return;
      }}

      if (selectedReportFilename) {{
        badge.textContent = "Mode: Frozen Report (" + selectedReportFilename + ")";
      }} else {{
        badge.textContent = "Mode: Frozen Report";
      }}
    }}

    function setButtonState() {{
      document.getElementById("liveModeBtn").classList.toggle("active", currentMode === "live");
      document.getElementById("frozenModeBtn").classList.toggle("active", currentMode === "frozen");
    }}

    function stopAutoRefresh() {{
      if (refreshTimer) {{
        window.clearInterval(refreshTimer);
        refreshTimer = null;
      }}
    }}

    function startAutoRefresh() {{
      stopAutoRefresh();
      if (currentMode === "live") {{
        refreshTimer = window.setInterval(loadData, 15000);
      }}
    }}

    async function fetchReports() {{
      const response = await fetch("/reports", {{ cache: "no-store" }});
      if (!response.ok) {{
        throw new Error("Failed to load reports (" + response.status + ")");
      }}
      return await response.json();
    }}

    function populateReportSelect(filenames) {{
      const select = document.getElementById("reportSelect");
      select.innerHTML = "";

      const placeholder = document.createElement("option");
      placeholder.value = "";
      placeholder.textContent = filenames.length ? "Select a saved report..." : "No saved reports found";
      placeholder.disabled = true;
      placeholder.selected = true;
      select.appendChild(placeholder);

      for (const filename of filenames) {{
        const option = document.createElement("option");
        option.value = filename;
        option.textContent = filename;
        select.appendChild(option);
      }}

      select.style.display = "inline-block";
    }}

    async function activateLiveMode() {{
      currentMode = "live";
      selectedReportFilename = "";
      document.getElementById("reportSelect").style.display = "none";
      updateModeBadge();
      setButtonState();
      startAutoRefresh();
      await loadData();
    }}

    async function activateFrozenMode() {{
      currentMode = "frozen";
      selectedReportFilename = "";
      stopAutoRefresh();
      updateModeBadge();
      setButtonState();
      const filenames = await fetchReports();
      populateReportSelect(Array.isArray(filenames) ? filenames : []);
      updateModeBadge();
    }}

    function renderMeta(meta) {{
      const grid = document.getElementById("windowMeta");
      const start = meta && meta.start_time ? meta.start_time : "insufficient data";
      const end = meta && meta.end_time ? meta.end_time : "insufficient data";
      const generated = meta && meta.generated_at ? meta.generated_at : "insufficient data";
      grid.innerHTML = `
        <div class="stat-box"><div class="label">Observation Start</div><div class="value">${{safeText(start)}}</div></div>
        <div class="stat-box"><div class="label">Observation End</div><div class="value">${{safeText(end)}}</div></div>
        <div class="stat-box"><div class="label">Generated At</div><div class="value">${{safeText(generated)}}</div></div>
      `;
    }}

    function renderH1(payload) {{
      const h1 = payload && payload.h1_protocol_fidelity ? payload.h1_protocol_fidelity : {{}};
      const blockInterval = h1.block_interval || {{}};
      const main = blockInterval.mainnet || {{}};
      const test = blockInterval.testnet || {{}};

      document.getElementById("h1Method").textContent =
        "Block interval uses normalized per-block elapsed time: (t_i - t_(i-1)) / (block_number_i - block_number_(i-1)), in seconds.";

      const h1Grid = document.getElementById("h1BlockInterval");
      h1Grid.innerHTML =
        statsSummaryHtml("Mainnet Block Interval", main, "(Δtime) / (Δblock_number)", "seconds per block") +
        statsSummaryHtml("Testnet Block Interval", test, "(Δtime) / (Δblock_number)", "seconds per block");

      const comp = blockInterval.comparison || {{}};
      const compDiv = document.getElementById("h1Comparison");
      if (comp.insufficient_data) {{
        compDiv.textContent = `Insufficient data for statistical comparison (n_a=${{safeText(comp.n_a)}}, n_b=${{safeText(comp.n_b)}})`;
      }} else if (comp.error) {{
        compDiv.textContent = `Mann-Whitney U test failed: ${{safeText(comp.error)}}`;
      }} else {{
        const pVal = safeNumber(comp.p_value);
        const significant = !!comp.significant;
        const msg = significant
          ? "statistically significant difference"
          : "no significant difference";
        compDiv.textContent = `Mann-Whitney U test: p = ${{pVal === null ? "insufficient data" : pVal.toFixed(6)}} - ${{msg}}`;
      }}

      const extra = document.getElementById("h1Extra");
      const lagStats = h1.finality_lag_epochs_stats || {{}};
      const cadenceStats = h1.finality_cadence_seconds || {{}};
      extra.innerHTML =
        statsSummaryHtml(
          "Mainnet Finality Lag",
          lagStats.mainnet || {{}},
          "observed_epoch - finalized_epoch",
          "epochs"
        ) +
        statsSummaryHtml(
          "Testnet Finality Lag",
          lagStats.testnet || {{}},
          "observed_epoch - finalized_epoch",
          "epochs"
        ) +
        statsSummaryHtml(
          "Mainnet Finality Cadence",
          cadenceStats.mainnet || {{}},
          "recorded_at(i) - recorded_at(i-1)",
          "seconds"
        ) +
        statsSummaryHtml(
          "Testnet Finality Cadence",
          cadenceStats.testnet || {{}},
          "recorded_at(i) - recorded_at(i-1)",
          "seconds"
        );
    }}

    function renderH2(payload) {{
      const h2 = payload && payload.h2_chain_integrity ? payload.h2_chain_integrity : {{}};
      const missed = h2.missed_slots || {{}};

      const mainMissed = missed.mainnet || {{}};
      const testMissed = missed.testnet || {{}};

      const missedGrid = document.getElementById("h2Missed");
      missedGrid.innerHTML =
        scalarMetricHtml(
          "Mainnet Missed Slot Rate",
          mainMissed.missed_rate,
          `missed=${{safeText(mainMissed.missed_slots)}} / total=${{safeText(mainMissed.total_slots)}}`,
          "missed_slots / total_slots",
          "ratio"
        ) +
        scalarMetricHtml(
          "Testnet Missed Slot Rate",
          testMissed.missed_rate,
          `missed=${{safeText(testMissed.missed_slots)}} / total=${{safeText(testMissed.total_slots)}}`,
          "missed_slots / total_slots",
          "ratio"
        );

      const reorgs = h2.reorgs || {{}};
      const mainReorgs = Array.isArray(reorgs.mainnet) ? reorgs.mainnet : [];
      const testReorgs = Array.isArray(reorgs.testnet) ? reorgs.testnet : [];
      const holder = document.getElementById("h2Reorgs");

      function renderReorgList(title, items) {{
        if (!items.length) {{
          return `<div class="stat-box"><div class="label">${{title}}</div><div class="value">0 reorgs observed</div></div>`;
        }}
        const listItems = items.map((item) => `
          <li>#${{safeText(item.block_number)}} depth=${{safeText(item.depth)}} at ${{safeText(item.detected_time)}} group=${{safeText(item.reorg_group_id)}}</li>
        `).join("");
        return `
          <div class="stat-box">
            <div class="label">${{title}}</div>
            <ul class="reorg-list">${{listItems}}</ul>
          </div>
        `;
      }}

      holder.innerHTML = `
        <div class="stats-grid">
          ${{renderReorgList("Mainnet Reorgs", mainReorgs)}}
          ${{renderReorgList("Testnet Reorgs", testReorgs)}}
        </div>
      `;
    }}

    function renderH3(payload) {{
      const h3 = payload && payload.h3_transaction_lifecycle ? payload.h3_transaction_lifecycle : {{}};
      const inclusion = h3.time_to_inclusion || {{}};
      const mainInc = inclusion.mainnet || {{}};
      const testInc = inclusion.testnet || {{}};

      document.getElementById("h3Method").textContent =
        "Transaction times are measured as event_time deltas in seconds. Finalization metrics include direct FINALIZED-event timing and a block-level proxy based on +64 blocks.";

      const inclusionGrid = document.getElementById("h3Inclusion");
      inclusionGrid.innerHTML =
        statsSummaryHtml("Mainnet Time To Inclusion", mainInc, "MINED.event_time - PENDING_SEEN.event_time", "seconds") +
        statsSummaryHtml("Testnet Time To Inclusion", testInc, "MINED.event_time - PENDING_SEEN.event_time", "seconds");

      const finalizationGrid = document.getElementById("h3Finalization");
      const txFinalized = h3.time_to_transaction_finalized || {{}};
      const minedToFinalized = h3.time_from_mined_to_finalized || {{}};
      const blockFinalityProxy = h3.block_time_to_finality_proxy_64 || {{}};
      finalizationGrid.innerHTML =
        statsSummaryHtml("Mainnet Tx Time To Finalized", txFinalized.mainnet || {{}}, "FINALIZED.event_time - PENDING_SEEN.event_time", "seconds") +
        statsSummaryHtml("Testnet Tx Time To Finalized", txFinalized.testnet || {{}}, "FINALIZED.event_time - PENDING_SEEN.event_time", "seconds") +
        statsSummaryHtml("Mainnet Mined->Finalized", minedToFinalized.mainnet || {{}}, "FINALIZED.event_time - MINED.event_time", "seconds") +
        statsSummaryHtml("Testnet Mined->Finalized", minedToFinalized.testnet || {{}}, "FINALIZED.event_time - MINED.event_time", "seconds") +
        statsSummaryHtml("Mainnet Block Finality Proxy (+64)", blockFinalityProxy.mainnet || {{}}, "observed_time(block+64) - observed_time(block)", "seconds") +
        statsSummaryHtml("Testnet Block Finality Proxy (+64)", blockFinalityProxy.testnet || {{}}, "observed_time(block+64) - observed_time(block)", "seconds");

      const milestones = h3.confirmation_milestones || {{}};
      const mainMilestones = milestones.mainnet || {{}};
      const testMilestones = milestones.testnet || {{}};
      const milestoneKeys = [1, 3, 12, 32, 64];
      const tbody = document.getElementById("milestoneTable");
      tbody.innerHTML = milestoneKeys.map((milestone) => {{
        const mainStat = mainMilestones[milestone] || mainMilestones[String(milestone)] || null;
        const testStat = testMilestones[milestone] || testMilestones[String(milestone)] || null;
        const mainMean = mainStat && mainStat.mean !== undefined ? safeText(mainStat.mean) : "insufficient data";
        const testMean = testStat && testStat.mean !== undefined ? safeText(testStat.mean) : "insufficient data";
        return `<tr><td>${{milestone}}</td><td>${{mainMean}}</td><td>${{testMean}}</td></tr>`;
      }}).join("");

      const gas = h3.gas_utilization || {{}};
      const gasGrid = document.getElementById("h3Gas");
      const mainGas = gas.mainnet || {{}};
      const testGas = gas.testnet || {{}};
      gasGrid.innerHTML = `
        <div class="stat-box">
          <div class="label">Mainnet Gas Utilization Mean</div>
          <div class="value">${{safeText(mainGas.mean)}}</div>
          <div class="muted" style="margin-top: 6px;">ratio of gas_used / gas_limit at block level.</div>
          <div class="muted"><strong>Unit:</strong> ratio in [0,1]</div>
        </div>
        <div class="stat-box">
          <div class="label">Testnet Gas Utilization Mean</div>
          <div class="value">${{safeText(testGas.mean)}}</div>
          <div class="muted" style="margin-top: 6px;">ratio of gas_used / gas_limit at block level.</div>
          <div class="muted"><strong>Unit:</strong> ratio in [0,1]</div>
        </div>
      `;
    }}

    function render(payload) {{
      renderMeta(payload ? payload.meta : null);
      try {{
        renderH1(payload || {{}});
      }} catch (error) {{
        console.error("renderH1 failed", error);
      }}

      try {{
        renderH2(payload || {{}});
      }} catch (error) {{
        console.error("renderH2 failed", error);
      }}

      try {{
        renderH3(payload || {{}});
      }} catch (error) {{
        console.error("renderH3 failed", error);
      }}
    }}

    async function loadData() {{
      try {{
        let url = "/data?mode=" + encodeURIComponent(currentMode);
        if (currentMode === "frozen" && selectedReportFilename) {{
          url += "&report=" + encodeURIComponent(selectedReportFilename);
        }}

        const response = await fetch(url, {{ cache: "no-store" }});
        if (!response.ok) {{
          throw new Error(`dashboard request failed with status ${{response.status}}`);
        }}
        const payload = await response.json();
        render(payload);
      }} catch (error) {{
        console.error("dashboard load error", error);
      }}
    }}

    document.getElementById("liveModeBtn").addEventListener("click", activateLiveMode);
    document.getElementById("frozenModeBtn").addEventListener("click", activateFrozenMode);
    document.getElementById("reportSelect").addEventListener("change", async (event) => {{
      selectedReportFilename = event.target.value;
      if (!selectedReportFilename) {{
        updateModeBadge();
        return;
      }}

      currentMode = "frozen";
      stopAutoRefresh();
      updateModeBadge();
      setButtonState();
      await loadData();
    }});

    updateModeBadge();
    setButtonState();
    startAutoRefresh();
    loadData();
  </script>
</body>
</html>
"""


def build_live_report(window_minutes: int) -> dict:
    end_dt = datetime.now(timezone.utc)
    start_dt = end_dt - timedelta(minutes=window_minutes)

    return generate_report(
        mainnet_db_path="databases/mainnet.db",
        testnet_db_path="databases/testnet.db",
        start_time=start_dt.isoformat(),
        end_time=end_dt.isoformat(),
    )


class DashboardHandler(BaseHTTPRequestHandler):
    window_minutes = 60
    html_page = ""

    def do_GET(self) -> None:
        parsed = urlparse(self.path)

        if parsed.path == "/":
            body = self.html_page.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if parsed.path == "/reports":
            os.makedirs(REPORTS_DIR, exist_ok=True)
            report_filenames = sorted(
                [filename for filename in os.listdir(REPORTS_DIR) if filename.endswith(".json")],
                reverse=True,
            )
            payload = json.dumps(report_filenames).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return

        if parsed.path == "/data":
            query = parse_qs(parsed.query)
            mode = (query.get("mode", ["live"])[0] or "live").strip().lower()

            if mode not in {"live", "frozen"}:
                self.send_error(400, "Invalid mode")
                return

            if mode == "live":
                payload_obj = build_live_report(self.window_minutes)
            else:
                report_filename = (query.get("report", [""])[0] or "").strip()
                if not report_filename:
                    self.send_error(400, "report query parameter is required for frozen mode")
                    return

                if "/" in report_filename or ".." in report_filename:
                    self.send_error(400, "Invalid report filename")
                    return

                os.makedirs(REPORTS_DIR, exist_ok=True)
                report_path = os.path.abspath(os.path.join(REPORTS_DIR, report_filename))
                reports_root = os.path.abspath(REPORTS_DIR)
                if os.path.commonpath([reports_root, report_path]) != reports_root:
                    self.send_error(400, "Invalid report filename")
                    return

                if not os.path.isfile(report_path):
                    self.send_error(404, "Report not found")
                    return

                payload_obj = load_report(report_path)

            payload = json.dumps(payload_obj, default=str).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return

        self.send_error(404, "Not found")

    def log_message(self, format: str, *args: Any) -> None:
        return


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Milestone 5 comparison dashboard server")
    parser.add_argument("--port", type=int, default=8002)
    parser.add_argument("--window-minutes", type=int, default=60)
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    DashboardHandler.window_minutes = args.window_minutes
    DashboardHandler.html_page = build_html_page()

    server = ThreadingHTTPServer((HOST, args.port), DashboardHandler)
    print(f"Serving comparison dashboard at http://{HOST}:{args.port}")
    print("Mode: live/frozen per request")
    print(f"Window: last {args.window_minutes} minute(s) for live mode")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\\nStopping dashboard server...")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()