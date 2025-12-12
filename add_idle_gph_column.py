"""
Script para agregar la columna idle_gph a fuel_metrics
"""
import pymysql

try:
    conn = pymysql.connect(
        host="localhost",
        port=3306,
        user="fuel_admin",
        password="FuelCopilot2025!",
        database="fuel_copilot",
        charset="utf8mb4",
    )
    
    cursor = conn.cursor()
    
    print("=" * 80)
    print("🔧 AGREGANDO COLUMNA idle_gph A fuel_metrics")
    print("=" * 80)
    print()
    
    # Agregar columna idle_gph después de idle_mode
    sql = """
        ALTER TABLE fuel_metrics 
        ADD COLUMN idle_gph DOUBLE NULL 
        AFTER idle_mode
    """
    
    print("Ejecutando: ALTER TABLE fuel_metrics ADD COLUMN idle_gph...")
    cursor.execute(sql)
    conn.commit()
    
    print("✅ Columna idle_gph agregada exitosamente")
    print()
    
    # Verificar
    cursor.execute("DESCRIBE fuel_metrics")
    columns = [row[0] for row in cursor.fetchall()]
    
    if 'idle_gph' in columns:
        print("✅ CONFIRMADO: idle_gph ahora existe en fuel_metrics")
        
        # Mostrar contexto
        idx = columns.index('idle_gph')
        print(f"\nColumnas alrededor de idle_gph:")
        for i in range(max(0, idx-2), min(len(columns), idx+3)):
            marker = " ← NUEVA" if columns[i] == 'idle_gph' else ""
            print(f"  {columns[i]}{marker}")
    else:
        print("❌ Error: idle_gph no se agregó correctamente")
    
    conn.close()
    
    print()
    print("=" * 80)
    print("🔄 Ahora reinicia WialonSyncService para que empiece a guardar datos:")
    print("   nssm restart WialonSyncService")
    print("=" * 80)
    
except pymysql.err.OperationalError as e:
    if "Duplicate column name" in str(e):
        print("✅ La columna idle_gph ya existe")
    else:
        print(f"❌ Error: {e}")
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
