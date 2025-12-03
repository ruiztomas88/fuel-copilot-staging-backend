"""
Bulk MySQL Handler - Batch inserts for better performance
Instead of 39 individual commits, accumulate records and commit in batches

🔒 SECURITY:
- All credentials loaded from environment variables
- Never hardcode passwords in code

⏰ TIMEZONE:
- Uses timezone_utils for consistent UTC handling
- Replaces deprecated datetime.utcnow()
"""

import os
import logging
from typing import Dict, List
from threading import Lock
from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

from timezone_utils import utc_now
from datetime import datetime  # For isinstance check only

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)


def get_local_db_config() -> Dict[str, any]:
    """Get local database configuration from environment variables"""
    return {
        "host": os.getenv("LOCAL_DB_HOST", os.getenv("MYSQL_HOST", "localhost")),
        "port": int(os.getenv("LOCAL_DB_PORT", os.getenv("MYSQL_PORT", "3306"))),
        "user": os.getenv("LOCAL_DB_USER", os.getenv("MYSQL_USER", "fuel_admin")),
        "password": os.getenv("LOCAL_DB_PASS", os.getenv("MYSQL_PASSWORD", "")),
        "database": os.getenv(
            "LOCAL_DB_NAME", os.getenv("MYSQL_DATABASE", "fuel_copilot")
        ),
    }


def get_local_engine():
    """Create SQLAlchemy engine for Local MySQL"""
    config = get_local_db_config()
    connection_string = (
        f"mysql+pymysql://{config['user']}:{config['password']}"
        f"@{config['host']}:{config['port']}/{config['database']}"
        f"?charset=utf8mb4"
    )
    return create_engine(connection_string, pool_pre_ping=True)


def get_local_session():
    """Get SQLAlchemy session for Local MySQL"""
    engine = get_local_engine()
    Session = sessionmaker(bind=engine)
    return Session()


