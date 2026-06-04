# Evaluation Scripts for Master Thesis

This directory contains benchmark and test scripts for evaluating the CAPIF integration with the Network Operations N-App and Slice Manager.

## Overview

Three evaluation scenarios are implemented:

- **Scenario A**: CAPIF-enabled invocation path with per-step timing measurements
- **Scenario B**: Direct Slice Manager invocation baseline (without CAPIF)
- **Scenario C**: Security enforcement validation with different token conditions

## Prerequisites

### System Requirements

- Python 3.10 or higher
- Active CAPIF infrastructure (OpenCAPIF)
- Slice Manager accessible at configured endpoint
- Network connectivity between N-App, CAPIF, and Slice Manager

### Python Dependencies

All dependencies are already included in the main `requirements.txt`. Ensure you have installed them:

```bash
pip install -r requirements.txt
```

Additional dependencies for evaluation scripts:
- `opencapif-sdk` - CAPIF client library
- `requests` - HTTP client
- `PyJWT` - JWT token manipulation (for Scenario C)

### Configuration

Before running the scripts, verify the following configuration:

1. **CAPIF Config File**: Ensure `invoker_impl/app/capif/invoker_config.json` exists and contains valid CAPIF credentials

2. **Slice Manager Endpoint**: The scripts use the following default endpoints:
   - Scenario A: `http://10.16.10.78:8000/ran/bbus`
   - Scenario B: `http://10.16.10.78:8000/ran/bbus`
   - Scenario C: `http://10.16.10.78:8000/ran/bbus`

   Modify these URLs in the scripts if your Slice Manager is at a different address.

3. **Network Access**: Ensure the evaluation environment can reach:
   - CAPIF endpoints (for onboarding, discovery, token acquisition)
   - Slice Manager endpoints

## Running the Scripts

All scripts are designed to be run from the repository root directory:

```bash
cd /path/to/itav-napp
```

### Scenario A: CAPIF-Enabled Invocation Benchmark

**Purpose**: Measures per-step latency for the complete CAPIF-enabled invocation workflow.

**Steps measured**:
1. Step 6: Invoker onboarding
2. Step 7: Service discovery
3. Step 8: Security context establishment
4. Step 9: Access token acquisition
5. Step 10: Protected Slice Manager invocation

**Run the script**:

```bash
python3 evaluation_scripts/scenario_a_benchmark.py
```

**Duration**: Approximately 20-30 minutes (30 iterations with 2-second pauses)

**Outputs**:
- `evaluation_scripts/results/scenario_a_results_<timestamp>.csv` - Timing data for statistical analysis
- `evaluation_scripts/results/scenario_a_results_<timestamp>.json` - Detailed results with metadata
- `evaluation_scripts/results/scenario_a_metadata_<timestamp>.json` - Experiment metadata and identifiers

**Mapping to thesis tables**:
- **Table 5.3**: Extract `invoker_id` and `service_api_id` from metadata file
- **Table 5.4**: Use CSV file to compute mean, std dev, min, max, median for each step
- **Table 5.6**: Use `total_ms` column for overhead calculation

### Scenario B: Direct Invocation Baseline

**Purpose**: Measures latency for direct Slice Manager invocation without CAPIF (baseline for overhead calculation).

**Run the script**:

```bash
python3 evaluation_scripts/scenario_b_baseline.py
```

**Duration**: Approximately 2-3 minutes (30 iterations with 0.5-second pauses)

**Outputs**:
- `evaluation_scripts/results/scenario_b_results_<timestamp>.csv` - Timing data
- `evaluation_scripts/results/scenario_b_results_<timestamp>.json` - Detailed results
- `evaluation_scripts/results/scenario_b_metadata_<timestamp>.json` - Experiment metadata

**Mapping to thesis tables**:
- **Table 5.5**: Use CSV file to compute mean, std dev, min, max, median
- **Table 5.6**: Use `direct_invocation_ms` as baseline for overhead decomposition

### Scenario C: Security Enforcement Validation

**Purpose**: Validates that the Slice Manager correctly enforces access control using CAPIF-issued JWTs.

**Test cases**:
1. Valid JWT → Expected: 202 Accepted
2. Invalid/malformed JWT → Expected: 401 Unauthorized
3. Expired JWT → Expected: 401 Unauthorized
4. Missing Authorization header → Expected: 401 Unauthorized

**Run the script**:

```bash
python3 evaluation_scripts/scenario_c_security.py
```

**Duration**: Approximately 5-7 minutes (20 total tests: 5 iterations × 4 test cases)

**Outputs**:
- `evaluation_scripts/results/scenario_c_results_<timestamp>.csv` - Test results
- `evaluation_scripts/results/scenario_c_results_<timestamp>.json` - Detailed results
- `evaluation_scripts/results/scenario_c_metadata_<timestamp>.json` - Test metadata and success rates

**Mapping to thesis tables**:
- **Table 5.7**: Use CSV/JSON to populate observed response codes and success rates for each test case

## Output Files

### CSV Files

CSV files contain the raw data suitable for statistical analysis and import into spreadsheet applications:

- **Scenario A CSV columns**: `run_id`, `onboarding_ms`, `discovery_ms`, `security_context_ms`, `token_acquisition_ms`, `protected_invocation_ms`, `total_ms`, `success`, `error_message`, `timestamp`, `invoker_id`, `service_api_id`, `token_metadata`

- **Scenario B CSV columns**: `run_id`, `direct_invocation_ms`, `success`, `error_message`, `timestamp`, `http_status_code`

- **Scenario C CSV columns**: `run_id`, `test_case`, `expected_response`, `observed_response`, `success`, `operation_executed`, `response_time_ms`, `error_message`, `timestamp`

### JSON Files

