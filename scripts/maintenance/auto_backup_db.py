#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Auto Database Backup Service
Backs up fuel_copilot DB every 6 hours
"""
import os
import subprocess
import sys
import time
from datetime import datetime

# Fix Windows console encoding for emojis
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

BACKUP_DIR = r"C:\Users\devteam\Proyectos\fuel-analytics-backend\backups"
BACKUP_INTERVAL = 6 * 60 * 60  # 6 hours in seconds


def backup_database():
    """Create MySQL backup using mysqldump"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = os.path.join(BACKUP_DIR, f"fuel_copilot_{timestamp}.sql")

    try:
        # Create backup directory if it doesn't exist
        os.makedirs(BACKUP_DIR, exist_ok=True)

        # Run mysqldump
        cmd = [
            "mysqldump",
            "-u",
            "fuel_admin",
            "-p"${MYSQL_PASSWORD}"",
            "fuel_copilot",
            "--single-transaction",
            "--quick",
            "--lock-tables=false",
        ]

        with open(backup_file, "w") as f:
            subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE, check=True)

        file_size = os.path.getsize(backup_file) / (1024 * 1024)  # MB
        print(
            f"[{datetime.now()}] ✅ Backup created: {backup_file} ({file_size:.2f} MB)"
        )

        # Keep only last 7 backups
        cleanup_old_backups()

    except Exception as e:
        print(f"[{datetime.now()}] ❌ Backup failed: {e}")


def cleanup_old_backups():
    """Keep only the 7 most recent backups"""
    try:
        backups = sorted(
            [
                os.path.join(BACKUP_DIR, f)
                for f in os.listdir(BACKUP_DIR)
                if f.endswith(".sql")
            ],
            key=os.path.getmtime,
            reverse=True,
        )

        for old_backup in backups[7:]:  # Keep 7, delete rest
            os.remove(old_backup)
            print(
                f"[{datetime.now()}] 🗑️  Deleted old backup: {os.path.basename(old_backup)}"
            )

    except Exception as e:
        print(f"[{datetime.now()}] ⚠️  Cleanup error: {e}")


if __name__ == "__main__":
    print(
        f"[{datetime.now()}] 🚀 Auto Backup Service started (interval: {BACKUP_INTERVAL/3600}h)"
    )

    # Initial backup on startup
    backup_database()

    # Run every 6 hours
    while True:
        time.sleep(BACKUP_INTERVAL)
        backup_database()
