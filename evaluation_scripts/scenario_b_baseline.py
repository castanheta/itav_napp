#!/usr/bin/env python3
"""Scenario B: Direct Slice Manager Invocation Baseline

Measures latency for direct Slice Manager invocation without CAPIF:
- No invoker onboarding
- No service discovery
- No security context establishment
- No token acquisition
- Direct HTTP request to Slice Manager

Runs 30 iterations and outputs:
- CSV file with timing measurements
- JSON file with detailed results

This provides the baseline for calculating CAPIF overhead.
"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "invoker_impl"))
sys.path.insert(0, str(Path(__file__).parent))

import requests

from utils import (
    ScenarioBResult,
    dataclass_to_dict,
    measure_time,
    print_summary_statistics,
    save_metadata,
    save_results_csv,
    save_results_json,
)


async def run_direct_invocation(
    run_id: int,
    url: str
) -> ScenarioBResult:
    """Execute a single direct invocation.
    
    Args:
        run_id: Iteration number
        url: Slice Manager endpoint URL
        
    Returns:
        ScenarioBResult with timing measurement
    """
    print(f"[Run {run_id}] ", end='', flush=True)
    
    result = ScenarioBResult(
        run_id=run_id,
        direct_invocation_ms=0,
        success=False
    )
    
    try:
        headers = {
            "Accept": "application/json"
        }
        
        def _request():
            return requests.get(url, headers=headers, timeout=10, verify=False)
        
        with measure_time("direct_invocation") as timer:
            response = await asyncio.to_thread(_request)
        
        result.direct_invocation_ms = timer.duration_ms
        result.http_status_code = response.status_code
        result.success = True
        
        print(f"✓ {result.direct_invocation_ms:.2f} ms (HTTP {response.status_code})")
        
    except Exception as e:
        result.success = False
        result.error_message = str(e)
        print(f"✗ Error: {e}")
    
    return result


async def main():
    """Run Scenario B baseline benchmark."""
    
    print("=" * 70)
    print("SCENARIO B: DIRECT INVOCATION BASELINE")
    print("=" * 70)
    print("\nThis script measures latency for direct Slice Manager invocation")
    print("without CAPIF (no onboarding, discovery, or token acquisition).")
    print("\nTarget: 30 successful runs")
    print("=" * 70 + "\n")
    
    # Configuration
    SLICE_MANAGER_URL = "http://10.16.255.51:8000/ran/bbus"
    NUM_RUNS = 30
    OUTPUT_DIR = Path("evaluation_scripts/results")
    
    results: list[ScenarioBResult] = []
    successful_runs = 0
    
    # Run iterations
    for i in range(1, NUM_RUNS + 1):
        result = await run_direct_invocation(i, SLICE_MANAGER_URL)
        results.append(result)
        
        if result.success:
            successful_runs += 1
        
        # Short pause between iterations
        if i < NUM_RUNS:
            await asyncio.sleep(0.5)
    
    # Convert results to dictionaries
    results_dict = [dataclass_to_dict(r) for r in results]
    
    # Save results
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    timestamp = results[0].timestamp.replace(':', '-').split('.')[0]
    csv_path = OUTPUT_DIR / f"scenario_b_results_{timestamp}.csv"
    json_path = OUTPUT_DIR / f"scenario_b_results_{timestamp}.json"
    metadata_path = OUTPUT_DIR / f"scenario_b_metadata_{timestamp}.json"
    
    save_results_csv(results_dict, csv_path)
    save_results_json(results_dict, json_path)
    
    # Save metadata
    metadata = {
        'experiment': 'Scenario B - Direct Invocation Baseline',
        'total_runs': NUM_RUNS,
        'successful_runs': successful_runs,
        'failed_runs': NUM_RUNS - successful_runs,
        'slice_manager_url': SLICE_MANAGER_URL,
        'capif_enabled': False
    }
    save_metadata(metadata, metadata_path)
    
    # Print summary statistics
    successful_results = [r for r in results_dict if r['success']]
    if successful_results:
        print_summary_statistics(successful_results, ['direct_invocation_ms'])
    
    # Final summary
    print(f"\n{'=' * 70}")
    print(f"BENCHMARK COMPLETE")
    print(f"{'=' * 70}")
    print(f"Total runs:      {NUM_RUNS}")
    print(f"Successful:      {successful_runs}")
    print(f"Failed:          {NUM_RUNS - successful_runs}")
    print(f"\nResults saved to:")
    print(f"  CSV:      {csv_path}")
    print(f"  JSON:     {json_path}")
    print(f"  Metadata: {metadata_path}")
    print(f"{'=' * 70}\n")


if __name__ == "__main__":
    # Disable SSL warnings (testbed environment)
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    asyncio.run(main())
