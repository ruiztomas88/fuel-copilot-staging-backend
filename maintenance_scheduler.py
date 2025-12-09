"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║              MAINTENANCE ALERT SCHEDULER v1.0                                  ║
║                     Fuel Copilot - FleetBooster                                ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║  Purpose: Periodic health checks with alert persistence & notifications       ║
║                                                                                ║
║  Architecture:                                                                 ║
║  - Runs every hour via APScheduler                                            ║
║  - Reads sensor data from Wialon DB                                           ║
║  - Analyzes with PredictiveMaintenanceEngine                                  ║
║  - Persists new alerts to MySQL (with deduplication)                          ║
║  - Sends notifications for CRITICAL alerts                                    ║
║                                                                                ║
║  Usage:                                                                        ║
║    python maintenance_scheduler.py              # Run as daemon               ║
║    python maintenance_scheduler.py --once       # Run once (for testing)      ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""

import os
import sys
import logging
import argparse
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional, Any
import pymysql
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

# Load .env file for credentials
from dotenv import load_dotenv

load_dotenv()

# Local imports
from predictive_maintenance_engine import (
    PredictiveMaintenanceEngine,
    HealthAlert,
    AlertSeverity,
)

# Configure logging (ASCII-safe for Windows)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("maintenance_scheduler.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("maintenance_scheduler")


# ═══════════════════════════════════════════════════════════════════════════════
# DATABASE CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

# Wialon DB (source of sensor data)
WIALON_DB_CONFIG = {
    "host": os.getenv("WIALON_DB_HOST", "20.127.200.135"),
    "port": int(os.getenv("WIALON_DB_PORT", "3306")),
    "user": os.getenv("WIALON_DB_USER", "fleetbooster"),
    "password": os.getenv("WIALON_DB_PASS", ""),
    "database": os.getenv("WIALON_DB_NAME", "wialon_collect"),
    "charset": "utf8mb4",
}

# Fuel Analytics DB (destination for alerts)
FUEL_DB_CONFIG = {
    "host": os.getenv("MYSQL_HOST", "localhost"),
    "port": int(os.getenv("MYSQL_PORT", "3306")),
    "user": os.getenv("MYSQL_USER", "root"),
    "password": os.getenv("MYSQL_PASSWORD", ""),
    "database": os.getenv("MYSQL_DATABASE", "fuel_analytics"),
    "charset": "utf8mb4",
}

# Alert deduplication window (hours)
DEDUP_WINDOW_HOURS = 24

# Minimum severity to persist (skip LOW alerts)
# Options: "critical", "high", "medium", "low"
MIN_PERSIST_SEVERITY = "medium"


# ═══════════════════════════════════════════════════════════════════════════════
# DATABASE SCHEMA
# ═══════════════════════════════════════════════════════════════════════════════

