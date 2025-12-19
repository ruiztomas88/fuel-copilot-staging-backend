"""Test del método get_truck_latest_record que usa el endpoint"""
import os
os.environ['MYSQL_PASSWORD'] = 'FuelCopilot2025!'

from database import db

print("=" * 60)
print("TEST: get_truck_latest_record('DO9693')")
print("=" * 60)

try:
    record = db.get_truck_latest_record('DO9693')
    if record:
        print(f"\n✅ RECORD FOUND:")
        print(f"   truck_id: {record.get('truck_id')}")
        print(f"   timestamp_utc: {record.get('timestamp_utc')}")
        print(f"   estimated_pct: {record.get('estimated_pct')}")
        print(f"   mpg_current: {record.get('mpg_current')}")
        print(f"   truck_status: {record.get('truck_status')}")
        print(f"\n📦 Full keys: {list(record.keys())[:10]}...")
    else:
        print(f"\n❌ RECORD IS NONE - No data found")
except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
