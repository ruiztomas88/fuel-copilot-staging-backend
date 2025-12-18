"""
🔍 Ver historial de barometer para FF7702 - últimas 48 horas
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from wialon_reader import TRUCK_UNIT_MAPPING, WialonConfig
from datetime import datetime, timedelta
import pytz
import pymysql

unit_id = TRUCK_UNIT_MAPPING["FF7702"]
print(f"FF7702 → unit_id: {unit_id}")

# Conectar
config = WialonConfig()
conn = pymysql.connect(
    host=config.host,
    port=config.port,
    user=config.user,
    password=config.password,
    database=config.database,
)

cursor = conn.cursor(pymysql.cursors.DictCursor)

# Buscar barometer en últimas 48 horas
utc_now = datetime.now(pytz.UTC)
cutoff_time = utc_now - timedelta(hours=48)
cutoff_epoch = int(cutoff_time.timestamp())

print(f"\nBuscando sensor 'barometer' para FF7702 (últimas 48h)...")
cursor.execute(
    """
    SELECT value, m as epoch_time, measure_datetime
    FROM sensors
    WHERE unit = %s
    AND p = 'barometer'
    AND m >= %s
    ORDER BY m DESC
    LIMIT 10
""",
    (unit_id, cutoff_epoch),
)

results = cursor.fetchall()

if results:
    print(f"\n✅ Encontrados {len(results)} registros de barometer:")
    for i, row in enumerate(results, 1):
        age_hours = (int(utc_now.timestamp()) - row["epoch_time"]) / 3600
        print(
            f"   {i}. value={row['value']:8.2f}  timestamp={row['measure_datetime']}  (hace {age_hours:.1f}h)"
        )
else:
    print("\n❌ NO hay datos de barometer en las últimas 48 horas")

    # Ver si existe el sensor en general
    cursor.execute(
        """
        SELECT value, m as epoch_time, measure_datetime
        FROM sensors
        WHERE unit = %s
        AND p = 'barometer'
        ORDER BY m DESC
        LIMIT 1
    """,
        (unit_id,),
    )

    last = cursor.fetchone()
    if last:
        age_hours = (int(utc_now.timestamp()) - last["epoch_time"]) / 3600
        age_days = age_hours / 24
        print(f"\n⚠️ Pero sí existe. Último dato:")
        print(f"   value={last['value']}  timestamp={last['measure_datetime']}")
        print(f"   Edad: {age_hours:.1f} horas ({age_days:.1f} días)")
    else:
        print("\n❌ El sensor 'barometer' NUNCA ha tenido datos para FF7702")

cursor.close()
conn.close()
