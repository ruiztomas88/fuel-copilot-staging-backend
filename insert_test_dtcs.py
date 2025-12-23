"""
Script para insertar DTCs de prueba en dtc_events
Basado en el DTC real de LH1141: SPN1548.FMI5
"""
import os
import pymysql
from datetime import datetime, timezone

conn = pymysql.connect(
    host='localhost',
    user='fuel_admin',
    password=os.getenv("DB_PASSWORD"),
    database='fuel_copilot'
)

cursor = conn.cursor()

print("=" * 70)
print("INSERTANDO DTCs DE PRUEBA")
print("=" * 70)

# DTCs de prueba basados en códigos reales
test_dtcs = [
    {
        'truck_id': 'LH1141',
        'dtc_code': 'SPN1548.FMI5',
        'component': 'Check Engine Light',
        'severity': 'CRITICAL',
        'status': 'ACTIVE',
        'description': 'Comando de Luz de Falla (Check Engine). Corriente bajo lo normal o circuito abierto',
    },
    {
        'truck_id': 'DO9693',
        'dtc_code': 'SPN157.FMI3',
        'component': 'Fuel Rail Pressure',
        'severity': 'WARNING',
        'status': 'ACTIVE',
        'description': 'Presión de riel de combustible - Voltaje arriba de lo normal',
    },
    {
        'truck_id': 'FF7702',
        'dtc_code': 'SPN100.FMI4',
        'component': 'Engine Oil Pressure',
        'severity': 'CRITICAL',
        'status': 'ACTIVE',
        'description': 'Presión de aceite del motor - Voltaje bajo de lo normal',
    },
    {
        'truck_id': 'GS5030',
        'dtc_code': 'SPN110.FMI0',
        'component': 'Coolant Temperature',
        'severity': 'WARNING',
        'status': 'ACTIVE',
        'description': 'Temperatura de refrigerante - Dato válido pero arriba del rango normal',
    },
    {
        'truck_id': 'NP1082',
        'dtc_code': 'SPN524.FMI2',
        'component': 'Transmission Output Shaft Speed',
        'severity': 'INFO',
        'status': 'ACTIVE',
        'description': 'Velocidad del eje de salida de transmisión - Dato errático',
    },
]

for dtc in test_dtcs:
    try:
        # Verificar si ya existe
        cursor.execute("""
            SELECT COUNT(*) FROM dtc_events 
            WHERE truck_id = %s AND dtc_code = %s 
            AND timestamp_utc > DATE_SUB(NOW(), INTERVAL 1 HOUR)
        """, (dtc['truck_id'], dtc['dtc_code']))
        
        if cursor.fetchone()[0] > 0:
            print(f"⏭️  {dtc['truck_id']}: {dtc['dtc_code']} ya existe (última hora)")
            continue
        
        # Insertar DTC
        cursor.execute("""
            INSERT INTO dtc_events 
            (truck_id, timestamp_utc, dtc_code, component, severity, status, description)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            dtc['truck_id'],
            datetime.now(timezone.utc),
            dtc['dtc_code'],
            dtc['component'],
            dtc['severity'],
            dtc['status'],
            dtc['description'],
        ))
        
        print(f"✅ {dtc['truck_id']}: {dtc['dtc_code']} ({dtc['severity']})")
        
    except Exception as e:
        print(f"❌ Error insertando {dtc['truck_id']}: {e}")

conn.commit()

# Verificar resultados
cursor.execute("""
    SELECT truck_id, dtc_code, severity, status, 
           DATE_FORMAT(timestamp_utc, '%Y-%m-%d %H:%i:%s') as timestamp
    FROM dtc_events 
    WHERE cleared_at IS NULL
    ORDER BY timestamp_utc DESC
""")

rows = cursor.fetchall()

print("\n" + "=" * 70)
print(f"DTCs ACTIVOS EN BASE DE DATOS: {len(rows)}")
print("=" * 70)

for row in rows:
    print(f"{row[0]:10} | {row[1]:15} | {row[2]:10} | {row[3]:10} | {row[4]}")

cursor.close()
conn.close()

print("\n✅ DTCs de prueba insertados exitosamente")
print("\nAhora deberías ver estos DTCs en Command Center")
