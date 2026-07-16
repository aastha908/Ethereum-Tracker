import sqlite3
from datetime import datetime
from typing import Dict, List, Optional


def _connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _parse_iso_datetime(value: Optional[str]) -> Optional[datetime]:
    if value is None:
        return None

    text = str(value).strip()
    if not text:
        return None

    if text.endswith("Z"):
        text = text[:-1] + "+00:00"

    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _parse_block_timestamp_seconds(value) -> Optional[float]:
    if value is None:
        return None

    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip()
    if not text:
        return None

    try:
        return float(text)
    except ValueError:
        dt_value = _parse_iso_datetime(text)
        if dt_value is None:
            return None
        return dt_value.timestamp()


def _seconds_diff(start_value: Optional[str], end_value: Optional[str]) -> Optional[float]:
    start_dt = _parse_iso_datetime(start_value)
    end_dt = _parse_iso_datetime(end_value)

    if start_dt is None or end_dt is None:
        return None

    return (end_dt - start_dt).total_seconds()


def get_block_intervals(db_path: str, start_time: str, end_time: str) -> List[float]:
    try:
        with _connect(db_path) as conn:
            rows = conn.execute(
                """
                SELECT block_number, timestamp
                FROM blocks
                WHERE observed_time >= ? AND observed_time <= ?
                ORDER BY block_number ASC
                """,
                (start_time, end_time),
            ).fetchall()
    except sqlite3.OperationalError as exc:
        print(f"[comparison warning] get_block_intervals failed: {exc}")
        return []

    if len(rows) < 2:
        return []

    intervals: List[float] = []

    for index in range(1, len(rows)):
        prev_row = rows[index - 1]
        curr_row = rows[index]

        previous_seconds = _parse_block_timestamp_seconds(prev_row["timestamp"])
        current_seconds = _parse_block_timestamp_seconds(curr_row["timestamp"])
        if previous_seconds is None or current_seconds is None:
            continue

        elapsed_seconds = float(current_seconds - previous_seconds)
        block_gap = int(curr_row["block_number"]) - int(prev_row["block_number"])

        if block_gap <= 0:
            continue

        # Normalize by block gap so sparse capture windows still approximate per-block interval.
        intervals.append(elapsed_seconds / float(block_gap))

    return intervals


def get_finality_lag_series(db_path: str, start_time: str, end_time: str) -> List[dict]:
    try:
        with _connect(db_path) as conn:
            rows = conn.execute(
                """
                SELECT
                    ef.recorded_at,
                    ef.epoch AS finalized_epoch,
                    (
                        SELECT MAX(cs.epoch)
                        FROM consensus_slots cs
                        WHERE cs.recorded_at <= ef.recorded_at
                    ) AS observed_epoch
                FROM epoch_finality ef
                WHERE ef.recorded_at >= ? AND ef.recorded_at <= ?
                ORDER BY ef.recorded_at ASC
                """,
                (start_time, end_time),
            ).fetchall()
    except sqlite3.OperationalError as exc:
        print(f"[comparison warning] get_finality_lag_series failed: {exc}")
        return []

    result: List[dict] = []
    for row in rows:
        finalized_epoch = row["finalized_epoch"]
        observed_epoch = row["observed_epoch"]

        lag_epochs = None
        if finalized_epoch is not None and observed_epoch is not None:
            lag_epochs = int(observed_epoch) - int(finalized_epoch)

        result.append(
            {
                "recorded_at": row["recorded_at"],
                "lag_epochs": lag_epochs,
            }
        )

    return result


def get_missed_slot_stats(db_path: str, start_time: str, end_time: str) -> dict:
    try:
        with _connect(db_path) as conn:
            row = conn.execute(
                """
                SELECT
                    COUNT(*) AS total_slots,
                    SUM(CASE WHEN is_missed = 1 THEN 1 ELSE 0 END) AS missed_slots
                FROM consensus_slots
                WHERE recorded_at >= ? AND recorded_at <= ?
                """,
                (start_time, end_time),
            ).fetchone()
    except sqlite3.OperationalError as exc:
        print(f"[comparison warning] get_missed_slot_stats failed: {exc}")
        return {
            "total_slots": 0,
            "missed_slots": 0,
            "missed_rate": 0.0,
        }

    if row is None:
        return {
            "total_slots": 0,
            "missed_slots": 0,
            "missed_rate": 0.0,
        }

    total_slots = int(row["total_slots"] or 0)
    missed_slots = int(row["missed_slots"] or 0)
    missed_rate = (float(missed_slots) / float(total_slots)) if total_slots > 0 else 0.0

    return {
        "total_slots": total_slots,
        "missed_slots": missed_slots,
        "missed_rate": missed_rate,
    }


