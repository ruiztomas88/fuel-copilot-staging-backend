"""
🔍 CHECK fuel_rate PER TRUCK - Diagnóstico específico para RT9127-RT9135

Verifica si NUESTROS trucks tienen fuel_rate habilitado
"""

import pymysql
from datetime import datetime, timedelta

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
print("🔍 fuel_rate SENSOR CHECK - PER TRUCK")
print("=" * 80)
print()

# Map truck IDs to Wialon unit IDs
TRUCK_UNIT_MAP = {
    "RT9127": 2201,
    "RT9129": 2202,
    "RT9134": 2203,
    "RT9135": 2204,
}

cursor = conn.cursor()

print("📊 ÚLTIMOS 7 DÍAS")
print("-" * 80)

for truck_id, unit_id in TRUCK_UNIT_MAP.items():
    # Check if fuel_rate exists for this truck in last 7 days
    query = """
        SELECT 
            COUNT(*) as sample_count,
            MIN(value) as min_value,
            MAX(value) as max_value,
            AVG(value) as avg_value,
            MIN(FROM_UNIXTIME(m)) as first_seen,
            MAX(FROM_UNIXTIME(m)) as last_seen
        FROM sensors
        WHERE unit = %s
            AND p = 'fuel_rate'
            AND m > UNIX_TIMESTAMP(NOW() - INTERVAL 7 DAY)
    """
    
    cursor.execute(query, (unit_id,))
    result = cursor.fetchone()
    
    if result and result['sample_count'] > 0:
        count = result['sample_count']
        avg_lph = result['avg_value']
        avg_gph = avg_lph / 3.78541
        min_lph = result['min_value']
        max_lph = result['max_value']
        last_seen = result['last_seen']
        
        print(f"{truck_id} (unit {unit_id}):")
        print(f"  ✅ fuel_rate EXISTS - {count:,} samples in last 7 days")
        print(f"  📈 Range: {min_lph:.2f} - {max_lph:.2f} LPH ({min_lph/3.78541:.2f} - {max_lph/3.78541:.2f} GPH)")
        print(f"  📊 Average: {avg_lph:.2f} LPH ({avg_gph:.2f} GPH)")
        print(f"  🕐 Last seen: {last_seen}")
    else:
        print(f"{truck_id} (unit {unit_id}):")
        print(f"  ❌ fuel_rate NOT FOUND (0 samples in last 7 days)")
    
    print()

print("=" * 80)
print()

# Now check what params ARE available for these trucks
print("🔬 AVAILABLE PARAMETERS FOR OUR TRUCKS (last 24h)")
print("-" * 80)

for truck_id, unit_id in TRUCK_UNIT_MAP.items():
    query = """
        SELECT p as param, COUNT(*) as count
        FROM sensors
        WHERE unit = %s
            AND m > UNIX_TIMESTAMP(NOW() - INTERVAL 24 HOUR)
        GROUP BY p
        ORDER BY count DESC
        LIMIT 15
    """
    
    cursor.execute(query, (unit_id,))
    results = cursor.fetchall()
    
    print(f"\n{truck_id} (unit {unit_id}) - Top parameters:")
    for row in results:
        print(f"  {row['param']:20s} {row['count']:>6,} samples")

print()
print("=" * 80)
print()
print("💡 CONCLUSIÓN:")
print()
print("Si fuel_rate NO existe para RT9127-RT9135:")
print("  → Pacific Track/Wialon no tiene este sensor habilitado")
print("  → Backend usará fallback: 0.8 GPH estimado")
print("  → Solución: Contactar Pacific Track para habilitar fuel_rate")
print()
print("Si fuel_rate SÍ existe:")
print("  → Backend debería usarlo automáticamente")
print("  → Verificar logs: tail -f logs/backend-stdout.log | grep fuel_rate")

conn.close()
