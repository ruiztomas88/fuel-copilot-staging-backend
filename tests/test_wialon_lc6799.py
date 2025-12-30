"""Quick test to see what wialon_reader returns for LC6799"""

import logging

# Configure logging FIRST
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

from wialon_reader import WialonReader, WialonConfig, TRUCK_UNIT_MAPPING

print(f"\n{'='*70}")
print(f" Testing wialon_reader for LC6799")
print(f"{'='*70}\n")

# Check mapping
print(f"TRUCK_UNIT_MAPPING for LC6799: {TRUCK_UNIT_MAPPING.get('LC6799')}")

# Create reader
config = WialonConfig()
reader = WialonReader(config=config, truck_unit_mapping=TRUCK_UNIT_MAPPING)

# Get all trucks data
print("\nFetching all trucks data...")
all_trucks = reader.get_all_trucks_data()

# Find LC6799
lc6799 = None
for truck in all_trucks:
    if truck.truck_id == 'LC6799':
        lc6799 = truck
        break

if lc6799:
    print(f"\nOK Found LC6799 (unit_id: {lc6799.unit_id})")
    print(f"\nSensor Values:")
    print(f"  Timestamp:      {lc6799.timestamp}")
    print(f"  Epoch:          {lc6799.epoch_time}")
    print(f"  RPM:            {lc6799.rpm}")
    print(f"  Coolant Temp:   {lc6799.coolant_temp}")
    print(f"  Oil Temp:       {lc6799.oil_temp}")
    print(f"  Oil Pressure:   {lc6799.oil_press}")
    print(f"  Engine Load:    {lc6799.engine_load}")
    print(f"  DEF Level:      {lc6799.def_level}")
    print(f"  Fuel Level:     {lc6799.fuel_lvl}")
else:
    print(f"\nERROR: LC6799 NOT FOUND in {len(all_trucks)} trucks!")
    print(f"\nAvailable trucks: {[t.truck_id for t in all_trucks[:10]]}")

print(f"\n{'='*70}\n")