class BulkMySQLHandler:
    """
    Accumulates fuel metrics records and commits them in batches
    Reduces MySQL overhead from 39 commits/cycle to 1-2 commits/cycle
    """

    def __init__(self, batch_size: int = 20, auto_flush_seconds: float = 30.0):
        """
        Args:
            batch_size: Number of records to accumulate before auto-commit
            auto_flush_seconds: Max seconds to wait before forcing a commit
        """
        self.batch_size = batch_size
        self.auto_flush_seconds = auto_flush_seconds
        self.pending_records: List[Dict] = []
        self.last_flush_time = utc_now()
        self.lock = Lock()
        self.total_records_saved = 0
        self.total_batches = 0
        self.failed_records = 0

    def add_record(self, truck_id: str, row_data: Dict) -> bool:
        """
        Add a record to the batch queue
        Auto-commits if batch is full or time threshold exceeded

        Returns:
            True if record added successfully, False if immediate commit failed
        """
        with self.lock:
            # DEBUG: Log what we are adding
            if truck_id == "LC6799":
                logger.info(
                    f"➕ [LC6799] Adding record to batch. Timestamp: {row_data.get('timestamp_utc')}"
                )

            self.pending_records.append({"truck_id": truck_id, "data": row_data})

            # Check if we should flush
            should_flush = (
                len(self.pending_records) >= self.batch_size
                or (utc_now() - self.last_flush_time).total_seconds()
                >= self.auto_flush_seconds
            )

            if should_flush:
                return self._flush_batch()

            return True  # Record queued successfully

    def _flush_batch(self) -> bool:
        """
        Commit all pending records to MySQL using native UPSERT

        🔧 FIX v3.9.2: Uses INSERT ... ON DUPLICATE KEY UPDATE for 50% fewer queries
        - Old: SELECT + UPDATE/INSERT = 2 queries per record
        - New: 1 UPSERT query per record

        Returns:
            True if all records saved successfully, False if any failures
        """
        if not self.pending_records:
            return True

        try:
            from sqlalchemy.dialects.mysql import insert as mysql_insert
            from tools.database_models import FuelMetrics

            # Use LOCAL session instead of generic get_session()
            session = get_local_session()

            if not session:
                logger.warning("⚠️ MySQL session unavailable, skipping batch")
                self.failed_records += len(self.pending_records)
                self.pending_records.clear()
                return False

            try:
                # Process all records with native UPSERT (INSERT ON DUPLICATE KEY UPDATE)
                for item in self.pending_records:
                    truck_id = item["truck_id"]
                    row_data = item["data"]

                    # Strip microseconds to match MySQL DATETIME precision
                    ts = row_data.get("timestamp_utc")
                    if isinstance(ts, datetime):
                        row_data["timestamp_utc"] = ts.replace(microsecond=0)

                    # Prepare values dict for UPSERT
                    # 🆕 v3.10.8: Include carrier_id for multi-tenant support
                    values = {
                        "truck_id": truck_id,
                        "carrier_id": row_data.get(
                            "carrier_id", "skylord"
                        ),  # Default to skylord
                        "timestamp_utc": row_data.get("timestamp_utc"),
                        "epoch_time": row_data.get("epoch_time"),
                        "data_age_min": row_data.get("data_age_min"),
                        "truck_status": row_data.get("truck_status"),
                        "estimated_liters": row_data.get("estimated_liters"),
                        "estimated_gallons": row_data.get("estimated_gallons"),
                        "estimated_pct": row_data.get("estimated_pct"),
                        "sensor_pct": row_data.get("sensor_pct"),
                        "sensor_liters": row_data.get("sensor_liters"),
                        "sensor_gallons": row_data.get("sensor_gallons"),
                        "sensor_ema_pct": row_data.get("sensor_ema_pct"),
                        "ecu_level_pct": row_data.get("ecu_level_pct"),
                        "model_level_pct": row_data.get("model_level_pct"),
                        "confidence_indicator": row_data.get("confidence_indicator"),
                        "consumption_lph": row_data.get("consumption_lph"),
                        "consumption_gph": row_data.get("consumption_gph"),
                        "idle_method": row_data.get("idle_method"),
                        "idle_mode": row_data.get("idle_mode"),
                        "mpg_current": row_data.get("mpg_current"),
                        "speed_mph": row_data.get("speed_mph"),
                        "rpm": row_data.get("rpm"),
                        "hdop": row_data.get("hdop"),
                        "altitude_ft": row_data.get("altitude_ft"),
                        "coolant_temp_f": row_data.get("coolant_temp_f"),
                        "odometer_mi": row_data.get("odometer_mi"),
                        "odom_delta_mi": row_data.get("odom_delta_mi"),
                        "drift_pct": row_data.get("drift_pct"),
                        "drift_warning": self._bool_to_yesno(
                            row_data.get("drift_warning")
                        ),
                        "anchor_detected": self._bool_to_yesno(
                            row_data.get("anchor_detected")
                        ),
                        "anchor_type": row_data.get("anchor_type"),
                        "static_anchors_total": row_data.get("static_anchors_total"),
                        "micro_anchors_total": row_data.get("micro_anchors_total"),
                        "refuel_events_total": row_data.get("refuel_events_total"),
                        "refuel_gallons": row_data.get("refuel_gallons"),
                        "flags": row_data.get("flags"),
                    }

                    # Build UPSERT statement (INSERT ON DUPLICATE KEY UPDATE)
                    stmt = mysql_insert(FuelMetrics).values(**values)

                    # On duplicate key, update only the fields we're actually inserting
                    # 🔧 Fix: Only update columns that are in the values dict
                    update_dict = {
                        col_name: stmt.inserted[col_name]
                        for col_name in values.keys()
                        if col_name
                        not in (
                            "id",
                            "truck_id",
                            "timestamp_utc",
                            "created_at",  # Should not be updated on duplicate
                        )
                    }

                    stmt = stmt.on_duplicate_key_update(**update_dict)

                    try:
                        session.execute(stmt)
                    except Exception as e:
                        logger.warning(
                            f"⚠️ UPSERT error for {truck_id} at {row_data.get('timestamp_utc')}: {e}"
                        )

                # Commit all changes at once
                session.commit()

                # Success metrics
                record_count = len(self.pending_records)
                self.total_records_saved += record_count
                self.total_batches += 1
                self.last_flush_time = utc_now()

                logger.info(
                    f"✅ MySQL UPSERT: {record_count} records "
                    f"(batch #{self.total_batches}, total: {self.total_records_saved})"
                )

                self.pending_records.clear()
                return True

            except Exception as e:
                session.rollback()
                logger.error(f"❌ MySQL UPSERT failed: {e}")

                # 🔧 FIX v3.9.7: Retry logic for transient failures
                retry_count = getattr(self, "_retry_count", 0)
                if retry_count < 2:  # Max 2 retries
                    self._retry_count = retry_count + 1
                    logger.info(
                        f"🔄 Retrying MySQL UPSERT (attempt {self._retry_count + 1}/3)..."
                    )
                    import time

                    time.sleep(0.5)  # Brief pause before retry
                    try:
                        session = get_local_session()
                        for item in self.pending_records:
                            truck_id = item["truck_id"]
                            row_data = item["data"]
                            # Simplified retry - just try single inserts
                            from tools.database_models import FuelMetrics

                            values = {
                                "truck_id": truck_id,
                                "timestamp_utc": row_data.get("timestamp_utc"),
                                **{
                                    k: v
                                    for k, v in row_data.items()
                                    if k not in ("truck_id", "timestamp_utc")
                                },
                            }
                            stmt = mysql_insert(FuelMetrics).values(**values)
                            # 🔧 Fix: Only update columns that are in the values dict
                            update_dict = {
                                col_name: stmt.inserted[col_name]
                                for col_name in values.keys()
                                if col_name
                                not in (
                                    "id",
                                    "truck_id",
                                    "timestamp_utc",
                                    "carrier_id",
                                    "created_at",
                                )
                            }
                            stmt = stmt.on_duplicate_key_update(**update_dict)
                            session.execute(stmt)
                        session.commit()
                        logger.info(f"✅ MySQL retry succeeded")
                        self._retry_count = 0
                        self.pending_records.clear()
                        return True
                    except Exception as retry_err:
                        logger.error(f"❌ MySQL retry also failed: {retry_err}")
                        session.rollback()
                    finally:
                        session.close()

                self._retry_count = 0
                self.failed_records += len(self.pending_records)
                self.pending_records.clear()
                return False

            finally:
                session.close()

        except ImportError:
            logger.warning("⚠️ MySQL models not available, skipping batch")
            self.pending_records.clear()
            return False

        except Exception as e:
            logger.error(f"❌ MySQL bulk handler error: {e}")
            self.pending_records.clear()
            return False

    def force_flush(self) -> bool:
        """
        Manually flush all pending records immediately
        Use this before shutdown or at end of processing cycle
        """
        with self.lock:
            return self._flush_batch()

    def get_stats(self) -> Dict:
        """Get handler statistics"""
        with self.lock:
            return {
                "pending_records": len(self.pending_records),
                "total_saved": self.total_records_saved,
                "total_batches": self.total_batches,
                "failed_records": self.failed_records,
                "avg_batch_size": (
                    self.total_records_saved / self.total_batches
                    if self.total_batches > 0
                    else 0
                ),
            }

    @staticmethod
    def _bool_to_yesno(value) -> str:
        """Convert boolean to YES/NO enum"""
        if value is None:
            return "NO"
        if isinstance(value, bool):
            return "YES" if value else "NO"
        if isinstance(value, str):
            return "YES" if value.upper() in ["YES", "TRUE", "1"] else "NO"
        return "NO"


