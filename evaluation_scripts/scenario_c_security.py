#!/usr/bin/env python3
"""Scenario C: Security Enforcement Validation

Tests whether the Slice Manager enforces access control via CAPIF tokens:
1. Valid JWT: Should accept (200/202)
2. Invalid/malformed JWT: Should reject (401)
3. Expired JWT: Should reject (401)
4. Missing Authorization header: Should reject (401)

Runs 5 iterations per test case (20 total) and outputs:
- CSV file with test results
- JSON file with detailed results

This validates that CAPIF is part of the actual enforcement path.
"""
import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "invoker_impl"))
sys.path.insert(0, str(Path(__file__).parent))

import jwt
import requests
from opencapif_sdk import capif_invoker_connector, service_discoverer

from utils import (
    ScenarioCResult,
    dataclass_to_dict,
    measure_time,
    save_metadata,
    save_results_csv,
    save_results_json,
)


class SecurityTester:
    """Tests security enforcement with different token conditions."""
    
    def __init__(self, config_file: str, slice_manager_url: str):
        self.config_file = config_file
        self.slice_manager_url = slice_manager_url
        self.valid_token: str | None = None
        self.connector: capif_invoker_connector | None = None
        self.discoverer: service_discoverer | None = None
    
    async def setup_capif(self):
        """Onboard and obtain a valid token for testing."""
        print("\n[Setup] Onboarding and obtaining valid token...")
        
        def _setup():
            connector = capif_invoker_connector(config_file=self.config_file)
            connector.onboard_invoker()
            
            discoverer = service_discoverer(config_file=self.config_file)
            discoverer.discover()
            discoverer.get_tokens()
            
            return connector, discoverer, discoverer.token
        
        self.connector, self.discoverer, self.valid_token = await asyncio.to_thread(_setup)
        print(f"[Setup] ✓ Valid token obtained (length: {len(self.valid_token)})")
    
    async def cleanup_capif(self):
        """Offboard the invoker."""
        if self.connector is None:
            return
        
        print("\n[Cleanup] Offboarding invoker...")
        
        def _cleanup():
            self.connector.offboard_invoker()
        
        try:
            await asyncio.to_thread(_cleanup)
            print("[Cleanup] ✓ Offboarding complete")
        except Exception as e:
            print(f"[Cleanup] Warning: Offboarding failed (non-fatal): {e}")
    
    def create_invalid_token(self) -> str:
        """Create an invalid/malformed JWT."""
        return "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.INVALID_PAYLOAD.INVALID_SIGNATURE"
    
    def create_expired_token(self) -> str:
        """Create an expired JWT (expired 1 hour ago)."""
        # Create a token that expired 1 hour ago
        payload = {
            'sub': 'test_invoker',
            'exp': datetime.utcnow() - timedelta(hours=1),
            'iat': datetime.utcnow() - timedelta(hours=2)
        }
        
        # Sign with arbitrary secret (Slice Manager will reject it anyway)
        expired_token = jwt.encode(payload, 'test_secret', algorithm='HS256')
        return expired_token
    
    async def test_with_token(
        self,
        test_case: str,
        token: str | None,
        expected_response: str
    ) -> tuple[int, float, bool]:
        """Execute a test with a specific token condition.
        
        Args:
            test_case: Name of the test case
            token: JWT token to use (None for missing header test)
            expected_response: Expected HTTP response code/description
            
        Returns:
            Tuple of (status_code, duration_ms, operation_executed)
        """
        headers = {"Accept": "application/json"}
        
        if token is not None:
            headers["Authorization"] = f"Bearer {token}"
        
        def _request():
            return requests.get(
                self.slice_manager_url,
                headers=headers,
                timeout=10,
                verify=False
            )
        
        with measure_time(test_case) as timer:
            try:
                response = await asyncio.to_thread(_request)
                status_code = response.status_code
            except requests.exceptions.HTTPError as e:
                # Still capture status code from error response
                status_code = e.response.status_code if e.response else 500
            except Exception as e:
                # Network error or timeout
                status_code = 0
        
        # Determine if operation was executed
        # If we get 200/202, the operation likely executed
        # If we get 401/403, it was blocked before execution
        operation_executed = status_code in [200, 202]
        
        return status_code, timer.duration_ms, operation_executed


