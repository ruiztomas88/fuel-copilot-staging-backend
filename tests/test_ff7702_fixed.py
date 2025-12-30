"""
🔍 TEST FF7702 - Verificar que ahora lee correctamente todos los sensores
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from wialon_reader import WialonReader, TRUCK_UNIT_MAPPING, WialonConfig
from datetime import datetime
import pytz

print("=" * 100)
print("🔍 TEST FF7702 - Lectura de sensores corregida")
print("=" * 100)

# Crear reader
config = WialonConfig()
reader = WialonReader(config, TRUCK_UNIT_MAPPING)

# Leer datos de FF7702
print(f"\n📊 Leyendo datos de FF7702...")
truck_data = reader.get_all_trucks_data()

ff7702_data = None
for data in truck_data:
    if data.truck_id == "FF7702":
        ff7702_data = data
        break

if not ff7702_data:
    print("❌ No se recibieron datos para FF7702")
    sys.exit(1)

print(f"\n✅ Datos recibidos para FF7702:")
print(f"   Timestamp: {ff7702_data.timestamp}")
print(f"   Epoch: {ff7702_data.epoch_time}")

# Sensores que el usuario mencionó
print(f"\n📋 SENSORES REPORTADOS POR EL USUARIO:")
print(f"   idle_hours:      {ff7702_data.idle_hours}")
print(f"   barometer:       {ff7702_data.barometer}")
print(f"   coolant_temp:    {ff7702_data.coolant_temp}")
print(f"   rpm:             {ff7702_data.rpm}")

# Sensores con mapeo corregido
print(f"\n🔧 SENSORES CON MAPEO CORREGIDO (v5.12.2):")
print(f"   intake_air_temp: {ff7702_data.intake_air_temp}  (intk_t)")
print(f"   fuel_temp:       {ff7702_data.fuel_temp}        (fuel_t)")
print(f"   intercooler_temp:{ff7702_data.intercooler_temp} (intrclr_t)")
print(f"   trans_temp:      {ff7702_data.trans_temp}       (trams_t)")
print(f"   intake_press:    {ff7702_data.intake_press}     (intake_pressure)")

# Nuevos sensores agregados
print(f"\n🆕 SENSORES NUEVOS (v5.12.2):")
print(f"   retarder:        {ff7702_data.retarder}         (actual_retarder)")
print(f"   lac:             {ff7702_data.lac}")
print(f"   mcc:             {ff7702_data.mcc}")
print(f"   mnc:             {ff7702_data.mnc}")

# Otros sensores importantes
print(f"\n📊 OTROS SENSORES:")
print(f"   fuel_lvl:        {ff7702_data.fuel_lvl}%")
print(f"   engine_hours:    {ff7702_data.engine_hours}")
print(f"   engine_load:     {ff7702_data.engine_load}%")
print(f"   oil_temp:        {ff7702_data.oil_temp}°F")
print(f"   oil_press:       {ff7702_data.oil_press} psi")
print(f"   def_level:       {ff7702_data.def_level}%")
print(f"   gear:            {ff7702_data.gear}")

# Contar sensores con datos
total_fields = 0
fields_with_data = 0
fields_null = []

for attr in dir(ff7702_data):
    if not attr.startswith("_") and attr not in [
        "truck_id",
        "unit_id",
        "timestamp",
        "epoch_time",
        "capacity_gallons",
        "capacity_liters",
        "dtc_code",
    ]:
        total_fields += 1
        value = getattr(ff7702_data, attr)
        if value is not None and not callable(value):
            fields_with_data += 1
        else:
            if not callable(value):
                fields_null.append(attr)

print(f"\n{'='*100}")
print(f"📊 RESUMEN")
print(f"{'='*100}")
print(f"   Total campos de sensores: {total_fields}")
print(f"   ✅ Con datos: {fields_with_data}")
print(f"   ❌ NULL: {len(fields_null)}")
print(f"   Cobertura: {fields_with_data/total_fields*100:.1f}%")

if fields_null:
    print(f"\n   Campos NULL:")
    for field in sorted(fields_null):
        print(f"      • {field}")

print(f"\n{'='*100}")
print(f"✅ TEST COMPLETADO")
print(f"{'='*100}")
