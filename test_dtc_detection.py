"""
Script para probar la detección de DTCs desde Wialon para un camión específico
"""
import os
import sys
sys.path.insert(0, '.')

from wialon_sync_enhanced import (
    get_wialon_connection,
    get_truck_latest_data,
    process_dtc_from_sensor_data,
    save_dtc_event,
    get_local_db_connection
)
import pymysql

# Configuración
TRUCK_ID = "LH1141"  # Camión con DTC activo visible en dashboard

print("=" * 70)
print(f"TEST: Detección de DTCs para {TRUCK_ID}")
print("=" * 70)

# 1. Conectar a Wialon
print("\n1. Conectando a Wialon...")
try:
    wialon_conn = get_wialon_connection()
    print("✅ Conexión a Wialon exitosa")
except Exception as e:
    print(f"❌ Error conectando a Wialon: {e}")
    sys.exit(1)

# 2. Obtener datos del camión
print(f"\n2. Obteniendo datos de {TRUCK_ID} desde Wialon...")
try:
    truck_data = get_truck_latest_data(wialon_conn, TRUCK_ID)
    
    if not truck_data:
        print(f"❌ No se encontraron datos para {TRUCK_ID}")
        sys.exit(1)
    
    print(f"✅ Datos obtenidos:")
    print(f"   - Timestamp: {truck_data.timestamp}")
    print(f"   - DTC flag: {truck_data.dtc}")
    print(f"   - DTC code: {truck_data.dtc_code}")
    print(f"   - Speed: {truck_data.speed_mph} mph")
    print(f"   - Status: {truck_data.truck_status}")
    
except Exception as e:
    print(f"❌ Error obteniendo datos: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 3. Procesar DTCs
print(f"\n3. Procesando DTCs...")

dtc_to_process = (
    truck_data.dtc_code
    if truck_data.dtc_code
    else (
        truck_data.dtc
        if truck_data.dtc and str(truck_data.dtc) not in ["0", "1", "0.0", "1.0"]
        else None
    )
)

if not dtc_to_process:
    print(f"❌ No hay DTCs activos en Wialon para {TRUCK_ID}")
    print(f"   dtc_code = {truck_data.dtc_code}")
    print(f"   dtc = {truck_data.dtc}")
else:
    print(f"✅ DTC detectado: {dtc_to_process}")
    
    # Procesar el DTC
    try:
        dtc_alerts = process_dtc_from_sensor_data(
            truck_id=TRUCK_ID,
            dtc_value=str(dtc_to_process),
            timestamp=truck_data.timestamp,
        )
        
        print(f"\n   Alertas generadas: {len(dtc_alerts)}")
        
        for i, alert in enumerate(dtc_alerts, 1):
            print(f"\n   Alerta {i}:")
            print(f"   - Mensaje: {alert.message}")
            print(f"   - Severidad: {alert.severity}")
            print(f"   - Códigos: {len(alert.codes)}")
            
            for code in alert.codes:
                print(f"     * {code.code} (SPN={code.spn}, FMI={code.fmi})")
                print(f"       Sistema: {getattr(code, 'system', 'N/A')}")
                print(f"       Descripción: {code.description}")
        
        # Guardar en base de datos
        print(f"\n4. Guardando en base de datos local...")
        local_conn = get_local_db_connection()
        
        sensor_data = {
            "unit_id": truck_data.unit_id if hasattr(truck_data, 'unit_id') else None,
        }
        
        for alert in dtc_alerts:
            result = save_dtc_event(
                local_conn,
                truck_id=TRUCK_ID,
                alert=alert,
                sensor_data=sensor_data,
            )
            if result:
                print(f"✅ DTC guardado en dtc_events")
            else:
                print(f"❌ Error guardando DTC")
        
        local_conn.close()
        
    except Exception as e:
        print(f"❌ Error procesando DTC: {e}")
        import traceback
        traceback.print_exc()

# 5. Verificar en base de datos
print(f"\n5. Verificando dtc_events en base de datos...")
conn = pymysql.connect(
    host='localhost',
    user='fuel_admin',
    password=os.getenv("DB_PASSWORD"),
    database='fuel_copilot'
)

cursor = conn.cursor()
cursor.execute("""
    SELECT truck_id, dtc_code, severity, status, timestamp_utc, description
    FROM dtc_events 
    WHERE truck_id = %s
    ORDER BY timestamp_utc DESC
    LIMIT 5
""", (TRUCK_ID,))

rows = cursor.fetchall()

if rows:
    print(f"✅ DTCs encontrados en base de datos:")
    for row in rows:
        print(f"   - {row[1]} | {row[2]} | {row[3]} | {row[4]} | {row[5][:50] if row[5] else 'N/A'}")
else:
    print(f"❌ No hay DTCs en dtc_events para {TRUCK_ID}")

cursor.close()
conn.close()

print("\n" + "=" * 70)
print("TEST COMPLETADO")
print("=" * 70)
