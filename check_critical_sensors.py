#!/usr/bin/env python3
"""
Buscar sensores adicionales de alta prioridad que tienen menos cobertura
pero que son críticos para nuestros módulos
"""
import pymysql

conn = pymysql.connect(
    host="20.127.200.135",
    port=3306,
    user="tomas",
    password="Tomas2025",
    database="wialon_collect",
    cursorclass=pymysql.cursors.DictCursor,
)

try:
    cursor = conn.cursor()

    print("=" * 80)
    print("SENSORES CRÍTICOS - Disponibilidad por Truck (>10 trucks)")
    print("=" * 80)

    critical_params = [
        "gear",  # Driver behavior
        "total_idle_fuel",  # Idle cost
        "pto_hours",  # PTO tracking
        "fuel_economy",  # ECU MPG
        "brake_switch",  # Driver behavior
        "actual_retarder",  # Engine brake
        "j1939_fmi",  # Fault codes (FMI)
        "j1939_spn",  # Fault codes (SPN)
        "oil_level",  # Oil monitoring
        "fuel_t",  # Fuel temp
        "intrclr_t",  # Intercooler temp
        "trams_t",  # Transmission temp
    ]

    for param in critical_params:
        cursor.execute(
            """
            SELECT 
                sensor_id, 
                n as name, 
                p as parameter, 
                type,
                COUNT(DISTINCT unit) as truck_count
            FROM sensors
            WHERE p = %s
            GROUP BY sensor_id, n, p, type
            HAVING truck_count > 10
            ORDER BY truck_count DESC
        """,
            (param,),
        )

        results = cursor.fetchall()

        if results:
            for r in results:
                print(f"\n✅ {param:20} | ID {r['sensor_id']:3} | {r['name']:30}")
                print(
                    f"   Disponible en: {r['truck_count']} trucks | Tipo: {r['type']}"
                )

                # Ver ejemplo de valores para este sensor
                cursor.execute(
                    """
                    SELECT value, counter, unit
                    FROM sensors
                    WHERE sensor_id = %s AND p = %s
                    LIMIT 3
                """,
                    (r["sensor_id"], param),
                )

                examples = cursor.fetchall()
                if examples:
                    print(f"   Valores ejemplo:")
                    for ex in examples:
                        val = (
                            ex["value"]
                            if ex["value"] is not None
                            else f"counter={ex['counter']}"
                        )
                        print(f"      Unit {ex['unit']}: {val}")
        else:
            print(f"\n❌ {param:20} - No encontrado con >10 trucks")

    print("\n" + "=" * 80)
    print("RESUMEN DE RECOMENDACIONES")
    print("=" * 80)

    print(
        """
🔴 ALTA PRIORIDAD - Extraer INMEDIATAMENTE:
   1. gear (ID 7) - 149 trucks - Driver behavior, shift analysis
   2. total_idle_fuel (ID 41) - Idle cost calculation
   3. idle_hours (ID 25) - 131 trucks - Idle time tracking
   4. dtc (ID 1) - 146 trucks - Fault count
   5. cool_lvl (ID 10) - 138 trucks - Coolant level monitoring
   6. odom (ID 30) - 147 trucks - CRÍTICO para MPG accuracy

🟡 MEDIA PRIORIDAD - Agregar después:
   7. pto_hours - PTO usage tracking
   8. fuel_economy - ECU MPG validation
   9. brake_switch - Brake usage analysis
   10. actual_retarder - Engine brake usage
   11. obd_speed (ID 16) - 147 trucks - Speed validation
   12. trams_t (ID 50/51) - Transmission temp monitoring

🟢 BAJA PRIORIDAD - Nice to have:
   13. j1939_fmi - Detailed fault diagnostics
   14. j1939_spn - Detailed fault diagnostics  
   15. oil_level - Oil level monitoring
   16. fuel_t (ID 44/46) - Fuel temperature
   17. intrclr_t (ID 43) - Intercooler temperature
"""
    )

finally:
    conn.close()