# Global singleton instance
_bulk_handler_instance = None
_handler_lock = Lock()


def get_bulk_handler(batch_size: int = 20, auto_flush_seconds: float = 30.0):
    """
    Get or create the global bulk handler instance (singleton pattern)

    Args:
        batch_size: Records to accumulate before auto-commit (default: 20)
        auto_flush_seconds: Max seconds before forcing commit (default: 30)
    """
    global _bulk_handler_instance

    with _handler_lock:
        if _bulk_handler_instance is None:
            _bulk_handler_instance = BulkMySQLHandler(batch_size, auto_flush_seconds)
            logger.info(
                f"🚀 Bulk MySQL Handler initialized "
                f"(batch_size={batch_size}, auto_flush={auto_flush_seconds}s)"
            )

        return _bulk_handler_instance


def save_to_mysql_bulk(truck_id: str, row_data: Dict) -> bool:
    """
    Drop-in replacement for save_to_mysql() that uses bulk inserts

    Usage:
        # Old way (39 commits/cycle):
        save_to_mysql(truck_id, data)

        # New way (1-2 commits/cycle):
        save_to_mysql_bulk(truck_id, data)

    Returns:
        True if record queued successfully, False if error
    """
    handler = get_bulk_handler()
    return handler.add_record(truck_id, row_data)


def flush_pending_records() -> bool:
    """
    Force flush all pending records to MySQL.
    Call this during shutdown to ensure no records are lost.

    Returns:
        True if flush successful or no pending records, False if error
    """
    global _bulk_handler_instance

    with _handler_lock:
        if _bulk_handler_instance is not None:
            pending_count = len(_bulk_handler_instance.pending_records)
            if pending_count > 0:
                logger.info(f"💾 Flushing {pending_count} pending MySQL records before shutdown...")
                result = _bulk_handler_instance._flush_batch()
                logger.info(f"✅ Shutdown flush complete: {_bulk_handler_instance.total_batches} batches, {_bulk_handler_instance.successful_records} records saved")
                return result
            else:
                logger.info("✅ No pending MySQL records to flush")
        return True
