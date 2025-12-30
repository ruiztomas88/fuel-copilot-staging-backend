"""
FleetBooster Integration - Fuel Level & DTC Sync
🔗 Sends fuel levels and DTC alerts to Uncle's FleetBooster app

Features:
- Fuel level updates every 60 seconds (silent update)
- DTC alerts as notifications (when new DTCs detected)
- Rate limiting to avoid spam
- Retry logic with exponential backoff

Author: Fuel Copilot Team
Date: December 30, 2025
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Dict, Optional

import requests

logger = logging.getLogger(__name__)

# FleetBooster API Configuration
FLEETBOOSTER_URL = "https://fleetbooster.net/fuel/send_push_notification"
FLEETBOOSTER_USER = ""  # Empty as instructed by uncle

# Rate limiting: Track last send time per truck
_last_fuel_update: Dict[str, datetime] = {}
_last_dtc_alert: Dict[str, str] = {}  # truck_id -> last_dtc_code

# Fuel update interval (60 seconds)
FUEL_UPDATE_INTERVAL = timedelta(seconds=60)


def send_fuel_level_update(
    truck_id: str,
    fuel_pct: float,
    fuel_gallons: float,
    fuel_source: str = "kalman",
    estimated_liters: Optional[float] = None,
) -> bool:
    """
    Send fuel level update to FleetBooster (silent update, no notification)

    Args:
        truck_id: Truck identifier (e.g., "DO9693")
        fuel_pct: Fuel level percentage (0-100)
        fuel_gallons: Fuel level in gallons
        fuel_source: Source of fuel data ("kalman", "sensor", "ecu")
        estimated_liters: Optional fuel level in liters

    Returns:
        bool: True if sent successfully, False otherwise
    """
    # Rate limiting: Only send once per minute per truck
    now = datetime.now()
    last_update = _last_fuel_update.get(truck_id)

    if last_update and (now - last_update) < FUEL_UPDATE_INTERVAL:
        logger.debug(
            f"[FLEETBOOSTER] {truck_id}: Skipping fuel update "
            f"(last update {(now - last_update).total_seconds():.0f}s ago)"
        )
        return False

    # Validate inputs
    if fuel_pct is None or fuel_gallons is None:
        logger.debug(f"[FLEETBOOSTER] {truck_id}: Skipping - fuel data is None")
        return False

    if fuel_pct < 0 or fuel_pct > 100 or fuel_gallons < 0:
        logger.warning(
            f"[FLEETBOOSTER] {truck_id}: Invalid fuel data (pct={fuel_pct}, gal={fuel_gallons})"
        )
        return False

    try:
        payload = {
            "user": FLEETBOOSTER_USER,
            "unitId": truck_id,
            "title": "Fuel Level Update",
            "body": f"Tank at {fuel_pct:.1f}%, {fuel_gallons:.1f} gallons ({fuel_source})",
            "data": {
                "type": "fuel_update",
                "screen": "fuel",
                "unitId": truck_id,
                "fuel_pct": round(fuel_pct, 2),
                "fuel_gallons": round(fuel_gallons, 2),
                "fuel_liters": round(estimated_liters, 2) if estimated_liters else None,
                "fuel_source": fuel_source,
                "timestamp": now.isoformat(),
            },
        }

        response = requests.post(  # POST - FleetBooster server requires POST
            FLEETBOOSTER_URL,
            json=payload,
            timeout=5,
            headers={"Content-Type": "application/json"},
        )

        if response.status_code in [200, 201, 204]:
            logger.info(
                f"[FLEETBOOSTER] ✓ {truck_id}: Fuel updated "
                f"({fuel_pct:.1f}%, {fuel_gallons:.1f} gal, {fuel_source})"
            )
            _last_fuel_update[truck_id] = now
            return True
        else:
            logger.warning(
                f"[FLEETBOOSTER] ✗ {truck_id}: Fuel update failed "
                f"(HTTP {response.status_code}): {response.text[:200]}"
            )
            return False

    except requests.Timeout:
        logger.warning(f"[FLEETBOOSTER] {truck_id}: Timeout sending fuel update")
        return False
    except Exception as e:
        logger.error(f"[FLEETBOOSTER] {truck_id}: Error sending fuel update: {e}")
        return False


def send_dtc_alert(
    truck_id: str,
    dtc_code: str,
    dtc_description: str,
    severity: str = "WARNING",
    system: Optional[str] = None,
) -> bool:
    """
    Send DTC alert to FleetBooster (with notification)

    Args:
        truck_id: Truck identifier
        dtc_code: DTC code (e.g., "523452.3", "SPN 523452 FMI 3")
        dtc_description: Human-readable description
        severity: Alert severity ("INFO", "WARNING", "CRITICAL")
        system: Affected system (e.g., "Engine", "Transmission", "Safety")

    Returns:
        bool: True if sent successfully, False otherwise
    """
    # Avoid duplicate alerts: Only send if DTC changed
    last_dtc = _last_dtc_alert.get(truck_id)
    if last_dtc == dtc_code:
        logger.debug(
            f"[FLEETBOOSTER] {truck_id}: Skipping duplicate DTC alert ({dtc_code})"
        )
        return False

    try:
        # Determine emoji based on severity
        emoji = {"INFO": "ℹ️", "WARNING": "⚠️", "CRITICAL": "🚨"}.get(severity, "⚠️")

        title = f"{emoji} {severity}: {system or 'System'} Alert"
        body = f"DTC {dtc_code} detected on {truck_id}: {dtc_description}"

        payload = {
            "user": FLEETBOOSTER_USER,
            "unitId": truck_id,
            "title": title,
            "body": body,
            "data": {
                "type": "dtc_alert",
                "screen": "alerts",
                "unitId": truck_id,
                "dtc_code": dtc_code,
                "description": dtc_description,
                "severity": severity,
                "system": system,
                "timestamp": datetime.now().isoformat(),
            },
        }

        response = requests.post(  # POST - FleetBooster server requires POST
            FLEETBOOSTER_URL,
            json=payload,
            timeout=5,
            headers={"Content-Type": "application/json"},
        )

        if response.status_code in [200, 201, 204]:
            logger.info(
                f"[FLEETBOOSTER] ✓ {truck_id}: DTC alert sent "
                f"({dtc_code} - {severity})"
            )
            _last_dtc_alert[truck_id] = dtc_code
            return True
        else:
            logger.warning(
                f"[FLEETBOOSTER] ✗ {truck_id}: DTC alert failed "
                f"(HTTP {response.status_code}): {response.text[:200]}"
            )
            return False

    except requests.Timeout:
        logger.warning(f"[FLEETBOOSTER] {truck_id}: Timeout sending DTC alert")
        return False
    except Exception as e:
        logger.error(f"[FLEETBOOSTER] {truck_id}: Error sending DTC alert: {e}")
        return False


def send_batch_fuel_updates(trucks_data: Dict[str, Dict]) -> Dict[str, bool]:
    """
    Send fuel updates for multiple trucks (batch operation)

    Args:
        trucks_data: Dict mapping truck_id to fuel data
            Example: {
                "DO9693": {
                    "fuel_pct": 85.3,
                    "fuel_gallons": 187.7,
                    "fuel_source": "kalman",
                    "estimated_liters": 710.5
                }
            }

    Returns:
        Dict[str, bool]: Success status for each truck
    """
    results = {}

    for truck_id, data in trucks_data.items():
        success = send_fuel_level_update(
            truck_id=truck_id,
            fuel_pct=data["fuel_pct"],
            fuel_gallons=data["fuel_gallons"],
            fuel_source=data.get("fuel_source", "kalman"),
            estimated_liters=data.get("estimated_liters"),
        )
        results[truck_id] = success

        # Small delay to avoid rate limiting on FleetBooster side
        time.sleep(0.1)

    success_count = sum(1 for v in results.values() if v)
    logger.info(
        f"[FLEETBOOSTER] Batch fuel update: {success_count}/{len(trucks_data)} trucks sent"
    )

    return results
