import argparse
import csv
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse
from collections import defaultdict, deque

parser = argparse.ArgumentParser(description="Blockchain fork viewer")
parser.add_argument("--network", choices=["mainnet", "testnet"], required=True)
parser.add_argument("--port", type=int, default=8000)
args = parser.parse_args()

if args.network == "mainnet":
  FINALIZED_CSV_FILE = "finalized_blocks_range.csv"
  LOG_CSV_FILE = "blocks_log.csv"
else:
  FINALIZED_CSV_FILE = "blocks_log_testnet.csv"
  LOG_CSV_FILE = "blocks_log_testnet.csv"

HOST = "127.0.0.1"
PORT = args.port

HTML_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Ethereum Chain And Reorg Viewer</title>
  <style>
    :root {
      --bg: #f4efe6;
      --panel: rgba(255, 251, 245, 0.96);
      --ink: #172121;
      --muted: #5f6b6d;
      --main-line: #c97d60;
      --fork-line: #2f6f83;
      --shared-line: #7d5a9f;
      --orphan-line: #b4552d;
      --main-node: #fffdf9;
      --fork-node: #eef8fb;
      --shared-node: #f6f0ff;
      --orphan-node: #fff1e8;
      --fork-border: rgba(47, 111, 131, 0.42);
      --shared-border: rgba(125, 90, 159, 0.42);
      --orphan-border: rgba(180, 85, 45, 0.42);
      --shadow: 0 18px 40px rgba(55, 38, 25, 0.12);
    }

    * { box-sizing: border-box; }

    body {
      margin: 0;
      font-family: Georgia, "Times New Roman", serif;
      color: var(--ink);
      background:
        radial-gradient(circle at top left, rgba(201, 125, 96, 0.22), transparent 28%),
        radial-gradient(circle at bottom right, rgba(47, 111, 131, 0.16), transparent 26%),
        linear-gradient(135deg, #f7f3eb 0%, #ece4d8 100%);
      min-height: 100vh;
    }

    .shell {
      max-width: 1460px;
      margin: 0 auto;
      padding: 24px;
    }

    .hero {
      background: var(--panel);
      border: 1px solid rgba(161, 61, 45, 0.12);
      border-radius: 24px;
      box-shadow: var(--shadow);
      padding: 24px;
      margin-bottom: 20px;
      backdrop-filter: blur(8px);
    }

    .hero h1 {
      margin: 0 0 8px;
      font-size: clamp(1.8rem, 3vw, 3rem);
      line-height: 1.05;
      letter-spacing: -0.03em;
    }

    .hero p {
      margin: 0;
      color: var(--muted);
      max-width: 980px;
      font-size: 1rem;
    }

    .toolbar {
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      align-items: center;
      justify-content: space-between;
      margin-top: 20px;
    }

    .controls {
      display: flex;
      gap: 10px;
      align-items: center;
      flex-wrap: wrap;
    }

    button {
      border: 0;
      border-radius: 999px;
      padding: 12px 16px;
      font: inherit;
      color: white;
      background: linear-gradient(135deg, #8d3529 0%, #bf6543 100%);
      cursor: pointer;
      box-shadow: 0 10px 24px rgba(161, 61, 45, 0.22);
    }

    button:disabled {
      cursor: not-allowed;
      opacity: 0.4;
      box-shadow: none;
    }

    .page-info {
      color: var(--muted);
      font-size: 0.95rem;
    }

    .legend {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      color: var(--muted);
      font-size: 0.9rem;
    }

    .chip {
      padding: 8px 12px;
      border-radius: 999px;
      background: rgba(201, 125, 96, 0.12);
      border: 1px solid rgba(201, 125, 96, 0.22);
    }

    .chip.fork {
      background: rgba(47, 111, 131, 0.1);
      border-color: rgba(47, 111, 131, 0.22);
    }

    .chip.orphan {
      background: rgba(180, 85, 45, 0.1);
      border-color: rgba(180, 85, 45, 0.22);
    }

    .graph-card {
      position: relative;
      background: var(--panel);
      border: 1px solid rgba(161, 61, 45, 0.12);
      border-radius: 28px;
      box-shadow: var(--shadow);
      overflow: hidden;
    }

    .graph-header {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      flex-wrap: wrap;
      padding: 18px 24px 0;
    }

    .graph-header h2 {
      margin: 0;
      font-size: 1.2rem;
    }

    .graph-header p {
      margin: 4px 0 0;
      color: var(--muted);
    }

    .canvas-wrap {
      position: relative;
      min-height: 520px;
      padding: 24px;
      overflow: hidden;
    }

    #graph {
      position: relative;
      min-height: 468px;
      border-radius: 22px;
      background:
        linear-gradient(180deg, rgba(255,255,255,0.75), rgba(255,250,245,0.8)),
        repeating-linear-gradient(
          90deg,
          rgba(191, 101, 67, 0.04) 0,
          rgba(191, 101, 67, 0.04) 1px,
          transparent 1px,
          transparent 92px
        );
      border: 1px solid rgba(191, 101, 67, 0.12);
      overflow: hidden;
      padding: 18px;
      cursor: grab;
      touch-action: pan-y;
      user-select: none;
    }

    #graph.dragging { cursor: grabbing; }

    #graph-inner {
      position: relative;
      min-height: 420px;
      width: 100%;
    }

    #links {
      position: absolute;
      inset: 0;
      pointer-events: none;
      overflow: visible;
    }

    .block-node {
      position: absolute;
      width: 154px;
      border-radius: 20px;
      padding: 14px 12px;
      min-height: 144px;
      box-shadow: 0 14px 32px rgba(64, 44, 31, 0.1);
      transition: transform 160ms ease, box-shadow 160ms ease, border-color 160ms ease;
    }

    .block-node.finalized {
      background: var(--main-node);
      border: 1px solid rgba(161, 61, 45, 0.18);
    }

    .block-node.fork {
      background: var(--fork-node);
      border: 1px solid var(--fork-border);
    }

    .block-node.shared-parent {
      background: var(--shared-node);
      border: 1px solid var(--shared-border);
    }

    .block-node.parent-proxy,
    .block-node.orphan {
      background: var(--orphan-node);
      border: 1px solid var(--orphan-border);
    }

    .block-node.focused {
      transform: translateY(-8px) scale(1.02);
      border-color: rgba(161, 61, 45, 0.65);
      box-shadow: 0 24px 38px rgba(161, 61, 45, 0.2);
    }

    .node-badge {
      display: inline-block;
      margin-bottom: 8px;
      padding: 4px 8px;
      border-radius: 999px;
      font-size: 0.68rem;
      font-weight: 700;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: #4f281e;
      background: rgba(201, 125, 96, 0.16);
    }

    .block-node.fork .node-badge {
      color: #184555;
      background: rgba(47, 111, 131, 0.14);
    }

    .block-node.shared-parent .node-badge {
      color: #4f2d73;
      background: rgba(125, 90, 159, 0.14);
    }

    .block-node.parent-proxy .node-badge,
    .block-node.orphan .node-badge {
      color: #7a3518;
      background: rgba(180, 85, 45, 0.14);
    }

    .block-number {
      font-size: 1.2rem;
      font-weight: 700;
      line-height: 1;
      margin-bottom: 8px;
    }

    .node-label {
      font-size: 0.74rem;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.08em;
      margin-bottom: 4px;
    }

    .node-value {
      font-family: Consolas, "Courier New", monospace;
      font-size: 0.72rem;
      color: #3b3f41;
      word-break: break-all;
    }

    .fork-detail-value {
      word-break: normal;
      white-space: normal;
      line-height: 1.35;
    }

    .status {
      padding: 0 24px 24px;
      color: var(--muted);
      font-size: 0.95rem;
    }

    .inline-note {
      color: var(--muted);
      font-size: 0.92rem;
    }

    .timeline-wrap {
      margin: 0 24px 24px;
      padding: 18px 20px 20px;
      border: 1px solid rgba(161, 61, 45, 0.1);
      border-radius: 22px;
      background:
        linear-gradient(180deg, rgba(255, 251, 245, 0.98), rgba(245, 238, 228, 0.94)),
        radial-gradient(circle at center, rgba(201, 125, 96, 0.08), transparent 65%);
      box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.85);
    }

    .timeline-header {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: flex-start;
      flex-wrap: wrap;
      margin-bottom: 18px;
    }

    .timeline-title {
      margin: 0;
      font-size: 1rem;
    }

    .timeline-subtitle {
      margin: 4px 0 0;
      color: var(--muted);
      font-size: 0.88rem;
    }

    .timeline-focus {
      padding: 10px 14px;
      border-radius: 16px;
      background: rgba(255, 255, 255, 0.74);
      border: 1px solid rgba(161, 61, 45, 0.12);
      box-shadow: 0 10px 28px rgba(55, 38, 25, 0.08);
      min-width: min(100%, 320px);
    }

    .timeline-focus-label {
      font-size: 0.72rem;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: var(--muted);
      margin-bottom: 4px;
    }

    .timeline-focus-value {
      font-size: 1rem;
      font-weight: 700;
      line-height: 1.2;
    }

    .timeline-focus-meta {
      margin-top: 4px;
      color: var(--muted);
      font-size: 0.85rem;
    }

    .timeline-rail {
      position: relative;
      height: 106px;
      overflow: hidden;
    }

    .timeline-date-anchor {
      position: absolute;
      left: 0;
      top: 0;
      z-index: 2;
      width: 132px;
      height: 100%;
      padding-right: 16px;
      background: linear-gradient(90deg, rgba(244, 239, 230, 0.98) 0%, rgba(244, 239, 230, 0.9) 78%, rgba(244, 239, 230, 0) 100%);
    }

    .timeline-date-day {
      font-size: 2rem;
      line-height: 0.9;
      font-weight: 700;
      letter-spacing: -0.04em;
      color: var(--ink);
    }

    .timeline-date-month {
      margin-top: 6px;
      font-size: 0.82rem;
      text-transform: uppercase;
      letter-spacing: 0.16em;
      color: var(--muted);
    }

    .timeline-line {
      position: absolute;
      left: 0;
      right: 0;
      top: 38px;
      height: 10px;
      border-radius: 999px;
      background:
        linear-gradient(90deg, rgba(201, 125, 96, 0.2), rgba(47, 111, 131, 0.16)),
        linear-gradient(180deg, rgba(255,255,255,0.72), rgba(255,255,255,0.2));
      box-shadow: inset 0 1px 3px rgba(0, 0, 0, 0.08);
    }

    .timeline-progress {
      position: absolute;
      top: 38px;
      height: 10px;
      border-radius: 999px;
      background: linear-gradient(90deg, #c97d60 0%, #8d3529 100%);
      box-shadow: 0 10px 24px rgba(161, 61, 45, 0.18);
      transform: translateX(-50%);
    }

    .timeline-marker {
      position: absolute;
      top: 18px;
      transform: translateX(-50%);
      width: 0;
      pointer-events: none;
    }

    .timeline-marker-dot {
      width: 14px;
      height: 14px;
      margin: 0 auto;
      border-radius: 999px;
      background: #fffaf4;
      border: 3px solid rgba(201, 125, 96, 0.68);
      box-shadow: 0 0 0 6px rgba(201, 125, 96, 0.12);
    }

    .timeline-marker.center .timeline-marker-dot {
      width: 18px;
      height: 18px;
      border-color: rgba(47, 111, 131, 0.78);
      box-shadow: 0 0 0 9px rgba(47, 111, 131, 0.16);
      background: #f5fcff;
    }

    .timeline-marker-label {
      margin-top: 14px;
      min-width: 62px;
      text-align: center;
      transform: translateX(-50%);
      color: var(--muted);
      font-size: 0.8rem;
      font-variant-numeric: tabular-nums;
      line-height: 1.25;
    }

    .timeline-marker-label strong {
      color: var(--ink);
      font-size: 0.92rem;
      font-weight: 700;
    }

    @media (max-width: 900px) {
      .timeline-wrap {
        margin: 0 18px 18px;
        padding: 16px;
      }

      .timeline-rail {
        height: 118px;
      }

      .timeline-date-anchor {
        width: 108px;
      }

      .timeline-date-day {
        font-size: 1.65rem;
      }

      .timeline-marker-label {
        min-width: 52px;
        font-size: 0.74rem;
      }
    }
  </style>
</head>
<body>
  <div class="shell">
    <section class="hero">
      <h1>Ethereum Chain And Reorg Viewer</h1>
      <p>
        The finalized chain stays as the main blockchain lane. Any conflicting blocks found in <code>blocks_log.csv</code>
        are rendered as branch lanes below it, so you can drag through the chain and visually inspect forks or short reorgs.
      </p>
      <div class="toolbar">
        <div class="controls">
          <button id="prevBtn" type="button">&larr; Move Left</button>
          <button id="nextBtn" type="button">Move Right &rarr;</button>
          <span id="positionInfo" class="page-info">Loading data...</span>
        </div>
        <div class="legend">
          <span class="chip">Main chain: finalized blocks</span>
          <span class="chip fork">Fork lanes: conflicting or reorg blocks</span>
          <span class="chip orphan">Orphan/linked parent helper</span>
          <span class="chip" id="windowSizeLabel">Visible span: 0 block numbers</span>
        </div>
      </div>
    </section>

    <section class="graph-card">
      <div class="graph-header">
        <div>
          <h2>Visible Chain Slice</h2>
          <p id="rangeLabel">Preparing graph...</p>
        </div>
        <div class="inline-note" id="summaryLabel"></div>
      </div>
      <div class="canvas-wrap">
        <div id="graph">
          <div id="graph-inner">
            <svg id="links"></svg>
          </div>
        </div>
      </div>
      <div class="timeline-wrap">
        <div class="timeline-header">
          <div>
            <h3 class="timeline-title">Chain Timeline</h3>
            <p class="timeline-subtitle" id="timelineSummary">Syncing timeline with the visible chain span...</p>
          </div>
          <div class="timeline-focus">
            <div class="timeline-focus-label">Focused Chain Position</div>
            <div class="timeline-focus-value" id="timelineFocusValue">Loading...</div>
            <div class="timeline-focus-meta" id="timelineFocusMeta"></div>
          </div>
        </div>
        <div class="timeline-rail">
          <div class="timeline-date-anchor">
            <div class="timeline-date-day" id="timelineDateDay">--</div>
          <div class="timeline-date-month" id="timelineDateMonth">---</div>
          </div>
          <div class="timeline-line" style="left: 132px;"></div>
          <div class="timeline-progress" id="timelineProgress"></div>
          <div id="timelineMarkers"></div>
        </div>
      </div>
      <div id="status" class="status"></div>
    </section>
  </div>

  <script>
    const state = {
      finalizedBlocks: [],
      forkBlocks: [],
      finalizedByNumber: {},
      forkBlocksByNumber: {},
      blockLookup: {},
      forkBlockNumbers: [],
      offsetPx: 0,
      maxOffsetPx: 0,
      minBlockNumber: 0,
      maxBlockNumber: 0,
      isDragging: false,
      dragStartX: 0,
      dragStartOffsetPx: 0,
      pendingFrame: null
    };

    const graph = document.getElementById("graph");
    const graphInner = document.getElementById("graph-inner");
    const links = document.getElementById("links");
    const prevBtn = document.getElementById("prevBtn");
    const nextBtn = document.getElementById("nextBtn");
    const positionInfo = document.getElementById("positionInfo");
    const rangeLabel = document.getElementById("rangeLabel");
    const summaryLabel = document.getElementById("summaryLabel");
    const status = document.getElementById("status");
    const windowSizeLabel = document.getElementById("windowSizeLabel");
    const timelineSummary = document.getElementById("timelineSummary");
    const timelineFocusValue = document.getElementById("timelineFocusValue");
    const timelineFocusMeta = document.getElementById("timelineFocusMeta");
    const timelineProgress = document.getElementById("timelineProgress");
    const timelineMarkers = document.getElementById("timelineMarkers");
    const timelineDateDay = document.getElementById("timelineDateDay");
    const timelineDateMonth = document.getElementById("timelineDateMonth");

    const layout = {
      cardWidth: 154,
      cardHeight: 236,
      gapX: 84,
      gapY: 98,
      padding: 32,
      renderBuffer: 4
    };

    function getStepX() {
      return layout.cardWidth + layout.gapX;
    }

    function shortHash(value) {
      if (!value) return "missing";
      if (value.length <= 18) return value;
      return value.slice(0, 10) + "..." + value.slice(-8);
    }

    function blockNumberToX(blockNumber) {
      return layout.padding + (blockNumber - state.minBlockNumber) * getStepX() - state.offsetPx;
    }

    function createNode(block, lane, kind, focused, offsetX = 0, offsetY = 0) {
      const node = document.createElement("div");
      node.className = `block-node ${kind}`;
      if (focused) {
        node.classList.add("focused");
      }

      node.style.left = (blockNumberToX(block.block_number) + offsetX) + "px";
      node.style.top = (layout.padding + lane * (layout.cardHeight + layout.gapY) + offsetY) + "px";
      node.dataset.hash = block.block_hash || "";

      const badgeLabel = kind === "fork"
        ? "Fork"
        : kind === "shared-parent"
          ? "Shared Unit"
          : kind === "parent-proxy"
            ? "Parent Link"
            : kind === "orphan"
              ? "Orphaned Block"
          : "Finalized";
      const parentDiffLabel = block.parent_matches_finalized === false ? "Different parent" : "Parent matches";
      const hashDiffLabel = block.hash_matches_finalized === false ? "Different hash" : "Hash matches";
      const unitLabel = block.parent_unit_label || "";
      const unitCountSummary = block.parent_unit_count > 1
        ? `${block.parent_unit_count} blocks`
        : "";
      const sharedParentSummary = block.shared_child_count
        ? `Shared by ${block.shared_child_count} child blocks`
        : "";

      node.innerHTML = `
        <div class="node-badge">${badgeLabel}</div>
        <div class="block-number">#${block.block_number}</div>
        <div class="node-label">Timestamp</div>
        <div class="node-value">${block.timestamp}</div>
        <div class="node-label" style="margin-top:10px;">Hash</div>
        <div class="node-value">${shortHash(block.block_hash)}</div>
        <div class="node-label" style="margin-top:10px;">Parent Hash</div>
        <div class="node-value">${shortHash(block.parent_hash)}</div>
        ${unitLabel ? `
          <div class="node-label" style="margin-top:10px;">${unitLabel}</div>
          <div class="node-value fork-detail-value">${unitCountSummary}</div>
        ` : ""}
        ${sharedParentSummary ? `
          <div class="node-label" style="margin-top:10px;">Fork Detail</div>
          <div class="node-value fork-detail-value">${sharedParentSummary}</div>
        ` : ""}
        ${kind === "fork" ? `
          <div class="node-label" style="margin-top:10px;">Fork Detail</div>
          <div class="node-value fork-detail-value">${hashDiffLabel} | ${parentDiffLabel}</div>
        ` : ""}
      `;

      return node;
    }

    function getVisibleRange() {
      const viewportWidth = Math.max(graph.clientWidth - 36, 1);
      const visibleCount = Math.max(Math.ceil(viewportWidth / getStepX()), 1);
      const startBlockNumber = Math.max(
        state.minBlockNumber,
        state.minBlockNumber + Math.floor(state.offsetPx / getStepX()) - layout.renderBuffer
      );
      const endBlockNumber = Math.min(
        state.maxBlockNumber,
        startBlockNumber + visibleCount + layout.renderBuffer * 2 - 1
      );

      return { startBlockNumber, endBlockNumber, visibleCount };
    }

    function getCenteredBlockNumber() {
      const viewportWidth = Math.max(graph.clientWidth - 36, 1);
      const centerPx = state.offsetPx + viewportWidth / 2;
      const centerOffset = Math.round((centerPx - layout.padding - layout.cardWidth / 2) / getStepX());
      return Math.min(Math.max(state.minBlockNumber + centerOffset, state.minBlockNumber), state.maxBlockNumber);
    }

    function blockNumberToOffset(blockNumber) {
      return clampOffset((blockNumber - state.minBlockNumber) * getStepX());
    }

    function formatTimestampParts(timestamp) {
      if (!timestamp) {
        return { date: "Unknown date", time: "Unknown time", day: "--", month: "---" };
      }

      const [datePart = timestamp, timePart = ""] = String(timestamp).split(" ");
      const [year = "", month = "", day = ""] = datePart.split("-");
      const monthNames = {
        "01": "Jan",
        "02": "Feb",
        "03": "Mar",
        "04": "Apr",
        "05": "May",
        "06": "Jun",
        "07": "Jul",
        "08": "Aug",
        "09": "Sep",
        "10": "Oct",
        "11": "Nov",
        "12": "Dec"
      };
      const hourMinute = timePart ? timePart.slice(0, 5) : "time unavailable";
      return {
        date: datePart,
        time: timePart || "time unavailable",
        shortTime: hourMinute,
        day: day || "--",
        month: monthNames[month] || month || "---"
      };
    }

    function buildTimelineEntries(startBlockNumber, endBlockNumber, centeredBlockNumber) {
      const entriesByBlock = new Map();
      const steps = 4;

      for (let index = 0; index <= steps; index += 1) {
        const ratio = steps === 0 ? 0 : index / steps;
        const blockNumber = Math.round(
          startBlockNumber + (endBlockNumber - startBlockNumber) * ratio
        );
        const block = state.finalizedByNumber[blockNumber];
        if (block) {
          entriesByBlock.set(blockNumber, {
            block_number: blockNumber,
            timestamp: block.timestamp,
            ratio
          });
        }
      }

      const centeredBlock = state.finalizedByNumber[centeredBlockNumber];
      if (centeredBlock) {
        const centeredRatio = endBlockNumber === startBlockNumber
          ? 0
          : (centeredBlockNumber - startBlockNumber) / (endBlockNumber - startBlockNumber);
        entriesByBlock.set(centeredBlockNumber, {
          block_number: centeredBlockNumber,
          timestamp: centeredBlock.timestamp,
          ratio: Math.min(Math.max(centeredRatio, 0), 1),
          centered: true
        });
      }

      return [...entriesByBlock.values()].sort((left, right) => left.block_number - right.block_number);
    }

    function renderTimeline(startBlockNumber, endBlockNumber, centeredBlockNumber) {
      timelineMarkers.replaceChildren();

      const centeredBlock = state.finalizedByNumber[centeredBlockNumber];
      if (!centeredBlock) {
        timelineSummary.textContent = "Timeline unavailable for the current chain location.";
        timelineFocusValue.textContent = "Timestamp unavailable";
        timelineFocusMeta.textContent = "";
        timelineProgress.style.width = "0";
        timelineProgress.style.left = "0";
        return;
      }

      const visibleStartBlock = state.finalizedByNumber[startBlockNumber] || centeredBlock;
      const visibleEndBlock = state.finalizedByNumber[endBlockNumber] || centeredBlock;
      const startParts = formatTimestampParts(visibleStartBlock.timestamp);
      const endParts = formatTimestampParts(visibleEndBlock.timestamp);
      const centerParts = formatTimestampParts(centeredBlock.timestamp);

      timelineSummary.textContent =
        `Visible time span from ${startParts.date} ${startParts.time} to ${endParts.date} ${endParts.time}`;
      timelineFocusValue.textContent = `${centerParts.date} ${centerParts.time}`;
      timelineFocusMeta.textContent = `Centered at block #${centeredBlockNumber.toLocaleString()}`;
      timelineDateDay.textContent = startParts.day;
      timelineDateMonth.textContent = startParts.month;

      const progressRatio = endBlockNumber === startBlockNumber
        ? 0
        : (centeredBlockNumber - startBlockNumber) / (endBlockNumber - startBlockNumber);
      const progressPercent = Math.min(Math.max(progressRatio, 0), 1) * 100;
      const railInset = window.innerWidth <= 900 ? 108 : 132;
      timelineProgress.style.left = `calc(${railInset}px + ((100% - ${railInset}px) * ${progressPercent / 100}))`;
      timelineProgress.style.width = `calc((100% - ${railInset}px) * ${progressPercent / 100})`;

      const fragment = document.createDocumentFragment();
      const entries = buildTimelineEntries(startBlockNumber, endBlockNumber, centeredBlockNumber);

      for (const entry of entries) {
        const parts = formatTimestampParts(entry.timestamp);
        const marker = document.createElement("div");
        marker.className = `timeline-marker${entry.centered ? " center" : ""}`;
        marker.style.left = `calc(${railInset}px + ((100% - ${railInset}px) * ${entry.ratio}))`;
        marker.innerHTML = `
          <div class="timeline-marker-dot"></div>
          <div class="timeline-marker-label">
            <strong>${parts.shortTime}</strong>
          </div>
        `;
        fragment.appendChild(marker);
      }

      timelineMarkers.appendChild(fragment);
    }

    function getPreviousForkBlockNumber(currentBlockNumber) {
      for (let index = state.forkBlockNumbers.length - 1; index >= 0; index -= 1) {
        if (state.forkBlockNumbers[index] < currentBlockNumber) {
          return state.forkBlockNumbers[index];
        }
      }
      return undefined;
    }

    function getNextForkBlockNumber(currentBlockNumber) {
      for (const blockNumber of state.forkBlockNumbers) {
        if (blockNumber > currentBlockNumber) {
          return blockNumber;
        }
      }
      return undefined;
    }

    function drawArrow(fromEl, toEl, strokeColor) {
      const startX = fromEl.offsetLeft + layout.cardWidth;
      const startY = fromEl.offsetTop + fromEl.offsetHeight / 2;
      const endX = toEl.offsetLeft;
      const endY = toEl.offsetTop + toEl.offsetHeight / 2;
      const midX = startX + (endX - startX) / 2;

      const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
      path.setAttribute("d", `M ${startX} ${startY} C ${midX} ${startY}, ${midX} ${endY}, ${endX - 16} ${endY}`);
      path.setAttribute("fill", "none");
      path.setAttribute("stroke", strokeColor);
      path.setAttribute("stroke-width", "3");
      path.setAttribute("stroke-linecap", "round");

      const arrow = document.createElementNS("http://www.w3.org/2000/svg", "polygon");
      arrow.setAttribute("points", `${endX - 16},${endY - 7} ${endX},${endY} ${endX - 16},${endY + 7}`);
      arrow.setAttribute("fill", strokeColor);

      links.appendChild(path);
      links.appendChild(arrow);
    }

    function getVisibleFinalized(startBlockNumber, endBlockNumber) {
      const firstNumber = state.finalizedBlocks[0]?.block_number ?? startBlockNumber;
      const startIndex = Math.max(startBlockNumber - firstNumber, 0);
      const endIndex = Math.min(endBlockNumber - firstNumber + 1, state.finalizedBlocks.length);
      return state.finalizedBlocks.slice(startIndex, endIndex);
    }

    function getVisibleForks(startBlockNumber, endBlockNumber) {
      const blocks = [];
      for (let number = startBlockNumber; number <= endBlockNumber; number += 1) {
        const items = state.forkBlocksByNumber[number];
        if (items) {
          blocks.push(...items);
        }
      }
      return blocks;
    }

    function buildParentReferenceNodes(visibleBlocks, nodesByHash, parentUnitByHash) {
      const parentRefs = [];
      const parentRefByHash = new Map();

      visibleBlocks.forEach((block) => {
        const parentHash = block.parent_hash;
        if (!parentHash || nodesByHash.has(parentHash) || parentRefByHash.has(parentHash)) {
          return;
        }

        const parentRow = state.blockLookup[parentHash];
        const unit = parentUnitByHash.get(parentHash);
        const isOrphan = !parentRow;
        const lane = block.kind === "finalized" ? 0 : (block.displayLane || 1);
        const parentBlock = parentRow
          ? {
              ...parentRow,
              parent_unit_label: unit?.label || parentRow.parent_unit_label || "",
              parent_unit_count: unit?.count || parentRow.parent_unit_count || 0
            }
          : {
              block_number: Math.max(block.block_number - 1, state.minBlockNumber),
              block_hash: parentHash,
              parent_hash: "missing",
              timestamp: "Unavailable in CSV",
              parent_unit_label: "",
              parent_unit_count: 0
            };

        const reference = {
          hash: parentHash,
          block: parentBlock,
          kind: isOrphan ? "orphan" : unit?.label === "Shared Unit" ? "shared-parent" : "parent-proxy",
          lane,
          offsetX: -Math.round(layout.cardWidth * 0.78),
          offsetY: isOrphan ? -18 : -34,
        };
        parentRefs.push(reference);
        parentRefByHash.set(parentHash, reference);
      });

      return parentRefs;
    }

    function render() {
      graphInner.querySelectorAll(".block-node").forEach((element) => element.remove());
      links.innerHTML = "";

      if (!state.finalizedBlocks.length) {
        positionInfo.textContent = "No blocks loaded";
        rangeLabel.textContent = "No blocks available";
        summaryLabel.textContent = "0 blocks loaded";
        status.textContent = "The dataset is empty.";
        prevBtn.disabled = true;
        nextBtn.disabled = true;
        return;
      }

      const { startBlockNumber, endBlockNumber, visibleCount } = getVisibleRange();
      const centeredBlockNumber = getCenteredBlockNumber();
      const visibleFinalized = getVisibleFinalized(startBlockNumber, endBlockNumber);
      const visibleForks = getVisibleForks(startBlockNumber, endBlockNumber);
      const visibleRealHashes = new Set([
        ...visibleFinalized.map((block) => block.block_hash),
        ...visibleForks.map((block) => block.block_hash)
      ]);
      const rootEntries = new Map();

      visibleForks.forEach((block) => {
        if (!rootEntries.has(block.root_hash)) {
          rootEntries.set(block.root_hash, {
            rootHash: block.root_hash,
            rootBlockNumber: block.root_block_number
          });
        }
      });

      const sortedRoots = [...rootEntries.values()].sort((left, right) => {
        if (left.rootBlockNumber !== right.rootBlockNumber) {
          return left.rootBlockNumber - right.rootBlockNumber;
        }
        return left.rootHash.localeCompare(right.rootHash);
      });

      const rootToLane = new Map(sortedRoots.map((root, index) => [root.rootHash, index + 1]));
      const forkDisplayByHash = new Map();
      const siblingGroups = new Map();
      const syntheticSharedParents = [];
      const parentUnitByHash = new Map();
      const visibleBlocks = [];

      [...visibleFinalized, ...visibleForks].forEach((block) => {
        const groupKey = `${block.block_number}|${block.parent_hash}`;
        if (!siblingGroups.has(groupKey)) {
          siblingGroups.set(groupKey, []);
        }
        siblingGroups.get(groupKey).push(block);
      });

      siblingGroups.forEach((group) => {
        const sortedGroup = [...group].sort((left, right) => left.block_hash.localeCompare(right.block_hash));
        const anchorLane = Math.min(
          ...sortedGroup.map((block) => rootToLane.get(block.root_hash) || 1)
        );
        const siblingCount = sortedGroup[0].shared_parent_total || sortedGroup.length;
        const unitLabel = siblingCount >= 3 ? "Shared Unit" : siblingCount === 2 ? "Single Unit" : "";
        const hasVisibleParentNode = visibleRealHashes.has(sortedGroup[0].parent_hash);
        const sharedParentBlock = siblingCount >= 3 && !hasVisibleParentNode
          ? {
              block_number: sortedGroup[0].block_number - 1,
              block_hash: sortedGroup[0].parent_hash,
              parent_hash: "n/a",
              timestamp: sortedGroup[0].timestamp,
              shared_child_count: sortedGroup.length,
              parent_unit_label: "Shared Unit",
              parent_unit_count: siblingCount,
            }
          : null;

        if (unitLabel) {
          parentUnitByHash.set(sortedGroup[0].parent_hash, {
            label: unitLabel,
            count: siblingCount,
          });
        }

        if (sharedParentBlock) {
          syntheticSharedParents.push({ parent: sharedParentBlock, lane: anchorLane, children: sortedGroup });
        }

        sortedGroup.forEach((block, index) => {
          const centeredIndex = index - (sortedGroup.length - 1) / 2;
          const offsetX = Math.round(centeredIndex * 46);
          const offsetY = sharedParentBlock ? 54 + index * 26 : sortedGroup.length > 1 ? index * 26 : 0;
          forkDisplayByHash.set(block.block_hash, {
            lane: anchorLane,
            offsetX,
            offsetY,
          });
        });
      });

      const nodesByHash = new Map();
      const visibleHashes = new Set();
      const centeredFinalized = state.finalizedByNumber[centeredBlockNumber];

      visibleFinalized.forEach((block) => {
        visibleHashes.add(block.block_hash);
        const parentUnit = parentUnitByHash.get(block.block_hash);
        const node = createNode(
          {
            ...block,
            hash_matches_finalized: true,
            parent_matches_finalized: true,
            parent_unit_label: parentUnit?.label || "",
            parent_unit_count: parentUnit?.count || 0
          },
          0,
          "finalized",
          centeredFinalized && centeredFinalized.block_hash === block.block_hash
        );
        graphInner.appendChild(node);
        nodesByHash.set(block.block_hash, node);
        visibleBlocks.push({
          ...block,
          kind: "finalized",
          displayLane: 0,
        });
      });

      syntheticSharedParents.forEach((entry) => {
        const parentBlock = entry.parent;
        visibleHashes.add(parentBlock.block_hash);
        const node = createNode(parentBlock, entry.lane, "shared-parent", false, 0, 0);
        graphInner.appendChild(node);
        nodesByHash.set(parentBlock.block_hash, node);
      });

      visibleForks.forEach((block) => {
        visibleHashes.add(block.block_hash);
        const display = forkDisplayByHash.get(block.block_hash) || {
          lane: rootToLane.get(block.root_hash) || 1,
          offsetX: 0,
          offsetY: 0,
        };
        const parentUnit = parentUnitByHash.get(block.block_hash);
        const node = createNode(
          {
            ...block,
            parent_unit_label: parentUnit?.label || block.parent_unit_label || "",
            parent_unit_count: parentUnit?.count || block.parent_unit_count || 0
          },
          display.lane,
          "fork",
          false,
          display.offsetX,
          display.offsetY
        );
        graphInner.appendChild(node);
        nodesByHash.set(block.block_hash, node);
        visibleBlocks.push({
          ...block,
          kind: "fork",
          displayLane: display.lane,
        });
      });

      parentUnitByHash.forEach((unit, hash) => {
        const node = nodesByHash.get(hash);
        if (node) {
          if (unit.label === "Shared Unit") {
            node.classList.add("shared-parent");
          }
          const badge = node.querySelector(".node-badge");
          if (badge) {
            badge.textContent = unit.label;
          }
        }
      });

      const parentReferenceNodes = buildParentReferenceNodes(visibleBlocks, nodesByHash, parentUnitByHash);
      parentReferenceNodes.forEach((reference) => {
        const node = createNode(
          reference.block,
          reference.lane,
          reference.kind,
          false,
          reference.offsetX,
          reference.offsetY
        );
        graphInner.appendChild(node);
        nodesByHash.set(reference.hash, node);
        visibleHashes.add(reference.hash);
      });

      const laneCount = Math.max(sortedRoots.length + 1, 1);
      const height = layout.padding * 2 + laneCount * layout.cardHeight + (laneCount - 1) * layout.gapY;
      const width = Math.max(graph.clientWidth - 36, 1);
      graphInner.style.width = width + "px";
      graphInner.style.height = Math.max(height, 420) + "px";
      links.setAttribute("width", String(width));
      links.setAttribute("height", String(Math.max(height, 420)));

      syntheticSharedParents.forEach((entry) => {
        const parentEl = nodesByHash.get(entry.parent.block_hash);
        if (!parentEl) {
          return;
        }
        entry.children.forEach((child) => {
          const childEl = nodesByHash.get(child.block_hash);
          if (childEl) {
            drawArrow(parentEl, childEl, "var(--shared-line)");
          }
        });
      });

      visibleBlocks.forEach((block) => {
        const unit = parentUnitByHash.get(block.parent_hash);
        if (unit && unit.label === "Shared Unit") {
          return;
        }
        const parentEl = nodesByHash.get(block.parent_hash);
        const childEl = nodesByHash.get(block.block_hash);
        if (!parentEl || !childEl) {
          return;
        }

        const lineColor = parentEl.classList.contains("orphan")
          ? "var(--orphan-line)"
          : block.kind === "fork"
            ? "var(--fork-line)"
            : "var(--main-line)";
        drawArrow(parentEl, childEl, lineColor);
      });

      const orphanCount = parentReferenceNodes.filter((reference) => reference.kind === "orphan").length;
      const outsideParentCount =
        visibleFinalized.filter((block) => block.parent_hash && !visibleHashes.has(block.parent_hash)).length +
        visibleForks.filter((block) => block.parent_hash && !visibleHashes.has(block.parent_hash)).length;

      positionInfo.textContent =
        `Centered block number #${centeredBlockNumber.toLocaleString()} | ${visibleForks.length.toLocaleString()} fork block(s) visible`;
      rangeLabel.textContent =
        `Visible block numbers ${startBlockNumber.toLocaleString()} to ${endBlockNumber.toLocaleString()}`;
      summaryLabel.textContent =
        `${state.finalizedBlocks.length.toLocaleString()} finalized blocks + ${state.forkBlocks.length.toLocaleString()} fork/reorg blocks`;
      status.textContent = visibleForks.length
        ? `${sortedRoots.length} fork lane(s) are visible in this slice. ${orphanCount} orphaned parent block(s) shown. ${outsideParentCount} link(s) continue outside the visible span.`
        : `No fork blocks are visible in this slice. ${orphanCount} orphaned parent block(s) shown. ${outsideParentCount} parent link(s) continue outside the visible span.`;
      renderTimeline(startBlockNumber, endBlockNumber, centeredBlockNumber);

      const prevFork = getPreviousForkBlockNumber(centeredBlockNumber);
      const nextFork = getNextForkBlockNumber(centeredBlockNumber);
      prevBtn.disabled = prevFork === undefined;
      nextBtn.disabled = nextFork === undefined;
      windowSizeLabel.textContent = `Visible span: ${visibleCount} block numbers`;
    }

    function clampOffset(offsetPx) {
      return Math.min(Math.max(offsetPx, 0), state.maxOffsetPx);
    }

    function scheduleRender() {
      if (state.pendingFrame) {
        return;
      }

      state.pendingFrame = window.requestAnimationFrame(() => {
        state.pendingFrame = null;
        render();
      });
    }

    function recalculateBounds() {
      const viewportWidth = Math.max(graph.clientWidth - 36, 1);
      const blockSpan = Math.max(state.maxBlockNumber - state.minBlockNumber, 0);
      const virtualWidth = layout.padding * 2 + blockSpan * getStepX() + layout.cardWidth;
      state.maxOffsetPx = Math.max(virtualWidth - viewportWidth, 0);
      state.offsetPx = clampOffset(state.offsetPx);
    }

    function moveByBlocks(direction, stepCount = 1) {
      state.offsetPx = clampOffset(state.offsetPx + direction * stepCount * getStepX());
      scheduleRender();
    }

    function jumpToFork(direction) {
      const centeredBlockNumber = getCenteredBlockNumber();
      const targetBlockNumber = direction < 0
        ? getPreviousForkBlockNumber(centeredBlockNumber)
        : getNextForkBlockNumber(centeredBlockNumber);

      if (targetBlockNumber === undefined) {
        return;
      }

      state.offsetPx = blockNumberToOffset(targetBlockNumber);
      scheduleRender();
    }

    function beginDrag(clientX) {
      state.isDragging = true;
      state.dragStartX = clientX;
      state.dragStartOffsetPx = state.offsetPx;
      graph.classList.add("dragging");
    }

    function updateDrag(clientX) {
      if (!state.isDragging) {
        return;
      }

      const deltaX = clientX - state.dragStartX;
      state.offsetPx = clampOffset(state.dragStartOffsetPx - deltaX);
      scheduleRender();
    }

    function endDrag() {
      state.isDragging = false;
      graph.classList.remove("dragging");
    }

    async function loadData() {
      try {
        const response = await fetch("/data");
        const payload = await response.json();
        state.finalizedBlocks = payload.finalized_blocks;
        state.forkBlocks = payload.fork_blocks;
        state.blockLookup = payload.block_lookup || {};
        state.minBlockNumber = payload.min_block_number;
        state.maxBlockNumber = payload.max_block_number;
        state.finalizedByNumber = Object.fromEntries(state.finalizedBlocks.map((block) => [block.block_number, block]));
        state.forkBlocksByNumber = {};

        for (const block of state.forkBlocks) {
          if (!state.forkBlocksByNumber[block.block_number]) {
            state.forkBlocksByNumber[block.block_number] = [];
          }
          state.forkBlocksByNumber[block.block_number].push(block);
        }
        state.forkBlockNumbers = [...new Set(state.forkBlocks.map((block) => block.block_number))].sort((left, right) => left - right);

        recalculateBounds();
        state.offsetPx = 0;
        render();
      } catch (error) {
        positionInfo.textContent = "Failed to load data";
        rangeLabel.textContent = "The graph could not be created.";
        status.textContent = error.message;
      }
    }

    prevBtn.addEventListener("click", () => jumpToFork(-1));
    nextBtn.addEventListener("click", () => jumpToFork(1));

    window.addEventListener("keydown", (event) => {
      if (event.key === "ArrowLeft") {
        moveByBlocks(-1, 1);
      } else if (event.key === "ArrowRight") {
        moveByBlocks(1, 1);
      }
    });

    graph.addEventListener("pointerdown", (event) => {
      beginDrag(event.clientX);
      graph.setPointerCapture(event.pointerId);
    });

    graph.addEventListener("pointermove", (event) => {
      updateDrag(event.clientX);
    });

    graph.addEventListener("pointerup", () => {
      endDrag();
    });

    graph.addEventListener("pointercancel", () => {
      endDrag();
    });

    graph.addEventListener("wheel", (event) => {
      const dominantDelta = Math.abs(event.deltaX) > Math.abs(event.deltaY) ? event.deltaX : event.deltaY;
      if (dominantDelta !== 0) {
        event.preventDefault();
        state.offsetPx = clampOffset(state.offsetPx + dominantDelta);
        scheduleRender();
      }
    }, { passive: false });

    window.addEventListener("resize", () => {
      recalculateBounds();
      scheduleRender();
    });

    loadData();
  </script>
</body>
</html>
"""


def load_blocks(csv_path):
    blocks = []
    with open(csv_path, newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        for row in reader:
            block_number = (row.get("block_number") or "").strip()
            if not block_number or block_number == "block_number":
                continue
            try:
                row["block_number"] = int(block_number)
            except ValueError:
                continue
            blocks.append(row)
    blocks.sort(key=lambda item: (item["block_number"], item["timestamp"], item["block_hash"]))
    return blocks


def build_chain_payload(finalized_path, log_path):
    finalized_blocks = load_blocks(finalized_path)
    finalized_by_number = {row["block_number"]: dict(row) for row in finalized_blocks}
    finalized_by_hash = {row["block_hash"]: row for row in finalized_blocks}

    log_blocks = load_blocks(log_path)
    log_by_hash = {row["block_hash"]: row for row in log_blocks}
    block_lookup = {}

    def register_block_lookup(row, source):
        existing = block_lookup.get(row["block_hash"])
        candidate = dict(row)
        candidate["source"] = source
        if existing is None or (existing.get("source") != "finalized" and source == "finalized"):
            block_lookup[row["block_hash"]] = candidate

    for row in finalized_blocks:
        register_block_lookup(row, "finalized")

    for row in log_blocks:
        register_block_lookup(row, "log")

    log_children_by_parent = defaultdict(list)
    for row in log_blocks:
        log_children_by_parent[row["parent_hash"]].append(dict(row))

    sibling_groups = defaultdict(list)

    for row in finalized_blocks:
        sibling_groups[(row["block_number"], row["parent_hash"])].append(
            {
                "source": "finalized",
                "block_hash": row["block_hash"],
            }
        )

    for row in log_blocks:
        sibling_groups[(row["block_number"], row["parent_hash"])].append(
            {
                "source": "log",
                "block_hash": row["block_hash"],
            }
        )

    def annotate_shared_parent_details(row):
        siblings = sibling_groups.get((row["block_number"], row["parent_hash"]), [])
        unique_siblings = []
        seen = set()
        for sibling in siblings:
            sibling_key = (sibling["source"], sibling["block_hash"])
            if sibling_key in seen:
                continue
            seen.add(sibling_key)
            unique_siblings.append(sibling)

        row["shared_parent_total"] = len(unique_siblings)
        row["shared_parent_log_count"] = sum(1 for sibling in unique_siblings if sibling["source"] == "log")
        row["shared_parent_finalized_count"] = sum(
            1 for sibling in unique_siblings if sibling["source"] == "finalized"
        )
        row["shared_parent_has_competition"] = row["shared_parent_total"] > 1
        if row["shared_parent_total"] >= 3:
            row["parent_unit_label"] = "Shared Unit"
            row["parent_unit_count"] = row["shared_parent_total"]
        elif row["shared_parent_total"] == 2:
            row["parent_unit_label"] = "Single Unit"
            row["parent_unit_count"] = row["shared_parent_total"]
        else:
            row["parent_unit_label"] = ""
            row["parent_unit_count"] = row["shared_parent_total"]

    def row_matches_finalized(row):
        baseline = finalized_by_number.get(row["block_number"])
        if not baseline:
            return False
        return (
            row["block_hash"] == baseline["block_hash"]
            and row["parent_hash"] == baseline["parent_hash"]
        )

    seed_rows = []
    for row in log_blocks:
        baseline = finalized_by_number.get(row["block_number"])
        if baseline and not row_matches_finalized(row):
            seed_rows.append(dict(row))

    fork_rows_by_hash = {}
    queue = deque(seed_rows)

    while queue:
        row = queue.popleft()
        row_hash = row["block_hash"]
        if row_hash in fork_rows_by_hash:
            continue

        fork_rows_by_hash[row_hash] = row

        for child in log_children_by_parent.get(row_hash, []):
            if child["block_hash"] in fork_rows_by_hash:
                continue

            baseline = finalized_by_number.get(child["block_number"])
            if baseline is None or not row_matches_finalized(child):
                queue.append(child)

    for fork_row in fork_rows_by_hash.values():
        baseline = finalized_by_number.get(fork_row["block_number"])
        fork_row["hash_matches_finalized"] = bool(
            baseline and fork_row["block_hash"] == baseline["block_hash"]
        )
        fork_row["parent_matches_finalized"] = bool(
            baseline and fork_row["parent_hash"] == baseline["parent_hash"]
        )

    for fork_row in fork_rows_by_hash.values():
        current = fork_row
        seen_hashes = set()
        while current["parent_hash"] in fork_rows_by_hash and current["parent_hash"] not in seen_hashes:
            seen_hashes.add(current["block_hash"])
            current = fork_rows_by_hash[current["parent_hash"]]
        fork_row["root_hash"] = current["block_hash"]
        fork_row["root_block_number"] = current["block_number"]
        annotate_shared_parent_details(fork_row)

    for finalized_row in finalized_blocks:
        finalized_row["hash_matches_finalized"] = True
        finalized_row["parent_matches_finalized"] = True
        annotate_shared_parent_details(finalized_row)

    for log_row in log_blocks:
        baseline = finalized_by_number.get(log_row["block_number"])
        log_row["hash_matches_finalized"] = bool(
            baseline and log_row["block_hash"] == baseline["block_hash"]
        )
        log_row["parent_matches_finalized"] = bool(
            baseline and log_row["parent_hash"] == baseline["parent_hash"]
        )
        annotate_shared_parent_details(log_row)

    for row_hash, row in list(block_lookup.items()):
        if row_hash in fork_rows_by_hash:
            block_lookup[row_hash] = dict(fork_rows_by_hash[row_hash])
            block_lookup[row_hash]["source"] = row.get("source", "log")
        elif row["source"] == "finalized":
            matching = finalized_by_hash.get(row_hash)
            if matching:
                block_lookup[row_hash] = dict(matching)
                block_lookup[row_hash]["source"] = "finalized"
        else:
            matching = log_by_hash.get(row_hash)
            if matching:
                block_lookup[row_hash] = dict(matching)
                block_lookup[row_hash]["source"] = "log"

    fork_blocks = sorted(
        fork_rows_by_hash.values(),
        key=lambda item: (
            item["block_number"],
            item["root_block_number"],
            item["timestamp"],
            item["block_hash"],
        ),
    )

    min_block_number = min(
        finalized_blocks[0]["block_number"],
        fork_blocks[0]["block_number"] if fork_blocks else finalized_blocks[0]["block_number"],
    )
    max_block_number = max(
        finalized_blocks[-1]["block_number"],
        fork_blocks[-1]["block_number"] if fork_blocks else finalized_blocks[-1]["block_number"],
    )

    return {
        "finalized_blocks": finalized_blocks,
        "fork_blocks": fork_blocks,
        "block_lookup": block_lookup,
        "min_block_number": min_block_number,
        "max_block_number": max_block_number,
    }


CHAIN_PAYLOAD = build_chain_payload(
    os.path.join(os.path.dirname(__file__), FINALIZED_CSV_FILE),
    os.path.join(os.path.dirname(__file__), LOG_CSV_FILE),
)


class ChainViewerHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == "/":
            body = HTML_PAGE.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if parsed.path == "/data":
            payload = json.dumps(CHAIN_PAYLOAD).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return

        self.send_error(404, "Not found")

    def log_message(self, format, *args):
        return


def main():
    server = ThreadingHTTPServer((HOST, PORT), ChainViewerHandler)
    print(f"Serving blockchain viewer at http://{HOST}:{PORT}")
    print(f"Finalized source: {FINALIZED_CSV_FILE}")
    print(f"Log source: {LOG_CSV_FILE}")
    if CHAIN_PAYLOAD["finalized_blocks"]:
        first_block = CHAIN_PAYLOAD["finalized_blocks"][0]
        last_block = CHAIN_PAYLOAD["finalized_blocks"][-1]
        print(
            "Loaded finalized range: "
            f"{first_block['timestamp']} (#{first_block['block_number']}) "
            f"to {last_block['timestamp']} (#{last_block['block_number']})"
        )
    print(
        "Loaded "
        f"{len(CHAIN_PAYLOAD['finalized_blocks'])} finalized blocks and "
        f"{len(CHAIN_PAYLOAD['fork_blocks'])} fork/reorg blocks"
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\\nStopping server...")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
