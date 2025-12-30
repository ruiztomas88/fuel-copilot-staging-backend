"""
🔬 Kalman Filter Consumption Calibration Tool

Auto-learns optimal consumption parameters from historical fleet data:
- baseline_consumption (idle/stationary fuel burn)
- load_factor (fuel increase per % engine load)
- altitude_factor (fuel increase per meter climbed)

These calibrated values replace the hardcoded estimates in your Kalman filter,
ensuring predictions match real-world truck behavior.

🆕 v2.0 Features:
- Stricter rate-of-consumption filters (max 2 gal/min, min 0.01 gal/min)
- Automatic data quality health check before calibration
- Prevents refuels from contaminating calibration data

Usage:
    python calibrate_kalman_consumption.py --days 30 --min-samples 100

Output:
    data/kalman_calibration.json - Calibrated parameters
    Recommended config to paste into your Kalman filter

Author: Fuel Copilot Team
Date: December 29, 2025
Version: 2.0 (Production-approved)
"""

import argparse
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import mysql.connector
import numpy as np
from scipy.optimize import minimize

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def check_data_quality(db_config: dict, days: int = 30) -> Optional[Dict]:
    """
    🆕 v2.0: Pre-flight data quality check before calibration.

    Validates:
    - Negative consumption % (sensor glitches)
    - Suspicious rate-of-consumption % (potential refuels)
    - Avg/stddev consumption (outlier detection)

    Args:
        db_config: Database configuration
        days: Days of data to check

    Returns:
        Quality metrics dict or None if data is too corrupted
    """
    logger.info("🔍 Running data quality health check...")

    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)

    start_date = datetime.now() - timedelta(days=days)

    query = """
    SELECT 
        COUNT(*) as total_samples,
        SUM(CASE WHEN fuel_consumed_gal < 0 THEN 1 ELSE 0 END) as negative_consumption,
        SUM(CASE WHEN fuel_consumed_gal > 50 THEN 1 ELSE 0 END) as refuels,
        SUM(CASE WHEN (fuel_consumed_gal / TIMESTAMPDIFF(MINUTE, prev_timestamp, timestamp)) > 2.0 
             THEN 1 ELSE 0 END) as suspicious_rate,
        AVG(fuel_consumed_gal) as avg_consumption,
        STDDEV(fuel_consumed_gal) as stddev_consumption
    FROM (
        SELECT 
            unit_id,
            timestamp,
            fuel_level_gal,
            LAG(fuel_level_gal) OVER (PARTITION BY unit_id ORDER BY timestamp) AS prev_fuel_level_gal,
            LAG(timestamp) OVER (PARTITION BY unit_id ORDER BY timestamp) AS prev_timestamp,
            CASE 
                WHEN LAG(fuel_level_gal) OVER (PARTITION BY unit_id ORDER BY timestamp) IS NOT NULL
                THEN LAG(fuel_level_gal) OVER (PARTITION BY unit_id ORDER BY timestamp) - fuel_level_gal
                ELSE 0
            END as fuel_consumed_gal
        FROM wialon_raw_data
        WHERE timestamp >= %s
          AND fuel_level_gal IS NOT NULL
    ) sub
    WHERE prev_fuel_level_gal IS NOT NULL
      AND TIMESTAMPDIFF(MINUTE, prev_timestamp, timestamp) BETWEEN 1 AND 60
    """

    cursor.execute(query, (start_date,))
    result = cursor.fetchone()
    cursor.close()
    conn.close()

    if not result or result["total_samples"] == 0:
        logger.error("❌ No data found for quality check")
        return None

    total = result["total_samples"]
    negative_pct = (result["negative_consumption"] / total) * 100
    refuel_pct = (result["refuels"] / total) * 100
    suspicious_pct = (result["suspicious_rate"] / total) * 100

    logger.info(f"\n📊 Data Quality Report ({days} days, {total:,} samples):")
    logger.info(
        f"   Negative consumption: {result['negative_consumption']:,} ({negative_pct:.2f}%)"
    )
    logger.info(f"   Refuels (>50 gal):    {result['refuels']:,} ({refuel_pct:.2f}%)")
    logger.info(
        f"   Suspicious rate:      {result['suspicious_rate']:,} ({suspicious_pct:.2f}%)"
    )
    logger.info(f"   Avg consumption:      {result['avg_consumption']:.2f} gal")
    logger.info(f"   Stddev:               {result['stddev_consumption']:.2f} gal\n")

    # Quality gates
    if negative_pct > 1.0:
        logger.error("❌ DATA CORRUPTION: >1% negative consumption detected!")
        logger.error("   Check sensor calibration and data ingestion pipeline")
        return None

    if suspicious_pct > 10.0:
        logger.warning(
            f"⚠️ HIGH SUSPICIOUS RATE: {suspicious_pct:.1f}% samples have rate > 2 gal/min"
        )
        logger.warning("   This may indicate refuels not properly filtered")

    logger.info("✅ Data quality acceptable for calibration\n")
    return result