JSON files contain the same data as CSV but with richer structure and formatting. They are useful for:
- Programmatic analysis with Python/JavaScript
- Archiving complete experimental runs
- Debugging failed runs

### Metadata Files

Metadata files contain:
- Experiment configuration
- CAPIF identifiers (invoker ID, service API ID)
- Success/failure counts
- Test case descriptions
- Sample data for reference

## Data Analysis

### Computing Statistics

All scripts print summary statistics to the console after execution. To recompute statistics from saved CSV files:

```python
import pandas as pd

# Load results
df = pd.read_csv('evaluation_scripts/results/scenario_a_results_<timestamp>.csv')

# Filter successful runs
successful = df[df['success'] == True]

# Compute statistics
print(successful['total_ms'].describe())
```

### Overhead Calculation (Table 5.6)

To compute the overhead introduced by CAPIF:

```python
import pandas as pd

# Load both scenarios
scenario_a = pd.read_csv('evaluation_scripts/results/scenario_a_results_<timestamp>.csv')
scenario_b = pd.read_csv('evaluation_scripts/results/scenario_b_results_<timestamp>.csv')

# Filter successful runs
a_success = scenario_a[scenario_a['success'] == True]
b_success = scenario_b[scenario_b['success'] == True]

# Lifecycle preparation overhead (Steps 6-8)
lifecycle_overhead = a_success[['onboarding_ms', 'discovery_ms', 'security_context_ms']].sum(axis=1)
print(f"Lifecycle overhead: {lifecycle_overhead.mean():.2f} ± {lifecycle_overhead.std():.2f} ms")

# Token acquisition overhead (Step 9)
token_overhead = a_success['token_acquisition_ms']
print(f"Token acquisition: {token_overhead.mean():.2f} ± {token_overhead.std():.2f} ms")

# Protected invocation vs baseline
protected_invocation = a_success['protected_invocation_ms']
direct_baseline = b_success['direct_invocation_ms']
invocation_overhead = protected_invocation.mean() - direct_baseline.mean()
print(f"Protected invocation overhead: {invocation_overhead:.2f} ms")

# Total overhead
total_overhead = a_success['total_ms'].mean() - direct_baseline.mean()
print(f"Total CAPIF overhead: {total_overhead:.2f} ms")
```

## Troubleshooting

### Script Fails with "Config file not found"

**Solution**: Ensure the CAPIF config file exists at the expected path:

```bash
ls -la invoker_impl/app/capif/invoker_config.json
```

If missing, create it with valid CAPIF credentials.

### Script Fails with "Connection refused"

**Solution**: Verify the Slice Manager is running and accessible:

```bash
curl -v http://localhost:8000/ran/bbus
```

Or for the testbed endpoint:

```bash
curl -v http://10.16.10.78:8000/ran/bbus
```

### CAPIF Onboarding Fails

**Solution**: 
1. Check OpenCAPIF is running and accessible
2. Verify CAPIF config file contains correct credentials
3. Check network connectivity to CAPIF endpoints
4. Review CAPIF logs for error details

### Script Times Out

**Solution**: 
1. Increase timeout values in the scripts (default: 10 seconds)
2. Check network latency between components
3. Verify Slice Manager is responding within reasonable time

### Low Success Rate in Results

**Solution**:
1. Review the `error_message` column in CSV outputs for failure patterns
2. Check for network instability or intermittent connectivity issues
3. Verify CAPIF token lifetime is sufficient for the test duration
4. Consider reducing the number of iterations or increasing pause duration

## Notes for Thesis Results Chapter

### Table 5.1: Overview of Evaluation Scenarios

Use the metadata files to populate:
- Valid runs: Count of `success == True` in CSV
- Evidence source: Reference the generated CSV/JSON file paths

### Table 5.3: Invoker Onboarding and Service Discovery

Extract from Scenario A metadata file:
- `invoker_id`: CAPIF API Invoker identifier
- `service_api_id`: Published Slice Manager service identifier
- Token metadata: Length and prefix (full token not saved for security)

### Table 5.4: Scenario A Per-Step Timing

Compute descriptive statistics from Scenario A CSV:
- Mean, Std Dev, Min, Max, Median for each step
- Use only successful runs (`success == True`)

### Table 5.5: Scenario B Direct Invocation Baseline

Compute descriptive statistics from Scenario B CSV:
- Mean, Std Dev, Min, Max, Median for `direct_invocation_ms`

### Table 5.6: Overhead Decomposition

Calculate from both Scenario A and B:
- Lifecycle preparation overhead: Sum of Steps 6-8
- Token acquisition overhead: Step 9
- Protected invocation overhead: Step 10 minus Scenario B baseline
- Total overhead: Scenario A total minus Scenario B

### Table 5.7: Security Enforcement Results

Extract from Scenario C CSV:
- Success rate per test case: `(sum(success) / count) × 100%`
- Observed response codes: `observed_response` column
- Operation executed: `operation_executed` column

### Figure 5.1: Per-Step Latency Distribution

Use Scenario A CSV to generate a bar chart or box plot showing:
- X-axis: Step names (Onboarding, Discovery, Security Context, Token Acquisition, Protected Invocation)
- Y-axis: Latency (ms)
- Error bars: Standard deviation or interquartile range

### Figure 5.2: CAPIF vs Direct Comparison

Use both Scenario A and B CSVs to generate a stacked bar chart:
- Bar 1: Direct baseline (Scenario B)
- Bar 2: CAPIF-enabled (Scenario A) broken into segments:
  - Lifecycle preparation (Steps 6-8)
  - Token acquisition (Step 9)
  - Protected invocation (Step 10)

## License

These evaluation scripts are part of the ITAV N-App project and follow the same license terms.

## Contact

For questions or issues related to these scripts, refer to the main project README or contact the project maintainers.
