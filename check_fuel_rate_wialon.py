"""
🔍 CHECK fuel_rate for FF7702, VD3579, JR7099, JB6858 - última hora

Verifica si estos trucks tienen fuel_rate en Wialon
"""

import pymysql
from datetime import datetime

# Wialon DB
conn = pymysql.connect(
    host="20.127.200.135",
    port=3306,
    user="tomas",
    password="Tomas2025",
    database="wialon_collect",
    charset="utf8mb4",
    cursorclass=pymysql.cursors.DictCursor,
)

print("=" * 80)
print("🔍 fuel_rate CHECK - FF7702, VD3579, JR7099, JB6858")
print("=" * 80)
print()

# Primero, encontrar los unit IDs de estos trucks
cursor = conn.cursor()

trucks_to_check = ["FF7702", "VD3579", "JR7099", "JB6858"]

print("📋 PASO 1: Buscar unit IDs")
print("-" * 80)

# Query para encontrar units que coincidan con estos nombres
query = """
    SELECT DISTINCT unit
    FROM sensors
    WHERE m > UNIX_TIMESTAMP(NOW() - INTERVAL 24 HOUR)
    ORDER BY unit
"""

cursor.execute(query)
all_units = [row['unit'] for row in cursor.fetchall()]

print(f"Units activos en últimas 24h: {len(all_units)} units")
print(f"Sample: {all_units[:10]}")
print()

# Ahora buscar fuel_rate para TODOS los units en última hora
print("📊 PASO 2: Buscar fuel_rate en TODOS los units (última hora)")
print("-" * 80)

query = """
    SELECT 
        unit,
        COUNT(*) as sample_count,
        MIN(value) as min_lph,
        MAX(value) as max_lph,
        AVG(value) as avg_lph,
        MAX(FROM_UNIXTIME(m)) as last_seen
    FROM sensors
    WHERE p = 'fuel_rate'
        AND m > UNIX_TIMESTAMP(NOW() - INTERVAL 1 HOUR)
    GROUP BY unit
    ORDER BY sample_count DESC
"""

cursor.execute(query)
fuel_rate_units = cursor.fetchall()

if fuel_rate_units:
    print(f"\n✅ Encontrados {len(fuel_rate_units)} units con fuel_rate en última hora:\n")
    
    for row in fuel_rate_units:
        unit = row['unit']
        count = row['sample_count']
        avg_lph = row['avg_lph']
        avg_gph = avg_lph / 3.78541
        min_lph = row['min_lph']
        max_lph = row['max_lph']
        last_seen = row['last_seen']
        
        print(f"Unit {unit}:")
        print(f"  📈 {count:>4} samples")
        print(f"  📊 Range: {min_lph:.2f} - {max_lph:.2f} LPH ({min_lph/3.78541:.2f} - {max_lph/3.78541:.2f} GPH)")
        print(f"  📊 Avg: {avg_lph:.2f} LPH ({avg_gph:.2f} GPH)")
        print(f"  🕐 Last: {last_seen}")
        print()
else:
    print("❌ NO se encontró fuel_rate para NINGÚN unit en la última hora")
    print()

# Verificar qué parámetros tienen estos units específicos
print("=" * 80)
print("🔬 PASO 3: Parámetros disponibles por unit (top 20 units, última hora)")
print("-" * 80)

query = """
    SELECT 
        unit,
        p as param,
        COUNT(*) as count
    FROM sensors
    WHERE m > UNIX_TIMESTAMP(NOW() - INTERVAL 1 HOUR)
    GROUP BY unit, p
    HAVING unit IN (
        SELECT unit 
        FROM sensors 
        WHERE m > UNIX_TIMESTAMP(NOW() - INTERVAL 1 HOUR)
        GROUP BY unit 
        ORDER BY COUNT(*) DESC 
        LIMIT 20
    )
    ORDER BY unit, count DESC
"""

cursor.execute(query)
results = cursor.fetchall()

current_unit = None
for row in results:
    if row['unit'] != current_unit:
        current_unit = row['unit']
        print(f"\n📍 Unit {current_unit}:")
    
    param = row['param']
    count = row['count']
    
    # Highlight fuel_rate if found
    if param == 'fuel_rate':
        print(f"  ✅ {param:20s} {count:>5,} samples  <-- FUEL_RATE!")
    else:
        print(f"     {param:20s} {count:>5,} samples")

print()
print("=" * 80)
print()
print("💡 CONCLUSIÓN:")
print()

if fuel_rate_units:
    print(f"✅ fuel_rate EXISTE en {len(fuel_rate_units)} units")
    print("   → Revisar si alguno corresponde a FF7702, VD3579, JR7099, JB6858")
    print("   → O pueden ser otros trucks en el sistema")
else:
    print("❌ fuel_rate NO EXISTE en ningún unit de Wialon")
    print("   → Pacific Track/Wialon no tiene este sensor habilitado")
    print("   → Backend debe usar fallback (0.8 GPH estimado)")

conn.close()
