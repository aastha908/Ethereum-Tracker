import argparse
import sqlite3

parser = argparse.ArgumentParser(description="Verify SQLite database contents")
parser.add_argument(
    "--db-path",
    default="databases/mainnet.db",
    help="Path to the SQLite database file",
)
args = parser.parse_args()

print(f"Inspecting database: {args.db_path}")

conn = sqlite3.connect(args.db_path)

cursor = conn.cursor()

cursor.execute("""
SELECT
    tx_hash,
    current_status,
    current_block_number
FROM transactions
""")

for row in cursor.fetchall():
    print(row)

conn.close()
