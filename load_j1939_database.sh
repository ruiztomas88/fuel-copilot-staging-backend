#!/bin/bash
# J1939 SPN Production Loader - FASE 4 Complete
# Loads complete 2000+ SPN database into production

set -e

echo "================================================"
echo "J1939 SPN Database - Production Load"
echo "================================================"

GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
DB_USER="${MYSQL_USER:-fuel_user}"
DB_PASS="${MYSQL_PASSWORD}"
DB_NAME="${MYSQL_DATABASE:-fuel_copilot}"
DB_HOST="${MYSQL_HOST:-localhost}"

echo -e "${BLUE}[INFO]${NC} Loading J1939 SPN database..."

# Step 1: Verify database connection
echo "Testing database connection..."
if ! mysql -h "$DB_HOST" -u "$DB_USER" -p"$DB_PASS" -e "SELECT 1" &>/dev/null; then
    echo "ERROR: Cannot connect to database"
    exit 1
fi
echo -e "${GREEN}✓${NC} Database connection OK"

# Step 2: Create table if not exists
echo "Creating j1939_spn_lookup table..."
mysql -h "$DB_HOST" -u "$DB_USER" -p"$DB_PASS" "$DB_NAME" <<'EOF'
CREATE TABLE IF NOT EXISTS j1939_spn_lookup (
    id INT AUTO_INCREMENT PRIMARY KEY,
    spn INT NOT NULL,
    fmi INT,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    severity ENUM('LOW', 'MEDIUM', 'HIGH', 'CRITICAL') DEFAULT 'MEDIUM',
    category VARCHAR(100),
    source VARCHAR(50) DEFAULT 'SAE_J1939',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY idx_spn_fmi (spn, fmi),
    INDEX idx_spn (spn),
    INDEX idx_category (category),
    INDEX idx_severity (severity)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
EOF
echo -e "${GREEN}✓${NC} Table created/verified"

# Step 3: Load SPN data
if [ -f "j1939_spn_insert.sql" ]; then
    echo "Loading SPN data from j1939_spn_insert.sql..."
    mysql -h "$DB_HOST" -u "$DB_USER" -p"$DB_PASS" "$DB_NAME" < j1939_spn_insert.sql
    
    # Count loaded SPNs
    COUNT=$(mysql -h "$DB_HOST" -u "$DB_USER" -p"$DB_PASS" "$DB_NAME" -sse "SELECT COUNT(*) FROM j1939_spn_lookup")
    echo -e "${GREEN}✓${NC} Loaded $COUNT SPNs into database"
else
    echo "WARNING: j1939_spn_insert.sql not found. Creating sample data..."
    
    # Load sample SPNs (common ones)
    mysql -h "$DB_HOST" -u "$DB_USER" -p"$DB_PASS" "$DB_NAME" <<'EOF'
-- Common J1939 SPNs
INSERT IGNORE INTO j1939_spn_lookup (spn, fmi, name, description, severity, category) VALUES
(84, 3, 'Wheel Speed', 'Wheel Speed Sensor - Voltage Above Normal', 'HIGH', 'BRAKE'),
(91, 4, 'Accelerator Pedal', 'Accelerator Pedal Position - Voltage Below Normal', 'MEDIUM', 'ENGINE'),
(94, 1, 'Fuel Delivery Pressure', 'Fuel Delivery Pressure - Data Valid But Below Normal', 'HIGH', 'FUEL'),
(100, 2, 'Engine Oil Pressure', 'Engine Oil Pressure - Data Erratic', 'CRITICAL', 'ENGINE'),
(102, 15, 'Intake Manifold Pressure', 'Intake Manifold Pressure - Not Responding', 'HIGH', 'ENGINE'),
(105, 16, 'Intake Air Temperature', 'Intake Air Temperature - Moderately Severe', 'MEDIUM', 'AIR'),
(110, 1, 'Engine Coolant Temperature', 'Engine Coolant Temperature - Below Normal', 'HIGH', 'COOLING'),
(111, 0, 'Coolant Level', 'Coolant Level - Above Normal', 'MEDIUM', 'COOLING'),
(158, 31, 'Battery Voltage', 'Battery Voltage - Condition Exists', 'MEDIUM', 'ELECTRICAL'),
(168, 2, 'Battery Voltage', 'Battery Voltage - Data Erratic', 'HIGH', 'ELECTRICAL'),
(174, 3, 'Fuel Temperature', 'Fuel Temperature - Voltage Above Normal', 'MEDIUM', 'FUEL'),
(190, 0, 'Engine Speed', 'Engine Speed - Data Valid But Above Normal', 'HIGH', 'ENGINE'),
(235, 9, 'Total ECU Software', 'Total ECU Software ID - Abnormal Update Rate', 'LOW', 'ELECTRICAL'),
(512, 4, 'Driver Demand', 'Driver Demand Engine Torque - Voltage Below Normal', 'MEDIUM', 'ENGINE'),
(513, 5, 'Actual Engine Torque', 'Actual Engine Torque - Current Below Normal', 'HIGH', 'ENGINE'),
(514, 11, 'Nominal Friction', 'Nominal Friction Percent Torque - Mechanical Failure', 'CRITICAL', 'ENGINE'),
(1637, 7, 'Aftertreatment DPF', 'Aftertreatment DPF Outlet Temperature - Not Responding', 'HIGH', 'EXHAUST'),
(3216, 16, 'Aftertreatment SCR', 'Aftertreatment SCR Operator Inducement - Severe', 'CRITICAL', 'EXHAUST'),
(3226, 0, 'Aftertreatment DEF', 'Aftertreatment DEF Tank Level - Above Normal', 'LOW', 'EXHAUST'),
(3251, 18, 'Aftertreatment DEF', 'Aftertreatment DEF Tank Temperature - Out of Range High', 'MEDIUM', 'EXHAUST');
EOF
    
    COUNT=$(mysql -h "$DB_HOST" -u "$DB_USER" -p"$DB_PASS" "$DB_NAME" -sse "SELECT COUNT(*) FROM j1939_spn_lookup")
    echo -e "${GREEN}✓${NC} Loaded $COUNT sample SPNs (for testing)"
    echo "NOTE: For complete 2000+ SPNs, run: python j1939_pdf_scraper.py --pdf J1939-71.pdf"
fi

# Step 4: Verify data quality
echo "Verifying data quality..."

# Check categories
echo "SPN Distribution by Category:"
mysql -h "$DB_HOST" -u "$DB_USER" -p"$DB_PASS" "$DB_NAME" -t <<'EOF'
SELECT category, COUNT(*) as count 
FROM j1939_spn_lookup 
GROUP BY category 
ORDER BY count DESC;
EOF

# Check severity
echo "SPN Distribution by Severity:"
mysql -h "$DB_HOST" -u "$DB_USER" -p"$DB_PASS" "$DB_NAME" -t <<'EOF'
SELECT severity, COUNT(*) as count 
FROM j1939_spn_lookup 
GROUP BY severity 
ORDER BY FIELD(severity, 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW');
EOF

# Test query performance
echo "Testing query performance..."
START=$(date +%s%N)
mysql -h "$DB_HOST" -u "$DB_USER" -p"$DB_PASS" "$DB_NAME" -sse "SELECT * FROM j1939_spn_lookup WHERE spn = 100 AND fmi = 2" >/dev/null
END=$(date +%s%N)
DURATION=$(( (END - START) / 1000000 ))
echo -e "${GREEN}✓${NC} Query time: ${DURATION}ms"

echo ""
echo "================================================"
echo "✅ J1939 SPN Database Load Complete"
echo "================================================"
echo "Total SPNs: $COUNT"
echo "Database: $DB_NAME"
echo "Host: $DB_HOST"
echo ""
echo "Next steps:"
echo "  1. Test DTC parser: python -c 'from dtc_parser_robust import DTCParserRobust; parser = DTCParserRobust(); print(parser.parse(\"SPN 100 FMI 2\"))'"
echo "  2. Query SPNs: mysql -u $DB_USER -p $DB_NAME -e 'SELECT * FROM j1939_spn_lookup LIMIT 10'"
echo "================================================"
