"""
Test FleetBooster Integration
Prueba la conexión con el API de FleetBooster de tu tío
"""

import sys

sys.path.insert(0, "/Users/tomasruiz/Desktop/Fuel-Analytics-Backend")

from fleetbooster_integration import send_dtc_alert, send_fuel_level_update

# Test 1: Fuel level update (silent)
print("=" * 60)
print("TEST 1: Fuel Level Update (silent)")
print("=" * 60)

result1 = send_fuel_level_update(
    truck_id="RR1272",
    fuel_pct=75.5,
    fuel_gallons=151.0,
    fuel_source="kalman",
    estimated_liters=571.5,
)

print(f"Result: {'✓ SUCCESS' if result1 else '✗ FAILED'}")
print()

# Test 2: DTC Alert (notification)
print("=" * 60)
print("TEST 2: DTC Alert (with notification)")
print("=" * 60)

result2 = send_dtc_alert(
    truck_id="RR1272",
    dtc_code="523452.3",
    dtc_description="Freightliner Safety/Radar - Voltage Above Normal",
    severity="WARNING",
    system="Safety/Radar",
)

print(f"Result: {'✓ SUCCESS' if result2 else '✗ FAILED'}")
print()

# Summary
print("=" * 60)
print("SUMMARY")
print("=" * 60)
print(f"Fuel Update: {'✓' if result1 else '✗'}")
print(f"DTC Alert:   {'✓' if result2 else '✗'}")
print()
print("Si ambos muestran ✓, el sistema está funcionando correctamente.")
print("Tu tío debería recibir la notificación del DTC en FleetBooster.")
