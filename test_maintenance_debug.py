import sys
import logging
from datetime import datetime, timezone

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

print("1. Testing UnifiedHealthEngine import...")
try:
    from unified_health_engine import UnifiedHealthEngine

    print("✅ UnifiedHealthEngine imported successfully")
except Exception as e:
    print(f"❌ Failed to import UnifiedHealthEngine: {e}")
    sys.exit(1)

print("\n2. Testing UnifiedHealthEngine initialization...")
try:
    engine = UnifiedHealthEngine()
    print("✅ Engine initialized")
except Exception as e:
    print(f"❌ Engine initialization failed: {e}")
    sys.exit(1)

print("\n3. Testing Threshold Checks (Mock Data)...")
try:
    mock_truck_id = "T101"
    mock_values = {
        "oil_press": 20,  # Should trigger warning
        "rpm": 1200,
        "cool_temp": 190,
        "pwr_ext": 14.0,
    }

    alerts = engine.check_thresholds(mock_truck_id, mock_values)
    print(f"✅ Threshold check complete. Found {len(alerts)} alerts.")
    for alert in alerts:
        print(f"   - {alert.title}: {alert.message}")

except Exception as e:
    print(f"❌ Threshold check failed: {e}")

print("\n4. Testing Fleet Report Generation (Mock Data)...")
try:
    mock_fleet_data = [
        {
            "unit_id": 101,
            "truck_id": "T101",
            "oil_press": 45,
            "cool_temp": 195,
            "pwr_ext": 14.1,
            "rpm": 1200,
        },
        {
            "unit_id": 102,
            "truck_id": "T102",
            "oil_press": 28,  # Low oil
            "cool_temp": 215,
            "pwr_ext": 13.2,
            "rpm": 1200,
        },
    ]

    report = engine.generate_fleet_report(mock_fleet_data)
    print("✅ Fleet report generated successfully")
    print(f"   - Healthy: {report['fleet_summary']['healthy_count']}")
    print(f"   - Warning: {report['fleet_summary']['warning_count']}")

except Exception as e:
    print(f"❌ Fleet report generation failed: {e}")
