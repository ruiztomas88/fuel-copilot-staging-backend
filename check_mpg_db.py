#!/usr/bin/env python3
"""Check MPG values in database"""
from datetime import datetime

import pymysql


def check_mpg_db():
    import os

    conn = pymysql.connect(
        host="localhost",
        user="fuel_admin",
        password=os.getenv("MYSQL_PASSWORD"),
        database="fuel_copilot",
        cursorclass=pymysql.cursors.DictCursor,
    )

    try:
        with conn.cursor() as cursor:
            # Check mpg_baseline table
            cursor.execute(
                """
                SELECT truck_id, mpg_current, last_updated
                FROM mpg_baseline
                WHERE mpg_current > 8.2
                ORDER BY mpg_current DESC
            """
            )
            high_mpg = cursor.fetchall()

            print("=" * 80)
            print("🔴 HIGH MPG VALUES IN DATABASE (> 8.2)")
            print("=" * 80)
            for row in high_mpg:
                print(
                    f"  {row['truck_id']}: {row['mpg_current']} MPG (updated: {row['last_updated']})"
                )

            if not high_mpg:
                print("  ✅ No high MPG values found")

            print("\n" + "=" * 80)
            print("📊 ALL MPG VALUES")
            print("=" * 80)
            cursor.execute(
                """
                SELECT truck_id, mpg_current, last_updated
                FROM mpg_baseline
                ORDER BY mpg_current DESC
            """
            )
            all_mpg = cursor.fetchall()
            for row in all_mpg:
                emoji = "🔴" if row["mpg_current"] > 8.2 else "✅"
                print(f"  {emoji} {row['truck_id']}: {row['mpg_current']} MPG")

    finally:
        conn.close()


if __name__ == "__main__":
    check_mpg_db()
