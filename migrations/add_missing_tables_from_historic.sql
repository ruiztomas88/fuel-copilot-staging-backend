-- ============================================
-- AGREGAR TABLAS FALTANTES DE BASE HISTÓRICA
-- ============================================
-- Ejecutar: mysql -u fuel_admin -pFuelCopilot2025! fuel_copilot < add_missing_tables_from_historic.sql
-- ============================================

USE fuel_copilot;

-- ============================================
-- COMMAND CENTER TABLES (7 tablas)
-- ============================================

CREATE TABLE IF NOT EXISTS cc_algorithm_state (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    truck_id VARCHAR(20) NOT NULL,
    algorithm_name VARCHAR(50) NOT NULL,
    state_data JSON COMMENT 'Estado del algoritmo en formato JSON',
    last_update DATETIME NOT NULL,
    confidence_score DECIMAL(5,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    INDEX idx_truck_algorithm (truck_id, algorithm_name),
    INDEX idx_last_update (last_update)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Estado de algoritmos del Command Center';

CREATE TABLE IF NOT EXISTS cc_anomaly_history (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    timestamp_utc DATETIME NOT NULL,
    truck_id VARCHAR(20) NOT NULL,
    anomaly_type VARCHAR(50) NOT NULL COMMENT 'FUEL_DRIFT, ENGINE_HEALTH, GPS_QUALITY, etc.',
    severity VARCHAR(20) COMMENT 'LOW, MEDIUM, HIGH, CRITICAL',
    description TEXT,
    metrics JSON COMMENT 'Métricas relacionadas con la anomalía',
    resolved TINYINT(1) DEFAULT 0,
    resolved_at DATETIME,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_truck_time (truck_id, timestamp_utc),
    INDEX idx_anomaly_type (anomaly_type),
    INDEX idx_severity (severity),
    INDEX idx_resolved (resolved)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Historial de anomalías detectadas';

CREATE TABLE IF NOT EXISTS cc_correlation_events (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    timestamp_utc DATETIME NOT NULL,
    truck_id VARCHAR(20) NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    correlated_events JSON COMMENT 'Array de eventos correlacionados',
    correlation_score DECIMAL(5,2),
    root_cause TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_truck_time (truck_id, timestamp_utc),
    INDEX idx_event_type (event_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Eventos correlacionados del sistema';

CREATE TABLE IF NOT EXISTS cc_def_history (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    timestamp_utc DATETIME NOT NULL,
    truck_id VARCHAR(20) NOT NULL,
    def_level_pct DECIMAL(5,2),
    def_consumption_rate DECIMAL(6,3) COMMENT 'Tasa de consumo DEF (gal/hr)',
    miles_to_empty INT COMMENT 'Millas estimadas hasta vacío',
    refill_recommended TINYINT(1) DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_truck_time (truck_id, timestamp_utc),
    INDEX idx_refill (refill_recommended)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Historial de DEF (Diesel Exhaust Fluid)';

CREATE TABLE IF NOT EXISTS cc_maintenance_events (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    timestamp_utc DATETIME NOT NULL,
    truck_id VARCHAR(20) NOT NULL,
    maintenance_type VARCHAR(50) NOT NULL COMMENT 'OIL_CHANGE, FILTER, INSPECTION, etc.',
    component VARCHAR(100),
    severity VARCHAR(20),
    miles_since_last INT,
    hours_since_last DECIMAL(10,2),
    recommended_action TEXT,
    due_date DATE,
    completed TINYINT(1) DEFAULT 0,
    completed_at DATETIME,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_truck_time (truck_id, timestamp_utc),
    INDEX idx_type (maintenance_type),
    INDEX idx_completed (completed),
    INDEX idx_due_date (due_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Eventos de mantenimiento programado';

CREATE TABLE IF NOT EXISTS cc_risk_history (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    timestamp_utc DATETIME NOT NULL,
    truck_id VARCHAR(20) NOT NULL,
    risk_type VARCHAR(50) NOT NULL COMMENT 'BREAKDOWN, FUEL_THEFT, EFFICIENCY, etc.',
    risk_score DECIMAL(5,2) COMMENT 'Score de riesgo 0-100',
    probability DECIMAL(5,2) COMMENT 'Probabilidad 0-100%',
    impact_level VARCHAR(20) COMMENT 'LOW, MEDIUM, HIGH, CRITICAL',
    contributing_factors JSON,
    mitigation_actions TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_truck_time (truck_id, timestamp_utc),
    INDEX idx_risk_type (risk_type),
    INDEX idx_risk_score (risk_score DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Historial de análisis de riesgos';

CREATE TABLE IF NOT EXISTS command_center_config (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    config_key VARCHAR(100) NOT NULL UNIQUE,
    config_value TEXT,
    data_type VARCHAR(20) COMMENT 'STRING, NUMBER, BOOLEAN, JSON',
    description TEXT,
    category VARCHAR(50) COMMENT 'THRESHOLDS, ALERTS, ALGORITHMS, etc.',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    INDEX idx_category (category),
    INDEX idx_key (config_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Configuración del Command Center';

-- ============================================
-- ENGINE HEALTH TABLES (5 tablas)
-- ============================================

CREATE TABLE IF NOT EXISTS engine_health_alerts (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    timestamp_utc DATETIME NOT NULL,
    truck_id VARCHAR(20) NOT NULL,
    alert_type VARCHAR(50) NOT NULL COMMENT 'TEMP_HIGH, PRESSURE_LOW, RPM_ABNORMAL, etc.',
    severity VARCHAR(20) COMMENT 'WARNING, CRITICAL, EMERGENCY',
    parameter_name VARCHAR(50),
    current_value DECIMAL(10,2),
    threshold_value DECIMAL(10,2),
    message TEXT,
    acknowledged TINYINT(1) DEFAULT 0,
    acknowledged_at DATETIME,
    acknowledged_by VARCHAR(100),
    resolved TINYINT(1) DEFAULT 0,
    resolved_at DATETIME,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_truck_time (truck_id, timestamp_utc),
    INDEX idx_alert_type (alert_type),
    INDEX idx_severity (severity),
    INDEX idx_resolved (resolved)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Alertas de salud del motor';

CREATE TABLE IF NOT EXISTS engine_health_baselines (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    truck_id VARCHAR(20) NOT NULL,
    parameter_name VARCHAR(50) NOT NULL,
    baseline_value DECIMAL(10,2),
    std_deviation DECIMAL(10,2),
    min_value DECIMAL(10,2),
    max_value DECIMAL(10,2),
    sample_count INT,
    last_calibration DATETIME,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    UNIQUE KEY unique_truck_parameter (truck_id, parameter_name),
    INDEX idx_truck (truck_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Líneas base de parámetros del motor';

CREATE TABLE IF NOT EXISTS engine_health_notifications (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    timestamp_utc DATETIME NOT NULL,
    truck_id VARCHAR(20) NOT NULL,
    notification_type VARCHAR(50) NOT NULL,
    title VARCHAR(255),
    message TEXT,
    priority VARCHAR(20) COMMENT 'LOW, MEDIUM, HIGH, URGENT',
    sent TINYINT(1) DEFAULT 0,
    sent_at DATETIME,
    delivery_method VARCHAR(50) COMMENT 'EMAIL, SMS, PUSH, SLACK',
    recipients JSON COMMENT 'Array de destinatarios',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_truck_time (truck_id, timestamp_utc),
    INDEX idx_sent (sent),
    INDEX idx_priority (priority)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Notificaciones de salud del motor';

CREATE TABLE IF NOT EXISTS engine_health_snapshots (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    timestamp_utc DATETIME NOT NULL,
    truck_id VARCHAR(20) NOT NULL,
    health_score DECIMAL(5,2) COMMENT 'Score general de salud 0-100',
    oil_pressure_psi DECIMAL(5,1),
    oil_temp_f DECIMAL(5,1),
    coolant_temp_f DECIMAL(5,2),
    boost_pressure_psi DOUBLE,
    exhaust_temp_f DOUBLE,
    battery_voltage DECIMAL(4,2),
    engine_load_pct DECIMAL(5,2),
    rpm INT,
    odometer_mi DOUBLE,
    engine_hours DOUBLE,
    active_dtc_count INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_truck_time (truck_id, timestamp_utc),
    INDEX idx_health_score (health_score DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Snapshots de salud del motor';

CREATE TABLE IF NOT EXISTS engine_health_thresholds (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    truck_id VARCHAR(20),
    parameter_name VARCHAR(50) NOT NULL,
    warning_low DECIMAL(10,2),
    warning_high DECIMAL(10,2),
    critical_low DECIMAL(10,2),
    critical_high DECIMAL(10,2),
    is_global TINYINT(1) DEFAULT 0 COMMENT '1=aplica a todos los trucks, 0=específico',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    UNIQUE KEY unique_truck_parameter (truck_id, parameter_name),
    INDEX idx_truck (truck_id),
    INDEX idx_global (is_global)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Umbrales configurables de salud del motor';

-- ============================================
-- PREDICTIVE MAINTENANCE TABLES (3 tablas)
-- ============================================

CREATE TABLE IF NOT EXISTS pm_predictions (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    timestamp_utc DATETIME NOT NULL,
    truck_id VARCHAR(20) NOT NULL,
    component VARCHAR(100) NOT NULL COMMENT 'ENGINE, TRANSMISSION, BRAKES, etc.',
    failure_probability DECIMAL(5,2) COMMENT 'Probabilidad de falla 0-100%',
    days_to_failure INT COMMENT 'Días estimados hasta falla',
    confidence_level DECIMAL(5,2) COMMENT 'Nivel de confianza 0-100%',
    contributing_factors JSON,
    recommended_action TEXT,
    severity VARCHAR(20),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_truck_time (truck_id, timestamp_utc),
    INDEX idx_component (component),
    INDEX idx_probability (failure_probability DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Predicciones de mantenimiento';

CREATE TABLE IF NOT EXISTS pm_sensor_daily_avg (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    date_local DATE NOT NULL,
    truck_id VARCHAR(20) NOT NULL,
    trans_temp_f_avg DECIMAL(6,2),
    oil_pressure_psi_avg DECIMAL(6,2),
    coolant_temp_f_avg DECIMAL(6,2),
    exhaust_temp_f_avg DECIMAL(7,2),
    battery_voltage_avg DECIMAL(5,2),
    engine_load_pct_avg DECIMAL(5,2),
    samples_count INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE KEY unique_truck_date (truck_id, date_local),
    INDEX idx_date (date_local)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Promedios diarios de sensores PM';

CREATE TABLE IF NOT EXISTS pm_sensor_history (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    timestamp_utc DATETIME NOT NULL,
    truck_id VARCHAR(20) NOT NULL,
    trans_temp_f DECIMAL(5,2),
    fuel_temp_f DECIMAL(5,2),
    intercooler_temp_f DECIMAL(5,2),
    intake_press_kpa DECIMAL(6,2),
    retarder_level DECIMAL(5,2),
    oil_pressure_psi DECIMAL(5,1),
    boost_pressure_psi DOUBLE,
    exhaust_temp_f DOUBLE,
    def_level_pct DECIMAL(5,2),
    battery_voltage DECIMAL(4,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_truck_time (truck_id, timestamp_utc)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Historial de sensores de mantenimiento predictivo';

-- ============================================
-- OTRAS TABLAS IMPORTANTES (7 tablas)
-- ============================================

CREATE TABLE IF NOT EXISTS gps_quality_events (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    timestamp_utc DATETIME NOT NULL,
    truck_id VARCHAR(20) NOT NULL,
    sats INT COMMENT 'Número de satélites',
    hdop DOUBLE COMMENT 'Horizontal dilution of precision',
    quality_score DECIMAL(5,2) COMMENT 'Score de calidad GPS 0-100',
    quality_level VARCHAR(20) COMMENT 'EXCELLENT, GOOD, FAIR, POOR',
    latitude DOUBLE,
    longitude DOUBLE,
    altitude_ft DOUBLE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_truck_time (truck_id, timestamp_utc),
    INDEX idx_quality (quality_level)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Eventos de calidad de GPS';

CREATE TABLE IF NOT EXISTS j1939_spn_lookup (
    spn INT PRIMARY KEY COMMENT 'Suspect Parameter Number',
    name VARCHAR(255) NOT NULL,
    description TEXT,
    units VARCHAR(50),
    data_type VARCHAR(50),
    system_type VARCHAR(50) COMMENT 'ENGINE, TRANSMISSION, BRAKE, etc.',
    severity_default VARCHAR(20) COMMENT 'Severidad por defecto',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_system (system_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Lookup de códigos SPN J1939';

CREATE TABLE IF NOT EXISTS maintenance_alerts (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    timestamp_utc DATETIME NOT NULL,
    truck_id VARCHAR(20) NOT NULL,
    alert_type VARCHAR(50) NOT NULL,
    component VARCHAR(100),
    severity VARCHAR(20),
    odometer_mi DOUBLE,
    engine_hours DOUBLE,
    message TEXT,
    recommended_date DATE,
    acknowledged TINYINT(1) DEFAULT 0,
    completed TINYINT(1) DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_truck_time (truck_id, timestamp_utc),
    INDEX idx_completed (completed),
    INDEX idx_severity (severity)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Alertas de mantenimiento';

CREATE TABLE IF NOT EXISTS maintenance_predictions (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    truck_id VARCHAR(20) NOT NULL,
    prediction_type VARCHAR(50) NOT NULL,
    component VARCHAR(100),
    current_value DECIMAL(10,2),
    predicted_failure_date DATE,
    confidence DECIMAL(5,2),
    recommendation TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    INDEX idx_truck (truck_id),
    INDEX idx_failure_date (predicted_failure_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Predicciones de mantenimiento';

CREATE TABLE IF NOT EXISTS telemetry_data (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    timestamp_utc DATETIME NOT NULL,
    truck_id VARCHAR(20) NOT NULL,
    data_type VARCHAR(50) NOT NULL,
    data_payload JSON COMMENT 'Payload de datos en formato JSON',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_truck_time (truck_id, timestamp_utc),
    INDEX idx_data_type (data_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Datos de telemetría genéricos';

CREATE TABLE IF NOT EXISTS trips (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    truck_id VARCHAR(20) NOT NULL,
    start_time DATETIME NOT NULL,
    end_time DATETIME,
    start_latitude DOUBLE,
    start_longitude DOUBLE,
    end_latitude DOUBLE,
    end_longitude DOUBLE,
    distance_mi DOUBLE,
    duration_minutes INT,
    avg_speed_mph DECIMAL(5,2),
    max_speed_mph DECIMAL(5,2),
    fuel_consumed_gal DECIMAL(8,2),
    avg_mpg DECIMAL(5,2),
    idle_time_minutes INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_truck_start (truck_id, start_time),
    INDEX idx_start_time (start_time),
    INDEX idx_end_time (end_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Viajes y rutas';

CREATE TABLE IF NOT EXISTS truck_health_history (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    timestamp_utc DATETIME NOT NULL,
    truck_id VARCHAR(20) NOT NULL,
    overall_health_score DECIMAL(5,2) COMMENT 'Score general 0-100',
    engine_health_score DECIMAL(5,2),
    fuel_system_score DECIMAL(5,2),
    maintenance_score DECIMAL(5,2),
    efficiency_score DECIMAL(5,2),
    active_issues_count INT DEFAULT 0,
    critical_issues_count INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_truck_time (truck_id, timestamp_utc),
    INDEX idx_health_score (overall_health_score DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Historial de salud general del camión';

CREATE TABLE IF NOT EXISTS voltage_events (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    timestamp_utc DATETIME NOT NULL,
    truck_id VARCHAR(20) NOT NULL,
    battery_voltage DECIMAL(4,2),
    voltage_status VARCHAR(20) COMMENT 'NORMAL, LOW, CRITICAL, HIGH',
    pwr_int DECIMAL(4,2) COMMENT 'Voltaje interno',
    pwr_ext DECIMAL(4,2) COMMENT 'Voltaje externo',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_truck_time (truck_id, timestamp_utc),
    INDEX idx_status (voltage_status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Eventos de voltaje de batería';

-- ============================================
-- Verificar tablas creadas
-- ============================================
SELECT 'Tablas agregadas exitosamente!' AS status;
SHOW TABLES;
