import pymysql
conn = pymysql.connect(host='localhost', port=3306, user='fuel_admin', password='FuelCopilot2025!', database='fuel_copilot')
cur = conn.cursor()

# Drop old table
cur.execute('DROP TABLE IF EXISTS fuel_metrics')

# Create with correct columns
cur.execute('''
CREATE TABLE fuel_metrics (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    timestamp_utc DATETIME NOT NULL,
    truck_id VARCHAR(20) NOT NULL,
    carrier_id VARCHAR(50) DEFAULT 'skylord',
    truck_status VARCHAR(20),
    latitude DOUBLE, longitude DOUBLE,
    speed_mph DOUBLE,
    estimated_liters DOUBLE, estimated_gallons DOUBLE, estimated_pct DOUBLE,
    sensor_pct DOUBLE, sensor_liters DOUBLE, sensor_gallons DOUBLE,
    consumption_lph DOUBLE, consumption_gph DOUBLE,
    mpg_current DOUBLE,
    rpm INT, engine_hours DOUBLE, odometer_mi DOUBLE,
    altitude_ft DOUBLE, hdop DOUBLE, coolant_temp_f DOUBLE,
    idle_method VARCHAR(30),
    drift_pct DOUBLE DEFAULT 0, drift_warning VARCHAR(10) DEFAULT 'NO',
    anchor_detected VARCHAR(10) DEFAULT 'NO', anchor_type VARCHAR(30),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY unique_truck_time (truck_id, timestamp_utc),
    INDEX idx_timestamp (timestamp_utc),
    INDEX idx_status (truck_status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
''')
print('Table recreated!')
conn.close()
