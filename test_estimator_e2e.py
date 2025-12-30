"""
End-to-End Test for Kalman Filter v6.1.0 with Real Database Data

Tests:
1. ✅ Innovation history bias detection
2. ✅ Adaptive R v2 (consistency-based)
3. ✅ Biodiesel blend correction
4. ✅ Data quality health checks
5. ✅ Integration with real Wialon data

Author: Fuel Copilot Team
Version: 1.0.0
Date: December 29, 2025
"""

import logging
import sys
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

import mysql.connector
import numpy as np

from estimator import EstimatorConfig, FuelEstimator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# DATABASE CONNECTION
# ═══════════════════════════════════════════════════════════════════════════════


def get_db_connection():
    """Connect to local MySQL database using production config"""
    try:
        # Use same config as wialon_sync_enhanced.py
        from config import get_local_db_config
        db_config = get_local_db_config()
        
        conn = mysql.connector.connect(
            host=db_config.get("host", "localhost"),
            port=db_config.get("port", 3306),
            user=db_config.get("user", "root"),
            password=db_config.get("password", ""),
            database=db_config.get("database", "fuel_copilot"),
            charset="utf8mb4",
            collation="utf8mb4_unicode_ci",
        )
        logger.info(f"✅ Connected to database: {db_config['database']}")
        return conn
    except mysql.connector.Error as err:
        logger.error(f"❌ Database connection failed: {err}")
        logger.info("💡 Make sure MySQL is running and credentials are correct")
        sys.exit(1)


def fetch_test_data(
    conn, truck_id: str, hours_back: int = 24, limit: int = 1000
) -> List[Dict]:
    """
    Fetch real sensor data from fuel_metrics (historical data with Kalman estimates)
    
    Args:
        conn: Database connection
        truck_id: Truck ID to fetch data for (or None for any active truck)
        hours_back: How many hours of historical data to fetch
        limit: Max number of records
    
    Returns:
        List of sensor readings sorted by timestamp
    """
    cursor = conn.cursor(dictionary=True)
    
    # If no truck_id specified, find most active truck
    if truck_id is None:
        active_query = """
            SELECT truck_id, COUNT(*) as records
            FROM fuel_metrics
            WHERE timestamp_utc >= DATE_SUB(NOW(), INTERVAL %s HOUR)
            GROUP BY truck_id
            ORDER BY records DESC
            LIMIT 1
        """
        cursor.execute(active_query, (hours_back,))
        result = cursor.fetchone()
        if result:
            truck_id = result["truck_id"]
            logger.info(f"Auto-selected truck {truck_id} with {result['records']} records")
        else:
            logger.error("No active trucks found in database")
            cursor.close()
            return []
    
    # Fetch recent data for this truck
    query = """
        SELECT 
            timestamp_utc as timestamp,
            truck_id,
            sensor_pct as fuel_lvl_pct,
            speed_mph,
            rpm,
            engine_hours,
            engine_load_pct,
            altitude_ft,
            hdop,
            battery_voltage as voltage
        FROM fuel_metrics
        WHERE truck_id = %s
        AND timestamp_utc >= DATE_SUB(NOW(), INTERVAL %s HOUR)
        AND sensor_pct IS NOT NULL
        ORDER BY timestamp_utc ASC
        LIMIT %s
    """
    
    cursor.execute(query, (truck_id, hours_back, limit))
    data = cursor.fetchall()
    cursor.close()
    
    # Convert altitude to meters and add calculated total_fuel_used
    for row in data:
        if row.get("altitude_ft"):
            row["altitude_m"] = row["altitude_ft"] * 0.3048
        row["satellites"] = 8  # Assume good GPS if we have data
        # Estimate total_fuel_used from engine_hours if available
        if row.get("engine_hours"):
            row["total_fuel_used_gal"] = row["engine_hours"] * 2.5  # rough estimate
    
    logger.info(f"✅ Fetched {len(data)} records for truck {truck_id}")
    return data


# ═══════════════════════════════════════════════════════════════════════════════
# DATA QUALITY HEALTH CHECKS
# ═══════════════════════════════════════════════════════════════════════════════


