"""
Diagnóstico del flujo de datos: Wialon -> MySQL -> API -> Dashboard
Objetivo: Entender por qué el fleet summary funciona pero truck detail muestra N/A
"""
import os
# Password should be set via .env file

from database_mysql import get_sqlalchemy_engine
from sqlalchemy import text
import json

print("=" * 80)
print("🔍 DIAGNÓSTICO: FLUJO DE DATOS WIALON -> DASHBOARD")
print("=" * 80)

truck_id = "DO9693"  # Truck example from screenshot

try:
    engine = get_sqlalchemy_engine()
    
    # ============================================================================
    # 1. VERIFICAR FLEET SUMMARY QUERY (La que funciona)
    # ============================================================================
    print("\n" + "=" * 80)
    print("1️⃣ QUERY DE FLEET SUMMARY (Pantalla principal - FUNCIONA)")
    print("=" * 80)
    
    fleet_query = text("""
        SELECT 
            truck_id,
            truck_status,
            timestamp_utc,
            estimated_pct,
            mpg_current,
            rpm,
            speed_mph,
            consumption_gph
        FROM (
            SELECT t1.*
            FROM fuel_metrics t1
            INNER JOIN (
                SELECT truck_id, MAX(timestamp_utc) as max_time
                FROM fuel_metrics
                WHERE timestamp_utc > NOW() - INTERVAL 24 HOUR
                  AND truck_id = :truck_id
                GROUP BY truck_id
            ) t2 ON t1.truck_id = t2.truck_id AND t1.timestamp_utc = t2.max_time
        ) latest
    """)
    
    with engine.connect() as conn:
        result = conn.execute(fleet_query, {"truck_id": truck_id}).fetchone()
        
        if result:
            print(f"\n✅ FLEET SUMMARY encontró datos para {truck_id}:")
            print(f"   truck_status: {result[1]}")
            print(f"   timestamp: {result[2]}")
            print(f"   fuel: {result[3]}%")
            print(f"   mpg: {result[4]}")
            print(f"   rpm: {result[5]}")
            print(f"   speed: {result[6]} mph")
        else:
            print(f"\n❌ FLEET SUMMARY: No encontró datos para {truck_id}")
    
    # ============================================================================
    # 2. VERIFICAR TRUCK DETAIL QUERY (La que NO funciona - muestra N/A)
    # ============================================================================
    print("\n" + "=" * 80)
    print("2️⃣ QUERY DE TRUCK DETAIL (Vista individual - FALLA)")
    print("=" * 80)
    
    # Esta es la query que usa get_truck_latest_record
    detail_query = text("""
        SELECT *
        FROM fuel_metrics
        WHERE truck_id = :truck_id
        ORDER BY timestamp_utc DESC
        LIMIT 1
    """)
    
    with engine.connect() as conn:
        result = conn.execute(detail_query, {"truck_id": truck_id}).fetchone()
        
        if result:
            print(f"\n✅ TRUCK DETAIL encontró datos para {truck_id}:")
            print(f"   Timestamp: {result[1]}")  # timestamp_utc
            print(f"   Status: {result[2] if len(result) > 2 else 'N/A'}")
            print(f"   Fuel %: {result[3] if len(result) > 3 else 'N/A'}")
            print(f"   RPM: {result[4] if len(result) > 4 else 'N/A'}")
            print(f"\n   Total columns: {len(result)}")
            print(f"   First 10 values: {result[:10]}")
        else:
            print(f"\n❌ TRUCK DETAIL: No encontró datos para {truck_id}")
    
    # ============================================================================
    # 3. VERIFICAR ESTRUCTURA DE LA TABLA
    # ============================================================================
    print("\n" + "=" * 80)
    print("3️⃣ ESTRUCTURA DE TABLA fuel_metrics")
    print("=" * 80)
    
    with engine.connect() as conn:
        # Get column names
        columns_query = text("""
            SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = 'fuel_metrics'
            AND TABLE_SCHEMA = DATABASE()
            ORDER BY ORDINAL_POSITION
        """)
        
        columns = conn.execute(columns_query).fetchall()
        print(f"\n📋 Columnas en fuel_metrics ({len(columns)} total):")
        for col in columns[:20]:  # Show first 20
            print(f"   - {col[0]}: {col[1]} ({'NULL' if col[2] == 'YES' else 'NOT NULL'})")
        
        if len(columns) > 20:
            print(f"   ... y {len(columns) - 20} columnas más")
    
    # ============================================================================
    # 4. VERIFICAR DATOS RECIENTES
    # ============================================================================
    print("\n" + "=" * 80)
    print("4️⃣ REGISTROS RECIENTES (últimas 24 horas)")
    print("=" * 80)
    
    with engine.connect() as conn:
        count_query = text("""
            SELECT COUNT(*) as total,
                   MIN(timestamp_utc) as oldest,
                   MAX(timestamp_utc) as newest
            FROM fuel_metrics
            WHERE truck_id = :truck_id
            AND timestamp_utc > NOW() - INTERVAL 24 HOUR
        """)
        
        result = conn.execute(count_query, {"truck_id": truck_id}).fetchone()
        
        print(f"\n📊 Registros en fuel_metrics:")
        print(f"   Total últimas 24h: {result[0]}")
        print(f"   Más antiguo: {result[1]}")
        print(f"   Más reciente: {result[2]}")
    
    # ============================================================================
    # 5. VERIFICAR QUÉ DEVUELVE EL ENDPOINT /api/v2/trucks/{truck_id}
    # ============================================================================
    print("\n" + "=" * 80)
    print("5️⃣ SIMULACIÓN DE ENDPOINT /api/v2/trucks/{truck_id}")
    print("=" * 80)
    
    # Simular lo que hace get_truck_detail
    from database import db
    
    record = db.get_truck_latest_record(truck_id)
    
    if record:
        print(f"\n✅ database.py.get_truck_latest_record() retornó:")
        print(f"   Tipo: {type(record)}")
        print(f"   Keys ({len(record.keys())}): {list(record.keys())[:15]}...")
        print(f"\n   truck_id: {record.get('truck_id')}")
        print(f"   timestamp: {record.get('timestamp_utc') or record.get('timestamp')}")
        print(f"   truck_status: {record.get('truck_status')}")
        print(f"   estimated_pct: {record.get('estimated_pct')}")
        print(f"   rpm: {record.get('rpm')}")
        print(f"   speed_mph: {record.get('speed_mph')}")
        print(f"   mpg_current: {record.get('mpg_current')}")
        
        # Check for NaN/None values
        none_fields = [k for k, v in record.items() if v is None or (isinstance(v, float) and v != v)]
        if none_fields:
            print(f"\n⚠️  Campos con None/NaN ({len(none_fields)}): {none_fields[:10]}...")
    else:
        print(f"\n❌ database.py.get_truck_latest_record() retornó None")
    
    # ============================================================================
    # 6. VERIFICAR TABLA truck_sensors_cache (si existe)
    # ============================================================================
    print("\n" + "=" * 80)
    print("6️⃣ VERIFICAR truck_sensors_cache")
    print("=" * 80)
    
    with engine.connect() as conn:
        try:
            cache_query = text("""
                SELECT * FROM truck_sensors_cache
                WHERE truck_id = :truck_id
                LIMIT 1
            """)
            result = conn.execute(cache_query, {"truck_id": truck_id}).fetchone()
            
            if result:
                print(f"\n✅ truck_sensors_cache tiene datos para {truck_id}")
                print(f"   Timestamp: {result[1] if len(result) > 1 else 'N/A'}")
            else:
                print(f"\n⚠️  truck_sensors_cache NO tiene datos para {truck_id}")
        except Exception as e:
            print(f"\n❌ truck_sensors_cache no existe o error: {e}")
    
    print("\n" + "=" * 80)
    print("✅ DIAGNÓSTICO COMPLETADO")
    print("=" * 80)
    
except Exception as e:
    print(f"\n❌ ERROR GLOBAL: {e}")
    import traceback
    traceback.print_exc()
