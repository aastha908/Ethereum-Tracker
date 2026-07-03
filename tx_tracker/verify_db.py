import argparse
from tx_tracker.database.db import Database

parser = argparse.ArgumentParser(description="Verify SQLite database contents")
parser.add_argument(
    "--db-path",
    default="databases/mainnet.db",
    help="Path to the SQLite database file",
)
args = parser.parse_args()

print(f"Inspecting database: {args.db_path}")

db = Database(args.db_path)

try:
    rows = []
    with db.get_connection() as conn:
        cursor = conn.execute(
            """
SELECT
    tx_hash,
    current_status,
    current_block_number
FROM transactions
"""
        )
        rows = cursor.fetchall()

    for row in rows:
        print(dict(row))
except Exception as exc:
    print(f"Error reading database: {exc}")
    raise
