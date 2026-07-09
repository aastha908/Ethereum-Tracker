import argparse
import json
from pathlib import Path
from eth_utils import to_checksum_address

from tx_tracker.config.networks import load_network_config
from tx_tracker.database.db import Database
from tx_tracker.tracker.rpc_client import RPCClient

try:
    from eth_account import Account
except ImportError:  # pragma: no cover - runtime dependency check
    Account = None


def load_testnet_accounts(path="replay/testnet_accounts.json"):
    with open(path, "r", encoding="utf-8") as f:
        accounts = json.load(f)

    if not isinstance(accounts, list) or not accounts:
        raise ValueError("Accounts file must be a non-empty JSON list.")

    for i, account in enumerate(accounts):
        if not isinstance(account, dict):
            raise ValueError(f"Account entry at index {i} must be an object.")
        if "address" not in account or "private_key" not in account:
            raise ValueError(
                f"Account entry at index {i} must include 'address' and 'private_key'."
            )

    return accounts


def load_last_processed_rowid(path="replay/last_processed.txt"):
    state_path = Path(path)
    if not state_path.exists():
        return 0

    value = state_path.read_text(encoding="utf-8").strip()
    if not value:
        return 0

    return int(value)


def save_last_processed_rowid(rowid, path="replay/last_processed.txt"):
    state_path = Path(path)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(str(int(rowid)), encoding="utf-8")


def load_mainnet_transactions(database, limit=10, min_rowid=0):
    query = """
        SELECT
            rowid,
            tx_hash,
            from_address,
            to_address,
            value_wei,
            gas_limit,
            gas_price_wei,
            input_data
        FROM transactions
        WHERE rowid > ?
        ORDER BY rowid ASC
        LIMIT ?
    """

    with database.get_connection() as conn:
        rows = conn.execute(query, (min_rowid, limit)).fetchall()

    return [dict(row) for row in rows]


def _to_int(value, field_name):
    if value is None:
        raise ValueError(f"{field_name} is required but was None")

    if isinstance(value, int):
        return value

    if isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith(("0x", "0X")):
            return int(stripped, 16)
        return int(stripped)

    return int(value)


def build_mirror_tx(mainnet_tx_row, sender_address, sender_private_key, nonce, chain_id):
    tx_dict = {
        "nonce": nonce,
        "value": _to_int(mainnet_tx_row.get("value_wei", 0), "value_wei"),
        "gas": _to_int(mainnet_tx_row.get("gas_limit"), "gas_limit"),
        "gasPrice": _to_int(mainnet_tx_row.get("gas_price_wei"), "gas_price_wei"),
        "data": mainnet_tx_row.get("input_data") or "0x",
        "chainId": chain_id,
    }

    to_address = mainnet_tx_row.get("to_address")
    if to_address:
        tx_dict["to"] = to_checksum_address(to_address)

    signed = Account.sign_transaction(tx_dict, sender_private_key)

    if hasattr(signed, "rawTransaction"):
        raw_bytes = signed.rawTransaction
    elif hasattr(signed, "raw_transaction"):
        raw_bytes = signed.raw_transaction
    else:
        raise RuntimeError(
            "Signed transaction object has neither 'rawTransaction' nor 'raw_transaction'."
        )

    return "0x" + raw_bytes.hex()


def get_live_nonce(rpc_client, address):
    result = rpc_client.rpc("eth_getTransactionCount", [address, "pending"])
    return int(result, 16)


def broadcast(rpc_client, signed_raw_tx_hex):
    return rpc_client.rpc("eth_sendRawTransaction", [signed_raw_tx_hex])


def main():
    parser = argparse.ArgumentParser(
        description="Build and optionally broadcast testnet mirror transactions from mainnet.db"
    )
    parser.add_argument("--network", default="testnet")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--broadcast", action="store_true", default=False)
    args = parser.parse_args()

    mode = "LIVE BROADCAST" if args.broadcast else "DRY RUN"
    print(f"=== {mode} MODE ===")

    if Account is None:
        print("Missing dependency: eth_account")
        print("Install it with: pip install eth-account")
        return

    network_config = load_network_config(args.network)
    mainnet_db = Database(db_path="databases/mainnet.db")
    accounts = load_testnet_accounts()

    rpc_client = None
    if args.broadcast:
        rpc_client = RPCClient(rpc_url=network_config.rpc_url)

    last_rowid = load_last_processed_rowid()
    transactions = load_mainnet_transactions(
        mainnet_db,
        limit=args.limit,
        min_rowid=last_rowid,
    )
    if not transactions:
        print("No new transactions found in databases/mainnet.db")
        return

    dry_run_nonce_counters = {account["address"]: 0 for account in accounts}
    highest_rowid_seen = last_rowid

    for index, tx in enumerate(transactions):
        tx_rowid = int(tx.get("rowid", 0) or 0)
        highest_rowid_seen = max(highest_rowid_seen, tx_rowid)

        account = accounts[index % len(accounts)]
        sender_address = account["address"]
        sender_private_key = account["private_key"]

        try:
            placeholder_nonce = dry_run_nonce_counters.get(sender_address, 0)
            nonce = placeholder_nonce

            if args.broadcast:
                nonce = get_live_nonce(rpc_client, sender_address)
            else:
                print(
                    f"[DRY RUN] placeholder nonce for {sender_address}: {placeholder_nonce}"
                )

            signed_raw_tx_hex = build_mirror_tx(
                mainnet_tx_row=tx,
                sender_address=sender_address,
                sender_private_key=sender_private_key,
                nonce=nonce,
                chain_id=network_config.chain_id,
            )

            value_int = _to_int(tx.get("value_wei", 0), "value_wei")
            gas_int = _to_int(tx.get("gas_limit"), "gas_limit")
            print(
                "source_tx={source} sender={sender} nonce={nonce} value={value} gas={gas}".format(
                    source=tx.get("tx_hash"),
                    sender=sender_address,
                    nonce=nonce,
                    value=value_int,
                    gas=gas_int,
                )
            )

            if args.broadcast:
                tx_hash = broadcast(rpc_client, signed_raw_tx_hex)
                print(f"[BROADCAST] testnet tx hash: {tx_hash}")
            else:
                print(
                    "[DRY RUN] would broadcast: {preview}...".format(
                        preview=signed_raw_tx_hex[:20]
                    )
                )

            dry_run_nonce_counters[sender_address] = placeholder_nonce + 1

        except Exception as exc:
            print(
                "[WARNING] Skipping processed source_tx={source} rowid={rowid}: {err}".format(
                    source=tx.get("tx_hash", "<unknown>"),
                    rowid=tx_rowid,
                    err=exc,
                )
            )
            continue

    save_last_processed_rowid(highest_rowid_seen)


if __name__ == "__main__":
    main()
