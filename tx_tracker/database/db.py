import sqlite3
from pathlib import Path
from contextlib import contextmanager
from datetime import datetime, UTC


class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.schema_path = Path(__file__).resolve().parent / "schema.sql"

    def initialize_database(self):
        db_path = Path(self.db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(str(db_path))

        with open(self.schema_path, "r", encoding="utf-8") as f:
            schema = f.read()

        conn.executescript(schema)

        conn.commit()
        conn.close()

        print("Database initialized successfully.")

    @contextmanager
    def get_connection(self):
        conn = sqlite3.connect(
            self.db_path,
            check_same_thread=False,
        )
        conn.row_factory = sqlite3.Row

        try:
            yield conn
            conn.commit()

        except Exception:
            conn.rollback()
            raise

        finally:
            conn.close()

    def create_transaction(
        self,
        tx_hash,
        from_address,
        to_address,
        nonce,
        value_wei,
        gas_limit,
        gas_price_wei,
        input_data,
        first_seen=None,
        status="PENDING",
    ):
        """
        Create a new transaction record.
        """

        if first_seen is None:
            first_seen = datetime.now(UTC).isoformat()

        with self.get_connection() as conn:
            conn.execute(
                """
        INSERT OR IGNORE INTO transactions (

            tx_hash,
            from_address,
            to_address,
            nonce,
            value_wei,
            gas_limit,
            gas_price_wei,
            input_data,
            first_seen,
            current_status

        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
                (
                    tx_hash,
                    from_address,
                    to_address,
                    nonce,
                    value_wei,
                    gas_limit,
                    gas_price_wei,
                    input_data,
                    first_seen,
                    status,
                ),
            )

    def add_event(
        self,
        tx_hash,
        event_type,
        details="",
    ):
        """
        Add lifecycle event.
        """

        event_time = datetime.now(UTC).isoformat()

        with self.get_connection() as conn:
            conn.execute(
                """
        INSERT INTO transaction_events (

            tx_hash,
            event_time,
            event_type,
            details

        )
        VALUES (?, ?, ?, ?)
        """,
                (
                    tx_hash,
                    event_time,
                    event_type,
                    details,
                ),
            )

    def save_block(
        self,
        block_number,
        block_hash,
        parent_hash,
        timestamp,
        is_canonical=1,
    ):
        """
        Store observed block.
        """

        observed_time = datetime.now(UTC).isoformat()

        with self.get_connection() as conn:
            conn.execute(
                """
        INSERT OR REPLACE INTO blocks (

            block_hash,
            block_number,
            parent_hash,
            timestamp,
            observed_time,
            is_canonical

        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
                (
                    block_hash,
                    block_number,
                    parent_hash,
                    timestamp,
                    observed_time,
                    is_canonical,
                ),
            )

    def save_receipt(
        self,
        tx_hash,
        block_number,
        block_hash,
        transaction_index,
        gas_used,
        effective_gas_price,
        status,
        contract_address=None,
    ):
        """
        Store transaction receipt.
        """

        with self.get_connection() as conn:
            conn.execute(
                """
        INSERT OR REPLACE INTO transaction_receipts (

            tx_hash,
            block_number,
            block_hash,
            transaction_index,
            gas_used,
            effective_gas_price,
            status,
            contract_address

        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
                (
                    tx_hash,
                    block_number,
                    block_hash,
                    transaction_index,
                    gas_used,
                    effective_gas_price,
                    status,
                    contract_address,
                ),
            )

    def update_status(
        self,
        tx_hash,
        new_status,
        block_number=None,
        block_hash=None,
    ):
        """
        Update transaction current state.
        Also records state history.
        """

        timestamp = datetime.now(UTC).isoformat()

        with self.get_connection() as conn:
            conn.execute(
                """
        UPDATE transactions
        SET
            current_status=?,
            current_block_number=COALESCE(?, current_block_number),
            current_block_hash=COALESCE(?, current_block_hash)
        WHERE tx_hash=?
        """,
                (
                    new_status,
                    block_number,
                    block_hash,
                    tx_hash,
                ),
            )

            conn.execute(
                """
        INSERT INTO transaction_state_history (

            tx_hash,
            state,
            block_number,
            block_hash,
            recorded_at

        )
        VALUES (?, ?, ?, ?, ?)
        """,
                (
                    tx_hash,
                    new_status,
                    block_number,
                    block_hash,
                    timestamp,
                ),
            )

    def get_transaction(self, tx_hash):
        with self.get_connection() as conn:
            result = conn.execute(
                """
        SELECT *
        FROM transactions
        WHERE tx_hash=?
        """,
                (tx_hash,),
            )

            row = result.fetchone()
            return dict(row) if row else None

    def get_transaction_events(self, tx_hash):
        with self.get_connection() as conn:
            result = conn.execute(
                """
        SELECT *
        FROM transaction_events
        WHERE tx_hash=?
        ORDER BY event_time
        """,
                (tx_hash,),
            )

            return [dict(row) for row in result.fetchall()]

    def has_event(
        self,
        tx_hash,
        event_type,
    ):
        with self.get_connection() as conn:
            result = conn.execute(
                """
        SELECT 1
        FROM transaction_events
        WHERE tx_hash=?
        AND event_type=?
        LIMIT 1
        """,
                (
                    tx_hash,
                    event_type,
                ),
            )

            return result.fetchone() is not None

    def save_confirmation(
        self,
        tx_hash,
        block_number,
        confirmation_count,
    ):
        """
        Store confirmation progress.
        """

        timestamp = datetime.now(UTC).isoformat()

        with self.get_connection() as conn:
            conn.execute(
                """
        INSERT INTO transaction_confirmations (

            tx_hash,
            block_number,
            confirmation_count,
            recorded_at

        )
        VALUES (?, ?, ?, ?)
        """,
                (
                    tx_hash,
                    block_number,
                    confirmation_count,
                    timestamp,
                ),
            )

    def save_trace(
        self,
        tx_hash,
        trace_address,
        call_type,
        from_address,
        to_address,
        value_wei,
        gas,
        trace_index,
    ):
        """
        Store internal trace call.
        """

        with self.get_connection() as conn:
            conn.execute(
                """
        INSERT INTO traces (

            tx_hash,
            trace_address,
            call_type,
            from_address,
            to_address,
            value_wei,
            gas,
            trace_index

        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
                (
                    tx_hash,
                    trace_address,
                    call_type,
                    from_address,
                    to_address,
                    value_wei,
                    gas,
                    trace_index,
                ),
            )

    def save_reorg(
        self,
        block_number,
        old_block_hash,
        new_block_hash,
    ):
        """
        Store reorg event.
        """

        timestamp = datetime.now(UTC).isoformat()

        with self.get_connection() as conn:
            conn.execute(
                """
        INSERT INTO reorgs (

            detected_time,
            block_number,
            old_block_hash,
            new_block_hash

        )
        VALUES (?, ?, ?, ?)
        """,
                (
                    timestamp,
                    block_number,
                    old_block_hash,
                    new_block_hash,
                ),
            )

    def save_replacement(
        self,
        original_tx,
        replacement_tx,
        sender,
        nonce,
    ):
        """
        Store replacement transaction.
        """

        timestamp = datetime.now(UTC).isoformat()

        with self.get_connection() as conn:
            conn.execute(
                """
        INSERT INTO replacements (

            original_tx,
            replacement_tx,
            sender,
            nonce,
            detected_time

        )
        VALUES (?, ?, ?, ?, ?)
        """,
                (
                    original_tx,
                    replacement_tx,
                    sender,
                    nonce,
                    timestamp,
                ),
            )

    def get_pending_transactions(self):
        with self.get_connection() as conn:
            result = conn.execute(
                """
        SELECT *
        FROM transactions
        WHERE current_status='PENDING'
        """,
            )

            return [dict(row) for row in result.fetchall()]

    def get_latest_block(self):
        with self.get_connection() as conn:
            result = conn.execute(
                """
        SELECT *
        FROM blocks
        ORDER BY block_number DESC
        LIMIT 1
        """,
            )

            row = result.fetchone()
            return dict(row) if row else None

    def transaction_exists(self, tx_hash):
        with self.get_connection() as conn:
            result = conn.execute(
                """
        SELECT 1
        FROM transactions
        WHERE tx_hash=?
        LIMIT 1
        """,
                (tx_hash,),
            )

            return result.fetchone() is not None

    def mark_transaction_mined(
        self,
        tx_hash,
        block_number,
        block_hash,
    ):
        self.update_status(
            tx_hash,
            "MINED",
            block_number,
            block_hash,
        )

        self.add_event(
            tx_hash,
            "MINED",
            f"Included in block {block_number}",
        )

    def mark_transaction_result(self, tx_hash, status):
        if status == 1:
            self.update_status(tx_hash, "SUCCESS")
            self.add_event(tx_hash, "SUCCESS", "Transaction executed successfully")
        else:
            self.update_status(tx_hash, "FAILED")
            self.add_event(tx_hash, "FAILED", "Transaction execution reverted")

    def get_active_transactions(self):
        with self.get_connection() as conn:
            result = conn.execute(
                """
        SELECT *
        FROM transactions
        WHERE current_status IN (
            'MINED',
            'SUCCESS',
            'FAILED'
        )
        """,
            )

            return [dict(row) for row in result.fetchall()]

    def get_latest_confirmation(self, tx_hash):
        with self.get_connection() as conn:
            result = conn.execute(
                """
        SELECT confirmation_count
        FROM transaction_confirmations
        WHERE tx_hash=?
        ORDER BY confirmation_count DESC
        LIMIT 1
        """,
                (tx_hash,),
            )

            row = result.fetchone()
            return row["confirmation_count"] if row else -1

    def mark_finalized(self, tx_hash):
        self.update_status(tx_hash, "FINALIZED")
        self.add_event(tx_hash, "FINALIZED", "Transaction finalized")

    def mark_safe(self, tx_hash):
        self.add_event(tx_hash, "SAFE", "Transaction reached safe block")
