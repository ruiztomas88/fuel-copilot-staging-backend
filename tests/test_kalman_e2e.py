"""
🧪 End-to-End Kalman Filter Testing with Real Database

Tests estimator.py v6.1.0 improvements against real fleet data:
- Sensor bias detection
- Adaptive R based on consistency
- Biodiesel correction
- Unified Q_L calculation (GPS + Voltage)

Usage:
    python test_kalman_e2e.py --truck CO0681 --days 7

Author: Fuel Copilot Team
Date: December 29, 2025
"""

import argparse
import logging
from datetime import datetime, timedelta

import mysql.connector
import pandas as pd

# Import our Kalman filter
from estimator import COMMON_CONFIG, FuelEstimator

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def connect_to_db():
    """Connect to local Wialon database"""
    try:
        # Use config module for credentials
        try:
            from config import get_local_db_config

            db_config = get_local_db_config()
            conn = mysql.connector.connect(**db_config)
        except ImportError:
            # Fallback to hardcoded (for testing)
            conn = mysql.connector.connect(
                host="localhost",
                user="root",
                password="",  # Empty password fallback
                database="fuel_copilot",
                charset="utf8mb4",
            )

        logger.info("✅ Connected to database")
        return conn
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
        return None


def fetch_truck_data(conn, truck_id: str, days: int = 7):
    """
    Fetch recent data for a truck from wialon_raw_data.

    Returns DataFrame with all sensors needed for Kalman testing.
    """
    start_date = datetime.now() - timedelta(days=days)

    query = """
    SELECT 
        timestamp,
        unit_id,
        fuel_lvl_pct,
        speed_mph,
        engine_load_pct AS rpm,
        total_fuel_used,
        GPS_satellites AS satellites,
        pwr_int AS voltage,
        altitude_m
    FROM wialon_raw_data
    WHERE unit_id = %s
      AND timestamp >= %s
      AND fuel_lvl_pct IS NOT NULL
    ORDER BY timestamp ASC
    """

    df = pd.read_sql(query, conn, params=(truck_id, start_date))
    logger.info(f"📊 Fetched {len(df)} data points for {truck_id} (last {days} days)")

    return df


def run_kalman_on_data(df: pd.DataFrame, truck_id: str, config: dict):
    """
    Run Kalman filter on historical data and collect results.

    Returns:
        DataFrame with Kalman estimates and diagnostics
    """
    if df.empty:
        logger.error("No data to process")
        return None

    # Initialize Kalman filter
    capacity_liters = 454.0  # 120 gallons typical
    kalman = FuelEstimator(
        truck_id=truck_id,
        capacity_liters=capacity_liters,
        config=config,
        tanks_config=None,
    )

    results = []
    last_timestamp = None

    for idx, row in df.iterrows():
        timestamp = row["timestamp"]
        fuel_pct = row["fuel_lvl_pct"]
        speed = row["speed_mph"]
        rpm = row.get("rpm", 0)
        total_fuel = row.get("total_fuel_used")
        satellites = row.get("satellites")
        voltage = row.get("voltage")

        # Initialize on first reading
        if not kalman.initialized:
            kalman.initialize(fuel_lvl_pct=fuel_pct)
            last_timestamp = timestamp
            continue

        # Calculate time delta
        dt_hours = (timestamp - last_timestamp).total_seconds() / 3600.0

        if dt_hours > 4.0:
            logger.warning(f"Large gap: {dt_hours:.1f}h at {timestamp}")

        # Update sensor quality (GPS + voltage)
        if satellites is not None or voltage is not None:
            kalman.update_sensor_quality(
                satellites=satellites, voltage=voltage, is_engine_running=(rpm > 0)
            )

        # Update adaptive Q_r
        kalman.update_adaptive_Q_r(
            speed=speed, rpm=rpm, consumption_lph=None  # Will be calculated by ECU
        )

        # Calculate ECU consumption
        consumption_lph = kalman.calculate_ecu_consumption(
            total_fuel_used=total_fuel, dt_hours=dt_hours
        )

        # Predict
        kalman.predict(
            dt_hours=dt_hours, consumption_lph=consumption_lph, speed_mph=speed, rpm=rpm
        )

        # Update with measurement
        kalman.update(fuel_pct)

        # Collect results
        estimate = kalman.get_estimate()
        results.append(
            {
                "timestamp": timestamp,
                "sensor_pct": fuel_pct,
                "kalman_pct": estimate["level_pct"],
                "drift_pct": estimate["drift_pct"],
                "consumption_lph": estimate["consumption_lph"],
                "kalman_gain": estimate["kalman_gain"],
                "current_Q_L": estimate["current_Q_L"],
                "confidence": estimate["kalman_confidence"]["level"],
                "confidence_score": estimate["kalman_confidence"]["score"],
                "sensor_quality": estimate["sensor_quality_factor"],
                "bias_detected": estimate.get("bias_detected", False),
                "bias_magnitude": estimate.get("bias_magnitude_pct", 0.0),
                "gps_quality": estimate.get("gps_quality", "UNKNOWN"),
                "satellites": satellites,
                "voltage": voltage,
            }
        )

        last_timestamp = timestamp

    results_df = pd.DataFrame(results)
    logger.info(f"✅ Kalman filter processed {len(results)} updates")

    return results_df


