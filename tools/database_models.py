"""
SQLAlchemy Models for Fuel Copilot Database
Defines ORM models for fuel_metrics and related tables

🔒 SECURITY:
- Credentials loaded from environment variables
- No hardcoded passwords
"""

import os
from datetime import datetime
from sqlalchemy import (
    Column, BigInteger, Integer, String, Float, DateTime, 
    Boolean, Text, create_engine, Index
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

Base = declarative_base()

# Database connection configuration
def get_db_config():
    """Get database configuration from environment variables"""
    return {
        "host": os.getenv("DB_HOST", os.getenv("MYSQL_HOST", "localhost")),
        "port": int(os.getenv("DB_PORT", os.getenv("MYSQL_PORT", "3306"))),
        "user": os.getenv("DB_USER", os.getenv("MYSQL_USER", "fuel_admin")),
        "password": os.getenv("DB_PASS", os.getenv("MYSQL_PASSWORD", "")),
        "database": os.getenv("DB_NAME", os.getenv("MYSQL_DATABASE", "fuel_copilot")),
    }


# SQLAlchemy engine (singleton)
_engine = None
_Session = None


def get_engine():
    """Get or create SQLAlchemy engine"""
    global _engine
    if _engine is None:
        config = get_db_config()
        connection_string = (
            f"mysql+pymysql://{config['user']}:{config['password']}"
            f"@{config['host']}:{config['port']}/{config['database']}"
            f"?charset=utf8mb4"
        )
        _engine = create_engine(
            connection_string,
            pool_pre_ping=True,
            pool_recycle=3600,
            pool_size=10,
            max_overflow=5,
        )
    return _engine


def get_session():
    """Get a new database session"""
    global _Session
    if _Session is None:
        engine = get_engine()
        _Session = sessionmaker(bind=engine)
    return _Session()


class FuelMetrics(Base):
    """
    Main fuel metrics table - stores real-time truck data
    Maps to: fuel_metrics table
    """
    __tablename__ = 'fuel_metrics'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    timestamp_utc = Column(DateTime, nullable=False)
    truck_id = Column(String(20), nullable=False)
    unit_id = Column(BigInteger)
    carrier_id = Column(String(50), default='skylord')
    
    # Data freshness
    data_age_min = Column(Float)
    epoch_time = Column(BigInteger)  # Unix timestamp
    
    # Location & Status
    truck_status = Column(String(20))  # MOVING, STOPPED, IDLE, OFFLINE
    latitude = Column(Float)
    longitude = Column(Float)
    speed_mph = Column(Float)
    
    # Fuel Data - Estimated (Kalman Filter)
    estimated_liters = Column(Float)
    estimated_gallons = Column(Float)
    estimated_pct = Column(Float)
    
    # Fuel Data - Raw Sensor
    sensor_pct = Column(Float)
    sensor_liters = Column(Float)
    sensor_gallons = Column(Float)
    sensor_ema_pct = Column(Float)
    
    # Fuel Data - Comparison
    ecu_level_pct = Column(Float)
    model_level_pct = Column(Float)
    
    # Kalman Filter
    kalman_estimate = Column(Float)
    kalman_uncertainty = Column(Float)
    confidence_indicator = Column(String(20))  # HIGH, MEDIUM, LOW
    
    # Consumption
    consumption_lph = Column(Float)
    consumption_gph = Column(Float)
    consumption_rate = Column(Float)
    mpg_current = Column(Float)
    mpg_avg_24h = Column(Float)
    
    # Engine Data
    rpm = Column(Integer)
    engine_hours = Column(Float)
    odometer_mi = Column(Float)
    odom_delta_mi = Column(Float)
    
    # Environment
    hdop = Column(Float)
    altitude_ft = Column(Float)
    coolant_temp_f = Column(Float)
    
    # Idle Detection
    idle_method = Column(String(30))
    idle_mode = Column(String(30))
    idle_duration_minutes = Column(Integer)
    
    # Drift Detection
    drift_pct = Column(Float)
    drift_warning = Column(String(10))  # YES/NO
    
    # Anchors
    anchor_detected = Column(String(10))  # YES/NO
    anchor_type = Column(String(20))
    anchor_fuel_level = Column(Float)
    static_anchors_total = Column(Integer)
    micro_anchors_total = Column(Integer)
    
    # Refuel Detection
    refuel_detected = Column(Boolean, default=False)
    refuel_amount = Column(Float)
    refuel_gallons = Column(Float)
    refuel_events_total = Column(Integer, default=0)
    
    # Flags & Metadata
    flags = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Indexes defined via __table_args__
    __table_args__ = (
        Index('idx_truck_time', 'truck_id', 'timestamp_utc'),
        Index('idx_timestamp', 'timestamp_utc'),
        Index('idx_carrier', 'carrier_id'),
        Index('idx_status', 'truck_status'),
    )


class RefuelEvent(Base):
    """
    Refuel events table - stores detected refueling events
    Maps to: refuel_events table
    """
    __tablename__ = 'refuel_events'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    timestamp_utc = Column(DateTime, nullable=False)
    truck_id = Column(String(20), nullable=False)
    unit_id = Column(BigInteger)
    carrier_id = Column(String(50), default='skylord')
    
    # Refuel Details
    fuel_before = Column(Float)
    fuel_after = Column(Float)
    gallons_added = Column(Float)
    refuel_type = Column(String(30))  # NORMAL, GAP_DETECTED, CONSECUTIVE
    
    # Location
    latitude = Column(Float)
    longitude = Column(Float)
    
    # Validation
    confidence = Column(Float)
    validated = Column(Boolean, default=False)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_refuel_truck_time', 'truck_id', 'timestamp_utc'),
        Index('idx_refuel_timestamp', 'timestamp_utc'),
    )


class TruckHistory(Base):
    """
    Truck history table - stores historical snapshots
    Maps to: truck_history table
    """
    __tablename__ = 'truck_history'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False)
    truck_id = Column(String(20), nullable=False)
    unit_id = Column(BigInteger)
    
    # Status
    status = Column(String(20))
    fuel_level = Column(Float)
    fuel_percent = Column(Float)
    
    # Location
    latitude = Column(Float)
    longitude = Column(Float)
    speed = Column(Float)
    
    # Engine
    odometer = Column(Float)
    engine_hours = Column(Float)
    
    # Consumption
    mpg = Column(Float)
    consumption_gph = Column(Float)
    
    __table_args__ = (
        Index('idx_history_truck_time', 'truck_id', 'timestamp'),
        Index('idx_history_timestamp', 'timestamp'),
    )


# Create tables if they don't exist
def init_db():
    """Initialize database tables"""
    engine = get_engine()
    Base.metadata.create_all(engine)
    print("✅ Database tables initialized")


if __name__ == "__main__":
    # Test database connection
    try:
        session = get_session()
        print("✅ Database connection successful")
        session.close()
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