class KalmanCalibrator:
    """
    Calibrates Kalman filter consumption model using historical fleet data.

    Mathematical Model:
        fuel_consumed = (baseline
                        + load_factor × engine_load
                        + altitude_factor × altitude_change) × time

    Goal: Find [baseline, load_factor, altitude_factor] that minimizes
          error between predicted and actual fuel consumption.

    🆕 v2.0: Enhanced with stricter filtering and data quality checks
    """

    def __init__(self, db_config: dict):
        self.db_config = db_config
        self.conn = None

    def connect(self):
        """Connect to MySQL database"""
        self.conn = mysql.connector.connect(**self.db_config)
        logger.info("✅ Connected to database")

    def disconnect(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            logger.info("🔌 Disconnected from database")

    def fetch_calibration_data(
        self, days: int = 30, min_samples: int = 100
    ) -> List[Dict]:
        """
        Fetch historical fuel consumption data for calibration.

        🆕 v2.0: Stricter filters
        - fuel_consumed < 10 gal (was 50 - prevents refuels)
        - rate < 2.0 gal/min (max consumption)
        - rate > 0.01 gal/min (min consumption - engine must be on)

        Args:
            days: Number of days of historical data
            min_samples: Minimum samples per truck to include

        Returns:
            List of dicts with calibration data
        """
        cursor = self.conn.cursor(dictionary=True)

        start_date = datetime.now() - timedelta(days=days)

        query = """
        SELECT 
            unit_id AS truck_id,
            
            -- Fuel consumed (gallons)
            fuel_consumed_gal,
            
            -- Time interval (minutes)
            TIMESTAMPDIFF(MINUTE, prev_timestamp, timestamp) AS time_minutes,
            
            -- Average engine load during interval
            (engine_load_pct + COALESCE(prev_engine_load_pct, engine_load_pct)) / 2 
                AS avg_engine_load_pct,
            
            -- Altitude change (meters)
            COALESCE(altitude_m - prev_altitude_m, 0) AS altitude_change_m,
            
            -- Movement status
            speed_mph > 5 AS is_moving
            
        FROM (
            SELECT 
                unit_id,
                timestamp,
                fuel_level_gal,
                LAG(fuel_level_gal) OVER (PARTITION BY unit_id ORDER BY timestamp) 
                    AS prev_fuel_level_gal,
                LAG(timestamp) OVER (PARTITION BY unit_id ORDER BY timestamp) 
                    AS prev_timestamp,
                engine_load_pct,
                LAG(engine_load_pct) OVER (PARTITION BY unit_id ORDER BY timestamp) 
                    AS prev_engine_load_pct,
                altitude_m,
                LAG(altitude_m) OVER (PARTITION BY unit_id ORDER BY timestamp) 
                    AS prev_altitude_m,
                speed_mph
            FROM wialon_raw_data
            WHERE timestamp >= %s
              AND fuel_level_gal IS NOT NULL
              AND engine_load_pct IS NOT NULL
        ) sub
        WHERE prev_fuel_level_gal IS NOT NULL
          AND fuel_consumed_gal > 0
          AND fuel_consumed_gal < 10                        -- 🔧 v2.0: Stricter (was 50)
          AND time_minutes BETWEEN 1 AND 60
          AND (fuel_consumed_gal / time_minutes) < 2.0      -- 🆕 v2.0: Max 2 gal/min
          AND (fuel_consumed_gal / time_minutes) > 0.01     -- 🆕 v2.0: Min 0.01 gal/min
          AND avg_engine_load_pct BETWEEN 0 AND 100
        ORDER BY truck_id, timestamp
        """

        cursor.execute(query, (start_date,))
        data = cursor.fetchall()
        cursor.close()

        logger.info(f"📊 Fetched {len(data)} calibration samples from last {days} days")

        # Calculate fuel_consumed_gal from deltas (if not already computed)
        for row in data:
            if "prev_fuel_level_gal" in row and row["fuel_consumed_gal"] is None:
                row["fuel_consumed_gal"] = row["prev_fuel_level_gal"] - row.get(
                    "fuel_level_gal", 0
                )

        # Filter trucks with enough samples
        truck_counts = {}
        for row in data:
            truck_id = row["truck_id"]
            truck_counts[truck_id] = truck_counts.get(truck_id, 0) + 1

        valid_trucks = {t for t, c in truck_counts.items() if c >= min_samples}
        filtered_data = [r for r in data if r["truck_id"] in valid_trucks]

        logger.info(f"✅ {len(valid_trucks)} trucks with ≥{min_samples} samples")
        logger.info(f"📈 Total calibration samples: {len(filtered_data)}")

        return filtered_data

    def separate_idle_moving(self, data: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
        """
        Separate data into idle and moving segments.

        Idle = speed < 5 mph, engine_load < 30%
        Moving = everything else
        """
        idle = []
        moving = []

        for row in data:
            if not row["is_moving"] and row["avg_engine_load_pct"] < 30:
                idle.append(row)
            else:
                moving.append(row)

        logger.info(f"🚦 Idle samples: {len(idle)}")
        logger.info(f"🚛 Moving samples: {len(moving)}")

        return idle, moving

    def calibrate_baseline_consumption(self, idle_data: List[Dict]) -> float:
        """
        Calibrate baseline consumption using idle data.

        Baseline = fuel consumed per minute when stationary.

        Method: Median of (fuel_consumed / time) for idle samples.
        """
        if not idle_data:
            logger.warning("⚠️ No idle data, using default baseline")
            return 0.01

        rates = []
        for row in idle_data:
            fuel_gal = row["fuel_consumed_gal"]
            time_min = row["time_minutes"]
            if time_min > 0:
                # Assuming 120 gal tank (adjust if needed)
                pct_per_min = (fuel_gal / 120.0) * 100.0 / time_min
                rates.append(pct_per_min)

        if not rates:
            return 0.01

        baseline = np.median(rates)

        logger.info(f"📊 Baseline consumption (idle): {baseline:.4f} %/min")
        logger.info(f"   = {baseline * 60:.2f} %/hour")
        logger.info(f"   = {baseline * 60 * 1.2:.2f} gal/hour (120 gal tank)")

        return baseline

    def optimize_consumption_model(
        self, moving_data: List[Dict], baseline_consumption: float
    ) -> Tuple[float, float]:
        """
        Optimize load_factor and altitude_factor using moving data.

        Model: fuel_rate = baseline + load_factor × load + altitude_factor × alt_change/dt

        Uses scipy.optimize.minimize to find factors that minimize RMSE.
        """
        if not moving_data:
            logger.warning("⚠️ No moving data, using defaults")
            return 0.0015, 0.0001

        X = []  # [engine_load, altitude_change_rate]
        y = []  # actual fuel consumed (gal)

        for row in moving_data:
            fuel_gal = row["fuel_consumed_gal"]
            time_min = row["time_minutes"]
            engine_load = row["avg_engine_load_pct"]
            alt_change = row["altitude_change_m"]

            if time_min <= 0:
                continue

            alt_rate = alt_change / time_min  # meters/min
            X.append([engine_load, alt_rate])
            y.append(fuel_gal)

        X = np.array(X)
        y = np.array(y)

        logger.info(f"🔬 Optimizing on {len(y)} moving samples...")

        def objective(params):
            load_factor, altitude_factor = params

            predictions = []
            for i in range(len(X)):
                engine_load, alt_rate = X[i]
                time_min = moving_data[i]["time_minutes"]

                fuel_rate_pct = (
                    baseline_consumption
                    + load_factor * engine_load
                    + altitude_factor * alt_rate
                )

                fuel_gal_pred = (fuel_rate_pct / 100.0) * 120.0 * time_min
                predictions.append(fuel_gal_pred)

            predictions = np.array(predictions)
            rmse = np.sqrt(np.mean((predictions - y) ** 2))
            return rmse

        x0 = [0.0015, 0.0001]
        bounds = [(0.0001, 0.01), (0.00001, 0.001)]

        result = minimize(objective, x0, method="L-BFGS-B", bounds=bounds)

        load_factor, altitude_factor = result.x
        final_rmse = result.fun

        logger.info(f"✅ Optimization converged:")
        logger.info(f"   load_factor = {load_factor:.6f}")
        logger.info(f"   altitude_factor = {altitude_factor:.6f}")
        logger.info(f"   RMSE = {final_rmse:.3f} gallons")

        return load_factor, altitude_factor

    def validate_calibration(
        self,
        data: List[Dict],
        baseline: float,
        load_factor: float,
        altitude_factor: float,
    ) -> Dict:
        """
        Validate calibrated parameters on full dataset.

        Returns metrics: MAE, RMSE, R²
        """
        predictions = []
        actuals = []

        for row in data:
            fuel_actual = row["fuel_consumed_gal"]
            time_min = row["time_minutes"]
            engine_load = row["avg_engine_load_pct"]
            alt_change = row["altitude_change_m"]
            is_moving = row["is_moving"]

            if time_min <= 0:
                continue

            if is_moving:
                alt_rate = alt_change / time_min
                fuel_rate_pct = (
                    baseline + load_factor * engine_load + altitude_factor * alt_rate
                )
            else:
                fuel_rate_pct = 0.05  # Idle/stopped

            fuel_pred_gal = (fuel_rate_pct / 100.0) * 120.0 * time_min

            predictions.append(fuel_pred_gal)
            actuals.append(fuel_actual)

        predictions = np.array(predictions)
        actuals = np.array(actuals)

        mae = np.mean(np.abs(predictions - actuals))
        rmse = np.sqrt(np.mean((predictions - actuals) ** 2))

        ss_res = np.sum((actuals - predictions) ** 2)
        ss_tot = np.sum((actuals - np.mean(actuals)) ** 2)
        r2 = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0

        metrics = {
            "mae_gal": round(mae, 3),
            "rmse_gal": round(rmse, 3),
            "r2_score": round(r2, 4),
            "sample_count": len(actuals),
        }

        logger.info(f"📊 Validation Metrics:")
        logger.info(f"   MAE:  {mae:.3f} gallons")
        logger.info(f"   RMSE: {rmse:.3f} gallons")
        logger.info(f"   R²:   {r2:.4f}")

        return metrics

    def run_calibration(self, days: int = 30, min_samples: int = 100) -> Optional[Dict]:
        """
        Run full calibration pipeline.

        Returns:
            Dict with calibrated parameters and validation metrics
        """
        logger.info("🚀 Starting Kalman Filter Calibration...")

        self.connect()
        data = self.fetch_calibration_data(days, min_samples)
        self.disconnect()

        if not data:
            logger.error("❌ No data available for calibration")
            return None

        idle_data, moving_data = self.separate_idle_moving(data)

        baseline = self.calibrate_baseline_consumption(idle_data)
        load_factor, altitude_factor = self.optimize_consumption_model(
            moving_data, baseline
        )
        metrics = self.validate_calibration(
            data, baseline, load_factor, altitude_factor
        )

        calibration = {
            "calibration_date": datetime.now().isoformat(),
            "data_period_days": days,
            "sample_count": len(data),
            "parameters": {
                "baseline_consumption": round(baseline, 6),
                "load_factor": round(load_factor, 6),
                "altitude_factor": round(altitude_factor, 6),
            },
            "validation_metrics": metrics,
            "usage_notes": {
                "baseline_consumption": "Fuel consumption rate (%/min) when idle/stopped",
                "load_factor": "Additional consumption per 1% engine load",
                "altitude_factor": "Additional consumption per meter/min altitude gain",
                "recommended_config": self._generate_config_snippet(
                    baseline, load_factor, altitude_factor
                ),
            },
        }

        logger.info("✅ Calibration complete!")
        return calibration

    def _generate_config_snippet(
        self, baseline: float, load_factor: float, altitude_factor: float
    ) -> str:
        """Generate Python config snippet to paste into Kalman filter"""
        return f"""
# 🔧 AUTO-CALIBRATED CONSUMPTION MODEL (Generated {datetime.now().strftime('%Y-%m-%d')})
KALMAN_CONFIG = {{
    # Consumption model (learned from {self.db_config.get('database', 'unknown')} fleet data)
    "baseline_consumption": {baseline:.6f},    # %/min idle consumption
    "load_factor": {load_factor:.6f},          # Additional %/min per % engine load
    "altitude_factor": {altitude_factor:.6f},  # Additional %/min per meter/min climb
    
    # Ruido del proceso
    "process_noise_fuel": 0.05,
    "process_noise_rate": 0.02,
    
    # Ruido de medición
    "measurement_noise": 1.5,
    
    # Temperatura
    "temp_correction_enabled": True,
    "base_temp_f": 60.0,
    "expansion_coeff": 0.00067
}}

# Expected consumption examples:
# - Idle: {baseline:.4f} %/min = {baseline*60:.2f} %/hr = {baseline*60*1.2:.2f} gal/hr (120 gal tank)
# - 60% load, highway: {baseline + load_factor*60:.4f} %/min = {(baseline + load_factor*60)*60*1.2:.2f} gal/hr
# - 100% load, climbing: {baseline + load_factor*100 + altitude_factor*50:.4f} %/min = {(baseline + load_factor*100 + altitude_factor*50)*60*1.2:.2f} gal/hr
"""


def main():
    parser = argparse.ArgumentParser(
        description="Calibrate Kalman filter consumption parameters from historical data"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Days of historical data to use (default: 30)",
    )
    parser.add_argument(
        "--min-samples",
        type=int,
        default=100,
        help="Minimum samples per truck to include (default: 100)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="data/kalman_calibration.json",
        help="Output file for calibration results",
    )

    args = parser.parse_args()

    # Database config (adjust for your environment)
    db_config = {
        "host": "localhost",
        "user": "root",
        "password": "your_password",  # TODO: Use environment variable
        "database": "fuel_copilot",
        "charset": "utf8mb4",
    }

    # 🆕 v2.0: Run data quality check first
    logger.info("🔍 Running data quality check...")
    quality = check_data_quality(db_config, days=args.days)
    if quality is None:
        logger.error("❌ Data quality check failed. Aborting calibration.")
        return 1

    # Run calibration
    calibrator = KalmanCalibrator(db_config)
    results = calibrator.run_calibration(days=args.days, min_samples=args.min_samples)

    if results:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w") as f:
            json.dump(results, f, indent=2)

        logger.info(f"💾 Calibration saved to: {output_path}")

        print("\n" + "=" * 80)
        print("📋 PASTE THIS INTO YOUR KALMAN FILTER:")
        print("=" * 80)
        print(results["usage_notes"]["recommended_config"])
        print("=" * 80)
    else:
        logger.error("❌ Calibration failed")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
