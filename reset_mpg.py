"""
Reset MPG table to force recalculation
"""

import os

import pymysql
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    "host": os.getenv("MYSQL_HOST", "localhost"),
    "user": os.getenv("MYSQL_USER", "root"),
    "password": os.getenv("MYSQL_PASSWORD"),
    "database": os.getenv("MYSQL_DATABASE", "fuel_copilot"),
    "port": int(os.getenv("MYSQL_PORT", 3306)),
}

conn = pymysql.connect(**DB_CONFIG)
cursor = conn.cursor()

# Count before
cursor.execute("SELECT COUNT(*) FROM fuel_metrics WHERE mpg_current IS NOT NULL")
before = cursor.fetchone()[0]

# Reset
cursor.execute("UPDATE fuel_metrics SET mpg_current = NULL")
conn.commit()

# Count after
cursor.execute("SELECT COUNT(*) FROM fuel_metrics WHERE mpg_current IS NOT NULL")
after = cursor.fetchone()[0]

print(f"✅ MPG limpiados: {before} → {after}")
print(f"🔄 Reinicia servicios: .\\stop-services.ps1; .\\start-services.ps1")

cursor.close()
conn.close()
