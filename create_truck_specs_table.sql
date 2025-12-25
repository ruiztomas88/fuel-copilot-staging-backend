-- Tabla de especificaciones de camiones basada en VIN decode
-- Esto permite MPG baselines más precisos por modelo/año

CREATE TABLE IF NOT EXISTS truck_specs (
    truck_id VARCHAR(20) PRIMARY KEY,
    vin VARCHAR(17) UNIQUE NOT NULL,
    year INT NOT NULL,
    make VARCHAR(50) NOT NULL,
    model VARCHAR(50) NOT NULL,
    baseline_mpg_loaded DECIMAL(3,1) NOT NULL COMMENT 'MPG esperado con carga (loaded 44k lbs)',
    baseline_mpg_empty DECIMAL(3,1) NOT NULL COMMENT 'MPG esperado sin carga (empty)',
    notes VARCHAR(255) DEFAULT NULL COMMENT 'Motor type, etc',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_make_model (make, model),
    INDEX idx_year (year)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Truck specifications from VIN decode for better MPG validation';

-- Insertar datos decodificados de VINs
INSERT INTO truck_specs (truck_id, vin, year, make, model, baseline_mpg_loaded, baseline_mpg_empty, notes) VALUES
('VD3579', '1FUJGLDR4GLGX3579', 2016, 'Freightliner', 'Cascadia', 6.5, 8.5, 'DD15'),
('JC1282', '3AKJHHDR6LSLL1282', 2020, 'Kenworth', 'T680', 7.0, 9.0, 'Paccar MX-13'),
('JC9352', '3AKJHHDR6NSNJ9352', 2022, 'Kenworth', 'T680', 7.5, 9.5, 'Paccar MX-13 (newer)'),
('NQ6975', '1FUJGLDR6DSBW6975', 2013, 'Freightliner', 'Cascadia', 6.0, 7.5, 'DD13/DD15 older'),
('GP9677', '1XKYDP9XBHJ129677', 2017, 'Kenworth', 'T680', 6.8, 8.8, 'Paccar MX-13'),
('GS5030', '1FUJGLDR3JLJK5030', 2018, 'Freightliner', 'Cascadia', 7.0, 8.8, 'DD15'),
('JB8004', '3HSDZAPR6KN128004', 2019, 'International', 'LT', 6.5, 8.0, 'Cummins X15'),
('FM3679', '3HSDZAPR3KN763679', 2019, 'International', 'LT', 6.5, 8.0, 'Cummins X15'),
('FM9838', '3HSDZAPR0LN319838', 2020, 'International', 'LT', 6.8, 8.3, 'Cummins X15'),
('JB6858', '3HSDZAPRXLN296858', 2020, 'International', 'LT', 6.8, 8.3, 'Cummins X15'),
('JP3281', '1FUJA6CKX9DAC1694', 2009, 'Freightliner', 'Columbia', 5.5, 6.5, 'Detroit Diesel older'),
('JR7099', '1FUJCRCK66PW87099', 2006, 'Freightliner', 'Century', 5.0, 6.0, 'Very old DD'),
('RA9250', '3AKJGLBG7FSGM9250', 2015, 'Kenworth', 'T680', 6.5, 8.2, 'Paccar MX-13'),
('RH1522', '4V4NC9EGXGN961522', 2016, 'Volvo', 'VNL', 6.8, 8.5, 'Volvo D13'),
('BV6395', '3AKJGLBG8ESFV6395', 2014, 'Kenworth', 'T680', 6.3, 8.0, 'Paccar MX-13'),
('CO0681', '3AKJGLDR3KSKV0681', 2019, 'Kenworth', 'T680', 7.0, 9.0, 'Paccar MX-13'),
('DR6664', '3HSDJAPRXHN506664', 2017, 'International', 'LT', 6.5, 8.0, 'Cummins X15'),
('DO9356', '3AKJGLDR8ESFK9356', 2014, 'Kenworth', 'T680', 6.3, 8.0, 'Paccar MX-13'),
('DO9693', '3AKJHHDR3JSKB9693', 2018, 'Kenworth', 'T680', 6.8, 8.8, 'Paccar MX-13'),
('FS7166', '3AKJGLD51GSFP7166', 2016, 'Kenworth', 'T680', 6.5, 8.5, 'Paccar MX-13'),
('MA8159', '1XPHDP9X2DD188159', 2013, 'Peterbilt', '579', 6.0, 7.5, 'Paccar MX-13'),
('PC1280', '1XPBDP9X0KD601280', 2019, 'Peterbilt', '579', 7.0, 9.0, 'Paccar MX-13'),
('RR3094', '1XKFDP9X1DJ363094', 2013, 'Kenworth', 'T680', 6.0, 7.8, 'Paccar MX-13'),
('RT9127', '1XPBDP9X1LD689127', 2020, 'Peterbilt', '579', 7.2, 9.2, 'Paccar MX-13'),
('SG5760', '1FUJA6CK87LY55760', 2008, 'Freightliner', 'Columbia', 5.2, 6.2, 'Detroit Diesel older'),
('YM6023', '4V4NC9EHXFN180586', 2015, 'Volvo', 'VNL', 6.5, 8.2, 'Volvo D13'),
('MJ9547', '3AKJHHDR8PSNV9547', 2023, 'Kenworth', 'T680', 7.8, 10.0, 'Paccar MX-13 latest'),
('FM3363', '3HSDZAPR4KN453363', 2019, 'International', 'LT', 6.5, 8.0, 'Cummins X15'),
('LC6799', '3AKJGLDR0HSHZ6799', 2017, 'Kenworth', 'T680', 6.8, 8.8, 'Paccar MX-13'),
('RC6625', '1XKYDP9X9MJ436625', 2021, 'Kenworth', 'T680', 7.3, 9.3, 'Paccar MX-13'),
('FF7702', '3HSDZAPRXLN267702', 2020, 'International', 'LT', 6.8, 8.3, 'Cummins X15'),
('OG2033', '1XKYD49XXHJ162033', 2017, 'Kenworth', 'T680', 6.8, 8.8, 'Paccar MX-13'),
('OS3717', '1XP7D49X3AD793717', 2010, 'Peterbilt', '579', 5.8, 7.0, 'Paccar MX older'),
('MR7679', '1FUJGLDR3HLJA7679', 2017, 'Freightliner', 'Cascadia', 6.8, 8.8, 'DD15'),
('OM7769', '1XKADU9X06R137769', 2006, 'Kenworth', 'T600', 5.0, 6.0, 'Very old Cummins'),
('LH1141', '3AKJGLDR1HSHF1141', 2017, 'Kenworth', 'T680', 6.8, 8.8, 'Paccar MX-13'),
('NP1082', '3AKJGLDR3LSLP1082', 2020, 'Kenworth', 'T680', 7.0, 9.0, 'Paccar MX-13')
ON DUPLICATE KEY UPDATE
    year = VALUES(year),
    make = VALUES(make),
    model = VALUES(model),
    baseline_mpg_loaded = VALUES(baseline_mpg_loaded),
    baseline_mpg_empty = VALUES(baseline_mpg_empty),
    notes = VALUES(notes),
    updated_at = CURRENT_TIMESTAMP;

-- Verificar datos insertados
SELECT 
    COUNT(*) as total_trucks,
    MIN(year) as oldest_year,
    MAX(year) as newest_year,
    COUNT(DISTINCT make) as num_makes,
    ROUND(AVG(baseline_mpg_loaded), 1) as avg_mpg_loaded,
    ROUND(AVG(baseline_mpg_empty), 1) as avg_mpg_empty
FROM truck_specs;

-- Ver resumen por fabricante
SELECT 
    make,
    COUNT(*) as count,
    ROUND(AVG(baseline_mpg_loaded), 1) as avg_loaded,
    ROUND(AVG(baseline_mpg_empty), 1) as avg_empty,
    MIN(year) as oldest,
    MAX(year) as newest
FROM truck_specs
GROUP BY make
ORDER BY count DESC;
