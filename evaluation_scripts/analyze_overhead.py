#!/usr/bin/env python3
"""Overhead Analysis Script

Computes overhead statistics for Table 5.6 by comparing Scenario A (CAPIF-enabled)
and Scenario B (direct baseline) results.

Usage:
    python3 evaluation_scripts/analyze_overhead.py \\
        evaluation_scripts/results/scenario_a_results_<timestamp>.csv \\
        evaluation_scripts/results/scenario_b_results_<timestamp>.csv
"""
import sys
from pathlib import Path

import pandas as pd

from evaluation_scripts.utils import compute_statistics


def analyze_overhead(scenario_a_csv: Path, scenario_b_csv: Path):
    """Compute and display overhead analysis.
    
    Args:
        scenario_a_csv: Path to Scenario A results CSV
        scenario_b_csv: Path to Scenario B results CSV
    """
    # Load data
    print("\n" + "=" * 70)
    print("OVERHEAD ANALYSIS - Table 5.6")
    print("=" * 70)
    print(f"\nLoading Scenario A: {scenario_a_csv}")
    print(f"Loading Scenario B: {scenario_b_csv}")
    
    df_a = pd.read_csv(scenario_a_csv)
    df_b = pd.read_csv(scenario_b_csv)
    
    # Filter successful runs
    a_success = df_a[df_a['success'] == True]
    b_success = df_b[df_b['success'] == True]
    
    print(f"\nScenario A: {len(a_success)}/{len(df_a)} successful runs")
    print(f"Scenario B: {len(b_success)}/{len(df_b)} successful runs")
    
    if len(a_success) == 0 or len(b_success) == 0:
        print("\n✗ Error: No successful runs found. Cannot compute overhead.")
        return
    
    # Compute overhead components
    print("\n" + "=" * 70)
    print("OVERHEAD DECOMPOSITION")
    print("=" * 70)
    
    # 1. Lifecycle preparation overhead (Steps 6-8)
    lifecycle_overhead = (
        a_success['onboarding_ms'] +
        a_success['discovery_ms'] +
        a_success['security_context_ms']
    )
    
    lifecycle_stats = compute_statistics(lifecycle_overhead.tolist())
    print(f"\n1. Lifecycle Preparation Overhead (Steps 6-8):")
    print(f"   - Onboarding + Discovery + Security Context")
    print(f"   Mean:   {lifecycle_stats['mean']:.2f} ms")
    print(f"   Std:    {lifecycle_stats['std_dev']:.2f} ms")
    print(f"   Interpretation: One-time or session-level cost")
    print(f"   Frequency: Per session (amortizable)")
    
    # 2. Token acquisition overhead (Step 9)
    token_overhead = a_success['token_acquisition_ms']
    token_stats = compute_statistics(token_overhead.tolist())
    
    print(f"\n2. Token Acquisition Overhead (Step 9):")
    print(f"   Mean:   {token_stats['mean']:.2f} ms")
    print(f"   Std:    {token_stats['std_dev']:.2f} ms")
    print(f"   Interpretation: Cost of obtaining access credentials")
    print(f"   Frequency: Per token lifetime (amortizable)")
    
    # 3. Protected invocation overhead (Step 10 minus baseline)
    protected_invocation = a_success['protected_invocation_ms']
    direct_baseline = b_success['direct_invocation_ms']
    
    protected_stats = compute_statistics(protected_invocation.tolist())
    baseline_stats = compute_statistics(direct_baseline.tolist())
    
    invocation_overhead_mean = protected_stats['mean'] - baseline_stats['mean']
    
    print(f"\n3. Protected Invocation Overhead:")
    print(f"   Protected invocation (Step 10): {protected_stats['mean']:.2f} ms")
    print(f"   Direct baseline (Scenario B):   {baseline_stats['mean']:.2f} ms")
    print(f"   Overhead:                        {invocation_overhead_mean:.2f} ms")
    print(f"   Interpretation: Cost of authenticated invocation and token validation")
    print(f"   Frequency: Per request")
    
    # 4. Total measured overhead
    total_capif = a_success['total_ms']
    total_stats = compute_statistics(total_capif.tolist())
    
    total_overhead_mean = total_stats['mean'] - baseline_stats['mean']
    total_overhead_std = ((total_stats['std_dev']**2 + baseline_stats['std_dev']**2) ** 0.5)
    
    print(f"\n4. Total Measured Overhead:")
    print(f"   Scenario A total:     {total_stats['mean']:.2f} ms")
    print(f"   Scenario B baseline:  {baseline_stats['mean']:.2f} ms")
    print(f"   Total overhead:       {total_overhead_mean:.2f} ms (± {total_overhead_std:.2f} ms)")
    print(f"   Interpretation: Overall cost of CAPIF-enabled path")
    print(f"   Frequency: Per measured run (includes all steps)")
    
    # Summary table
    print("\n" + "=" * 70)
    print("TABLE 5.6: OPERATIONAL OVERHEAD SUMMARY")
    print("=" * 70)
    print(f"\n{'Latency Component':<40} {'Mean (ms)':<12} {'Std Dev (ms)':<15} {'Frequency':<20}")
    print("-" * 100)
    print(f"{'Lifecycle preparation (Steps 6-8)':<40} {lifecycle_stats['mean']:<12.2f} {lifecycle_stats['std_dev']:<15.2f} {'Per session':<20}")
    print(f"{'Token acquisition (Step 9)':<40} {token_stats['mean']:<12.2f} {token_stats['std_dev']:<15.2f} {'Per token lifetime':<20}")
    print(f"{'Protected invocation overhead (Step 10 - baseline)':<40} {invocation_overhead_mean:<12.2f} {'N/A':<15} {'Per request':<20}")
    print(f"{'Total measured overhead (Scenario A - B)':<40} {total_overhead_mean:<12.2f} {total_overhead_std:<15.2f} {'Per measured run':<20}")
    print("-" * 100)
    
    # Percentage breakdown
    print("\n" + "=" * 70)
    print("OVERHEAD BREAKDOWN (as % of total CAPIF overhead)")
    print("=" * 70)
    
    lifecycle_pct = (lifecycle_stats['mean'] / total_overhead_mean) * 100
    token_pct = (token_stats['mean'] / total_overhead_mean) * 100
    invocation_pct = (invocation_overhead_mean / total_overhead_mean) * 100
    
    print(f"\nLifecycle preparation: {lifecycle_pct:.1f}%")
    print(f"Token acquisition:     {token_pct:.1f}%")
    print(f"Protected invocation:  {invocation_pct:.1f}%")
    
    print("\n" + "=" * 70)
    print("INTERPRETATION")
    print("=" * 70)
    print("\nThe overhead analysis shows that:")
    print(f"- Lifecycle preparation accounts for {lifecycle_pct:.1f}% of total overhead")
    print(f"  → One-time cost per session, amortizable across multiple requests")
    print(f"- Token acquisition accounts for {token_pct:.1f}% of total overhead")
    print(f"  → Periodic cost based on token lifetime, amortizable within validity period")
    print(f"- Protected invocation adds {invocation_overhead_mean:.2f} ms per request")
    print(f"  → Per-request cost for JWT validation and authenticated access")
    print(f"\nTotal CAPIF overhead: {total_overhead_mean:.2f} ms vs {baseline_stats['mean']:.2f} ms baseline")
    print(f"This represents a {((total_overhead_mean / baseline_stats['mean']) * 100):.1f}× increase over direct invocation")
    print("=" * 70 + "\n")


def main():
    """Main entry point."""
    if len(sys.argv) != 3:
        print("Usage:")
        print("  python3 evaluation_scripts/analyze_overhead.py \\")
        print("      evaluation_scripts/results/scenario_a_results_<timestamp>.csv \\")
        print("      evaluation_scripts/results/scenario_b_results_<timestamp>.csv")
        sys.exit(1)
    
    scenario_a_csv = Path(sys.argv[1])
    scenario_b_csv = Path(sys.argv[2])
    
    if not scenario_a_csv.exists():
        print(f"✗ Error: Scenario A CSV not found: {scenario_a_csv}")
        sys.exit(1)
    
    if not scenario_b_csv.exists():
        print(f"✗ Error: Scenario B CSV not found: {scenario_b_csv}")
        sys.exit(1)
    
    analyze_overhead(scenario_a_csv, scenario_b_csv)


if __name__ == "__main__":
    main()
