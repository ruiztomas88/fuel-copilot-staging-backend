"""Direct test using exec() to bypass import issues"""
import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Run wialon_reader code directly
exec(open('wialon_reader.py').read())

# Now test
config = WialonConfig()
reader = WialonReader(config)
data = reader.get_all_trucks_data()

# Find LC6799
lc6799 = next((t for t in data if t.truck_id == 'LC6799'), None)
if lc6799:
    print(f"\n{'='*70}")
    print(f"LC6799 Data:")
    print(f"unit_id: {lc6799.unit_id}")
    print(f"timestamp: {lc6799.timestamp}")
    print(f"oil_press: {lc6799.oil_press}")
    print(f"fuel_lvl: {lc6799.fuel_lvl}")
    print(f"rpm: {lc6799.rpm}")
    print(f"coolant_temp: {lc6799.coolant_temp}")
    print(f"oil_temp: {lc6799.oil_temp}")
    print(f"engine_load: {lc6799.engine_load}")
    print(f"def_level: {lc6799.def_level}")
    print(f"{'='*70}\n")
else:
    print("LC6799 not found in data!")
