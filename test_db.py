import argparse
from tx_tracker.database.db import Database

parser = argparse.ArgumentParser(description="Inspect pending transactions in the database")
parser.add_argument(
    "--db-path",
    default="databases/mainnet.db",
    help="Path to the SQLite database file",
)
args = parser.parse_args()

print(f"Inspecting database: {args.db_path}")

db = Database(args.db_path)

try:
    txs = db.get_pending_transactions()
except Exception as exc:
    print(f"Error reading database: {exc}")
    raise

print(f"Pending TXs: {len(txs)}")
for tx in txs[:5]:
    print(tx["tx_hash"])
