"""Utilities for evaluation benchmarking and data collection."""
import csv
import json
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class TimingMeasurement:
    """Single timing measurement in milliseconds."""
    
    name: str
    duration_ms: float
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class ScenarioAResult:
    """Result structure for Scenario A (CAPIF-enabled invocation)."""
    
    run_id: int
    onboarding_ms: float
    discovery_ms: float
    security_context_ms: float
    token_acquisition_ms: float
    protected_invocation_ms: float
    total_ms: float
    success: bool
    error_message: str | None = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    # Metadata fields (populated when available)
    invoker_id: str | None = None
    service_api_id: str | None = None
    token_metadata: dict | None = None


@dataclass
class ScenarioBResult:
    """Result structure for Scenario B (direct invocation baseline)."""
    
    run_id: int
    direct_invocation_ms: float
    success: bool
    error_message: str | None = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    http_status_code: int | None = None


@dataclass
class ScenarioCResult:
    """Result structure for Scenario C (security enforcement)."""
    
    run_id: int
    test_case: str  # 'valid_jwt', 'invalid_jwt', 'expired_jwt', 'missing_jwt'
    expected_response: str
    observed_response: int
    success: bool
    operation_executed: bool
    response_time_ms: float
    error_message: str | None = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class Timer:
    """High-resolution timer context manager."""
    
    def __init__(self):
        self.start_time: float = 0
        self.end_time: float = 0
        self.duration_ms: float = 0
    
    def __enter__(self):
        self.start_time = time.perf_counter()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = time.perf_counter()
        self.duration_ms = (self.end_time - self.start_time) * 1000


@contextmanager
def measure_time(name: str = "operation"):
    """Context manager for timing operations.
    
    Usage:
        with measure_time("onboarding") as timer:
            # perform operation
            pass
        print(f"Duration: {timer.duration_ms:.2f} ms")
    """
    timer = Timer()
    try:
        timer.__enter__()
        yield timer
    finally:
        timer.__exit__(None, None, None)


def save_results_csv(results: list[dict], output_path: Path) -> None:
    """Save results to CSV file.
    
    Args:
        results: List of result dictionaries
        output_path: Path to output CSV file
    """
    if not results:
        print(f"Warning: No results to save to {output_path}")
        return
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=results[0].keys())
        writer.writeheader()
        writer.writerows(results)
    
    print(f"✓ Saved {len(results)} results to {output_path}")


def save_results_json(results: list[dict], output_path: Path) -> None:
    """Save results to JSON file with pretty formatting.
    
    Args:
        results: List of result dictionaries
        output_path: Path to output JSON file
    """
    if not results:
        print(f"Warning: No results to save to {output_path}")
        return
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"✓ Saved {len(results)} results to {output_path}")


def save_metadata(metadata: dict, output_path: Path) -> None:
    """Save metadata to JSON file.
    
    Args:
        metadata: Metadata dictionary
        output_path: Path to output JSON file
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
    
    print(f"✓ Saved metadata to {output_path}")


def compute_statistics(values: list[float]) -> dict[str, float]:
    """Compute descriptive statistics for a list of values.
    
    Args:
        values: List of numeric values
        
    Returns:
        Dictionary with mean, std_dev, min, max, median
    """
    if not values:
        return {
            'mean': 0.0,
            'std_dev': 0.0,
            'min': 0.0,
            'max': 0.0,
            'median': 0.0,
            'count': 0
        }
    
    sorted_values = sorted(values)
    n = len(sorted_values)
    mean = sum(values) / n
    
    # Standard deviation
    variance = sum((x - mean) ** 2 for x in values) / n
    std_dev = variance ** 0.5
    
    # Median
    if n % 2 == 0:
        median = (sorted_values[n // 2 - 1] + sorted_values[n // 2]) / 2
    else:
        median = sorted_values[n // 2]
    
    return {
        'mean': round(mean, 2),
        'std_dev': round(std_dev, 2),
        'min': round(min(values), 2),
        'max': round(max(values), 2),
        'median': round(median, 2),
        'count': n
    }


def print_summary_statistics(results: list[dict], metric_keys: list[str]) -> None:
    """Print summary statistics for specified metrics.
    
    Args:
        results: List of result dictionaries
        metric_keys: List of metric keys to compute statistics for
    """
    print("\n" + "=" * 70)
    print("SUMMARY STATISTICS")
    print("=" * 70)
    
    for key in metric_keys:
        values = [r[key] for r in results if key in r and r[key] is not None]
        
        if not values:
            print(f"\n{key}: No valid values")
            continue
        
        stats = compute_statistics(values)
        print(f"\n{key}:")
        print(f"  Mean:   {stats['mean']:.2f} ms")
        print(f"  Std:    {stats['std_dev']:.2f} ms")
        print(f"  Min:    {stats['min']:.2f} ms")
        print(f"  Max:    {stats['max']:.2f} ms")
        print(f"  Median: {stats['median']:.2f} ms")
        print(f"  Count:  {stats['count']}")
    
    print("=" * 70 + "\n")


def dataclass_to_dict(obj: Any) -> dict:
    """Convert a dataclass instance to a dictionary.
    
    Args:
        obj: Dataclass instance
        
    Returns:
        Dictionary representation
    """
    return asdict(obj)
