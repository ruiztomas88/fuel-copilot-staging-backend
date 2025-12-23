"""
Verificar datos recientes de idle en fuel_metrics para los trucks de interés
"""
import os
import pymysql
from datetime import datetime

try:
    # Conectar a fuel_copilot (base de datos local de la VM)
    conn = pymysql.connect(
        host="localhost",
        port=3306,
        user="fuel_admin",
        password=os.getenv("DB_PASSWORD"),
        database="fuel_copilot",
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )
    
    cursor = conn.cursor()
    
    print("=" * 80)
    print("🔍 VERIFICANDO DATOS RECIENTES DE IDLE")
    print("=" * 80)
    print()
    
    # Primero, verificar el esquema de la tabla
    print("📋 ESQUEMA DE LA TABLA fuel_metrics:")
    print("-" * 80)
    cursor.execute("DESCRIBE fuel_metrics")
    columns = cursor.fetchall()
    
    has_idle_gph = False
    has_idle_method = False
    
    for col in columns:
        print(f"  {col['Field']:30} {col['Type']:20} {col['Null']:5} {col['Key']:5}")
        if col['Field'] == 'idle_gph':
            has_idle_gph = True
        if col['Field'] == 'idle_method':
            has_idle_method = True
    
    print()
    if not has_idle_gph:
        print("❌ COLUMNA 'idle_gph' NO EXISTE")
    if not has_idle_method:
        print("❌ COLUMNA 'idle_method' NO EXISTE")
    
    if not has_idle_gph or not has_idle_method:
        print("\n⚠️  El esquema de fuel_metrics NO está actualizado!")
        print("   El backend está intentando guardar datos en columnas que no existen.")
        print()
    
    # Verificar datos recientes para los trucks de interés
    trucks = ['FF7702', 'JB6858', 'RT9127', 'JR7099', 'VD3579', 'RH1522', 'SG5760']
    
    print("=" * 80)
    print("📊 DATOS RECIENTES (últimos 5 minutos):")
    print("=" * 80)
    print()
    
    # Construir query dependiendo de las columnas disponibles
    if has_idle_gph:
        query = """
            SELECT 
                truck_id,
                idle_gph,
                idle_method,
                timestamp_utc,
                TIMESTAMPDIFF(SECOND, timestamp_utc, NOW()) as seconds_ago
            FROM fuel_metrics
            WHERE truck_id IN (%s)
                AND timestamp_utc > DATE_SUB(NOW(), INTERVAL 5 MINUTE)
            ORDER BY truck_id, timestamp_utc DESC
        """ % ','.join(['%s'] * len(trucks))
        
        cursor.execute(query, trucks)
        results = cursor.fetchall()
        
        if results:
            current_truck = None
            for row in results:
                if row['truck_id'] != current_truck:
                    if current_truck is not None:
                        print()
                    current_truck = row['truck_id']
                    print(f"{row['truck_id']}:")
                
                method_icon = "✅" if row.get('idle_method') == 'SENSOR_FUEL_RATE' else "⚠️ "
                print(f"  {row['idle_gph']:.2f} GPH  {method_icon} {row.get('idle_method', 'N/A')}  ({row['seconds_ago']}s ago)")
        else:
            print("❌ No hay datos recientes en fuel_metrics para estos trucks")
    else:
        print("⚠️  No se puede verificar idle_gph porque la columna no existe")
        
        # Ver qué columnas SÍ tienen datos
        cursor.execute("""
            SELECT truck_id, COUNT(*) as records, MAX(timestamp_utc) as last_update
            FROM fuel_metrics
            WHERE truck_id IN (%s)
            GROUP BY truck_id
        """ % ','.join(['%s'] * len(trucks)), trucks)
        
        results = cursor.fetchall()
        if results:
            print("\nRegistros encontrados (pero sin idle_gph):")
            for row in results:
                print(f"  {row['truck_id']}: {row['records']} records, último: {row['last_update']}")
    
    conn.close()
    
    print()
    print("=" * 80)
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
