"""
Sync units_map table with tanks.yaml
Fixes incorrect unit_id mappings that cause missing sensor data

PROBLEM:
- units_map has outdated/incorrect unit_id values
- wialon_reader loads truck mapping from units_map
- Query uses wrong unit_id → no sensor data returned

SOLUTION:
- Read correct unit_id from tanks.yaml
- Update units_map table with correct values
"""
import os

import mysql.connector
import yaml
from typing import Dict, List, Tuple
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_tanks_yaml(path: str = "tanks.yaml") -> Dict:
    """Load tanks.yaml configuration"""
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def get_units_map_data(conn) -> Dict[str, int]:
    """Get current units_map table data"""
    cursor = conn.cursor(dictionary=True, buffered=True)
    cursor.execute("SELECT beyondId, unit FROM units_map")
    return {row['beyondId']: row['unit'] for row in cursor.fetchall()}


def compare_mappings(yaml_trucks: Dict, db_mapping: Dict) -> Tuple[List, List]:
    """
    Compare tanks.yaml with units_map
    
    Returns:
        (mismatches, missing)
        mismatches: [(truck_id, yaml_unit_id, db_unit_id), ...]
        missing: [(truck_id, yaml_unit_id), ...]
    """
    mismatches = []
    missing = []
    
    for truck_id, truck_config in yaml_trucks.items():
        yaml_unit_id = truck_config.get('unit_id')
        db_unit_id = db_mapping.get(truck_id)
        
        if db_unit_id is None:
            missing.append((truck_id, yaml_unit_id))
        elif yaml_unit_id != db_unit_id:
            mismatches.append((truck_id, yaml_unit_id, db_unit_id))
    
    return mismatches, missing


def clean_duplicates(conn, dry_run: bool = True):
    """
    Remove duplicate rows from units_map, keeping only correct unit_id
    
    Args:
        conn: MySQL connection  
        dry_run: If True, only show what would be deleted
        
    Returns:
        Number of rows that would be/were deleted
    """
    cursor = conn.cursor(dictionary=True, buffered=True)
    
    # Find duplicates
    cursor.execute("""
        SELECT beyondId, COUNT(*) as count
        FROM units_map
        GROUP BY beyondId
        HAVING COUNT(*) > 1
    """)
    duplicates = cursor.fetchall()
    
    if not duplicates:
        logger.info("✅ No duplicates found in units_map")
        return 0
    
    logger.warning(f"🔧 Found {len(duplicates)} trucks with duplicate rows")
    
    total_deleted = 0
    
    for dup in duplicates:
        truck_id = dup['beyondId']
        count = dup['count']
        
        # Get all rows for this truck
        cursor.execute(
            "SELECT beyondId, unit, fuel_capacity FROM units_map WHERE beyondId = %s",
            (truck_id,)
        )
        rows = cursor.fetchall()
        
        # Count occurrences of each unit_id
        unit_counts = {}
        for row in rows:
            unit_id = row['unit']
            unit_counts[unit_id] = unit_counts.get(unit_id, 0) + 1
        
        # The correct unit_id is the one that appears most often
        correct_unit_id = max(unit_counts, key=unit_counts.get)
        
        logger.warning(f"  {truck_id}: {count} rows, keeping unit={correct_unit_id}")
        
        if not dry_run:
            # Delete ALL rows for this truck
            cursor.execute("DELETE FROM units_map WHERE beyondId = %s", (truck_id,))
            deleted = cursor.rowcount
            
            # Insert ONE correct row
            cursor.execute(
                "INSERT INTO units_map (beyondId, unit, fuel_capacity) VALUES (%s, %s, %s)",
                (truck_id, correct_unit_id, 200)  # Default capacity
            )
            
            total_deleted += (deleted - 1)  # -1 because we re-inserted one
            logger.info(f"    ✅ Deleted {deleted} rows, re-inserted 1")
    
    if not dry_run:
        conn.commit()
    
    return total_deleted


def fix_units_map(conn, yaml_trucks: Dict, dry_run: bool = True):
    """
    Update units_map with correct unit_id from tanks.yaml
    
    Args:
        conn: MySQL connection
        yaml_trucks: Truck configuration from tanks.yaml
        dry_run: If True, only show changes without applying them
    """
    cursor = conn.cursor(buffered=True)
    
    # Get current mapping
    db_mapping = get_units_map_data(conn)
    
    # Find discrepancies
    mismatches, missing = compare_mappings(yaml_trucks, db_mapping)
    
    logger.info("=" * 70)
    logger.info(f"UNITS_MAP SYNC - {'DRY RUN' if dry_run else 'LIVE UPDATE'}")
    logger.info("=" * 70)
    
    if mismatches:
        logger.warning(f"\n🔧 Found {len(mismatches)} unit_id mismatches:")
        for truck_id, yaml_id, db_id in mismatches:
            logger.warning(f"  {truck_id}: DB has {db_id}, should be {yaml_id}")
            
            if not dry_run:
                # Update the incorrect unit_id
                cursor.execute(
                    "UPDATE units_map SET unit = %s WHERE beyondId = %s",
                    (yaml_id, truck_id)
                )
                logger.info(f"    ✅ Updated {truck_id} to {yaml_id}")
    
    if missing:
        logger.warning(f"\n➕ Found {len(missing)} trucks missing from units_map:")
        for truck_id, yaml_id in missing:
            logger.warning(f"  {truck_id}: unit_id {yaml_id}")
            
            if not dry_run:
                # Get capacity from yaml
                capacity = yaml_trucks[truck_id].get('capacity_gallons', 200)
                
                # Insert missing truck
                cursor.execute(
                    "INSERT INTO units_map (beyondId, unit, fuel_capacity) VALUES (%s, %s, %s)",
                    (truck_id, yaml_id, capacity)
                )
                logger.info(f"    ✅ Inserted {truck_id} with unit {yaml_id}")
    
    if not mismatches and not missing:
        logger.info("\n✅ All trucks in sync - no changes needed!")
    
    if not dry_run and (mismatches or missing):
        conn.commit()
        logger.info(f"\n💾 Changes committed: {len(mismatches)} updated, {len(missing)} inserted")
    elif dry_run and (mismatches or missing):
        logger.info(f"\n⚠️  DRY RUN - no changes applied. Run with --apply to fix.")
    
    cursor.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Sync units_map with tanks.yaml')
    parser.add_argument('--apply', action='store_true', help='Apply changes (default is dry-run)')
    args = parser.parse_args()
    
    # Load tanks.yaml
    logger.info("📖 Loading tanks.yaml...")
    config = load_tanks_yaml()
    trucks = config.get('trucks', {})
    logger.info(f"   Found {len(trucks)} trucks in tanks.yaml")
    
    # Connect to Wialon DB
    logger.info("🔌 Connecting to Wialon DB...")
    conn = mysql.connector.connect(
        host='20.127.200.135',
        user='tomas',
        password=os.getenv("WIALON_MYSQL_PASSWORD"),
        database='wialon_collect',
        port=3306
    )
    
    try:
        # Step 1: Clean duplicates
        logger.info("\n📋 STEP 1: Clean duplicate rows")
        clean_duplicates(conn, dry_run=not args.apply)
        
        # Step 2: Sync units_map with tanks.yaml
        logger.info("\n📋 STEP 2: Sync with tanks.yaml")
        fix_units_map(conn, trucks, dry_run=not args.apply)
    finally:
        conn.close()
        logger.info("\n✅ Done")