def get_time_to_inclusion(db_path: str, start_time: str, end_time: str) -> List[float]:
    try:
        with _connect(db_path) as conn:
            rows = conn.execute(
                """
                SELECT
                    te.tx_hash,
                    MIN(CASE WHEN te.event_type = 'PENDING_SEEN' THEN te.event_time END) AS pending_seen_time,
                    MIN(CASE WHEN te.event_type = 'MINED' THEN te.event_time END) AS mined_time
                FROM transaction_events te
                WHERE te.event_type IN ('PENDING_SEEN', 'MINED')
                  AND te.tx_hash IN (
                      SELECT tx_hash
                      FROM transaction_events
                      WHERE event_type = 'PENDING_SEEN'
                        AND event_time >= ?
                        AND event_time <= ?
                  )
                GROUP BY te.tx_hash
                """,
                (start_time, end_time),
            ).fetchall()
    except sqlite3.OperationalError as exc:
        print(f"[comparison warning] get_time_to_inclusion failed: {exc}")
        return []

    inclusion_times: List[float] = []
    for row in rows:
        pending_seen_time = row["pending_seen_time"]
        mined_time = row["mined_time"]

        if not pending_seen_time or not mined_time:
            continue

        seconds = _seconds_diff(pending_seen_time, mined_time)
        if seconds is None:
            continue
        inclusion_times.append(float(seconds))

    return inclusion_times


def get_confirmation_milestone_times(db_path: str, start_time: str, end_time: str) -> Dict[int, List[float]]:
    milestones = [1, 3, 12, 32, 64]
    output: Dict[int, List[float]] = {milestone: [] for milestone in milestones}

    for milestone in milestones:
        try:
            with _connect(db_path) as conn:
                rows = conn.execute(
                    """
                    SELECT
                        tc.tx_hash,
                        t.first_seen,
                        MIN(tc.recorded_at) AS milestone_recorded_at
                    FROM transaction_confirmations tc
                    JOIN transactions t ON t.tx_hash = tc.tx_hash
                                        WHERE tc.confirmation_count >= ?
                      AND t.first_seen >= ?
                      AND t.first_seen <= ?
                    GROUP BY tc.tx_hash, t.first_seen
                    """,
                    (milestone, start_time, end_time),
                ).fetchall()
        except sqlite3.OperationalError as exc:
            print(
                "[comparison warning] "
                f"get_confirmation_milestone_times failed for milestone {milestone}: {exc}"
            )
            return {1: [], 3: [], 12: [], 32: [], 64: []}

        series: List[float] = []
        for row in rows:
            delta = _seconds_diff(row["first_seen"], row["milestone_recorded_at"])
            if delta is None:
                continue
            series.append(float(delta))

        output[milestone] = series

    return output


def get_reorg_events(db_path: str, start_time: str, end_time: str) -> List[dict]:
    target_columns = ["block_number", "depth", "detected_time", "reorg_group_id"]

    try:
        with _connect(db_path) as conn:
            table_info = conn.execute("PRAGMA table_info(reorgs)").fetchall()
            available = {row["name"] for row in table_info}
            selected = [column for column in target_columns if column in available]

            if not selected:
                return []

            sql = (
                "SELECT "
                + ", ".join(selected)
                + " FROM reorgs WHERE detected_time >= ? AND detected_time <= ?"
                + " ORDER BY detected_time ASC"
            )
            rows = conn.execute(sql, (start_time, end_time)).fetchall()
    except sqlite3.OperationalError as exc:
        print(f"[comparison warning] get_reorg_events failed: {exc}")
        return []

    return [dict(row) for row in rows]


