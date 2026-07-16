import json
import os
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from comparison.queries import (
    get_block_intervals,
    get_block_time_to_finality_proxy,
    get_confirmation_milestone_times,
    get_finality_lag_series,
    get_gas_utilization_series,
    get_missed_slot_stats,
    get_reorg_events,
    get_time_from_mined_to_finalized,
    get_time_to_inclusion,
    get_time_to_transaction_finalized,
)
from comparison.stats import compare_distributions, descriptive_stats


MIN_BLOCK_INTERVAL_SAMPLES = 30


def _safe_query_call(
    query_name: str,
    query_fn: Callable[..., Any],
    db_path: str,
    start_time: str,
    end_time: str,
    fallback: Any,
) -> Any:
    try:
        return query_fn(db_path, start_time, end_time)
    except Exception as exc:
        print(f"[comparison warning] {query_name} failed for {db_path}: {exc}")
        return fallback


def _safe_descriptive(values: Optional[List[Any]]) -> Optional[Dict[str, float]]:
    if values is None:
        return None
    try:
        return descriptive_stats(values)
    except Exception as exc:
        print(f"[comparison warning] descriptive_stats failed: {exc}")
        return None


def _safe_descriptive_with_min_samples(
    values: Optional[List[Any]],
    min_samples: int,
) -> Optional[Dict[str, float]]:
    if values is None:
        return None

    if len(values) < min_samples:
        return None

    return _safe_descriptive(values)


def _milestone_stats(milestone_data: Any) -> Dict[int, Optional[Dict[str, float]]]:
    milestones = [1, 3, 12, 32, 64]
    output: Dict[int, Optional[Dict[str, float]]] = {}

    if not isinstance(milestone_data, dict):
        for milestone in milestones:
            output[milestone] = None
        return output

    for milestone in milestones:
        series = milestone_data.get(milestone, [])
        if not isinstance(series, list):
            series = []
        output[milestone] = _safe_descriptive(series)

    return output


def _safe_series_from_rows(rows: Any, key: str) -> List[float]:
    if not isinstance(rows, list):
        return []

    series: List[float] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        value = row.get(key)
        if value is None:
            continue
        try:
            series.append(float(value))
        except (TypeError, ValueError):
            continue
    return series


def _iso_time_deltas_seconds(rows: Any, key: str) -> List[float]:
    if not isinstance(rows, list):
        return []

    values: List[datetime] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        raw = row.get(key)
        if raw is None:
            continue
        text = str(raw).strip()
        if not text:
            continue
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            values.append(datetime.fromisoformat(text))
        except ValueError:
            continue

    deltas: List[float] = []
    for index in range(1, len(values)):
        deltas.append((values[index] - values[index - 1]).total_seconds())
    return deltas


def _reorg_summary(events: Any) -> Dict[str, float]:
    if not isinstance(events, list) or not events:
        return {
            "count": 0,
            "max_depth": 0,
            "mean_depth": 0.0,
        }

    depths: List[float] = []
    for event in events:
        if not isinstance(event, dict):
            continue
        depth = event.get("depth")
        if depth is None:
            continue
        try:
            depths.append(float(depth))
        except (TypeError, ValueError):
            continue

    if not depths:
        return {
            "count": len(events),
            "max_depth": 0,
            "mean_depth": 0.0,
        }

    return {
        "count": len(events),
        "max_depth": max(depths),
        "mean_depth": sum(depths) / float(len(depths)),
    }


