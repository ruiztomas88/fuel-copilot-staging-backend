# Fuel Copilot Test Suite

**Version**: v3.0.2-DEFENSIVE  
**Test Framework**: pytest  

## Overview

This test suite validates the defensive improvements implemented in v3.0.2-DEFENSIVE:
- ✅ Fuel rate validation (physical ranges)
- ✅ Idle fallback (2 LPH when no sensor)
- ✅ MPG-based estimation (5 MPG city, 6.5 MPG highway)
- ✅ Anchor mechanisms (static/micro)
- ✅ Edge case handling (gaps, spikes, negatives)

## Test Structure

```
tests/
├── fixtures/              # JSON scenario data (10 files)
│   ├── idle_scenario.json
│   ├── city_scenario.json
│   ├── highway_scenario.json
│   ├── fuel_rate_spike.json
│   ├── fuel_rate_negative.json
│   ├── no_sensor.json
│   ├── static_anchor.json
│   ├── micro_anchor.json
│   ├── refuel_event.json
│   └── long_gap.json
├── test_fuel_estimator.py # Unit tests (20+ tests)
├── test_scenarios.py      # Integration tests (10 scenarios)
├── README_TESTS.md        # This file
└── requirements-test.txt  # Test dependencies
```

## Setup

1. **Install test dependencies**:
   ```bash
   pip install -r tests/requirements-test.txt
   ```

2. **Verify installation**:
   ```bash
   pytest --version
   ```

## Running Tests

### Run all tests
```bash
cd "/Users/tomasruiz/Desktop/Fuel Copilot"
pytest tests/ -v
```

### Run specific test file
```bash
pytest tests/test_fuel_estimator.py -v
pytest tests/test_scenarios.py -v
```

### Run specific test function
```bash
pytest tests/test_fuel_estimator.py::test_idle_fallback_no_sensor -v
```

### Run with detailed output
```bash
pytest tests/ -v --tb=short --disable-warnings
```

### Quick test (stop on first failure)
```bash
./run_tests.sh
```

## Test Categories

### Unit Tests (test_fuel_estimator.py)

**1. Idle Fallback (2 tests)**
- `test_idle_fallback_no_sensor()` - No sensor → 2 LPH
- `test_idle_fallback_invalid_sensor()` - Invalid sensor → 2 LPH

**2. City Driving (2 tests)**
- `test_city_valid_rate()` - Valid 18 LPH @ 30 mph
- `test_city_mpg_fallback()` - No sensor → MPG estimate (~15 LPH)

**3. Highway Driving (2 tests)**
- `test_highway_valid_rate()` - Valid 30 LPH @ 65 mph
- `test_highway_mpg_fallback()` - No sensor → MPG estimate (~20 LPH)

**4. Invalid Sensor Rejection (3 tests)**
- `test_reject_spike()` - 200 LPH rejected
- `test_reject_negative()` - -5 LPH rejected
- `test_reject_unrealistic()` - 50 LPH @ 30 mph rejected

**5. MPG Estimation (2 tests)**
- `test_mpg_city_estimate()` - 5 MPG baseline
- `test_mpg_highway_estimate()` - 6.5 MPG baseline

**6. Anchor Mechanisms (2 tests)**
- `test_static_anchor()` - 0 mph idle
- `test_micro_anchor()` - Stable cruise

**7. Gap Handling (2 tests)**
- `test_gap_rejection()` - 2+ hour gap skipped
- `test_normal_gap()` - 5 min gap processed

**8. Edge Cases (3 tests)**
- `test_zero_speed_consumption()` - Idle consumption
- `test_sequential_fallback()` - Sensor → MPG → Previous
- `test_boundary_speed()` - City/Highway threshold

### Integration Tests (test_scenarios.py)

**1. Scenario Tests (10 tests)**
- `test_idle_scenario()` - Multiple idle ticks
- `test_city_scenario()` - City driving sequence
- `test_highway_scenario()` - Highway driving sequence
- `test_fuel_rate_spike_scenario()` - Spike rejection
- `test_fuel_rate_negative_scenario()` - Negative rejection
- `test_no_sensor_scenario()` - MPG fallback
- `test_static_anchor_scenario()` - Stopped conditions
- `test_micro_anchor_scenario()` - Cruise conditions
- `test_long_gap_scenario()` - Gap handling
- `test_full_day_simulation()` - Mixed driving

## Expected Results

All tests should pass with output like:
```
tests/test_fuel_estimator.py::test_idle_fallback_no_sensor PASSED
tests/test_fuel_estimator.py::test_city_valid_rate PASSED
...
tests/test_scenarios.py::test_full_day_simulation PASSED

======================== 30 passed in 0.45s ========================
```

## Troubleshooting

### ModuleNotFoundError: No module named 'pytest'
```bash
pip install pytest
```

### Import errors for FuelEstimator
- Ensure `fuel_copilot_v2_1_fixed.py` is in workspace root
- Tests use `sys.path.insert()` to find parent module

### Assertion failures
- Review logs in test output
- Check if v3.0.2-DEFENSIVE implementation matches expectations
- Verify fixture data is correct

### Type warnings (est.L could be None)
- These are Pylance warnings, not runtime errors
- Tests ensure initialization before assertions
- Can be ignored if tests pass

## Fixtures Documentation

Each JSON fixture contains an array of tick parameters:

**Format**:
```json
[
  {
    "dt_hours": 0.0166667,  // 1 minute
    "rate_lph": 18.0,        // Fuel rate (or null)
    "speed_mph": 30.0        // Speed in MPH
  }
]
```

**Scenarios**:
- **idle_scenario**: Bad sensors, low speed (<5 mph) → should use 2 LPH fallback
- **city_scenario**: Valid 18-22 LPH @ 28-32 mph → accept sensor
- **highway_scenario**: Valid 28-32 LPH @ 63-67 mph → accept sensor
- **fuel_rate_spike**: 120-200 LPH → reject as physically impossible
- **fuel_rate_negative**: -5 to -3 LPH → reject negative rates
- **no_sensor**: null rate_lph @ 40-50 mph → use MPG estimate
- **static_anchor**: 0 mph → idle consumption only
- **micro_anchor**: Stable cruise 60 mph → steady consumption
- **refuel_event**: 30%→70% jump → detect refuel (not tested in current suite)
- **long_gap**: First tick has 2.5 hour gap → skip consumption

## Continuous Integration

To run tests automatically:

**GitHub Actions** (example):
```yaml
- name: Run Tests
  run: |
    pip install -r tests/requirements-test.txt
    pytest tests/ -v --maxfail=1
```

**Pre-commit Hook**:
```bash
#!/bin/bash
pytest tests/ -q || exit 1
```

## Coverage Analysis

To generate coverage report:
```bash
pip install pytest-cov
pytest tests/ --cov=fuel_copilot_v2_1_fixed --cov-report=html
open htmlcov/index.html
```

## Contributing

When adding new features:
1. Add corresponding test fixtures if needed
2. Write unit tests for new functions
3. Add integration tests for workflows
4. Update this README with new test descriptions
5. Ensure all tests pass before committing

## Version History

- **v3.0.2-DEFENSIVE**: Initial test suite creation
  - 20+ unit tests
  - 10 integration scenarios
  - Full fixture library

## Contact

For test failures or questions, review:
- `CODE_DOCUMENTATION.md` - Implementation details
- `README.md` - System overview
- Test logs and assertion messages
