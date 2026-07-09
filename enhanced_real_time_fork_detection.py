import argparse
from web3 import Web3
import asyncio
import time
import csv
import os
from collections import deque

from tx_tracker.config.networks import load_network_config


parser = argparse.ArgumentParser(description="Enhanced real-time fork detection")
parser.add_argument("--network", choices=["mainnet", "testnet"], required=True)
args = parser.parse_args()

network_config = load_network_config(args.network)
WSS_URL = network_config.ws_url

w3 = Web3(Web3.LegacyWebSocketProvider(WSS_URL))

if not w3.is_connected():
    print("[!] Connection failed")
    exit()

print(f"[+] Connected to {args.network} (WSS)")
print("[+] Listening for blocks...\n")

# ==============================
# CONFIG
# ==============================
MAX_HISTORY = 20
CONFIRMATIONS_REQUIRED = 3
FETCH_RETRIES = 3
RETRY_DELAY = 0.5
PROCESSING_DELAY = 0.2   # reduced for accuracy

LOG_FILE = f"reorg_log_{args.network}.txt"
CSV_FILE = f"blocks_log_{args.network}.csv"
TX_CSV_FILE = f"transactions_log_{args.network}.csv"

# ==============================
# DATA STRUCTURES
# ==============================
block_history = {}
history_queue = deque(maxlen=MAX_HISTORY)
block_buffer = {}  # {block_number: [blocks]}

tx_queue = asyncio.Queue()

# ==============================
# INIT CSVs
# ==============================
if not os.path.exists(CSV_FILE):
    with open(CSV_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "block_number", "block_hash", "parent_hash", "status"])

if not os.path.exists(TX_CSV_FILE):
    with open(TX_CSV_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "block_number", "tx_hash", "from", "to", "value", "status"])

# ==============================
# LOG FUNCTIONS
# ==============================
def log_block_csv(timestamp, number, hash_, parent, status):
    with open(CSV_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([timestamp, number, hash_, parent, status])


def log_tx_csv(timestamp, block_number, tx_hash, from_, to_, value, status):
    with open(TX_CSV_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([timestamp, block_number, tx_hash, from_, to_, value, status])


def log_reorg(event_type, details):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

    log_entry = f"""
[{timestamp}] REORG DETECTED ({event_type})
{details}
--------------------------------------------------
"""
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(log_entry)

    print(log_entry)

# ==============================
# FETCH WITH RETRY
# ==============================
def fetch_block_with_retry(block_hash, full_tx=False):
    for _ in range(FETCH_RETRIES):
        try:
            return w3.eth.get_block(block_hash, full_transactions=full_tx)
        except:
            time.sleep(RETRY_DELAY)
    return None

# ==============================
# REORG DEPTH
# ==============================
def calculate_reorg_depth(block_number, new_parent):
    depth = 0
    current_parent = new_parent
    current_number = block_number - 1

    while current_number in block_history:
        old_block = block_history[current_number]

        if old_block["hash"] == current_parent:
            break

        depth += 1
        current_parent = old_block["parent"]
        current_number -= 1

    return depth

# ==============================
# CONFIRMATION UPDATE
# ==============================
def update_confirmations(latest_number):
    for num in list(block_history.keys()):
        confirmations = latest_number - num
        if confirmations >= CONFIRMATIONS_REQUIRED:
            block_history[num]["status"] = "confirmed"

# ==============================
# TX WORKER
# ==============================
async def tx_worker():
    while True:
        block_number, block_hash, status = await tx_queue.get()

        block = fetch_block_with_retry(block_hash, full_tx=True)

        if block:
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

            for tx in block.transactions:
                try:
                    log_tx_csv(
                        timestamp,
                        block_number,
                        tx.hash.hex(),
                        tx["from"],
                        tx.get("to", "contract_creation"),
                        tx["value"],
                        status
                    )
                except:
                    continue

        tx_queue.task_done()

# ==============================
# COLLECT REORG BLOCKS
# ==============================
def collect_reorg_blocks(block_number, new_parent):
    old_blocks = []
    new_blocks = []

    current_number = block_number
    current_parent = new_parent

    while current_number in block_history:
        old_block = block_history[current_number]

        if old_block["hash"] == current_parent:
            break

        old_blocks.append((current_number, old_block["hash"]))
        new_blocks.append((current_number, current_parent))

        current_parent = old_block["parent"]
        current_number -= 1

    return list(set(old_blocks)), list(set(new_blocks))

# ==============================
# PROCESS BLOCK
# ==============================
def process_block(block):
    number = block.number
    hash_ = block.hash.hex()
    parent = block.parentHash.hex()
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

    print(f"[+] Block {number} -> {hash_}")

    reorg_detected = False
    old_blocks = []
    new_blocks = []

    # HASH MISMATCH
    if number in block_history:
        if block_history[number]["hash"] != hash_:
            depth = calculate_reorg_depth(number, parent)
            log_reorg("Hash Mismatch", f"Block {number}, Depth {depth}")
            reorg_detected = True

            o, n = collect_reorg_blocks(number, parent)
            old_blocks.extend(o)
            new_blocks.extend(n)

    # PARENT MISMATCH
    if (number - 1) in block_history:
        expected_parent = block_history[number - 1]["hash"]

        if parent != expected_parent:
            depth = calculate_reorg_depth(number, parent)
            log_reorg("Parent Mismatch", f"Block {number}, Depth {depth}")
            reorg_detected = True

            o, n = collect_reorg_blocks(number, parent)
            old_blocks.extend(o)
            new_blocks.extend(n)

    # TRIGGER TX FETCH
    if reorg_detected:
        for num, h in old_blocks:
            asyncio.create_task(tx_queue.put((num, h, "replaced")))

        for num, h in new_blocks:
            asyncio.create_task(tx_queue.put((num, h, "canonical")))

        asyncio.create_task(tx_queue.put((number, block.hash, "canonical")))

    # ALWAYS STORE BLOCK
    block_history[number] = {
        "hash": hash_,
        "parent": parent,
        "status": "pending"
    }

    history_queue.append(number)

    while len(history_queue) > MAX_HISTORY:
        old = history_queue.popleft()
        block_history.pop(old, None)

    log_block_csv(timestamp, number, hash_, parent, "pending")

    update_confirmations(number)

# ==============================
# MAIN LOOP
# ==============================
async def monitor_blocks():
    block_filter = w3.eth.filter("latest")

    while True:
        try:
            for block_hash in block_filter.get_new_entries():
                block = fetch_block_with_retry(block_hash)

                if not block:
                    log_reorg("Missing Block", str(block_hash))
                    continue

                if block.number not in block_buffer:
                    block_buffer[block.number] = []

                block_buffer[block.number].append(block)

            await asyncio.sleep(PROCESSING_DELAY)

            for num in sorted(block_buffer.keys()):
                for block in block_buffer[num]:
                    process_block(block)

            block_buffer.clear()

        except Exception as e:
            print(f"[!] Error: {e}")
            await asyncio.sleep(3)

        await asyncio.sleep(0.5)

# ==============================
# RUN
# ==============================
async def main():
    worker = asyncio.create_task(tx_worker())
    await monitor_blocks()
    await worker

asyncio.run(main())