def analyze_results(results_df: pd.DataFrame):
    """
    Analyze Kalman filter performance.

    Metrics:
    - MAE (Mean Absolute Error)
    - RMSE (Root Mean Squared Error)
    - Bias detection frequency
    - Confidence distribution
    """
    print("\n" + "=" * 80)
    print("📊 KALMAN FILTER PERFORMANCE ANALYSIS")
    print("=" * 80)

    # Error metrics
    errors = results_df["drift_pct"].abs()
    mae = errors.mean()
    rmse = (errors**2).mean() ** 0.5
    max_error = errors.max()

    print(f"\n📈 Error Metrics:")
    print(f"   MAE:  {mae:.2f}%")
    print(f"   RMSE: {rmse:.2f}%")
    print(f"   Max:  {max_error:.2f}%")

    # Bias detection stats
    bias_count = results_df["bias_detected"].sum()
    bias_pct = (bias_count / len(results_df)) * 100

    print(f"\n🔴 Bias Detection:")
    print(f"   Detected: {bias_count} times ({bias_pct:.1f}%)")
    if bias_count > 0:
        avg_bias = results_df[results_df["bias_detected"]]["bias_magnitude"].mean()
        print(f"   Avg Magnitude: {avg_bias:.2f}%")

    # Confidence distribution
    print(f"\n📊 Confidence Distribution:")
    conf_counts = results_df["confidence"].value_counts()
    for level in ["HIGH", "MEDIUM", "LOW", "VERY_LOW"]:
        count = conf_counts.get(level, 0)
        pct = (count / len(results_df)) * 100
        print(f"   {level:10s}: {count:4d} ({pct:5.1f}%)")

    # Sensor quality
    avg_quality = results_df["sensor_quality"].mean()
    print(f"\n📡 Sensor Quality:")
    print(f"   Average: {avg_quality:.2f} (0.5-1.0)")

    # GPS stats
    if "satellites" in results_df.columns:
        avg_sats = results_df["satellites"].dropna().mean()
        print(f"   Avg GPS Satellites: {avg_sats:.1f}")

    # Voltage stats
    if "voltage" in results_df.columns:
        avg_voltage = results_df["voltage"].dropna().mean()
        print(f"   Avg Voltage: {avg_voltage:.1f}V")

    # Sample predictions
    print(f"\n📋 Sample Predictions (first 5):")
    print(
        f"{'Timestamp':<20} {'Sensor':<8} {'Kalman':<8} {'Drift':<8} {'Confidence':<10}"
    )
    print("-" * 70)

    for _, row in results_df.head().iterrows():
        ts = row["timestamp"].strftime("%Y-%m-%d %H:%M")
        sensor = row["sensor_pct"]
        kalman = row["kalman_pct"]
        drift = row["drift_pct"]
        conf = row["confidence"]

        print(f"{ts:<20} {sensor:<8.2f} {kalman:<8.2f} {drift:<8.2f} {conf:<10}")

    print("=" * 80)

    # Validation checks
    print(f"\n✅ Validation Checks:")

    if mae < 2.0:
        print(f"   ✅ MAE < 2%: {mae:.2f}% (EXCELLENT)")
    elif mae < 5.0:
        print(f"   ✅ MAE < 5%: {mae:.2f}% (GOOD)")
    else:
        print(f"   ⚠️ MAE > 5%: {mae:.2f}% (NEEDS TUNING)")

    if bias_pct < 1.0:
        print(f"   ✅ Bias detection < 1%: {bias_pct:.2f}% (HEALTHY)")
    elif bias_pct < 5.0:
        print(f"   ⚠️ Bias detection < 5%: {bias_pct:.2f}% (ACCEPTABLE)")
    else:
        print(f"   🔴 Bias detection > 5%: {bias_pct:.2f}% (SENSOR ISSUES)")

    high_conf_pct = (conf_counts.get("HIGH", 0) / len(results_df)) * 100
    if high_conf_pct > 60:
        print(f"   ✅ High confidence > 60%: {high_conf_pct:.1f}% (EXCELLENT)")
    elif high_conf_pct > 40:
        print(f"   ✅ High confidence > 40%: {high_conf_pct:.1f}% (GOOD)")
    else:
        print(f"   ⚠️ High confidence < 40%: {high_conf_pct:.1f}% (LOW)")

    print("\n" + "=" * 80)

    return {
        "mae": mae,
        "rmse": rmse,
        "max_error": max_error,
        "bias_count": bias_count,
        "bias_pct": bias_pct,
        "high_conf_pct": high_conf_pct,
        "avg_quality": avg_quality,
    }