def get_gas_utilization_series(db_path: str, start_time: str, end_time: str) -> List[dict]:
    try:
        with _connect(db_path) as conn:
            rows = conn.execute(
                """
                SELECT block_number, gas_used, gas_limit, timestamp
                FROM blocks
                WHERE observed_time >= ? AND observed_time <= ?
                ORDER BY block_number ASC
                """,
                (start_time, end_time),
            ).fetchall()
    except sqlite3.OperationalError as exc:
        print(f"[comparison warning] get_gas_utilization_series failed: {exc}")
        return []

    series: List[dict] = []
    for row in rows:
        gas_used = float(row["gas_used"] or 0)
        gas_limit = float(row["gas_limit"] or 0)
        utilization = (gas_used / gas_limit) if gas_limit > 0 else 0.0

        series.append(
            {
                "block_number": row["block_number"],
                "utilization": utilization,
                "timestamp": row["timestamp"],
            }
        )

    return series


def get_time_to_transaction_finalized(db_path: str, start_time: str, end_time: str) -> List[float]:
    try:
        with _connect(db_path) as conn:
            rows = conn.execute(
                """
                SELECT
                    te.tx_hash,
                    MIN(CASE WHEN te.event_type = 'PENDING_SEEN' THEN te.event_time END) AS pending_seen_time,
                    MIN(CASE WHEN te.event_type = 'FINALIZED' THEN te.event_time END) AS finalized_time
                FROM transaction_events te
                WHERE te.event_type IN ('PENDING_SEEN', 'FINALIZED')
                  AND te.tx_hash IN (
                      SELECT tx_hash
                      FROM transaction_events
                      WHERE event_type = 'PENDING_SEEN'
                        AND event_time >= ?
                        AND event_time <= ?
                  )
                GROUP BY te.tx_hash
                """,
                (start_time, end_time),
            ).fetchall()
    except sqlite3.OperationalError as exc:
        print(f"[comparison warning] get_time_to_transaction_finalized failed: {exc}")
        return []

    finalized_times: List[float] = []
    for row in rows:
        pending_seen_time = row["pending_seen_time"]
        finalized_time = row["finalized_time"]

        if not pending_seen_time or not finalized_time:
            continue

        seconds = _seconds_diff(pending_seen_time, finalized_time)
        if seconds is None:
            continue
        finalized_times.append(float(seconds))

    return finalized_times


def get_time_from_mined_to_finalized(db_path: str, start_time: str, end_time: str) -> List[float]:
    try:
        with _connect(db_path) as conn:
            rows = conn.execute(
                """
                SELECT
                    te.tx_hash,
                    MIN(CASE WHEN te.event_type = 'MINED' THEN te.event_time END) AS mined_time,
                    MIN(CASE WHEN te.event_type = 'FINALIZED' THEN te.event_time END) AS finalized_time
                FROM transaction_events te
                WHERE te.event_type IN ('MINED', 'FINALIZED')
                  AND te.tx_hash IN (
                      SELECT tx_hash
                      FROM transaction_events
                      WHERE event_type = 'MINED'
                        AND event_time >= ?
                        AND event_time <= ?
                  )
                GROUP BY te.tx_hash
                """,
                (start_time, end_time),
            ).fetchall()
    except sqlite3.OperationalError as exc:
        print(f"[comparison warning] get_time_from_mined_to_finalized failed: {exc}")
        return []

    finalized_times: List[float] = []
    for row in rows:
        mined_time = row["mined_time"]
        finalized_time = row["finalized_time"]

        if not mined_time or not finalized_time:
            continue

        seconds = _seconds_diff(mined_time, finalized_time)
        if seconds is None:
            continue
        finalized_times.append(float(seconds))

    return finalized_times


def get_block_time_to_finality_proxy(db_path: str, start_time: str, end_time: str, block_delta: int = 64) -> List[float]:
    try:
        with _connect(db_path) as conn:
            rows = conn.execute(
                """
                SELECT
                    b0.block_number AS start_block,
                    b0.observed_time AS start_observed_time,
                    b1.block_number AS end_block,
                    b1.observed_time AS end_observed_time
                FROM blocks b0
                JOIN blocks b1 ON b1.block_number = b0.block_number + ?
                WHERE b0.observed_time >= ?
                  AND b0.observed_time <= ?
                ORDER BY b0.block_number ASC
                """,
                (block_delta, start_time, end_time),
            ).fetchall()
    except sqlite3.OperationalError as exc:
        print(f"[comparison warning] get_block_time_to_finality_proxy failed: {exc}")
        return []

    proxy_times: List[float] = []
    for row in rows:
        seconds = _seconds_diff(row["start_observed_time"], row["end_observed_time"])
        if seconds is None:
            continue
        proxy_times.append(float(seconds))

    return proxy_times