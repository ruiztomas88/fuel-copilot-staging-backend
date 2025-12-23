"""
Ejecutar el script SQL para agregar columnas idle a fuel_metrics
"""
import os
import pymysql

try:
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
    print("🔧 AGREGANDO COLUMNAS IDLE A fuel_metrics")
    print("=" * 80)
    print()
    
    # Verificar estado actual
    print("📋 Verificando columnas existentes...")
    cursor.execute("""
        SELECT COUNT(*) as count
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = 'fuel_copilot'
          AND TABLE_NAME = 'fuel_metrics'
          AND COLUMN_NAME IN ('idle_gph', 'idle_method', 'idle_mode')
    """)
    existing = cursor.fetchone()['count']
    print(f"   Columnas idle existentes: {existing}/3")
    print()
    
    # Agregar idle_gph si no existe
    print("🔨 Agregando idle_gph...")
    cursor.execute("""
        SELECT COUNT(*) as count
        FROM INFORMATION_SCHEMA.COLUMNS 
        WHERE TABLE_SCHEMA = 'fuel_copilot'
          AND TABLE_NAME = 'fuel_metrics'
          AND COLUMN_NAME = 'idle_gph'
    """)
    
    if cursor.fetchone()['count'] == 0:
        cursor.execute("""
            ALTER TABLE fuel_metrics 
            ADD COLUMN idle_gph DECIMAL(6,3) DEFAULT NULL 
            COMMENT 'Idle consumption in gallons per hour'
        """)
        print("   ✅ idle_gph agregada")
    else:
        print("   ℹ️  idle_gph ya existe")
    
    # idle_method ya existe según el esquema
    print("🔨 Verificando idle_method...")
    cursor.execute("""
        SELECT COUNT(*) as count
        FROM INFORMATION_SCHEMA.COLUMNS 
        WHERE TABLE_SCHEMA = 'fuel_copilot'
          AND TABLE_NAME = 'fuel_metrics'
          AND COLUMN_NAME = 'idle_method'
    """)
    
    if cursor.fetchone()['count'] == 0:
        cursor.execute("""
            ALTER TABLE fuel_metrics 
            ADD COLUMN idle_method VARCHAR(50) DEFAULT NULL 
            COMMENT 'Method used to calculate idle'
        """)
        print("   ✅ idle_method agregada")
    else:
        print("   ✅ idle_method ya existe")
    
    # idle_mode ya existe según el esquema
    print("🔨 Verificando idle_mode...")
    cursor.execute("""
        SELECT COUNT(*) as count
        FROM INFORMATION_SCHEMA.COLUMNS 
        WHERE TABLE_SCHEMA = 'fuel_copilot'
          AND TABLE_NAME = 'fuel_metrics'
          AND COLUMN_NAME = 'idle_mode'
    """)
    
    if cursor.fetchone()['count'] == 0:
        cursor.execute("""
            ALTER TABLE fuel_metrics 
            ADD COLUMN idle_mode VARCHAR(50) DEFAULT NULL 
            COMMENT 'Idle classification'
        """)
        print("   ✅ idle_mode agregada")
    else:
        print("   ✅ idle_mode ya existe")
    
    conn.commit()
    
    print()
    print("=" * 80)
    print("📊 VERIFICACIÓN FINAL")
    print("=" * 80)
    
    cursor.execute("""
        SELECT 
            COLUMN_NAME,
            DATA_TYPE,
            COLUMN_COMMENT
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = 'fuel_copilot'
          AND TABLE_NAME = 'fuel_metrics'
          AND COLUMN_NAME IN ('idle_gph', 'idle_method', 'idle_mode')
        ORDER BY ORDINAL_POSITION
    """)
    
    results = cursor.fetchall()
    for row in results:
        print(f"  ✅ {row['COLUMN_NAME']:15} {row['DATA_TYPE']:15} - {row['COLUMN_COMMENT']}")
    
    print()
    
    if len(results) == 3:
        print("✅ SUCCESS: All 3 idle columns exist")
    else:
        print(f"⚠️  WARNING: Only {len(results)} of 3 idle columns exist")
    
    conn.close()
    
    print()
    print("=" * 80)
    print("🔄 Ahora reinicia WialonSyncService:")
    print("   nssm restart WialonSyncService")
    print("=" * 80)
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
