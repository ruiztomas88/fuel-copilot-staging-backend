import pymysql

conn = pymysql.connect(
    host="localhost", user="fuel_admin", password="FuelCopilot2025!", db="fuel_copilot"
)

cur = conn.cursor()
cur.execute(
    """
    SELECT truck_id, mpg_current, delta_miles, delta_fuel, created_at 
    FROM fuel_metrics 
    WHERE created_at > DATE_SUB(NOW(), INTERVAL 3 MINUTE) 
    ORDER BY created_at DESC 
    LIMIT 20
"""
)

rows = cur.fetchall()
print("truck_id | mpg     | delta_mi | delta_fuel | timestamp")
print("=" * 75)
for r in rows:
    mpg = f"{r[1]:.2f}" if r[1] else "NULL"
    delta_mi = f"{r[2]:.2f}" if r[2] else "0.00"
    delta_gal = f"{r[3]:.3f}" if r[3] else "0.000"
    print(f"{r[0]:8} | {mpg:>7} | {delta_mi:>8} | {delta_gal:>10} | {r[4]}")

print(f"\n✅ Total: {len(rows)} registros en últimos 3 min")

# Estadísticas de MPG
cur.execute(
    """
    SELECT 
        COUNT(*) as total, 
        AVG(mpg_current) as avg_mpg,
        MIN(mpg_current) as min_mpg, 
        MAX(mpg_current) as max_mpg,
        COUNT(CASE WHEN mpg_current > 8.2 THEN 1 END) as above_max,
        COUNT(CASE WHEN mpg_current < 3.8 THEN 1 END) as below_min
    FROM fuel_metrics 
    WHERE created_at > DATE_SUB(NOW(), INTERVAL 10 MINUTE)
      AND mpg_current IS NOT NULL
"""
)
stats = cur.fetchone()
print(f"\n📊 MPG Estadísticas (últimos 10 min):")
print(f"   Total records: {stats[0]}")
print(f"   Average MPG: {stats[1]:.2f}" if stats[1] else "   No data")
print(
    f"   Range: {stats[2]:.2f} - {stats[3]:.2f}"
    if stats[2] and stats[3]
    else "   No range"
)
print(f"   🔴 Above 8.2 (INVALID): {stats[4]}")
print(f"   🔴 Below 3.8 (INVALID): {stats[5]}")

conn.close()