async def run_test_case(
    tester: SecurityTester,
    run_id: int,
    test_case: str,
    token: str | None,
    expected_response: str
) -> ScenarioCResult:
    """Execute a single security test.
    
    Args:
        tester: SecurityTester instance
        run_id: Test iteration number
        test_case: Test case name
        token: Token to use (or None)
        expected_response: Expected HTTP response description
        
    Returns:
        ScenarioCResult with test results
    """
    status_code, duration_ms, operation_executed = await tester.test_with_token(
        test_case, token, expected_response
    )
    
    # Determine success based on expected response
    if expected_response == "202 Accepted":
        success = status_code in [200, 202]
    elif expected_response == "401 Unauthorized":
        success = status_code == 401
    else:
        success = False
    
    result = ScenarioCResult(
        run_id=run_id,
        test_case=test_case,
        expected_response=expected_response,
        observed_response=status_code,
        success=success,
        operation_executed=operation_executed,
        response_time_ms=duration_ms
    )
    
    status_icon = "✓" if success else "✗"
    exec_status = "Executed" if operation_executed else "Blocked"
    print(f"  {status_icon} HTTP {status_code} - {exec_status} ({duration_ms:.2f} ms)")
    
    return result


async def main():
    """Run Scenario C security enforcement tests."""
    
    print("=" * 70)
    print("SCENARIO C: SECURITY ENFORCEMENT VALIDATION")
    print("=" * 70)
    print("\nThis script validates that the Slice Manager enforces access control")
    print("using CAPIF-issued JWTs. Four test cases are executed:")
    print("  1. Valid JWT → Should accept (200/202)")
    print("  2. Invalid JWT → Should reject (401)")
    print("  3. Expired JWT → Should reject (401)")
    print("  4. Missing JWT → Should reject (401)")
    print("\nTarget: 5 iterations per test case (20 total)")
    print("=" * 70)
    
    # Configuration
    CAPIF_CONFIG = "invoker_impl/app/capif/invoker_config.json"
    SLICE_MANAGER_URL = "http://10.16.255.51:8000/ran/bbus"
    ITERATIONS_PER_TEST = 5
    OUTPUT_DIR = Path("evaluation_scripts/results")
    
    # Verify config file exists
    config_path = Path(CAPIF_CONFIG)
    if not config_path.exists():
        print(f"\n✗ Error: Config file not found: {CAPIF_CONFIG}")
        print("  Please ensure the CAPIF config file exists before running.")
        sys.exit(1)
    
    # Initialize tester
    tester = SecurityTester(str(config_path), SLICE_MANAGER_URL)
    
    try:
        # Setup: Onboard and get valid token
        await tester.setup_capif()
        
        results: list[ScenarioCResult] = []
        run_counter = 1
        
        # Test Case 1: Valid JWT
        print(f"\n{'=' * 70}")
        print("TEST CASE 1: Valid JWT (Expected: 202 Accepted)")
        print('=' * 70)
        
        for i in range(ITERATIONS_PER_TEST):
            print(f"[Run {run_counter}]")
            result = await run_test_case(
                tester,
                run_counter,
                "valid_jwt",
                tester.valid_token,
                "202 Accepted"
            )
            results.append(result)
            run_counter += 1
            await asyncio.sleep(0.5)
        
        # Test Case 2: Invalid/Malformed JWT
        print(f"\n{'=' * 70}")
        print("TEST CASE 2: Invalid JWT (Expected: 401 Unauthorized)")
        print('=' * 70)
        
        invalid_token = tester.create_invalid_token()
        
        for i in range(ITERATIONS_PER_TEST):
            print(f"[Run {run_counter}]")
            result = await run_test_case(
                tester,
                run_counter,
                "invalid_jwt",
                invalid_token,
                "401 Unauthorized"
            )
            results.append(result)
            run_counter += 1
            await asyncio.sleep(0.5)
        
        # Test Case 3: Expired JWT
        print(f"\n{'=' * 70}")
        print("TEST CASE 3: Expired JWT (Expected: 401 Unauthorized)")
        print('=' * 70)
        
        expired_token = tester.create_expired_token()
        
        for i in range(ITERATIONS_PER_TEST):
            print(f"[Run {run_counter}]")
            result = await run_test_case(
                tester,
                run_counter,
                "expired_jwt",
                expired_token,
                "401 Unauthorized"
            )
            results.append(result)
            run_counter += 1
            await asyncio.sleep(0.5)
        
        # Test Case 4: Missing Authorization Header
        print(f"\n{'=' * 70}")
        print("TEST CASE 4: Missing JWT (Expected: 401 Unauthorized)")
        print('=' * 70)
        
        for i in range(ITERATIONS_PER_TEST):
            print(f"[Run {run_counter}]")
            result = await run_test_case(
                tester,
                run_counter,
                "missing_jwt",
                None,
                "401 Unauthorized"
            )
            results.append(result)
            run_counter += 1
            await asyncio.sleep(0.5)
        
        # Cleanup
        await tester.cleanup_capif()
        
        # Convert results to dictionaries
        results_dict = [dataclass_to_dict(r) for r in results]
        
        # Save results
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        
        timestamp = results[0].timestamp.replace(':', '-').split('.')[0]
        csv_path = OUTPUT_DIR / f"scenario_c_results_{timestamp}.csv"
        json_path = OUTPUT_DIR / f"scenario_c_results_{timestamp}.json"
        metadata_path = OUTPUT_DIR / f"scenario_c_metadata_{timestamp}.json"
        
        save_results_csv(results_dict, csv_path)
        save_results_json(results_dict, json_path)
        
        # Calculate success rates per test case
        test_cases = ["valid_jwt", "invalid_jwt", "expired_jwt", "missing_jwt"]
        success_rates = {}
        
        for test_case in test_cases:
            case_results = [r for r in results if r.test_case == test_case]
            successful = sum(1 for r in case_results if r.success)
            success_rates[test_case] = f"{successful}/{len(case_results)}"
        
        # Save metadata
        metadata = {
            'experiment': 'Scenario C - Security Enforcement',
            'total_tests': len(results),
            'iterations_per_test_case': ITERATIONS_PER_TEST,
            'slice_manager_url': SLICE_MANAGER_URL,
            'success_rates': success_rates,
            'test_cases': {
                'valid_jwt': {
                    'expected': '202 Accepted',
                    'description': 'Valid CAPIF-issued JWT'
                },
                'invalid_jwt': {
                    'expected': '401 Unauthorized',
                    'description': 'Malformed JWT signature'
                },
                'expired_jwt': {
                    'expected': '401 Unauthorized',
                    'description': 'JWT with expired timestamp'
                },
                'missing_jwt': {
                    'expected': '401 Unauthorized',
                    'description': 'No Authorization header'
                }
            }
        }
        save_metadata(metadata, metadata_path)
        
        # Print summary
        print(f"\n{'=' * 70}")
        print("SECURITY TEST SUMMARY")
        print('=' * 70)
        
        for test_case in test_cases:
            case_results = [r for r in results if r.test_case == test_case]
            successful = sum(1 for r in case_results if r.success)
            blocked = sum(1 for r in case_results if not r.operation_executed)
            
            print(f"\n{test_case.upper().replace('_', ' ')}:")
            print(f"  Success rate: {successful}/{len(case_results)}")
            print(f"  Operations blocked: {blocked}/{len(case_results)}")
        
        # Final summary
        total_successful = sum(1 for r in results if r.success)
        print(f"\n{'=' * 70}")
        print(f"TEST COMPLETE")
        print(f"{'=' * 70}")
        print(f"Total tests:     {len(results)}")
        print(f"Successful:      {total_successful}")
        print(f"Failed:          {len(results) - total_successful}")
        print(f"\nResults saved to:")
        print(f"  CSV:      {csv_path}")
        print(f"  JSON:     {json_path}")
        print(f"  Metadata: {metadata_path}")
        print(f"{'=' * 70}\n")
        
    except Exception as e:
        print(f"\n✗ Fatal error: {e}")
        
        # Attempt cleanup
        try:
            await tester.cleanup_capif()
        except:
            pass
        
        sys.exit(1)


if __name__ == "__main__":
    # Disable SSL warnings (testbed environment)
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    asyncio.run(main())
