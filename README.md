# eth_tx_tracker

A simple Ethereum transaction tracker that can run against either Ethereum mainnet or a local testnet.

## Requirements

- Python 3.12+
- `requests`
- `websockets`

Install dependencies:

```bash
python3 -m pip install requests websockets
```

## Network modes

This tracker uses `--network` to select the environment:

- `mainnet` — uses `networks/mainnet.env` and requires `ALCHEMY_API_KEY`
- `testnet` — uses `networks/testnet.env`

## Run the tracker

From the repository root:

```bash
python3 -m tx_tracker.main --network testnet
```

For mainnet, set your Alchemy key first:

```bash
export ALCHEMY_API_KEY="your_alchemy_key_here"
python3 -m tx_tracker.main --network mainnet
```

The tracker creates or uses:

- `databases/mainnet.db`
- `databases/testnet.db`

## Inspect the database

Use the root helper scripts:

```bash
python3 verify_db.py --db-path databases/testnet.db
python3 tx_tracker/test_db.py --db-path databases/testnet.db
```

## Notes

- Relative database paths in `networks/*.env` are resolved from the repository root.
- `mainnet` requires network access to Alchemy RPC and WebSocket endpoints.
