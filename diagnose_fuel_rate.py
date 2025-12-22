"""
Diagnóstico de fuel_rate_gph para entender variabilidad y calidad de datos
"""

from datetime import datetime, timedelta

import pymysql

conn = pymysql.connect(
    host="localhost", user="fuel_admin", password="FuelCopilot2025!", db="fuel_copilot"
)

print("=" * 80)
print("🔍 DIAGNÓSTICO DE FUEL_RATE_GPH")
print("=" * 80)

# 1. Verificar qué trucks tienen fuel_rate_gph
cur = conn.cursor()
cur.execute(
    """
    SELECT 
        truck_id,
        COUNT(*) as records,
        COUNT(CASE WHEN consumption_gph > 0 THEN 1 END) as with_fuel_rate,
        AVG(consumption_gph) as avg_gph,
        STDDEV(consumption_gph) as stddev_gph,
        MIN(consumption_gph) as min_gph,
        MAX(consumption_gph) as max_gph,
        MAX(created_at) as last_update
    FROM fuel_metrics
    WHERE created_at > DATE_SUB(NOW(), INTERVAL 2 HOUR)
      AND truck_status = 'MOVING'
    GROUP BY truck_id
    HAVING with_fuel_rate > 0
    ORDER BY stddev_gph DESC
    LIMIT 15
"""
)

print("\n📊 VARIABILIDAD DE FUEL_RATE_GPH (últimas 2 horas, trucks MOVING):")
print("-" * 80)
print(
    f"{'Truck':<10} {'Records':<10} {'Avg GPH':<10} {'StdDev':<10} {'Min':<8} {'Max':<8} {'Last Update'}"
)
print("-" * 80)

trucks_with_data = []
for row in cur.fetchall():
    truck_id, records, with_fuel, avg_gph, stddev, min_gph, max_gph, last_update = row
    if avg_gph and stddev:
        print(
            f"{truck_id:<10} {records:<10} {avg_gph:>9.2f} {stddev:>9.2f} {min_gph:>7.2f} {max_gph:>7.2f} {last_update}"
        )
        trucks_with_data.append((truck_id, stddev))

if not trucks_with_data:
    print("\n❌ No hay datos de fuel_rate_gph en las últimas 2 horas")
    print("\n🔍 Verificando datos más antiguos...")

    cur.execute(
        """
        SELECT 
            truck_id,
            COUNT(*) as records,
            AVG(consumption_gph) as avg_gph,
            MAX(created_at) as last_update
        FROM fuel_metrics
        WHERE consumption_gph > 0
        GROUP BY truck_id
        ORDER BY last_update DESC
        LIMIT 10
    """
    )

    print("\n📊 ÚLTIMOS DATOS DE FUEL_RATE_GPH (cualquier fecha):")
    print("-" * 80)
    for row in cur.fetchall():
        print(f"{row[0]:<10} {row[1]:<10} {row[2]:>9.2f} {row[3]}")

