# Ethereum Tracker: Complete Runbook

This project can run the full pipeline end-to-end:

- transaction tracker (`tx_tracker`)
- consensus slot/finality monitoring
- reorg detector script
- blockchain viewer
- replay injector (to generate testnet traffic)

Follow the steps in order from the repository root.

## 1. Prerequisites

- macOS/Linux shell
- Python 3.9+ (project is compatible with Python 3.9)
- network access to your configured RPC/WS/Beacon endpoints

## 2. Initial Setup

Create and activate a virtual environment, then install dependencies:

```bash
python3 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
python -m pip install requests websockets web3 eth-account eth-utils
```

## 3. Configure Networks

Files:

- `networks/testnet.env`
- `networks/mainnet.env`

Current expected fields:

- `CHAIN_ID`
- `RPC_URL`
- `WS_URL`
- `BEACON_URL`
- `DB_PATH`

For mainnet, export your Alchemy key before starting:

```bash
export ALCHEMY_API_KEY="your_alchemy_key_here"
```

## 4. Prepare Replay Accounts (Testnet Injector)

Create local testnet signer config from example:

```bash
cp replay/testnet_accounts.example.json replay/testnet_accounts.json
```

Then edit `replay/testnet_accounts.json` with funded testnet addresses/private keys.

Important:

- `replay/testnet_accounts.json` is intentionally ignored by git.
- never commit real private keys.

## 5. Start Core Tracker

Open Terminal 1:

```bash
source venv/bin/activate
python -m tx_tracker.main --network testnet
```

Expected startup logs include:

- `Starting tracker for testnet ...`
- `Database initialized successfully.`
- `Consensus monitoring: enabled` (if `BEACON_URL` is set)
- `Receipt monitor started`
- `Confirmation monitor started`
- `Block listener started`
- `Connected to ws://...`

Use `--network mainnet` for mainnet:

```bash
python -m tx_tracker.main --network mainnet
```

## 6. Start Reorg Detector (Standalone)

Open Terminal 2:

```bash
source venv/bin/activate
python enhanced_real_time_fork_detection.py --network testnet
```

Outputs:

- `reorg_log_testnet.txt`
- `blocks_log_testnet.csv`
- `transactions_log_testnet.csv`

Mainnet variant:

```bash
python enhanced_real_time_fork_detection.py --network mainnet
```

## 7. Start Blockchain Viewer

Open Terminal 3:

```bash
source venv/bin/activate
python blockchain_viewer_final.py --network testnet --port 8000
```

Open browser:

- `http://127.0.0.1:8000`

Mainnet on another port:

```bash
python blockchain_viewer_final.py --network mainnet --port 8001
```

## 8. Start Injector (Generate Testnet Traffic)

Open Terminal 4.

One-time run:

```bash
source venv/bin/activate
PYTHONPATH=. python replay/mirror_injector.py --network testnet --limit 5 --broadcast
```

Continuous loop:

```bash
source venv/bin/activate
while true; do
	PYTHONPATH=. python replay/mirror_injector.py --network testnet --limit 5 --broadcast
	sleep 15
done
```

Dry-run mode (no broadcast):

```bash
PYTHONPATH=. python replay/mirror_injector.py --network testnet --limit 5
```

## 9. Verify It Is Working

Tracker terminal should show lines such as:

- `[PENDING] ...`
- `[MINED] ...`
- `[CONFIRMATIONS] ...`

Quick DB checks:

```bash
python verify_db.py --db-path databases/testnet.db
python tx_tracker/test_db.py --db-path databases/testnet.db
```

Or direct SQL check:

```bash
venv/bin/python -c "
import sqlite3
conn = sqlite3.connect('databases/testnet.db')
conn.row_factory = sqlite3.Row
print('blocks:', [dict(r) for r in conn.execute('SELECT block_number, gas_used, transaction_count FROM blocks ORDER BY block_number DESC LIMIT 3').fetchall()])
print('slots:', [dict(r) for r in conn.execute('SELECT slot, epoch, is_missed FROM consensus_slots ORDER BY slot DESC LIMIT 3').fetchall()])
print('epochs:', [dict(r) for r in conn.execute('SELECT epoch, finalized FROM epoch_finality ORDER BY epoch DESC LIMIT 3').fetchall()])
"
```

## 10. Run Everything Together (Quick Start)

From four terminals (all from repo root):

Terminal 1:

```bash
source venv/bin/activate
python -m tx_tracker.main --network testnet
```

Terminal 2:

```bash
source venv/bin/activate
python enhanced_real_time_fork_detection.py --network testnet
```

Terminal 3:

```bash
source venv/bin/activate
python blockchain_viewer_final.py --network testnet --port 8000
```

Terminal 4:

```bash
source venv/bin/activate
while true; do
	PYTHONPATH=. python replay/mirror_injector.py --network testnet --limit 5 --broadcast
	sleep 15
done
```

## 11. Common Issues and Fixes

`ModuleNotFoundError: No module named tx_tracker`

- run tracker as module: `python -m tx_tracker.main --network ...`
- for injector, use `PYTHONPATH=. python replay/mirror_injector.py ...`

Tracker starts but no transaction logs appear

- this usually means no new pending txs are arriving
- run injector broadcast loop to generate fresh txs

Mainnet does not start

- confirm `ALCHEMY_API_KEY` is exported
- confirm DNS/network access to Alchemy endpoints

`Consensus monitoring: disabled`

- set `BEACON_URL` in your `networks/<network>.env`

## 12. Generated Files

Typical outputs:

- databases: `databases/mainnet.db`, `databases/testnet.db`
- reorg logs: `reorg_log_mainnet.txt`, `reorg_log_testnet.txt`
- block logs: `blocks_log_mainnet.csv`, `blocks_log_testnet.csv`
- tx logs: `transactions_log_mainnet.csv`, `transactions_log_testnet.csv`

## 13. Stop Services

- Press `Ctrl+C` in each running terminal.
- For injector loop, `Ctrl+C` stops the loop immediately.