def main():
    parser = argparse.ArgumentParser(
        description="End-to-end test of Kalman filter v6.1.0 with real database"
    )
    parser.add_argument(
        "--truck", type=str, default="CO0681", help="Truck ID to test (default: CO0681)"
    )
    parser.add_argument(
        "--days", type=int, default=7, help="Days of historical data (default: 7)"
    )
    parser.add_argument(
        "--biodiesel",
        type=float,
        default=0.0,
        help="Biodiesel blend percentage (0, 5, 10, 20)",
    )

    args = parser.parse_args()

    # Connect to database
    conn = connect_to_db()
    if not conn:
        return 1

    # Fetch data
    df = fetch_truck_data(conn, args.truck, args.days)
    if df.empty:
        logger.error(f"No data found for truck {args.truck}")
        conn.close()
        return 1

    # Configure Kalman filter
    config = COMMON_CONFIG.copy()
    config["biodiesel_blend_pct"] = args.biodiesel

    logger.info(f"🔧 Configuration:")
    logger.info(f"   Truck: {args.truck}")
    logger.info(f"   Data period: {args.days} days")
    logger.info(f"   Biodiesel: {args.biodiesel}%")
    logger.info(f"   Q_r: {config['Q_r']}")
    logger.info(f"   Q_L_moving: {config['Q_L_moving']}")
    logger.info(f"   Q_L_static: {config['Q_L_static']}")

    # Run Kalman filter
    results_df = run_kalman_on_data(df, args.truck, config)

    if results_df is None or results_df.empty:
        logger.error("Kalman filter failed to produce results")
        conn.close()
        return 1

    # Analyze results
    metrics = analyze_results(results_df)

    # Save results
    output_file = (
        f"data/kalman_test_{args.truck}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    )
    results_df.to_csv(output_file, index=False)
    logger.info(f"💾 Results saved to: {output_file}")

    conn.close()

    # Final verdict
    print(f"\n🎯 FINAL VERDICT:")
    if (
        metrics["mae"] < 2.0
        and metrics["bias_pct"] < 1.0
        and metrics["high_conf_pct"] > 60
    ):
        print(f"   ✅ EXCELLENT - Kalman v6.1.0 performing optimally")
        return 0
    elif metrics["mae"] < 5.0 and metrics["bias_pct"] < 5.0:
        print(f"   ✅ GOOD - Performance acceptable, minor tuning recommended")
        return 0
    else:
        print(f"   ⚠️ NEEDS TUNING - Review configuration and sensor quality")
        return 1


if __name__ == "__main__":
    exit(main())