def generate_report(
    mainnet_db_path: str,
    testnet_db_path: str,
    start_time: str,
    end_time: str,
) -> dict:
    generated_at = datetime.now(timezone.utc).isoformat()

    mainnet_block_intervals = _safe_query_call(
        "get_block_intervals",
        get_block_intervals,
        mainnet_db_path,
        start_time,
        end_time,
        [],
    )
    testnet_block_intervals = _safe_query_call(
        "get_block_intervals",
        get_block_intervals,
        testnet_db_path,
        start_time,
        end_time,
        [],
    )

    try:
        mainnet_block_n = len(mainnet_block_intervals) if isinstance(mainnet_block_intervals, list) else 0
        testnet_block_n = len(testnet_block_intervals) if isinstance(testnet_block_intervals, list) else 0

        if mainnet_block_n < MIN_BLOCK_INTERVAL_SAMPLES or testnet_block_n < MIN_BLOCK_INTERVAL_SAMPLES:
            block_interval_comparison = {
                "insufficient_data": True,
                "n_a": mainnet_block_n,
                "n_b": testnet_block_n,
                "min_required": MIN_BLOCK_INTERVAL_SAMPLES,
            }
        else:
            block_interval_comparison = compare_distributions(
                mainnet_block_intervals,
                testnet_block_intervals,
                label_a="mainnet",
                label_b="testnet",
            )
    except Exception as exc:
        print(f"[comparison warning] compare_distributions failed for block intervals: {exc}")
        block_interval_comparison = {
            "error": str(exc),
            "n_a": len(mainnet_block_intervals) if isinstance(mainnet_block_intervals, list) else 0,
            "n_b": len(testnet_block_intervals) if isinstance(testnet_block_intervals, list) else 0,
        }

    mainnet_finality_series = _safe_query_call(
        "get_finality_lag_series",
        get_finality_lag_series,
        mainnet_db_path,
        start_time,
        end_time,
        [],
    )
    testnet_finality_series = _safe_query_call(
        "get_finality_lag_series",
        get_finality_lag_series,
        testnet_db_path,
        start_time,
        end_time,
        [],
    )

    mainnet_missed_slots = _safe_query_call(
        "get_missed_slot_stats",
        get_missed_slot_stats,
        mainnet_db_path,
        start_time,
        end_time,
        {"total_slots": 0, "missed_slots": 0, "missed_rate": 0.0},
    )
    testnet_missed_slots = _safe_query_call(
        "get_missed_slot_stats",
        get_missed_slot_stats,
        testnet_db_path,
        start_time,
        end_time,
        {"total_slots": 0, "missed_slots": 0, "missed_rate": 0.0},
    )

    mainnet_reorgs = _safe_query_call(
        "get_reorg_events",
        get_reorg_events,
        mainnet_db_path,
        start_time,
        end_time,
        [],
    )
    testnet_reorgs = _safe_query_call(
        "get_reorg_events",
        get_reorg_events,
        testnet_db_path,
        start_time,
        end_time,
        [],
    )

    mainnet_inclusion_times = _safe_query_call(
        "get_time_to_inclusion",
        get_time_to_inclusion,
        mainnet_db_path,
        start_time,
        end_time,
        [],
    )
    testnet_inclusion_times = _safe_query_call(
        "get_time_to_inclusion",
        get_time_to_inclusion,
        testnet_db_path,
        start_time,
        end_time,
        [],
    )

    mainnet_milestones = _safe_query_call(
        "get_confirmation_milestone_times",
        get_confirmation_milestone_times,
        mainnet_db_path,
        start_time,
        end_time,
        {1: [], 3: [], 12: [], 32: [], 64: []},
    )
    testnet_milestones = _safe_query_call(
        "get_confirmation_milestone_times",
        get_confirmation_milestone_times,
        testnet_db_path,
        start_time,
        end_time,
        {1: [], 3: [], 12: [], 32: [], 64: []},
    )

    mainnet_gas_series = _safe_query_call(
        "get_gas_utilization_series",
        get_gas_utilization_series,
        mainnet_db_path,
        start_time,
        end_time,
        [],
    )
    testnet_gas_series = _safe_query_call(
        "get_gas_utilization_series",
        get_gas_utilization_series,
        testnet_db_path,
        start_time,
        end_time,
        [],
    )

    mainnet_tx_finalized_times = _safe_query_call(
        "get_time_to_transaction_finalized",
        get_time_to_transaction_finalized,
        mainnet_db_path,
        start_time,
        end_time,
        [],
    )
    testnet_tx_finalized_times = _safe_query_call(
        "get_time_to_transaction_finalized",
        get_time_to_transaction_finalized,
        testnet_db_path,
        start_time,
        end_time,
        [],
    )

    mainnet_mined_to_finalized_times = _safe_query_call(
        "get_time_from_mined_to_finalized",
        get_time_from_mined_to_finalized,
        mainnet_db_path,
        start_time,
        end_time,
        [],
    )
    testnet_mined_to_finalized_times = _safe_query_call(
        "get_time_from_mined_to_finalized",
        get_time_from_mined_to_finalized,
        testnet_db_path,
        start_time,
        end_time,
        [],
    )

    mainnet_block_finality_proxy = _safe_query_call(
        "get_block_time_to_finality_proxy",
        get_block_time_to_finality_proxy,
        mainnet_db_path,
        start_time,
        end_time,
        [],
    )
    testnet_block_finality_proxy = _safe_query_call(
        "get_block_time_to_finality_proxy",
        get_block_time_to_finality_proxy,
        testnet_db_path,
        start_time,
        end_time,
        [],
    )

    mainnet_gas_values = []
    if isinstance(mainnet_gas_series, list):
        mainnet_gas_values = [row.get("utilization") for row in mainnet_gas_series if isinstance(row, dict)]

    testnet_gas_values = []
    if isinstance(testnet_gas_series, list):
        testnet_gas_values = [row.get("utilization") for row in testnet_gas_series if isinstance(row, dict)]

    mainnet_finality_lags = _safe_series_from_rows(mainnet_finality_series, "lag_epochs")
    testnet_finality_lags = _safe_series_from_rows(testnet_finality_series, "lag_epochs")
    mainnet_finality_cadence = _iso_time_deltas_seconds(mainnet_finality_series, "recorded_at")
    testnet_finality_cadence = _iso_time_deltas_seconds(testnet_finality_series, "recorded_at")

    report = {
        "meta": {
            "start_time": start_time,
            "end_time": end_time,
            "generated_at": generated_at,
        },
        "h1_protocol_fidelity": {
            "block_interval": {
                "mainnet": _safe_descriptive_with_min_samples(
                    mainnet_block_intervals if isinstance(mainnet_block_intervals, list) else [],
                    MIN_BLOCK_INTERVAL_SAMPLES,
                ),
                "testnet": _safe_descriptive_with_min_samples(
                    testnet_block_intervals if isinstance(testnet_block_intervals, list) else [],
                    MIN_BLOCK_INTERVAL_SAMPLES,
                ),
                "comparison": block_interval_comparison,
                "min_required_samples": MIN_BLOCK_INTERVAL_SAMPLES,
            },
            "finality_epoch": {
                "mainnet": mainnet_finality_series if isinstance(mainnet_finality_series, list) else [],
                "testnet": testnet_finality_series if isinstance(testnet_finality_series, list) else [],
            },
            "finality_lag_epochs_stats": {
                "mainnet": _safe_descriptive(mainnet_finality_lags),
                "testnet": _safe_descriptive(testnet_finality_lags),
            },
            "finality_cadence_seconds": {
                "mainnet": _safe_descriptive(mainnet_finality_cadence),
                "testnet": _safe_descriptive(testnet_finality_cadence),
            },
        },
        "h2_chain_integrity": {
            "missed_slots": {
                "mainnet": mainnet_missed_slots if isinstance(mainnet_missed_slots, dict) else {"total_slots": 0, "missed_slots": 0, "missed_rate": 0.0},
                "testnet": testnet_missed_slots if isinstance(testnet_missed_slots, dict) else {"total_slots": 0, "missed_slots": 0, "missed_rate": 0.0},
            },
            "reorgs": {
                "mainnet": mainnet_reorgs if isinstance(mainnet_reorgs, list) else [],
                "testnet": testnet_reorgs if isinstance(testnet_reorgs, list) else [],
            },
            "reorg_summary": {
                "mainnet": _reorg_summary(mainnet_reorgs),
                "testnet": _reorg_summary(testnet_reorgs),
            },
        },
        "h3_transaction_lifecycle": {
            "time_to_inclusion": {
                "mainnet": _safe_descriptive(mainnet_inclusion_times if isinstance(mainnet_inclusion_times, list) else []),
                "testnet": _safe_descriptive(testnet_inclusion_times if isinstance(testnet_inclusion_times, list) else []),
            },
            "time_to_transaction_finalized": {
                "mainnet": _safe_descriptive(mainnet_tx_finalized_times if isinstance(mainnet_tx_finalized_times, list) else []),
                "testnet": _safe_descriptive(testnet_tx_finalized_times if isinstance(testnet_tx_finalized_times, list) else []),
            },
            "time_from_mined_to_finalized": {
                "mainnet": _safe_descriptive(mainnet_mined_to_finalized_times if isinstance(mainnet_mined_to_finalized_times, list) else []),
                "testnet": _safe_descriptive(testnet_mined_to_finalized_times if isinstance(testnet_mined_to_finalized_times, list) else []),
            },
            "block_time_to_finality_proxy_64": {
                "mainnet": _safe_descriptive(mainnet_block_finality_proxy if isinstance(mainnet_block_finality_proxy, list) else []),
                "testnet": _safe_descriptive(testnet_block_finality_proxy if isinstance(testnet_block_finality_proxy, list) else []),
            },
            "confirmation_milestones": {
                "mainnet": _milestone_stats(mainnet_milestones),
                "testnet": _milestone_stats(testnet_milestones),
            },
            "gas_utilization": {
                "mainnet": _safe_descriptive(mainnet_gas_values),
                "testnet": _safe_descriptive(testnet_gas_values),
            },
        },
    }

    return report


def save_report(report: dict, output_dir: str = "comparison/reports") -> str:
    os.makedirs(output_dir, exist_ok=True)

    meta = report.get("meta", {}) if isinstance(report, dict) else {}
    generated_at = meta.get("generated_at") if isinstance(meta, dict) else None
    if not generated_at:
        generated_at = datetime.now(timezone.utc).isoformat()

    safe_timestamp = str(generated_at).replace(":", "-").replace("/", "-")
    filename = f"report_{safe_timestamp}.json"
    file_path = os.path.join(output_dir, filename)

    with open(file_path, "w", encoding="utf-8") as report_file:
        json.dump(report, report_file, indent=2, ensure_ascii=False, default=str)

    return file_path


def load_report(filepath: str) -> dict:
    with open(filepath, "r", encoding="utf-8") as report_file:
        return json.load(report_file)