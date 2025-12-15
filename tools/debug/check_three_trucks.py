"""
Verificar fuel_rate para FF7702, JB6858, RT9127
"""
import pymysql

# Unit IDs conocidos (desde tanks.yaml)
TRUCKS = {
    "FF7702": 401989385,
    "JB6858": 402007354,
    "RT9127": 401905963,
}

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
print("🔬 fuel_rate CHECK - FF7702, JB6858, RT9127")
print("=" * 80)
print()

cursor = conn.cursor()

for truck_id, unit_id in TRUCKS.items():
    print(f"📊 {truck_id} (Wialon unit: {unit_id})")
    print("-" * 80)
    
    # Check last hour
    query = """
        SELECT 
            COUNT(*) as samples,
            MIN(value) as min_val,
            MAX(value) as max_val,
            AVG(value) as avg_val,
            MAX(FROM_UNIXTIME(m)) as last_time,
            TIMESTAMPDIFF(SECOND, MAX(FROM_UNIXTIME(m)), NOW()) as seconds_ago
        FROM sensors
        WHERE unit = %s 
            AND p = 'fuel_rate'
            AND m > UNIX_TIMESTAMP(NOW() - INTERVAL 1 HOUR)
    """
    cursor.execute(query, (unit_id,))
    result = cursor.fetchone()
    
    if result and result["samples"] > 0:
        print(f"  ✅ fuel_rate ACTIVO")
        print(f"  📈 Samples (1h): {result['samples']}")
        print(f"  📊 Range: {result['min_val']:.2f} - {result['max_val']:.2f} LPH")
        print(f"  📊 Avg: {result['avg_val']:.2f} LPH ({result['avg_val']/3.785:.2f} GPH)")
        print(f"  🕐 Last: {result['seconds_ago']}s ago")
        
        # Check if values are in valid idle range (0.4-3.0 LPH)
        if result['min_val'] >= 0.4 and result['max_val'] <= 3.0:
            print(f"  🎯 VALORES EN RANGO IDLE (0.4-3.0 LPH) ✓")
        elif result['min_val'] < 0.4:
            print(f"  ⚠️  Algunos valores BAJO umbral (< 0.4 LPH)")
        else:
            print(f"  ⚠️  Algunos valores SOBRE rango idle (> 3.0 LPH) - truck en movimiento")
            
        # Get recent samples
        query2 = """
            SELECT 
                value,
                FROM_UNIXTIME(m) as timestamp
            FROM sensors
            WHERE unit = %s 
                AND p = 'fuel_rate'
                AND m > UNIX_TIMESTAMP(NOW() - INTERVAL 5 MINUTE)
            ORDER BY m DESC
            LIMIT 5
        """
        cursor.execute(query2, (unit_id,))
        samples = cursor.fetchall()
        
        if samples:
            print(f"\n  📋 Últimas 5 muestras:")
            for s in samples:
                print(f"     {s['timestamp']}: {s['value']:.2f} LPH ({s['value']/3.785:.2f} GPH)")
    else:
        print(f"  ❌ fuel_rate NO DISPONIBLE")
        print(f"  → Sensor no habilitado en Pacific Track para este truck")
        
        # Check what sensors ARE available
        query3 = """
            SELECT DISTINCT p
            FROM sensors
            WHERE unit = %s
                AND m > UNIX_TIMESTAMP(NOW() - INTERVAL 1 HOUR)
            ORDER BY p
        """
        cursor.execute(query3, (unit_id,))
        sensors = [row["p"] for row in cursor.fetchall()]
        
        if sensors:
            print(f"\n  📋 Sensores disponibles: {', '.join(sensors[:10])}")
            if len(sensors) > 10:
                print(f"     ... y {len(sensors)-10} más")
    
    print()

conn.close()

print("=" * 80)
print("💡 NOTAS:")
print("  - fuel_rate debe estar entre 0.4-3.0 LPH para idle detection")
print("  - Backend usa fuel_rate_min_lph = 0.4 (v5.4.5)")
print("  - Si fuel_rate no está, backend usa fallback 0.66 GPH estimado")
print("=" * 80)
