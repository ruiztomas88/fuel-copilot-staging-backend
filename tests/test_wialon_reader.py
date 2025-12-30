from wialon_reader import WialonReader, WialonConfig, TRUCK_UNIT_MAPPING
import logging

logging.basicConfig(level=logging.INFO)

print('Probando WialonReader con mapeo actualizado...')
print(f'TRUCK_UNIT_MAPPING tiene {len(TRUCK_UNIT_MAPPING)} camiones')

# Mostrar algunos ejemplos
for i, (truck_id, unit_id) in enumerate(TRUCK_UNIT_MAPPING.items()):
    if i < 5:  # Solo mostrar los primeros 5
        print(f'  {truck_id}: {unit_id}')
    elif i == 5:
        print('  ...')

# Probar conexión
config = WialonConfig()
reader = WialonReader(config, TRUCK_UNIT_MAPPING)

if reader.ensure_connection():
    print('Conexión exitosa')

    # Probar lectura de un camión
    test_truck = list(TRUCK_UNIT_MAPPING.keys())[0]
    test_unit = TRUCK_UNIT_MAPPING[test_truck]

    print(f'Probando lectura de {test_truck} (unit {test_unit})...')
    sensor_data = reader.get_latest_sensor_data(test_unit)

    if sensor_data:
        print('Datos obtenidos exitosamente!')
        timestamp = sensor_data.get('timestamp')
        speed = sensor_data.get('speed')
        fuel_lvl = sensor_data.get('fuel_lvl')
        print(f'  Timestamp: {timestamp}')
        print(f'  Speed: {speed}')
        print(f'  Fuel Level: {fuel_lvl}')
    else:
        print('No se pudieron obtener datos')

else:
    print('Falló la conexión')