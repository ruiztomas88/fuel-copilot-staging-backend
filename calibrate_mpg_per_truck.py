#!/usr/bin/env python3
"""
🔧 MPG Calibration Script v5.3.3
Calculate individual MPG baselines per truck from actual fuel_metrics data.

This script:
1. Queries 30 days of MPG data per truck
2. Filters outliers using IQR method
3. Calculates highway/city/overall MPG per truck
4. Outputs updated tanks.yaml entries

Usage:
    python calibrate_mpg_per_truck.py
    python calibrate_mpg_per_truck.py --days 60 --output updated_tanks.yaml
"""

import os
import sys
import argparse
import yaml
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dotenv import load_dotenv
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()


def get_mysql_connection():
    """Get connection to fuel_copilot database"""
    import pymysql
    
    return pymysql.connect(
        host=os.getenv("MYSQL_HOST", "localhost"),
        user=os.getenv("MYSQL_USER", "root"),
        password=os.getenv("MYSQL_PASSWORD", ""),
        database=os.getenv("MYSQL_DATABASE", "fuel_copilot"),
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )


def calculate_iqr_bounds(values: List[float], k: float = 1.5) -> Tuple[float, float]:
    """Calculate IQR bounds for outlier detection"""
    if len(values) < 4:
        return min(values), max(values)
    
    sorted_values = sorted(values)
    n = len(sorted_values)
    q1 = sorted_values[n // 4]
    q3 = sorted_values[3 * n // 4]
    iqr = q3 - q1
    
    lower = q1 - k * iqr
    upper = q3 + k * iqr
    
    # Physical limits for Class 8 trucks
    lower = max(lower, 3.5)  # Minimum realistic MPG
    upper = min(upper, 10.0)  # Maximum realistic MPG
    
    return lower, upper


def fetch_mpg_data(days: int = 30) -> Dict[str, Dict[str, List[float]]]:
    """
    Fetch MPG data per truck, categorized by driving condition.
    
    Returns: {truck_id: {'highway': [mpg...], 'city': [mpg...], 'all': [mpg...]}}
    """
    conn = get_mysql_connection()
    try:
        with conn.cursor() as cursor:
            # Query MPG with speed to categorize highway vs city
            query = """
                SELECT 
                    truck_id,
                    mpg_current,
                    speed_mph,
                    truck_status
                FROM fuel_metrics
                WHERE timestamp_utc > NOW() - INTERVAL %s DAY
                  AND truck_status = 'MOVING'
                  AND mpg_current > 2.0 AND mpg_current < 15.0
                  AND speed_mph > 5
                ORDER BY truck_id, timestamp_utc
            """
            cursor.execute(query, (days,))
            rows = cursor.fetchall()
            
            logger.info(f"Fetched {len(rows)} MPG readings from last {days} days")
            
            trucks: Dict[str, Dict[str, List[float]]] = {}
            
            for row in rows:
                truck_id = row['truck_id']
                mpg = float(row['mpg_current'])
                speed = float(row['speed_mph'] or 0)
                
                if truck_id not in trucks:
                    trucks[truck_id] = {'highway': [], 'city': [], 'all': []}
                
                trucks[truck_id]['all'].append(mpg)
                
                # Categorize: highway (>55mph), city (<35mph)
                if speed > 55:
                    trucks[truck_id]['highway'].append(mpg)
                elif speed < 35:
                    trucks[truck_id]['city'].append(mpg)
            
            return trucks
            
    finally:
        conn.close()


def calculate_truck_mpg(mpg_data: Dict[str, List[float]]) -> Dict[str, float]:
    """
    Calculate MPG stats for a single truck with outlier filtering.
    
    Returns: {'highway': X.XX, 'city': X.XX, 'overall': X.XX}
    """
    result = {}
    
    for category in ['highway', 'city', 'all']:
        values = mpg_data.get(category, [])
        
        if len(values) < 10:
            # Not enough data, skip
            result[category] = None
            continue
        
        # Filter outliers
        lower, upper = calculate_iqr_bounds(values)
        filtered = [v for v in values if lower <= v <= upper]
        
        if len(filtered) < 5:
            result[category] = None
            continue
        
        # Calculate mean of filtered values
        result[category] = round(sum(filtered) / len(filtered), 2)
    
    # Map 'all' to 'overall'
    result['overall'] = result.pop('all', None)
    
    return result


def load_tanks_yaml(path: str = "tanks.yaml") -> dict:
    """Load existing tanks.yaml"""
    with open(path, 'r') as f:
        return yaml.safe_load(f)


def update_tanks_with_mpg(tanks_config: dict, mpg_by_truck: Dict[str, Dict[str, float]]) -> dict:
    """Update tanks.yaml config with calculated MPG values"""
    updated_count = 0
    
    for truck_id, mpg_values in mpg_by_truck.items():
        if truck_id not in tanks_config.get('trucks', {}):
            logger.warning(f"Truck {truck_id} not found in tanks.yaml, skipping")
            continue
        
        truck_config = tanks_config['trucks'][truck_id]
        
        # Only update if we have valid data
        new_mpg = {}
        
        if mpg_values.get('highway'):
            new_mpg['highway'] = mpg_values['highway']
        elif 'mpg' in truck_config:
            new_mpg['highway'] = truck_config['mpg'].get('highway', 7.0)
        
        if mpg_values.get('city'):
            new_mpg['city'] = mpg_values['city']
        elif 'mpg' in truck_config:
            new_mpg['city'] = truck_config['mpg'].get('city', 4.0)
        
        if mpg_values.get('overall'):
            new_mpg['overall'] = mpg_values['overall']
        elif 'mpg' in truck_config:
            new_mpg['overall'] = truck_config['mpg'].get('overall', 6.0)
        
        if new_mpg:
            old_mpg = truck_config.get('mpg', {})
            truck_config['mpg'] = new_mpg
            
            # Add calibration metadata
            truck_config['mpg_calibrated_at'] = datetime.now().isoformat()
            
            if old_mpg.get('overall') != new_mpg.get('overall'):
                updated_count += 1
                logger.info(f"{truck_id}: MPG updated {old_mpg.get('overall', '?')} → {new_mpg.get('overall', '?')}")
    
    logger.info(f"Updated MPG for {updated_count} trucks")
    return tanks_config


def main():
    parser = argparse.ArgumentParser(description='Calculate individual MPG per truck')
    parser.add_argument('--days', type=int, default=30, help='Days of data to analyze')
    parser.add_argument('--output', type=str, default=None, help='Output file (default: print to stdout)')
    parser.add_argument('--update-inplace', action='store_true', help='Update tanks.yaml in place')
    args = parser.parse_args()
    
    logger.info(f"🔧 MPG Calibration - Analyzing last {args.days} days of data...")
    
    # Fetch data
    mpg_data = fetch_mpg_data(args.days)
    logger.info(f"Found data for {len(mpg_data)} trucks")
    
    # Calculate per-truck MPG
    mpg_by_truck: Dict[str, Dict[str, float]] = {}
    
    print("\n" + "="*60)
    print("📊 MPG CALIBRATION RESULTS")
    print("="*60)
    print(f"{'Truck':<10} {'Highway':<10} {'City':<10} {'Overall':<10} {'Samples':<10}")
    print("-"*60)
    
    for truck_id, data in sorted(mpg_data.items()):
        mpg_values = calculate_truck_mpg(data)
        mpg_by_truck[truck_id] = mpg_values
        
        highway = mpg_values.get('highway') or '-'
        city = mpg_values.get('city') or '-'
        overall = mpg_values.get('overall') or '-'
        samples = len(data['all'])
        
        print(f"{truck_id:<10} {str(highway):<10} {str(city):<10} {str(overall):<10} {samples:<10}")
    
    print("="*60)
    
    # Update tanks.yaml
    if args.update_inplace or args.output:
        tanks_config = load_tanks_yaml()
        updated_config = update_tanks_with_mpg(tanks_config, mpg_by_truck)
        
        output_path = args.output or ("tanks.yaml" if args.update_inplace else None)
        
        if output_path:
            with open(output_path, 'w') as f:
                yaml.dump(updated_config, f, default_flow_style=False, allow_unicode=True)
            logger.info(f"✅ Saved updated config to {output_path}")
        else:
            print("\n📄 Updated YAML (preview):")
            print(yaml.dump({'trucks': {k: v for k, v in list(updated_config['trucks'].items())[:3]}}, 
                          default_flow_style=False))
            print("... (use --output or --update-inplace to save)")
    
    print("\n✅ MPG Calibration complete!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
