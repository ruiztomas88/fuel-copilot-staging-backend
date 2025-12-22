import pymysql
from config import get_local_db_config

conn = pymysql.connect(**get_local_db_config())
cur = conn.cursor()
cur.execute('''
CREATE TABLE IF NOT EXISTS fuel_metrics (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    timestamp_utc DATETIME NOT NULL,
    truck_id VARCHAR(20) NOT NULL,
    carrier_id VARCHAR(50) DEFAULT 'skylord',
    truck_status VARCHAR(20),
    latitude DOUBLE, longitude DOUBLE, speed DOUBLE,
    fuel_level_raw DOUBLE, fuel_level_filtered DOUBLE,
    fuel_capacity INT, fuel_percent DOUBLE,
    consumption_gph DOUBLE, consumption_rate DOUBLE,
    mpg_current DOUBLE, mpg_avg_24h DOUBLE,
    engine_rpm INT, engine_hours DOUBLE, odometer DOUBLE,
    mileage_delta DOUBLE, idle_method VARCHAR(30), idle_duration_minutes INT,
    kalman_estimate DOUBLE, kalman_uncertainty DOUBLE,
    anchor_type VARCHAR(20), anchor_fuel_level DOUBLE,
    refuel_detected TINYINT(1) DEFAULT 0, refuel_amount DOUBLE,
    refuel_events_total INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY unique_truck_time (truck_id, timestamp_utc),
    INDEX idx_timestamp (timestamp_utc),
    INDEX idx_status (truck_status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
''')
print('Table fuel_metrics created!')
conn.close()
