#!/usr/bin/env python3
"""
Test refuel detection logic with a simulated refuel event
"""
import sys

sys.path.insert(0, "/Users/tomasruiz/Desktop/Fuel-Analytics-Backend")

from datetime import datetime, timezone

from wialon_sync_enhanced import detect_refuel

# Simulating MR7679's refuel: 69.0% → 80.4%
print("🧪 Testing refuel detection for MR7679 scenario...")
print("=" * 60)

# Parameters
truck_id = "MR7679"
prev_fuel_pct = 69.0  # Before refuel
curr_fuel_pct = 80.4  # After refuel
kalman_estimate = 68.5  # What we expected after consumption
last_sensor_pct = 69.0  # Last reading 5 minutes ago
time_gap_hours = 5 / 60  # 5 minutes
tank_capacity = 125  # gallons (typical for Kenworth)
truck_status = "STOPPED"

print(f"Truck: {truck_id}")
print(f"Previous: {prev_fuel_pct}% → Current: {curr_fuel_pct}%")
print(f"Kalman expected: {kalman_estimate}%")
print(f"Time gap: {time_gap_hours*60:.0f} minutes")
print(f"Tank capacity: {tank_capacity} gallons")
print()

# Call detection
result = detect_refuel(
    sensor_pct=curr_fuel_pct,
    estimated_pct=kalman_estimate,
    last_sensor_pct=last_sensor_pct,
    time_gap_hours=time_gap_hours,
    truck_status=truck_status,
    tank_capacity_gal=tank_capacity,
    truck_id=truck_id,
)

print("=" * 60)
if result:
    print("✅ REFUEL DETECTED!")
    print()
    print("Details:")
    print(f"  Before: {result['prev_pct']:.1f}%")
    print(f"  After: {result['new_pct']:.1f}%")
    print(f"  Increase: {result['increase_pct']:.1f}%")
    print(f"  Gallons added: {result['increase_gal']:.1f} gal")
    print(f"  Detection method: {result['detection_method']}")
    print(f"  Time gap: {result['time_gap_hours']*60:.0f} minutes")
else:
    print("❌ Refuel NOT detected - check thresholds")

print()
print("=" * 60)
print("🔧 Checking current thresholds...")

from settings import get_settings

_settings = get_settings()
print(f"Min increase: {_settings.fuel.min_refuel_jump_pct}%")
print(f"Min gallons: {_settings.fuel.min_refuel_gallons} gal")

# Calculate what we got
actual_increase_pct = curr_fuel_pct - kalman_estimate
actual_gal = (actual_increase_pct / 100) * tank_capacity
print()
print(f"Actual increase: {actual_increase_pct:.1f}%")
print(f"Actual gallons: {actual_gal:.1f} gal")

if actual_increase_pct >= _settings.fuel.min_refuel_jump_pct:
    print(
        f"✅ Exceeds % threshold ({actual_increase_pct:.1f}% >= {_settings.fuel.min_refuel_jump_pct}%)"
    )
else:
    print(
        f"❌ Below % threshold ({actual_increase_pct:.1f}% < {_settings.fuel.min_refuel_jump_pct}%)"
    )

if actual_gal >= _settings.fuel.min_refuel_gallons:
    print(
        f"✅ Exceeds gallon threshold ({actual_gal:.1f} >= {_settings.fuel.min_refuel_gallons})"
    )
else:
    print(
        f"❌ Below gallon threshold ({actual_gal:.1f} < {_settings.fuel.min_refuel_gallons})"
    )
