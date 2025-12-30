#!/usr/bin/env python3
"""
Debug script para verificar por qué MR7679 no está sincronizando
"""

import os
import sys
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import mysql.connector

print("=" * 60)
print("🔍 DEBUG: MR7679 Sync Issue")
print("=" * 60)

# 1. Check database
print("\n1️⃣ Verificando base de datos local...")
conn = mysql.connector.connect(
    host='localhost',
    user='root',
    password=os.getenv('LOCAL_DB_PASS', 'root'),
    database='fuel_copilot_local'
)
cursor = conn.cursor(dictionary=True)
cursor.execute("""
    SELECT timestamp_utc, speed_mph, sensor_pct, engine_hours
    FROM fuel_metrics
    WHERE truck_id = 'MR7679'
    ORDER BY timestamp_utc DESC
    LIMIT 5
""")
latest = cursor.fetchall()
cursor.close()
conn.close()
if latest:
    print(f"   ✅ Encontrados {len(latest)} registros")
    for record in latest:
        timestamp = record.get('timestamp_utc', 'N/A')
        speed = record.get('speed_mph', 0)
        fuel = record.get('sensor_pct', 0)
        
        if isinstance(timestamp, datetime):
            minutes_ago = (datetime.now() - timestamp).total_seconds() / 60
            print(f"   📊 {timestamp} ({minutes_ago:.0f} min ago) - Speed: {speed} mph, Fuel: {fuel}%")
        else:
            print(f"   📊 {timestamp} - Speed: {speed} mph, Fuel: {fuel}%")
else:
    print("   ❌ No se encontraron registros")

# 2. Check if we need Wialon credentials
print("\n2️⃣ Verificando credenciales Wialon...")
wialon_token = os.getenv('WIALON_TOKEN')
if wialon_token:
    print(f"   ✅ WIALON_TOKEN configurado (len: {len(wialon_token)})")
else:
    print("   ❌ WIALON_TOKEN no configurado")
    print("      Esto podría ser la razón del problema!")

# 3. Recommendations
print("\n" + "=" * 60)
print("💡 DIAGNÓSTICO Y RECOMENDACIONES")
print("=" * 60)

if latest and len(latest) > 0:
    last_update = latest[0].get('timestamp_utc')
    if isinstance(last_update, datetime):
        hours_ago = (datetime.now() - last_update).total_seconds() / 3600
        
        if hours_ago > 2:
            print(f"\n⚠️  PROBLEMA DETECTADO:")
            print(f"   - Última actualización hace {hours_ago:.1f} horas")
            print(f"   - MR7679 está visible en Wialon pero no sincroniza")
            print(f"\n🔧 POSIBLES CAUSAS:")
            print(f"   1. Token de Wialon expiró")
            print(f"   2. Filtro de tiempo en query está mal")
            print(f"   3. Unit ID de MR7679 cambió en Wialon")
            print(f"   4. Rate limiting de Wialon API")
            print(f"\n✅ ACCIONES RECOMENDADAS:")
            print(f"   1. Reiniciar wialon_sync_enhanced.py")
            print(f"   2. Verificar logs en logs/wialon_sync.log")
            print(f"   3. Revisar WIALON_TOKEN en .env")
            print(f"   4. Verificar que MR7679 existe en Wialon")
        else:
            print("\n✅ Datos parecen estar actualizados")

print("\n" + "=" * 60)
