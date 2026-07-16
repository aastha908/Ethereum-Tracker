import argparse
import json
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, List
from urllib.parse import urlparse

from tx_tracker.config.networks import load_network_config
from tx_tracker.database.db import Database

parser = argparse.ArgumentParser(description="Blockchain fork viewer")
parser.add_argument("--network", choices=["mainnet", "testnet"], required=True)
parser.add_argument("--port", type=int, default=8000)
args = parser.parse_args()

network_config = load_network_config(args.network)
database = Database(db_path=network_config.db_path)

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
      min-height: 350px;
      padding: 24px;
      overflow: hidden;
    }

    #graph {
      position: relative;
      min-height: 300px;
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
      min-height: 252px;
      width: 100%;
    }

    .block-node {
      position: absolute;
      width: 154px;
      border-radius: 20px;
      padding: 14px 12px;
      min-height: 218px;
      box-shadow: 0 14px 32px rgba(64, 44, 31, 0.1);
      transition: transform 160ms ease, box-shadow 160ms ease, border-color 160ms ease;
      background: var(--main-node);
      border: 1px solid rgba(161, 61, 45, 0.18);
    }

    .block-node.reorg {
      background: var(--orphan-node);
      border: 2px solid var(--orphan-border);
      box-shadow: 0 18px 36px rgba(180, 85, 45, 0.2);
    }

    .block-node.focused {
      transform: translateY(-6px) scale(1.01);
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

    .block-node.reorg .node-badge {
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
      margin-top: 8px;
    }

    .node-value {
      font-family: Consolas, "Courier New", monospace;
      font-size: 0.72rem;
      color: #3b3f41;
      word-break: break-all;
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
  </style>
</head>
<body>
  <div class="shell">
    <section class="hero">
      <h1>Ethereum Chain And Reorg Viewer</h1>
      <p>
        Live view of recent blocks from the configured SQLite database. Reorg events are highlighted directly on affected block numbers.
      </p>
      <div class="toolbar">
        <div class="controls">
          <button id="prevBtn" type="button">&larr; Move Left</button>
          <button id="nextBtn" type="button">Move Right &rarr;</button>
          <span id="positionInfo" class="page-info">Loading data...</span>
        </div>
        <div class="legend">
          <span class="chip">Main chain: live blocks table</span>
          <span class="chip orphan">Reorg marker: from reorgs table</span>
          <span class="chip" id="windowSizeLabel">Visible span: 0 blocks</span>
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
          <div id="graph-inner"></div>
        </div>
      </div>
      <div id="status" class="status"></div>
    </section>
  </div>

  <script>
    const state = {
      blocks: [],
      reorgs: [],
      reorgByBlockNumber: {},
      offsetPx: 0,
      maxOffsetPx: 0,
      minBlockNumber: null,
      maxBlockNumber: null,
      isDragging: false,
      dragStartX: 0,
      dragStartOffsetPx: 0,
      pendingFrame: null,
      lastUpdated: null
    };

    const graph = document.getElementById("graph");
    const graphInner = document.getElementById("graph-inner");
    const prevBtn = document.getElementById("prevBtn");
    const nextBtn = document.getElementById("nextBtn");
    const positionInfo = document.getElementById("positionInfo");
    const rangeLabel = document.getElementById("rangeLabel");
    const summaryLabel = document.getElementById("summaryLabel");
    const status = document.getElementById("status");
    const windowSizeLabel = document.getElementById("windowSizeLabel");

    const layout = {
      cardWidth: 154,
      cardHeight: 218,
      gapX: 84,
      padding: 28,
      renderBuffer: 3
    };

    function getStepX() {
      return layout.cardWidth + layout.gapX;
    }

    function shortHash(value) {
      if (!value) return "missing";
      if (value.length <= 18) return value;
      return value.slice(0, 10) + "..." + value.slice(-8);
    }

    function getVisibleRange() {
      const viewportWidth = Math.max(graph.clientWidth - 36, 1);
      const visibleCount = Math.max(Math.ceil(viewportWidth / getStepX()), 1);
      const startIndex = Math.max(Math.floor(state.offsetPx / getStepX()) - layout.renderBuffer, 0);
      const endIndex = Math.min(startIndex + visibleCount + layout.renderBuffer * 2 - 1, state.blocks.length - 1);
      return { startIndex, endIndex, visibleCount };
    }

    function blockIndexToX(index) {
      return layout.padding + index * getStepX() - state.offsetPx;
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
      const virtualWidth = layout.padding * 2 + Math.max(state.blocks.length - 1, 0) * getStepX() + layout.cardWidth;
      state.maxOffsetPx = Math.max(virtualWidth - viewportWidth, 0);
      state.offsetPx = clampOffset(state.offsetPx);
    }

    function getCenteredIndex() {
      const viewportWidth = Math.max(graph.clientWidth - 36, 1);
      const centerPx = state.offsetPx + viewportWidth / 2;
      const index = Math.round((centerPx - layout.padding - layout.cardWidth / 2) / getStepX());
      return Math.min(Math.max(index, 0), Math.max(state.blocks.length - 1, 0));
    }

    function moveByBlocks(direction, stepCount = 1) {
      state.offsetPx = clampOffset(state.offsetPx + direction * stepCount * getStepX());
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

    function createNode(block, index, isFocused) {
      const node = document.createElement("div");
      const reorg = state.reorgByBlockNumber[block.block_number];
      node.className = "block-node" + (reorg ? " reorg" : "") + (isFocused ? " focused" : "");
      node.style.left = blockIndexToX(index) + "px";
      node.style.top = layout.padding + "px";

      const badge = reorg
        ? `REORG DETECTED - depth ${reorg.depth ?? "?"}`
        : "Canonical Block";

      node.innerHTML = `
        <div class="node-badge">${badge}</div>
        <div class="block-number">#${Number(block.block_number).toLocaleString()}</div>
        <div class="node-label">Hash</div>
        <div class="node-value">${shortHash(block.block_hash)}</div>
        <div class="node-label">Timestamp</div>
        <div class="node-value">${block.timestamp || "unknown"}</div>
        <div class="node-label">Gas Used / Limit</div>
        <div class="node-value">${(block.gas_used ?? 0).toLocaleString()} / ${(block.gas_limit ?? 0).toLocaleString()}</div>
        <div class="node-label">Tx Count</div>
        <div class="node-value">${(block.transaction_count ?? 0).toLocaleString()}</div>
      `;

      return node;
    }

    function render() {
      graphInner.replaceChildren();

      if (!state.blocks.length) {
        graphInner.style.width = "100%";
        graphInner.style.height = "252px";
        positionInfo.textContent = "No blocks loaded";
        rangeLabel.textContent = "No blocks available";
        summaryLabel.textContent = "Live - refreshing every 12s";
        status.textContent = "No rows were returned from the blocks table.";
        prevBtn.disabled = true;
        nextBtn.disabled = true;
        return;
      }

      const { startIndex, endIndex, visibleCount } = getVisibleRange();
      const centeredIndex = getCenteredIndex();
      const visibleBlocks = state.blocks.slice(startIndex, endIndex + 1);

      for (let i = 0; i < visibleBlocks.length; i += 1) {
        const blockIndex = startIndex + i;
        const block = visibleBlocks[i];
        const isFocused = blockIndex === centeredIndex;
        graphInner.appendChild(createNode(block, blockIndex, isFocused));
      }

      const width = Math.max(graph.clientWidth - 36, 1);
      graphInner.style.width = width + "px";
      graphInner.style.height = (layout.padding * 2 + layout.cardHeight) + "px";

      const centeredBlock = state.blocks[centeredIndex] || state.blocks[0];
      const reorgCount = state.reorgs.length;
      const updatedLabel = state.lastUpdated
        ? state.lastUpdated.toLocaleString()
        : "never";

      positionInfo.textContent =
        `Centered block #${Number(centeredBlock.block_number).toLocaleString()} | ${reorgCount.toLocaleString()} reorg event(s) in view window`;
      rangeLabel.textContent =
        `Visible block numbers ${Number(state.minBlockNumber).toLocaleString()} to ${Number(state.maxBlockNumber).toLocaleString()}`;
      summaryLabel.textContent = `Live - refreshing every 12s | Last updated: ${updatedLabel}`;
      status.textContent =
        reorgCount > 0
          ? "Reorg-highlighted cards indicate block numbers that appear in the reorgs table for this range."
          : "No reorg events were found in the currently loaded block range.";

      prevBtn.disabled = state.offsetPx <= 0;
      nextBtn.disabled = state.offsetPx >= state.maxOffsetPx;
      windowSizeLabel.textContent = `Visible span: ${visibleCount} blocks`;
    }

    function applyPayload(payload, preserveOffset) {
      if (!preserveOffset) {
        state.offsetPx = 0;
      }

      state.blocks = payload.blocks || [];
      state.reorgs = payload.reorgs || [];
      state.minBlockNumber = payload.min_block_number;
      state.maxBlockNumber = payload.max_block_number;

      state.reorgByBlockNumber = {};
      for (const reorg of state.reorgs) {
        const existing = state.reorgByBlockNumber[reorg.block_number];
        if (!existing) {
          state.reorgByBlockNumber[reorg.block_number] = reorg;
          continue;
        }

        const currentDepth = Number(existing.depth ?? 0);
        const incomingDepth = Number(reorg.depth ?? 0);
        if (incomingDepth >= currentDepth) {
          state.reorgByBlockNumber[reorg.block_number] = reorg;
        }
      }

      recalculateBounds();
      if (!preserveOffset) {
        state.offsetPx = clampOffset(state.maxOffsetPx);
      }
      state.lastUpdated = new Date();
      render();
    }

    async function loadData(preserveOffset = true) {
      try {
        const response = await fetch("/data", { cache: "no-store" });
        if (!response.ok) {
          throw new Error(`Server returned ${response.status}`);
        }

        const payload = await response.json();
        applyPayload(payload, preserveOffset);
      } catch (error) {
        positionInfo.textContent = "Failed to load data";
        rangeLabel.textContent = "The graph could not be updated.";
        summaryLabel.textContent = "Live - refreshing every 12s";
        status.textContent = error.message;
      }
    }

    prevBtn.addEventListener("click", () => moveByBlocks(-1));
    nextBtn.addEventListener("click", () => moveByBlocks(1));

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

    loadData(false);
    window.setInterval(() => {
      loadData(true);
    }, 12000);
  </script>
</body>
</html>
"""


def _format_timestamp(value: Any) -> str:
    if value is None:
        return "unknown"

    if isinstance(value, int):
        seconds = float(value)
    elif isinstance(value, float):
        seconds = value
    else:
        text = str(value).strip()
        if not text:
            return "unknown"
        try:
            seconds = float(text)
        except ValueError:
            return text

    if seconds > 10_000_000_000:
        seconds = seconds / 1000.0

    try:
        return datetime.fromtimestamp(seconds, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    except (OverflowError, OSError, ValueError):
        return str(value)


def get_live_chain_payload(database: Database, limit: int = 60) -> Dict[str, Any]:
    with database.get_connection() as conn:
        block_rows = conn.execute(
            """
            SELECT
                block_number,
                block_hash,
                parent_hash,
                timestamp,
                gas_used,
                gas_limit,
                transaction_count,
                block_size,
                is_empty
            FROM blocks
            ORDER BY block_number DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

        if not block_rows:
            return {
                "blocks": [],
                "reorgs": [],
                "min_block_number": None,
                "max_block_number": None,
            }

        blocks_desc: List[Dict[str, Any]] = []
        for row in block_rows:
            block = dict(row)
            block["timestamp"] = _format_timestamp(block.get("timestamp"))
            block["is_empty"] = bool(block.get("is_empty", 0))
            blocks_desc.append(block)

        blocks = list(reversed(blocks_desc))

        min_block_number = blocks[0]["block_number"]
        max_block_number = blocks[-1]["block_number"]

        reorg_rows = conn.execute(
            """
            SELECT
                block_number,
                old_block_hash,
                new_block_hash,
                reorg_group_id,
                depth,
                detected_time
            FROM reorgs
            WHERE block_number BETWEEN ? AND ?
            ORDER BY block_number ASC, id ASC
            """,
            (min_block_number, max_block_number),
        ).fetchall()

        reorgs: List[Dict[str, Any]] = []
        for row in reorg_rows:
            reorg = dict(row)
            detected_time = reorg.get("detected_time")
            if detected_time is not None:
                reorg["detected_time"] = str(detected_time)
            reorgs.append(reorg)

        return {
            "blocks": blocks,
            "reorgs": reorgs,
            "min_block_number": min_block_number,
            "max_block_number": max_block_number,
        }


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
            payload_dict = get_live_chain_payload(database)
            payload = json.dumps(payload_dict).encode("utf-8")
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


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), ChainViewerHandler)
    print(f"Serving blockchain viewer at http://{HOST}:{PORT}")
    print(f"Network: {args.network}")
    print(f"Database: {network_config.db_path}")

    initial_payload = get_live_chain_payload(database)
    print(
        "Initial live load: "
        f"{len(initial_payload['blocks'])} blocks, "
        f"{len(initial_payload['reorgs'])} reorg event(s)"
    )
    if initial_payload["blocks"]:
        print(
            "Block window: "
            f"#{initial_payload['min_block_number']} to "
            f"#{initial_payload['max_block_number']}"
        )

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\\nStopping server...")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
