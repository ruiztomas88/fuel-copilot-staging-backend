"""
Test con logging detallado del flujo de get_truck_detail
"""
import os
os.environ['MYSQL_PASSWORD'] = 'FuelCopilot2025!'
os.environ['PYTHONIOENCODING'] = 'utf-8'

import sys
import logging

# Configure detailed logging WITHOUT emojis
logging.basicConfig(
    level=logging.WARNING,  # Reduce noise
    format='%(message)s',
    stream=sys.stdout
)

from database import db

truck_id = "DO9693"

print("=" * 80)
print(f"TEST DETALLADO: database.py.get_truck_latest_record('{truck_id}')")
print("=" * 80)

print(f"\n1. Verificando MySQL disponible...")
print(f"   db.mysql_available: {db.mysql_available}")

print(f"\n2. Llamando db.get_truck_latest_record('{truck_id}')...")
try:
    record = db.get_truck_latest_record(truck_id)
    
    if record:
        print(f"\nOK RECORD OBTENIDO:")
        print(f"   Tipo: {type(record)}")
        print(f"   Keys: {len(record.keys())}")
        print(f"   truck_id: {record.get('truck_id')}")
        print(f"   timestamp: {record.get('timestamp_utc') or record.get('timestamp')}")
        print(f"   truck_status: {record.get('truck_status')}")
        print(f"   estimated_pct: {record.get('estimated_pct')}")
        print(f"   mpg_current: {record.get('mpg_current')}")
        print(f"   speed_mph: {record.get('speed_mph')}")
        print(f"   rpm: {record.get('rpm')}")
        
        # Imprimir todos los campos no-None
        non_none = {k: v for k, v in record.items() if v is not None and str(v) != 'nan'}
        print(f"\nCampos con valores ({len(non_none)}):")
        for k, v in list(non_none.items())[:20]:
            print(f"   {k}: {v}")
            
        if len(non_none) > 20:
            print(f"   ... y {len(non_none) - 20} campos mas")
    else:
        print(f"\nERROR: RECORD ES NONE")
        
except Exception as e:
    print(f"\nERROR: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 80)
