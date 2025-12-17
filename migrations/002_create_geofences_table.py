"""
Database Migration: Create geofences table
═══════════════════════════════════════════════════════════════════════════════

BUG-003 FIX: Real geofence system instead of hardcoded 30% productive idle assumption.

Creates table for storing customer/warehouse/terminal locations as polygons.

Run with: python3 migrations/002_create_geofences_table.py
"""

from sqlalchemy import text
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from database_pool import get_local_engine


CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS geofences (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    location_type ENUM('customer', 'warehouse', 'terminal', 'rest_area', 'other') NOT NULL,
    is_productive BOOLEAN NOT NULL DEFAULT TRUE,
    
    -- Center point for quick distance checks
    center_lat DECIMAL(10, 7) NOT NULL,
    center_lon DECIMAL(10, 7) NOT NULL,
    
    -- Polygon vertices (stored as JSON array of [lat, lon] pairs)
    -- Example: [[42.123, -71.456], [42.124, -71.455], ...]
    polygon_coords JSON DEFAULT NULL,
    
    -- Simple circular geofence (alternative to polygon)
    radius_meters INT DEFAULT NULL,
    
    -- Metadata
    address VARCHAR(500) DEFAULT NULL,
    city VARCHAR(100) DEFAULT NULL,
    state VARCHAR(50) DEFAULT NULL,
    customer_name VARCHAR(200) DEFAULT NULL,
    notes TEXT DEFAULT NULL,
    
    -- Timestamps
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    last_visited TIMESTAMP DEFAULT NULL,
    visit_count INT DEFAULT 0,
    
    -- Indexes for geospatial queries
    KEY idx_location (center_lat, center_lon),
    KEY idx_type (location_type),
    KEY idx_productive (is_productive),
    KEY idx_customer (customer_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
"""

# Create a spatial index if MySQL supports it
CREATE_SPATIAL_INDEX_SQL = """
CREATE INDEX idx_center_point 
ON geofences(center_lat, center_lon);
"""

# Sample data for testing
INSERT_SAMPLE_DATA_SQL = """
INSERT INTO geofences 
(name, location_type, is_productive, center_lat, center_lon, radius_meters, city, state, customer_name)
VALUES
-- Customer locations (productive)
('Walmart DC - Bentonville', 'customer', TRUE, 36.3729, -94.2088, 500, 'Bentonville', 'AR', 'Walmart'),
('Amazon Fulfillment - Phoenix', 'customer', TRUE, 33.3783, -112.0377, 600, 'Phoenix', 'AZ', 'Amazon'),
('Home Depot DC - Atlanta', 'customer', TRUE, 33.6407, -84.4277, 400, 'Atlanta', 'GA', 'Home Depot'),

-- Company terminals (productive)
('Main Terminal - Dallas', 'terminal', TRUE, 32.7767, -96.7970, 300, 'Dallas', 'TX', 'Fleet Terminal'),
('Terminal - Houston', 'terminal', TRUE, 29.7604, -95.3698, 300, 'Houston', 'TX', 'Fleet Terminal'),

-- Warehouses (productive)
('Distribution Center - Memphis', 'warehouse', TRUE, 35.1495, -90.0490, 500, 'Memphis', 'TN', 'Main Warehouse'),

-- Rest areas (non-productive but expected)
('I-40 Rest Area - Tennessee', 'rest_area', FALSE, 35.5175, -86.5804, 200, 'Nashville', 'TN', NULL)
ON DUPLICATE KEY UPDATE updated_at = NOW();
"""


def run_migration():
    """Execute the migration"""
    print("🔧 BUG-003 FIX: Creating geofences table...")
    
    engine = get_local_engine()
    if not engine:
        print("❌ ERROR: Could not connect to database")
        print("   Set MYSQL_PASSWORD environment variable")
        return False
    
    try:
        with engine.connect() as conn:
            # Create table
            print("   Creating table...")
            conn.execute(text(CREATE_TABLE_SQL))
            conn.commit()
            print("   ✅ Table created")
            
            # Create spatial index
            print("   Creating spatial index...")
            try:
                conn.execute(text(CREATE_SPATIAL_INDEX_SQL))
                conn.commit()
                print("   ✅ Spatial index created")
            except Exception as e:
                print(f"   ⚠️  Spatial index skipped (may already exist): {e}")
            
            # Insert sample data
            print("   Inserting sample geofences...")
            conn.execute(text(INSERT_SAMPLE_DATA_SQL))
            conn.commit()
            print("   ✅ Sample data inserted")
            
            # Verify
            result = conn.execute(text("""
                SELECT COUNT(*) as count 
                FROM information_schema.tables 
                WHERE table_name = 'geofences'
            """))
            count = result.scalar()
            
            if count > 0:
                # Count geofences
                result = conn.execute(text("SELECT COUNT(*) FROM geofences"))
                geofence_count = result.scalar()
                
                print(f"\n✅ Migration completed successfully!")
                print(f"   Table: geofences")
                print(f"   Sample geofences: {geofence_count}")
                print(f"   Columns: name, location_type, center_lat, center_lon, radius_meters, ...")
                return True
            else:
                print("\n❌ Migration failed - table not found")
                return False
                
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)
