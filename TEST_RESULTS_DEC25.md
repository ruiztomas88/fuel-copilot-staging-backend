# Test Results - December 25, 2025

## Summary
- **Total test files**: 114
- **Total time**: 243 seconds (~4 minutes)
- **No hanging tests** ✅

## Critical Errors to Fix

### 1. Version Mismatches
- `test_fleet_command_center.py`: Expected 1.6.0, got 1.8.0
- `test_fleet_command_center_old.py`: Expected 1.3.0, got 1.8.0

### 2. Missing Enum Values
- `test_fleet_complete.py`: `IssueCategory.BRAKE` doesn't exist (should be `BRAKES`)
- `test_fleet_direct_execution.py`: `ActionType.SCHEDULE_URGENT` missing

### 3. API Endpoint Errors
- `test_http_endpoints_massive.py`: Truck detail endpoint returns 500
- `test_gps_notifications.py`: NaN values not JSON compliant
- DTC report endpoint 404 (FIXED)

### 4. ML/Prediction Errors
- `test_lstm_maintenance.py`: StandardScaler not fitted
- `test_ml_integration.py`: StandardScaler not fitted
- `test_ml_router.py`: 500 error on predict endpoint
- `test_predictive_complete.py`: MaintenancePrediction missing required args
- `test_predictive_engine_core.py`: MaintenancePrediction missing 'days_to_failure' attribute

### 5. Test Configuration Errors
- `test_mpg_baseline_service.py`: Percentile calculation mismatch (2.75 not in [2, 3])
- `test_mpg_baseline_v5_7_6.py`: Percentile 3.25 != 3
- `test_mpg_engine.py`: min_fuel_gal 1.5 != 0.75

### 6. Database/Repository Errors
- `test_truck_repository.py`: Module doesn't have 'get_pool' attribute
- `test_predictive_maintenance_simple.py`: Module doesn't have 'get_mysql_connection'

### 7. Wialon Integration
- `test_wialon_reader.py`: Sensor data parsing returns None
- `test_wialon_comprehensive.py`: DEF data loading returns empty

### 8. Router/Response Model Mismatches
- `test_routers_comprehensive.py`: Response validation error in trucks router

## Tests with Warnings (Non-Critical)
- Deprecation warnings for `datetime.utcnow()` (multiple files)
- NumPy deprecation warnings
- Pytest `regex` parameter deprecated

## Passing Test Suites ✅
- test_gamification_engine.py (73 passed)
- test_fleet_utilization_engine.py (78 passed)
- test_terrain_factor.py (80 passed)
- test_predictive_maintenance.py (89 passed)
- test_theft_detection.py (55 passed)
- test_truck_health_monitor.py (59 passed)
- test_v2_endpoints_integration.py (11 passed)
- And 50+ more with partial passes