else:
    # Analizar el truck con más datos
    most_stable_truck = min(trucks_with_data, key=lambda x: x[1])[0]

    print(f"\n🎯 Analizando truck más estable: {most_stable_truck}")
    print("-" * 80)

    cur.execute(
        """
        SELECT 
            timestamp_utc,
            consumption_gph,
            speed_mph,
            rpm,
            mpg_current,
            odometer_mi
        FROM fuel_metrics
        WHERE truck_id = %s
          AND created_at > DATE_SUB(NOW(), INTERVAL 1 HOUR)
          AND consumption_gph > 0
        ORDER BY timestamp_utc DESC
        LIMIT 30
    """,
        (most_stable_truck,),
    )

    print(
        f"{'Timestamp':<20} {'GPH':<8} {'Speed':<8} {'RPM':<8} {'MPG':<8} {'Odometer'}"
    )
    print("-" * 80)

    samples = []
    for row in cur.fetchall():
        ts, gph, speed, rpm, mpg, odo = row
        samples.append((ts, gph, speed, rpm, mpg, odo))
        speed_str = f"{speed:.1f}" if speed else "NULL"
        rpm_str = f"{rpm}" if rpm else "NULL"
        mpg_str = f"{mpg:.2f}" if mpg else "NULL"
        odo_str = f"{odo:.0f}" if odo else "NULL"
        print(
            f"{str(ts):<20} {gph:>7.2f} {speed_str:>7} {rpm_str:>7} {mpg_str:>7} {odo_str:>10}"
        )

    # Análisis de consistencia
    if len(samples) >= 5:
        print("\n📈 ANÁLISIS DE CONSISTENCIA:")
        print("-" * 80)

        # Calcular MPG usando fuel_rate_gph
        valid_pairs = []
        for i in range(len(samples) - 1):
            curr = samples[i]
            prev = samples[i + 1]

            if curr[5] and prev[5] and curr[1] and prev[1]:  # odo y gph válidos
                delta_mi = curr[5] - prev[5]
                delta_time_sec = (curr[0] - prev[0]).total_seconds()
                delta_time_hr = delta_time_sec / 3600.0

                if 0.001 < delta_time_hr < 0.1 and delta_mi > 0:  # Entre 3.6s y 6min
                    avg_gph = (curr[1] + prev[1]) / 2.0
                    fuel_consumed = avg_gph * delta_time_hr

                    if fuel_consumed > 0.001:
                        calculated_mpg = delta_mi / fuel_consumed
                        valid_pairs.append(
                            {
                                "delta_mi": delta_mi,
                                "delta_time_min": delta_time_hr * 60,
                                "avg_gph": avg_gph,
                                "fuel_consumed": fuel_consumed,
                                "calculated_mpg": calculated_mpg,
                            }
                        )

        if valid_pairs:
            print(f"\n✅ {len(valid_pairs)} pares válidos para calcular MPG:")
            print(
                f"{'Delta Mi':<12} {'Time (min)':<12} {'Avg GPH':<12} {'Fuel Gal':<12} {'Calc MPG'}"
            )
            print("-" * 80)
            for p in valid_pairs[:10]:
                print(
                    f"{p['delta_mi']:>11.3f} {p['delta_time_min']:>11.2f} {p['avg_gph']:>11.2f} {p['fuel_consumed']:>11.3f} {p['calculated_mpg']:>10.2f}"
                )

            mpg_values = [p["calculated_mpg"] for p in valid_pairs]
            avg_mpg = sum(mpg_values) / len(mpg_values)
            min_mpg = min(mpg_values)
            max_mpg = max(mpg_values)

            print(f"\n📊 ESTADÍSTICAS MPG CALCULADO:")
            print(f"   Promedio: {avg_mpg:.2f} MPG")
            print(f"   Rango: {min_mpg:.2f} - {max_mpg:.2f} MPG")
            print(f"   Variación: {max_mpg - min_mpg:.2f} MPG")

            # Comparar con MPG almacenado
            stored_mpg = [s[4] for s in samples if s[4] is not None]
            if stored_mpg:
                avg_stored = sum(stored_mpg) / len(stored_mpg)
                print(f"\n🔍 COMPARACIÓN:")
                print(f"   MPG almacenado promedio: {avg_stored:.2f}")
                print(f"   MPG calculado promedio: {avg_mpg:.2f}")
                print(
                    f"   Diferencia: {abs(avg_stored - avg_mpg):.2f} MPG ({abs(avg_stored - avg_mpg)/avg_stored*100:.1f}%)"
                )

# 2. Verificar si hay columnas de fuel_level o total_fuel
print("\n\n🔍 VERIFICANDO COLUMNAS DE COMBUSTIBLE:")
print("-" * 80)
cur.execute("DESCRIBE fuel_metrics")
fuel_columns = [
    row[0]
    for row in cur.fetchall()
    if "fuel" in row[0].lower() or "level" in row[0].lower()
]
print("Columnas relacionadas con fuel:")
for col in fuel_columns:
    print(f"  - {col}")

# 3. Verificar datos en truck_sensors_cache
print("\n\n🔍 SENSORES EN CACHE (truck_sensors_cache):")
print("-" * 80)
cur.execute(
    """
    SELECT 
        truck_id,
        JSON_KEYS(sensors) as sensor_names
    FROM truck_sensors_cache
    WHERE JSON_KEYS(sensors) LIKE '%fuel%'
    LIMIT 5
"""
)

for row in cur.fetchall():
    print(f"Truck {row[0]}: {row[1]}")

conn.close()

print("\n" + "=" * 80)
print("✅ DIAGNÓSTICO COMPLETO")
print("=" * 80)