def validate_sensor_data(reading: Dict) -> Dict:
    """
    🆕 v6.1.0: Data quality health checks
    
    Validates sensor readings before passing to Kalman filter:
    - Fuel level in valid range (0-100%)
    - Speed reasonable (0-100 mph)
    - RPM reasonable (0-3000)
    - No NaN/Inf values
    
    Returns:
        Dict with is_valid flag and quality_score (0.0-1.0)
    """
    issues = []
    quality_score = 1.0
    
    # Check fuel level
    fuel = reading.get("fuel_lvl_pct")
    if fuel is None or np.isnan(fuel) or np.isinf(fuel):
        issues.append("fuel_null_or_invalid")
        quality_score -= 0.5
    elif fuel < 0 or fuel > 100:
        issues.append(f"fuel_out_of_range_{fuel:.1f}")
        quality_score -= 0.3
    
    # Check speed
    speed = reading.get("speed_mph")
    if speed is not None and (speed < 0 or speed > 100):
        issues.append(f"speed_unreasonable_{speed:.1f}")
        quality_score -= 0.1
    
    # Check RPM
    rpm = reading.get("rpm")
    if rpm is not None and (rpm < 0 or rpm > 3000):
        issues.append(f"rpm_unreasonable_{rpm:.0f}")
        quality_score -= 0.1
    
    # Check GPS satellites
    sats = reading.get("satellites")
    if sats is not None and sats < 4:
        issues.append(f"poor_gps_{sats}_sats")
        quality_score -= 0.1
    
    # Voltage check
    voltage = reading.get("voltage")
    if voltage is not None:
        if voltage < 11.0 or voltage > 15.0:
            issues.append(f"voltage_abnormal_{voltage:.1f}V")
            quality_score -= 0.1
    
    quality_score = max(0.0, quality_score)
    is_valid = quality_score >= 0.5  # Require at least 50% quality
    
    return {
        "is_valid": is_valid,
        "quality_score": quality_score,
        "issues": issues,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# KALMAN FILTER TESTING
# ═══════════════════════════════════════════════════════════════════════════════


def test_bias_detection(estimator: FuelEstimator, test_data: List[Dict]) -> Dict:
    """
    Test 1: Innovation history bias detection
    
    Inject persistent positive bias and verify R multiplier increases
    """
    logger.info("\n" + "=" * 80)
    logger.info("TEST 1: Sensor Bias Detection")
    logger.info("=" * 80)
    
    # Take first 10 readings and add +5% bias
    biased_data = test_data[:10]
    bias_detected = False
    r_multipliers = []
    
    for i, reading in enumerate(biased_data):
        # Initialize on first reading
        if i == 0:
            estimator.initialize(fuel_lvl_pct=reading["fuel_lvl_pct"])
            continue
        
        # Inject +5% bias to simulate faulty sensor
        biased_fuel = reading["fuel_lvl_pct"] + 5.0
        
        # Predict step (assume 0.1 hour between readings)
        estimator.predict(
            dt_hours=0.1,
            consumption_lph=5.0,
            speed_mph=reading.get("speed_mph"),
            rpm=reading.get("rpm"),
        )
        
        # Update step
        estimator.update(biased_fuel)
        
        # Check R multiplier after 4+ measurements
        if len(estimator.innovation_history) >= 4:
            r_mult = estimator._adaptive_measurement_noise_v2()
            r_multipliers.append(r_mult)
            
            if r_mult > 2.0:
                bias_detected = True
                logger.info(
                    f"  ✅ Reading {i+1}: Bias detected! R multiplier = {r_mult:.2f}"
                )
            else:
                logger.info(f"  ⚠️  Reading {i+1}: No bias yet, R mult = {r_mult:.2f}")
    
    avg_r_mult = np.mean(r_multipliers) if r_multipliers else 1.0
    
    result = {
        "test_name": "Bias Detection",
        "passed": bias_detected,
        "avg_r_multiplier": avg_r_mult,
        "expected_r_multiplier": ">2.0",
        "innovation_history": list(estimator.innovation_history),
    }
    
    logger.info(f"\n{'✅ PASSED' if bias_detected else '❌ FAILED'}: Bias detection")
    logger.info(f"Average R multiplier: {avg_r_mult:.2f} (expected >2.0)")
    
    return result


def test_biodiesel_correction(test_data: List[Dict]) -> Dict:
    """
    Test 2: Biodiesel blend correction
    
    Compare estimates with B0 vs B20 blend
    """
    logger.info("\n" + "=" * 80)
    logger.info("TEST 2: Biodiesel Blend Correction")
    logger.info("=" * 80)
    
    # Test with B0 (pure diesel)
    config_b0 = {"biodiesel_blend_pct": 0.0}
    est_b0 = FuelEstimator(
        truck_id="TEST_B0",
        capacity_liters=300.0,
        config=config_b0,
    )
    
    # Test with B20 (20% biodiesel)
    config_b20 = {"biodiesel_blend_pct": 20.0}
    est_b20 = FuelEstimator(
        truck_id="TEST_B20",
        capacity_liters=300.0,
        config=config_b20,
    )
    
    # Process 5 readings
    sample_data = test_data[:5]
    
    for i, reading in enumerate(sample_data):
        if i == 0:
            est_b0.initialize(fuel_lvl_pct=reading["fuel_lvl_pct"])
            est_b20.initialize(fuel_lvl_pct=reading["fuel_lvl_pct"])
            continue
        
        # Both predict same consumption
        for est in [est_b0, est_b20]:
            est.predict(dt_hours=0.1, consumption_lph=5.0)
            est.update(reading["fuel_lvl_pct"])
    
    # B20 should show slightly higher fuel level due to density correction
    diff_pct = est_b20.level_pct - est_b0.level_pct
    expected_diff = 0.5  # ~2.4% density difference over multiple readings
    
    passed = abs(diff_pct) > expected_diff
    
    result = {
        "test_name": "Biodiesel Correction",
        "passed": passed,
        "b0_level_pct": est_b0.level_pct,
        "b20_level_pct": est_b20.level_pct,
        "difference_pct": diff_pct,
        "expected_difference": f">{expected_diff}%",
    }
    
    logger.info(f"B0 (pure diesel):  {est_b0.level_pct:.2f}%")
    logger.info(f"B20 (20% bio):     {est_b20.level_pct:.2f}%")
    logger.info(f"Difference:        {diff_pct:.2f}%")
    logger.info(f"{'✅ PASSED' if passed else '❌ FAILED'}: Biodiesel correction")
    
    return result


def test_data_quality_validation(test_data: List[Dict]) -> Dict:
    """
    Test 3: Data quality health checks
    
    Validate sensor data quality checks are working
    """
    logger.info("\n" + "=" * 80)
    logger.info("TEST 3: Data Quality Health Checks")
    logger.info("=" * 80)
    
    valid_count = 0
    invalid_count = 0
    quality_scores = []
    issues_summary = {}
    
    for reading in test_data[:50]:  # Check first 50 readings
        validation = validate_sensor_data(reading)
        
        if validation["is_valid"]:
            valid_count += 1
        else:
            invalid_count += 1
        
        quality_scores.append(validation["quality_score"])
        
        # Track issue types
        for issue in validation["issues"]:
            issues_summary[issue] = issues_summary.get(issue, 0) + 1
    
    avg_quality = np.mean(quality_scores)
    passed = valid_count > invalid_count  # Most data should be valid
    
    result = {
        "test_name": "Data Quality Validation",
        "passed": passed,
        "valid_readings": valid_count,
        "invalid_readings": invalid_count,
        "avg_quality_score": avg_quality,
        "issues_summary": issues_summary,
    }
    
    logger.info(f"Valid readings:    {valid_count}/{len(test_data[:50])}")
    logger.info(f"Invalid readings:  {invalid_count}/{len(test_data[:50])}")
    logger.info(f"Avg quality score: {avg_quality:.2f}")
    logger.info(f"Issues found:      {issues_summary}")
    logger.info(f"{'✅ PASSED' if passed else '❌ FAILED'}: Data quality checks")
    
    return result


def test_full_integration(test_data: List[Dict], truck_capacity: float = 300.0) -> Dict:
    """
    Test 4: Full integration with real data
    
    Run complete Kalman filter pipeline with all v6.1.0 features
    """
    logger.info("\n" + "=" * 80)
    logger.info("TEST 4: Full Integration with Real Data")
    logger.info("=" * 80)
    
    config = {
        "biodiesel_blend_pct": 5.0,  # B5 blend
        "Q_r": 0.05,
        "Q_L_moving": 2.5,
        "Q_L_static": 1.0,
    }
    
    estimator = FuelEstimator(
        truck_id=test_data[0]["truck_id"],
        capacity_liters=truck_capacity,
        config=config,
    )
    
    valid_updates = 0
    skipped_updates = 0
    max_drift = 0.0
    drift_history = []
    
    last_timestamp = None
    
    for i, reading in enumerate(test_data):
        # Validate data quality
        validation = validate_sensor_data(reading)
        if not validation["is_valid"]:
            skipped_updates += 1
            continue
        
        # Initialize on first valid reading
        if not estimator.initialized:
            estimator.initialize(fuel_lvl_pct=reading["fuel_lvl_pct"])
            last_timestamp = reading["timestamp"]
            continue
        
        # Calculate time delta
        current_timestamp = reading["timestamp"]
        dt_hours = (current_timestamp - last_timestamp).total_seconds() / 3600.0
        last_timestamp = current_timestamp
        
        # Update adaptive Q_r
        estimator.update_adaptive_Q_r(
            speed=reading.get("speed_mph"),
            rpm=reading.get("rpm"),
            consumption_lph=5.0,  # Estimate
        )
        
        # Update sensor quality (GPS + voltage)
        estimator.update_sensor_quality(
            satellites=reading.get("satellites"),
            voltage=reading.get("voltage"),
            is_engine_running=(reading.get("rpm", 0) > 100),
        )
        
        # Predict step
        ecu_consumption = estimator.calculate_ecu_consumption(
            total_fuel_used=reading.get("total_fuel_used_gal"),
            dt_hours=dt_hours,
        )
        
        estimator.predict(
            dt_hours=dt_hours,
            consumption_lph=ecu_consumption or 5.0,
            speed_mph=reading.get("speed_mph"),
            rpm=reading.get("rpm"),
        )
        
        # Update step
        estimator.update(reading["fuel_lvl_pct"])
        
        valid_updates += 1
        
        # Track drift
        drift = abs(estimator.drift_pct)
        drift_history.append(drift)
        max_drift = max(max_drift, drift)
        
        if i % 50 == 0:
            estimate = estimator.get_estimate()
            logger.info(
                f"  Reading {i+1}: "
                f"Estimate={estimate['level_pct']:.1f}%, "
                f"Sensor={reading['fuel_lvl_pct']:.1f}%, "
                f"Drift={drift:.1f}%, "
                f"Q_L={estimate['current_Q_L']:.2f}, "
                f"Confidence={estimate['kalman_confidence']['level']}"
            )
    
    avg_drift = np.mean(drift_history)
    passed = avg_drift < 3.0 and max_drift < 10.0  # Reasonable drift thresholds
    
    final_estimate = estimator.get_estimate()
    
    result = {
        "test_name": "Full Integration",
        "passed": passed,
        "valid_updates": valid_updates,
        "skipped_updates": skipped_updates,
        "avg_drift_pct": avg_drift,
        "max_drift_pct": max_drift,
        "final_estimate": final_estimate,
    }
    
    logger.info(f"\nProcessed {valid_updates} valid readings")
    logger.info(f"Skipped {skipped_updates} invalid readings")
    logger.info(f"Average drift: {avg_drift:.2f}%")
    logger.info(f"Max drift:     {max_drift:.2f}%")
    logger.info(f"Final confidence: {final_estimate['kalman_confidence']['level']}")
    logger.info(f"{'✅ PASSED' if passed else '❌ FAILED'}: Full integration test")
    
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN TEST RUNNER
# ═══════════════════════════════════════════════════════════════════════════════


def main():
    """Run all end-to-end tests"""
    logger.info("╔" + "=" * 78 + "╗")
    logger.info("║" + " " * 20 + "KALMAN FILTER v6.1.0 E2E TESTS" + " " * 28 + "║")
    logger.info("╚" + "=" * 78 + "╝")
    
    # Connect to database
    conn = get_db_connection()
    
    # Auto-select most active truck
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT truck_id
        FROM truck_sensors_cache
        ORDER BY last_updated DESC
        LIMIT 1
    """)
    result = cursor.fetchone()
    truck_id = result[", COUNT(*) as records
        FROM fuel_metrics
        WHERE timestamp_utc >= DATE_SUB(NOW(), INTERVAL 24 HOUR)
        GROUP BY truck_id
        ORDER BY records DESC
        LIMIT 1
    """)
    result = cursor.fetchone()
    truck_id = result["truck_id"] if result else "JP3281"
    cursor.close()
    
    logger.info(f"Testing with truck: {truck_id} ({result['records'] if result else 0} recent records)(only {len(test_data)} records)")
        logger.info("Try a different truck_id or increase hours_back")
        conn.close()
        sys.exit(1)
    
    # Run all tests
    results = []
    
    # Test 1: Bias detection
    estimator1 = FuelEstimator(
        truck_id=truck_id,
        capacity_liters=300.0,
        config={},
    )
    results.append(test_bias_detection(estimator1, test_data))
    
    # Test 2: Biodiesel correction
    results.append(test_biodiesel_correction(test_data))
    
    # Test 3: Data quality validation
    results.append(test_data_quality_validation(test_data))
    
    # Test 4: Full integration
    results.append(test_full_integration(test_data))
    
    # Summary
    logger.info("\n" + "╔" + "=" * 78 + "╗")
    logger.info("║" + " " * 32 + "TEST SUMMARY" + " " * 34 + "║")
    logger.info("╚" + "=" * 78 + "╝")
    
    passed_count = sum(1 for r in results if r["passed"])
    total_count = len(results)
    
    for result in results:
        status = "✅ PASSED" if result["passed"] else "❌ FAILED"
        logger.info(f"{status}: {result['test_name']}")
    
    logger.info(f"\n{'═' * 80}")
    logger.info(f"FINAL RESULT: {passed_count}/{total_count} tests passed")
    logger.info(f"{'═' * 80}")
    
    conn.close()
    
    # Exit with appropriate code
    sys.exit(0 if passed_count == total_count else 1)


if __name__ == "__main__":
    main()
