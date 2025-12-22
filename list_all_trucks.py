"""
List all trucks in units_map to find C00681
"""

import os

import pymysql
from dotenv import load_dotenv

load_dotenv()

conn = pymysql.connect(
    host=os.getenv("WIALON_DB_HOST"),
    port=int(os.getenv("WIALON_DB_PORT", "3306")),
    user=os.getenv("WIALON_DB_USER"),
    password=os.getenv("WIALON_DB_PASS"),
    database=os.getenv("WIALON_DB_NAME"),
    charset="utf8mb4",
    cursorclass=pymysql.cursors.DictCursor,
)

cursor = conn.cursor()

query = "SELECT beyondId, unit FROM units_map ORDER BY beyondId"
cursor.execute(query)
all_trucks = cursor.fetchall()

print(f"\n📋 ALL TRUCKS IN units_map ({len(all_trucks)} total):")
print("=" * 70)

for truck in all_trucks:
    print(f"{truck['beyondId']:15s} -> unit_id: {truck['unit']}")

cursor.close()
conn.close()
