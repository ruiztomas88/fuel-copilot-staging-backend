"""
Script para agregar columnas faltantes a fuel_metrics
Basado en los errores del pull: idle_hours, intake_temp_f
"""
import pymysql

conn = pymysql.connect(
    host='localhost',
    user='fuel_admin',
    password='FuelCopilot2025!',
    database='fuel_copilot'
)

cursor = conn.cursor()

print("=" * 70)
print("AGREGANDO COLUMNAS FALTANTES A fuel_metrics")
print("=" * 70)

# Columnas que el pull espera pero no existen
columns_to_add = [
    ('idle_hours', 'DECIMAL(10,2)', 'Horas totales en idle (acumulativo)'),
    ('intake_air_temp_f', 'DECIMAL(6,2)', 'Temperatura de aire de admisión en °F'),
]

for col_name, col_type, description in columns_to_add:
    try:
        # Verificar si existe
        cursor.execute(f"""
            SELECT COUNT(*) 
            FROM information_schema.COLUMNS 
            WHERE TABLE_SCHEMA = 'fuel_copilot' 
            AND TABLE_NAME = 'fuel_metrics' 
            AND COLUMN_NAME = '{col_name}'
        """)
        
        if cursor.fetchone()[0] == 0:
            # Agregar columna
            cursor.execute(f"""
                ALTER TABLE fuel_metrics 
                ADD COLUMN {col_name} {col_type} 
                COMMENT '{description}'
            """)
            print(f"✅ Agregada: {col_name} ({col_type})")
        else:
            print(f"⏭️  Ya existe: {col_name}")
            
    except Exception as e:
        print(f"❌ Error con {col_name}: {e}")

conn.commit()

# Verificar columnas finales
cursor.execute("SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA='fuel_copilot' AND TABLE_NAME='fuel_metrics'")
total = cursor.fetchone()[0]

print(f"\n✅ Total columnas en fuel_metrics: {total}")

cursor.close()
conn.close()
