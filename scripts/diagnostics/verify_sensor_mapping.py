#!/usr/bin/env python3
"""
Verificar que todos los sensores críticos están correctamente mapeados
"""
import sys

sys.path.insert(0, "/Users/tomasruiz/Desktop/Fuel-Analytics-Backend")

from wialon_reader import WialonConfig

config = WialonConfig()

print("=" * 80)
print("VERIFICACIÓN: SENSORES CRÍTICOS MAPEADOS")
print("=" * 80)

critical_sensors = {
    # ALTA PRIORIDAD
    "odometer": ("odom", 30, 147),
    "gear": ("gear", 20, 36),
    "idle_hours": ("idle_hours", 25, 131),
    "total_idle_fuel": ("total_idle_fuel", 41, 45),
    "coolant_level": ("cool_lvl", 10, 138),
    "dtc": ("dtc", 1, 146),
    # MEDIA PRIORIDAD
    "obd_speed": ("obd_speed", 16, 147),
    "fuel_economy": ("fuel_economy", 4, 27),
    "brake_switch": ("brake_switch", 45, 32),
    "engine_brake": ("actual_retarder", 52, 30),
    "pto_hours": ("pto_hours", 35, 21),
    "trans_temp": ("trams_t", 50, 22),
    # BAJA PRIORIDAD
    "j1939_fmi": ("j1939_fmi", 44, 27),
    "j1939_spn": ("j1939_spn", 51, 25),
    "oil_level": ("oil_level", 31, 40),
    "fuel_temp": ("fuel_t", 46, 28),
    "intercooler_temp": ("intrclr_t", 43, 28),
}

print("\nSENSORES CONFIGURADOS EN SENSOR_PARAMS:")
print("-" * 80)

missing = []
correct = []

for our_name, (wialon_param, sensor_id, trucks) in critical_sensors.items():
    if our_name in config.SENSOR_PARAMS:
        mapped_value = config.SENSOR_PARAMS[our_name]
        if mapped_value == wialon_param:
            status = "✅ OK"
            correct.append(our_name)
        else:
            status = f"⚠️  WRONG (maps to '{mapped_value}' instead of '{wialon_param}')"
        print(
            f"{status:30} | {our_name:20} → {wialon_param:20} | ID {sensor_id:3} | {trucks:3} trucks"
        )
    else:
        status = "❌ MISSING"
        missing.append(our_name)
        print(
            f"{status:30} | {our_name:20} → {wialon_param:20} | ID {sensor_id:3} | {trucks:3} trucks"
        )

print("\n" + "=" * 80)
print("RESUMEN:")
print("=" * 80)
print(f"✅ Correctos: {len(correct)}/17")
print(f"❌ Faltantes: {len(missing)}/17")

if missing:
    print(f"\n⚠️  SENSORES FALTANTES: {', '.join(missing)}")
    print("\nAGREGAR AL DICCIONARIO SENSOR_PARAMS:")
    for name in missing:
        wialon_param, sensor_id, trucks = critical_sensors[name]
        print(f'    "{name}": "{wialon_param}",  # ID {sensor_id} - {trucks} trucks')
else:
    print("\n🎉 ¡TODOS LOS SENSORES CRÍTICOS ESTÁN MAPEADOS CORRECTAMENTE!")

print("\n" + "=" * 80)
print("TOTAL SENSORES EN SENSOR_PARAMS: {}".format(len(config.SENSOR_PARAMS)))
print("=" * 80)
