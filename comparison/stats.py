import math
import statistics
from typing import Any, Dict, List, Optional

from scipy.stats import mannwhitneyu


def _to_float_list(values: List[Any]) -> List[float]:
    numeric: List[float] = []
    for value in values:
        try:
            numeric.append(float(value))
        except (TypeError, ValueError):
            continue
    return numeric


def _percentile(values: List[float], percentile: float) -> Optional[float]:
    if not values:
        return None

    sorted_values = sorted(values)
    if len(sorted_values) == 1:
        return sorted_values[0]

    rank = (len(sorted_values) - 1) * (percentile / 100.0)
    lower_index = int(math.floor(rank))
    upper_index = int(math.ceil(rank))

    lower = sorted_values[lower_index]
    upper = sorted_values[upper_index]

    if lower_index == upper_index:
        return lower

    weight = rank - lower_index
    return lower + (upper - lower) * weight


def descriptive_stats(values: List[Any]) -> Optional[Dict[str, float]]:
    numeric = _to_float_list(values)

    if len(numeric) == 0:
        return None

    if len(numeric) == 1:
        single = numeric[0]
        return {
            "n": 1,
            "mean": single,
            "median": single,
            "stddev": single,
            "min": single,
            "max": single,
            "p90": single,
            "p99": single,
        }

    p90 = _percentile(numeric, 90.0)
    p99 = _percentile(numeric, 99.0)

    return {
        "n": len(numeric),
        "mean": statistics.mean(numeric),
        "median": statistics.median(numeric),
        "stddev": statistics.pstdev(numeric),
        "min": min(numeric),
        "max": max(numeric),
        "p90": p90 if p90 is not None else numeric[0],
        "p99": p99 if p99 is not None else numeric[0],
    }


def compare_distributions(
    values_a: List[Any],
    values_b: List[Any],
    label_a: str = "mainnet",
    label_b: str = "testnet",
) -> Dict[str, Any]:
    numeric_a = _to_float_list(values_a)
    numeric_b = _to_float_list(values_b)

    n_a = len(numeric_a)
    n_b = len(numeric_b)

    if n_a < 3 or n_b < 3:
        return {
            "insufficient_data": True,
            "n_a": n_a,
            "n_b": n_b,
        }

    try:
        result = mannwhitneyu(numeric_a, numeric_b, alternative="two-sided")
    except Exception as exc:
        print(f"[comparison warning] compare_distributions failed: {exc}")
        return {
            "error": str(exc),
            "n_a": n_a,
            "n_b": n_b,
        }

    p_value = float(result.pvalue)

    return {
        "u_statistic": float(result.statistic),
        "p_value": p_value,
        "significant": p_value < 0.05,
        "label_a": label_a,
        "label_b": label_b,
        "n_a": n_a,
        "n_b": n_b,
    }