CREATE_ALERTS_TABLE = """
CREATE TABLE IF NOT EXISTS maintenance_alerts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    truck_id VARCHAR(50) NOT NULL,
    alert_hash VARCHAR(64) NOT NULL COMMENT 'Hash for deduplication',
    category VARCHAR(50) NOT NULL,
    severity ENUM('critical', 'high', 'medium', 'low') NOT NULL,
    title VARCHAR(200) NOT NULL,
    message TEXT,
    metric VARCHAR(50),
    current_value FLOAT,
    threshold FLOAT,
    trend_pct FLOAT,
    recommendation TEXT,
    estimated_days_to_failure INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    acknowledged_at TIMESTAMP NULL,
    acknowledged_by VARCHAR(100) NULL,
    resolved_at TIMESTAMP NULL,
    resolved_by VARCHAR(100) NULL,
    notification_sent_at TIMESTAMP NULL,
    INDEX idx_truck_severity (truck_id, severity),
    INDEX idx_created (created_at),
    INDEX idx_hash (alert_hash),
    INDEX idx_unresolved (resolved_at, severity)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""

CREATE_HEALTH_HISTORY_TABLE = """
CREATE TABLE IF NOT EXISTS truck_health_history (
    id INT AUTO_INCREMENT PRIMARY KEY,
    truck_id VARCHAR(50) NOT NULL,
    overall_score INT NOT NULL,
    overall_status VARCHAR(20) NOT NULL,
    engine_score INT,
    cooling_score INT,
    electrical_score INT,
    fuel_score INT,
    emissions_score INT,
    alert_count INT DEFAULT 0,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_truck_time (truck_id, recorded_at),
    INDEX idx_recorded (recorded_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""


# ═══════════════════════════════════════════════════════════════════════════════
# MAINTENANCE SCHEDULER CLASS
# ═══════════════════════════════════════════════════════════════════════════════


class MaintenanceScheduler:
    """
    Scheduled maintenance health checker

    Runs periodically to:
    1. Fetch latest sensor data from Wialon
    2. Run predictive analysis
    3. Persist new alerts (with deduplication)
    4. Send notifications for critical issues
    """

    def __init__(self):
        self.engine = PredictiveMaintenanceEngine()
        self._ensure_tables_exist()

    def _get_wialon_connection(self):
        """Get connection to Wialon DB"""
        return pymysql.connect(
            **WIALON_DB_CONFIG,
            cursorclass=pymysql.cursors.DictCursor,
            connect_timeout=10,
        )

    def _get_fuel_connection(self):
        """Get connection to Fuel Analytics DB"""
        return pymysql.connect(
            **FUEL_DB_CONFIG,
            cursorclass=pymysql.cursors.DictCursor,
            connect_timeout=10,
        )

    def _ensure_tables_exist(self):
        """Create tables if they don't exist"""
        try:
            conn = self._get_fuel_connection()
            with conn.cursor() as cursor:
                cursor.execute(CREATE_ALERTS_TABLE)
                cursor.execute(CREATE_HEALTH_HISTORY_TABLE)
            conn.commit()
            conn.close()
            logger.info("[OK] Database tables verified")
        except Exception as e:
            logger.error(f"Failed to create tables: {e}")

    # ───────────────────────────────────────────────────────────────────────────
    # DATA FETCHING
    # ───────────────────────────────────────────────────────────────────────────

    def fetch_sensor_data(self) -> List[Dict]:
        """
        Fetch latest sensor data from Wialon for all trucks

        Returns:
            List of truck data dicts with sensor values
        """
        try:
            conn = self._get_wialon_connection()
            trucks_data = []

            with conn.cursor() as cursor:
                # Get latest readings for each truck (last 2 hours)
                query = """
                    SELECT 
                        s.unit,
                        s.n as truck_name,
                        s.p as param,
                        s.value,
                        s.m as epoch
                    FROM sensors s
                    INNER JOIN (
                        SELECT unit, p, MAX(m) as max_epoch
                        FROM sensors
                        WHERE m >= UNIX_TIMESTAMP() - 7200
                        GROUP BY unit, p
                    ) latest ON s.unit = latest.unit 
                           AND s.p = latest.p 
                           AND s.m = latest.max_epoch
                    WHERE s.m >= UNIX_TIMESTAMP() - 7200
                """
                cursor.execute(query)
                rows = cursor.fetchall()

                # Group by unit
                unit_data: Dict[int, Dict] = {}
                for row in rows:
                    unit_id = row["unit"]
                    if unit_id not in unit_data:
                        unit_data[unit_id] = {
                            "truck_id": row["truck_name"] or str(unit_id),
                            "unit_id": unit_id,
                        }

                    param = row["param"]
                    value = row["value"]

                    # Map Wialon params to our standard names
                    param_mapping = {
                        "oil_press": "oil_press",
                        "cool_temp": "cool_temp",
                        "oil_temp": "oil_temp",
                        "pwr_ext": "pwr_ext",
                        "def_level": "def_level",
                        "rpm": "rpm",
                        "engine_load": "engine_load",
                        "fuel_rate": "fuel_rate",
                        "fuel_lvl": "fuel_lvl",
                    }

                    if param in param_mapping:
                        unit_data[unit_id][param_mapping[param]] = value

                trucks_data = list(unit_data.values())

            conn.close()
            logger.info(f"[DATA] Fetched sensor data for {len(trucks_data)} trucks")
            return trucks_data

        except Exception as e:
            logger.error(f"Failed to fetch Wialon data: {e}")
            return []

    def fetch_historical_data(self, truck_id: str, unit_id: Optional[int] = None, days: int = 7) -> Dict[str, List]:
        """
        Fetch historical sensor data for trend analysis

        Args:
            truck_id: Truck name (for fallback)
            unit_id: Wialon unit ID (preferred)
            days: Number of days of history

        Returns:
            Dict of {metric: [(timestamp, value), ...]}
        """
        try:
            conn = self._get_wialon_connection()
            historical: Dict[str, List] = {}

            with conn.cursor() as cursor:
                cutoff = int(
                    (datetime.now(timezone.utc) - timedelta(days=days)).timestamp()
                )

                # Prefer unit_id (numeric) over truck name (string)
                if unit_id:
                    query = """
                        SELECT p as param, m as epoch, value
                        FROM sensors
                        WHERE unit = %s AND m >= %s
                        ORDER BY m ASC
                    """
                    cursor.execute(query, (unit_id, cutoff))
                else:
                    query = """
                        SELECT p as param, m as epoch, value
                        FROM sensors
                        WHERE n = %s AND m >= %s
                        ORDER BY m ASC
                    """
                    cursor.execute(query, (truck_id, cutoff))
                rows = cursor.fetchall()

                for row in rows:
                    param = row["param"]
                    if param not in historical:
                        historical[param] = []

                    ts = datetime.fromtimestamp(row["epoch"], tz=timezone.utc)
                    historical[param].append((ts, row["value"]))

            conn.close()
            return historical

        except Exception as e:
            logger.error(f"Failed to fetch historical data for {truck_id}: {e}")
            return {}

    # ───────────────────────────────────────────────────────────────────────────
    # ALERT PERSISTENCE
    # ───────────────────────────────────────────────────────────────────────────

    def _generate_alert_hash(self, alert: Dict) -> str:
        """
        Generate hash for deduplication

        Same truck + same metric + same severity = same alert
        """
        import hashlib

        key = f"{alert['truck_id']}:{alert['metric']}:{alert['severity']}"
        return hashlib.sha256(key.encode()).hexdigest()[:16]

    def _alert_exists_recent(self, conn, alert_hash: str) -> bool:
        """Check if similar alert exists within dedup window"""
        with conn.cursor() as cursor:
            query = """
                SELECT id FROM maintenance_alerts
                WHERE alert_hash = %s
                  AND created_at >= NOW() - INTERVAL %s HOUR
                  AND resolved_at IS NULL
                LIMIT 1
            """
            cursor.execute(query, (alert_hash, DEDUP_WINDOW_HOURS))
            return cursor.fetchone() is not None

    def persist_alerts(self, alerts: List[Dict]) -> int:
        """
        Persist new alerts to database with deduplication

        Args:
            alerts: List of alert dicts from PredictiveMaintenanceEngine

        Returns:
            Number of new alerts inserted
        """
        if not alerts:
            return 0

        try:
            conn = self._get_fuel_connection()
            inserted = 0

            severity_order = {
                "critical": 0,
                "high": 1,
                "medium": 2,
                "low": 3,
            }

            for alert in alerts:
                # Skip low severity alerts
                if severity_order.get(alert["severity"], 3) > severity_order.get(
                    MIN_PERSIST_SEVERITY, 2
                ):
                    continue

                alert_hash = self._generate_alert_hash(alert)

                # Check for duplicate
                if self._alert_exists_recent(conn, alert_hash):
                    logger.debug(f"Skipping duplicate alert: {alert['title']}")
                    continue

                # Insert new alert
                with conn.cursor() as cursor:
                    query = """
                        INSERT INTO maintenance_alerts (
                            truck_id, alert_hash, category, severity, title, message,
                            metric, current_value, threshold, trend_pct,
                            recommendation, estimated_days_to_failure
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                        )
                    """
                    cursor.execute(
                        query,
                        (
                            alert["truck_id"],
                            alert_hash,
                            alert["category"],
                            alert["severity"],
                            alert["title"],
                            alert["message"],
                            alert["metric"],
                            alert.get("current_value"),
                            alert.get("threshold"),
                            alert.get("trend_pct"),
                            alert.get("recommendation"),
                            alert.get("estimated_days_to_failure"),
                        ),
                    )
                    inserted += 1
                    logger.info(
                        f"[ALERT] New alert: [{alert['severity'].upper()}] "
                        f"{alert['truck_id']} - {alert['title']}"
                    )

            conn.commit()
            conn.close()
            return inserted

        except Exception as e:
            logger.error(f"Failed to persist alerts: {e}")
            return 0

    def persist_health_history(self, trucks_health: List[Dict]):
        """
        Save health scores to history table for trend tracking
        """
        if not trucks_health:
            return

        try:
            conn = self._get_fuel_connection()

            with conn.cursor() as cursor:
                for truck in trucks_health:
                    components = truck.get("components", {})

                    query = """
                        INSERT INTO truck_health_history (
                            truck_id, overall_score, overall_status,
                            engine_score, cooling_score, electrical_score,
                            fuel_score, emissions_score, alert_count
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """
                    cursor.execute(
                        query,
                        (
                            truck["truck_id"],
                            truck["overall_score"],
                            truck["overall_status"],
                            components.get("engine", {}).get("score"),
                            components.get("cooling", {}).get("score"),
                            components.get("electrical", {}).get("score"),
                            components.get("fuel", {}).get("score"),
                            components.get("emissions", {}).get("score"),
                            len(truck.get("alerts", [])),
                        ),
                    )

            conn.commit()
            conn.close()
            logger.info(
                f"[HISTORY] Saved health history for {len(trucks_health)} trucks"
            )

        except Exception as e:
            logger.error(f"Failed to persist health history: {e}")

    # ───────────────────────────────────────────────────────────────────────────
    # NOTIFICATIONS
    # ───────────────────────────────────────────────────────────────────────────

    def send_critical_notifications(self, alerts: List[Dict]) -> int:
        """
        Send notifications for CRITICAL alerts

        Integrates with existing AlertService (Twilio/email)
        """
        critical_alerts = [
            a for a in alerts if a["severity"] == AlertSeverity.CRITICAL.value
        ]

        if not critical_alerts:
            return 0

        sent = 0
        try:
            # Import AlertService if available
            from alert_service import AlertService

            alert_service = AlertService()
            conn = self._get_fuel_connection()

            for alert in critical_alerts:
                message = (
                    f"CRITICAL: {alert['truck_id']}\n"
                    f"{alert['title']}\n"
                    f"{alert['message']}\n"
                    f"Action: {alert.get('recommendation', 'Check immediately')}"
                )

                # Send via AlertService (which handles SMS/email)
                alert_service.send_alert(
                    truck_id=alert["truck_id"],
                    alert_type="maintenance_critical",
                    message=message,
                    severity="critical",
                )
                
                # Mark notification as sent to prevent re-sends
                if alert.get("id"):
                    with conn.cursor() as cursor:
                        cursor.execute(
                            "UPDATE maintenance_alerts SET notification_sent_at = NOW() WHERE id = %s",
                            (alert["id"],)
                        )
                
                sent += 1
                logger.info(f"[SMS] Notification sent for {alert['truck_id']}")

            conn.commit()
            conn.close()

        except ImportError:
            logger.warning("AlertService not available - notifications disabled")
        except Exception as e:
            logger.error(f"Failed to send notifications: {e}")

        return sent

    # ───────────────────────────────────────────────────────────────────────────
    # MAIN RUN LOOP
    # ───────────────────────────────────────────────────────────────────────────

    def run_health_check(self):
        """
        Main health check routine

        Called every hour by scheduler
        """
        start_time = datetime.now(timezone.utc)
        logger.info("=" * 60)
        logger.info("[START] Starting scheduled health check...")

        try:
            # 1. Fetch sensor data
            trucks_data = self.fetch_sensor_data()
            if not trucks_data:
                logger.warning("No truck data available - skipping analysis")
                return

            # 2. Run predictive analysis
            report = self.engine.generate_fleet_health_report(trucks_data)

            # 3. Log summary
            summary = report.get("fleet_summary", {})
            alert_summary = report.get("alert_summary", {})

            logger.info(
                f"[HEALTH] Fleet Health: {summary.get('fleet_health_score', 'N/A')}% | "
                f"OK: {summary.get('trucks_ok', 0)} | "
                f"Warning: {summary.get('trucks_warning', 0)} | "
                f"Critical: {summary.get('trucks_critical', 0)}"
            )
            logger.info(
                f"[ALERTS] Alerts: {alert_summary.get('total_alerts', 0)} total | "
                f"Critical: {alert_summary.get('critical', 0)} | "
                f"High: {alert_summary.get('high', 0)} | "
                f"Medium: {alert_summary.get('medium', 0)}"
            )

            # 4. Persist alerts (with deduplication)
            alerts = report.get("alerts", [])
            new_alerts = self.persist_alerts(alerts)
            logger.info(f"[DB] Persisted {new_alerts} new alerts")

            # 5. Save health history
            trucks_health = report.get("trucks", [])
            self.persist_health_history(trucks_health)

            # 6. Send notifications for critical alerts
            notifications = self.send_critical_notifications(alerts)
            if notifications > 0:
                logger.info(f"[SMS] Sent {notifications} critical notifications")

            # 7. Done
            elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
            logger.info(f"[DONE] Health check completed in {elapsed:.1f}s")

        except Exception as e:
            logger.error(f"[ERROR] Health check failed: {e}", exc_info=True)

        logger.info("=" * 60)


# ═══════════════════════════════════════════════════════════════════════════════
# SCHEDULER SETUP
# ═══════════════════════════════════════════════════════════════════════════════


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Predictive Maintenance Scheduler")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run once and exit (for testing)",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=60,
        help="Run interval in minutes (default: 60)",
    )
    args = parser.parse_args()

    scheduler_instance = MaintenanceScheduler()

    if args.once:
        # Single run mode (for testing)
        logger.info("Running single health check...")
        scheduler_instance.run_health_check()
        return

    # Daemon mode with APScheduler
    logger.info("[DAEMON] Starting Maintenance Scheduler daemon")
    logger.info(f"   Interval: every {args.interval} minutes")

    scheduler = BlockingScheduler()

    # Run every hour at minute 0 (or custom interval)
    if args.interval == 60:
        # Every hour at :00
        scheduler.add_job(
            scheduler_instance.run_health_check,
            CronTrigger(minute=0),
            id="health_check",
            name="Hourly Health Check",
        )
    else:
        # Custom interval
        scheduler.add_job(
            scheduler_instance.run_health_check,
            "interval",
            minutes=args.interval,
            id="health_check",
            name=f"Health Check (every {args.interval}m)",
        )

    # Run immediately on startup
    scheduler_instance.run_health_check()

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped")


if __name__ == "__main__":
    main()
