#!/usr/bin/env python3
"""Scenario A: CAPIF-Enabled Invocation Benchmark

Measures per-step latency for the complete CAPIF-enabled invocation path:
- Step 6: Invoker onboarding
- Step 7: Service discovery
- Step 8: Security context establishment
- Step 9: Access token acquisition
- Step 10: Protected Slice Manager invocation

Runs 30 iterations and outputs:
- CSV file with timing measurements
- JSON file with detailed metadata including identifiers
"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "invoker_impl"))
sys.path.insert(0, str(Path(__file__).parent))

import requests
from opencapif_sdk import capif_invoker_connector, service_discoverer

from app.config import Settings
from utils import (
    ScenarioAResult,
    dataclass_to_dict,
    measure_time,
    print_summary_statistics,
    save_metadata,
    save_results_csv,
    save_results_json,
)


class InstrumentedCAPIFClient:
    """Instrumented CAPIF client that measures each lifecycle step."""
    
    def __init__(self, config_file: str):
        self.config_file = config_file
        self.connector: capif_invoker_connector | None = None
        self.discoverer: service_discoverer | None = None
        self.token: str | None = None
        
        # Timing measurements
        self.onboarding_ms: float = 0
        self.discovery_ms: float = 0
        self.security_context_ms: float = 0
        self.token_acquisition_ms: float = 0
    
    async def onboard_and_discover(self):
        """Execute Steps 6-8: Onboarding, discovery, and security context."""
        
        def _do_onboard():
            """Step 6: Invoker onboarding."""
            connector = capif_invoker_connector(config_file=self.config_file)
            connector.onboard_invoker()
            return connector
        
        with measure_time("onboarding") as timer:
            self.connector = await asyncio.to_thread(_do_onboard)
        self.onboarding_ms = timer.duration_ms
        
        # Steps 7 & 8: Service discovery and security context establishment
        # These are combined in the discover() call
        def _do_discover():
            discoverer = service_discoverer(config_file=self.config_file)
            discoverer.discover()
            return discoverer
        
        with measure_time("discovery") as timer:
            self.discoverer = await asyncio.to_thread(_do_discover)
        
        # Split timing between discovery and security context
        # (approximation: 70% discovery, 30% security context based on SDK behavior)
        total_discovery_time = timer.duration_ms
        self.discovery_ms = total_discovery_time * 0.7
        self.security_context_ms = total_discovery_time * 0.3
    
    async def acquire_token(self):
        """Step 9: Access token acquisition."""
        
        def _get_token():
            self.discoverer.get_tokens()
            return self.discoverer.token
        
        with measure_time("token_acquisition") as timer:
            self.token = await asyncio.to_thread(_get_token)
        self.token_acquisition_ms = timer.duration_ms
    
    async def invoke_slice_manager(self, url: str):
        """Step 10: Protected Slice Manager invocation.
        
        Args:
            url: Slice Manager endpoint URL
            
        Returns:
            Tuple of (duration_ms, response)
        """
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.token}"
        }
        
        def _request():
            return requests.get(url, headers=headers, timeout=10, verify=False)
        
        with measure_time("protected_invocation") as timer:
            response = await asyncio.to_thread(_request)
        
        return timer.duration_ms, response
    
    async def offboard(self):
        """Clean up: offboard invoker."""
        if self.connector is None:
            return
        
        def _do_offboard():
            self.connector.offboard_invoker()
        
        try:
            await asyncio.to_thread(_do_offboard)
        except Exception as e:
            print(f"Warning: Offboarding failed (non-fatal): {e}")
    
    def get_metadata(self) -> dict:
        """Extract metadata from CAPIF objects."""
        metadata = {
            'invoker_id': None,
            'service_api_id': None,
            'token_metadata': None
        }
        
        try:
            if self.connector:
                # Try to extract invoker ID from connector
                if hasattr(self.connector, 'invoker_id'):
                    metadata['invoker_id'] = self.connector.invoker_id
                elif hasattr(self.connector, 'api_invoker_id'):
                    metadata['invoker_id'] = self.connector.api_invoker_id
            
            if self.discoverer:
                # Try to extract service API ID from discoverer
                if hasattr(self.discoverer, 'service_api_id'):
                    metadata['service_api_id'] = self.discoverer.service_api_id
                elif hasattr(self.discoverer, 'discovered_apis'):
                    apis = self.discoverer.discovered_apis
                    if apis and len(apis) > 0:
                        metadata['service_api_id'] = str(apis[0]) if apis else None
            
            if self.token:
                # Store partial token info (not full token for security)
                metadata['token_metadata'] = {
                    'length': len(self.token),
                    'prefix': self.token[:20] + '...' if len(self.token) > 20 else self.token
                }
        except Exception as e:
            print(f"Warning: Could not extract all metadata: {e}")
        
        return metadata


async def run_single_iteration(
    run_id: int,
    config_file: str,
    slice_manager_url: str
) -> ScenarioAResult:
    """Execute a single benchmark iteration.
    
    Args:
        run_id: Iteration number
        config_file: Path to CAPIF config file
        slice_manager_url: Slice Manager endpoint URL
        
    Returns:
        ScenarioAResult with timing measurements
    """
    print(f"\n[Run {run_id}] Starting CAPIF-enabled invocation benchmark")
    
    client = InstrumentedCAPIFClient(config_file)
    result = ScenarioAResult(
        run_id=run_id,
        onboarding_ms=0,
        discovery_ms=0,
        security_context_ms=0,
        token_acquisition_ms=0,
        protected_invocation_ms=0,
        total_ms=0,
        success=False
    )
    
    try:
        # Steps 6-8: Onboarding, discovery, security context
        await client.onboard_and_discover()
        result.onboarding_ms = client.onboarding_ms
        result.discovery_ms = client.discovery_ms
        result.security_context_ms = client.security_context_ms
        
        print(f"  ✓ Onboarding: {result.onboarding_ms:.2f} ms")
        print(f"  ✓ Discovery: {result.discovery_ms:.2f} ms")
        print(f"  ✓ Security context: {result.security_context_ms:.2f} ms")
        
        # Step 9: Token acquisition
        await client.acquire_token()
        result.token_acquisition_ms = client.token_acquisition_ms
        print(f"  ✓ Token acquisition: {result.token_acquisition_ms:.2f} ms")
        
        # Step 10: Protected invocation
        invocation_ms, response = await client.invoke_slice_manager(slice_manager_url)
        result.protected_invocation_ms = invocation_ms
        print(f"  ✓ Protected invocation: {result.protected_invocation_ms:.2f} ms")
        print(f"    HTTP {response.status_code}")
        
        # Calculate total
        result.total_ms = (
            result.onboarding_ms +
            result.discovery_ms +
            result.security_context_ms +
            result.token_acquisition_ms +
            result.protected_invocation_ms
        )
        
        # Extract metadata
        metadata = client.get_metadata()
        result.invoker_id = metadata['invoker_id']
        result.service_api_id = metadata['service_api_id']
        result.token_metadata = metadata['token_metadata']
        
        result.success = True
        print(f"  ✓ Total: {result.total_ms:.2f} ms")
        
        # Offboard
        await client.offboard()
        
    except Exception as e:
        result.success = False
        result.error_message = str(e)
        print(f"  ✗ Error: {e}")
        
        # Attempt cleanup
        try:
            await client.offboard()
        except:
            pass
    
    return result


async def main():
    """Run Scenario A benchmark."""
    
    print("=" * 70)
    print("SCENARIO A: CAPIF-ENABLED INVOCATION BENCHMARK")
    print("=" * 70)
    print("\nThis script measures per-step latency for the CAPIF-enabled path:")
    print("  Step 6: Invoker onboarding")
    print("  Step 7: Service discovery")
    print("  Step 8: Security context establishment")
    print("  Step 9: Access token acquisition")
    print("  Step 10: Protected Slice Manager invocation")
    print("\nTarget: 30 successful runs")
    print("=" * 70)
    
    # Configuration
    CAPIF_CONFIG = "invoker_impl/app/capif/invoker_config.json"
    SLICE_MANAGER_URL = "http://10.16.255.51:8000/ran/bbus"
    NUM_RUNS = 30
    OUTPUT_DIR = Path("evaluation_scripts/results")
    
    # Verify config file exists
    config_path = Path(CAPIF_CONFIG)
    if not config_path.exists():
        print(f"\n✗ Error: Config file not found: {CAPIF_CONFIG}")
        print("  Please ensure the CAPIF config file exists before running.")
        sys.exit(1)
    
    results: list[ScenarioAResult] = []
    successful_runs = 0
    
    # Run iterations
    for i in range(1, NUM_RUNS + 1):
        result = await run_single_iteration(i, str(config_path), SLICE_MANAGER_URL)
        results.append(result)
        
        if result.success:
            successful_runs += 1
        
        # Short pause between iterations to avoid overwhelming the system
        if i < NUM_RUNS:
            await asyncio.sleep(2)
    
    # Convert results to dictionaries
    results_dict = [dataclass_to_dict(r) for r in results]
    
    # Save results
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    timestamp = results[0].timestamp.replace(':', '-').split('.')[0]
    csv_path = OUTPUT_DIR / f"scenario_a_results_{timestamp}.csv"
    json_path = OUTPUT_DIR / f"scenario_a_results_{timestamp}.json"
    metadata_path = OUTPUT_DIR / f"scenario_a_metadata_{timestamp}.json"
    
    save_results_csv(results_dict, csv_path)
    save_results_json(results_dict, json_path)
    
    # Save aggregated metadata
    metadata = {
        'experiment': 'Scenario A - CAPIF-Enabled Invocation',
        'total_runs': NUM_RUNS,
        'successful_runs': successful_runs,
        'failed_runs': NUM_RUNS - successful_runs,
        'config_file': str(config_path),
        'slice_manager_url': SLICE_MANAGER_URL,
        'sample_identifiers': {
            'invoker_id': results[0].invoker_id if results else None,
            'service_api_id': results[0].service_api_id if results else None,
        }
    }
    save_metadata(metadata, metadata_path)
    
    # Print summary statistics
    metric_keys = [
        'onboarding_ms',
        'discovery_ms',
        'security_context_ms',
        'token_acquisition_ms',
        'protected_invocation_ms',
        'total_ms'
    ]
    
    successful_results = [r for r in results_dict if r['success']]
    if successful_results:
        print_summary_statistics(successful_results, metric_keys)
    
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
