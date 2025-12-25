"""
Wialon API Client - Direct API Communication
Reads data directly from Wialon API (SINGLE SOURCE OF TRUTH)

NO dependencies on wialon_collect MySQL database.
All data comes fresh from Wialon cloud.

Author: Fuel Copilot Team
Date: December 23, 2025
"""

import logging
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class WialonAPIClient:
    """
    Client for Wialon Remote API

    Wialon is the SINGLE SOURCE OF TRUTH for all sensor data.
    This client fetches data directly from Wialon cloud API.

    API Documentation: https://sdk.wialon.com/wiki/en/sidebar/remoteapi/apiref/apiref
    """

    def __init__(self, token: Optional[str] = None):
        """
        Initialize Wialon API client

        Args:
            token: Wialon API token (if None, reads from WIALON_TOKEN env var)
        """
        self.token = token or os.getenv("WIALON_TOKEN")
        if not self.token:
            raise ValueError("WIALON_TOKEN not set in environment variables")

        self.base_url = "https://hst-api.wialon.com/wialon/ajax.html"
        self.session_id: Optional[str] = None
        self.session_created_at: Optional[float] = None
        self.max_session_age = 3600  # Re-login every hour

    def _ensure_session(self):
        """Ensure we have a valid session, login if needed"""
        if self.session_id is None or self._session_expired():
            self._login()

    def _session_expired(self) -> bool:
        """Check if session has expired"""
        if self.session_created_at is None:
            return True
        age = time.time() - self.session_created_at
        return age > self.max_session_age

    def _login(self):
        """Login to Wialon API and get session ID"""
        try:
            params = {"svc": "token/login", "params": f'{{"token":"{self.token}"}}'}

            response = requests.post(self.base_url, params=params, timeout=10)
            data = response.json()

            if "eid" in data:
                self.session_id = data["eid"]
                self.session_created_at = time.time()
                logger.info(
                    f"✅ Logged in to Wialon API, session: {self.session_id[:20]}..."
                )
            else:
                error_msg = data.get("error", "Unknown error")
                raise Exception(f"Wialon login failed: {error_msg}")

        except Exception as e:
            logger.error(f"❌ Failed to login to Wialon: {e}")
            raise

    def _call_api(self, svc: str, params: Dict) -> Dict:
        """
        Make API call to Wialon

        Args:
            svc: Service name (e.g., 'messages/load_interval')
            params: Parameters dict

        Returns:
            Response dict
        """
        self._ensure_session()

        try:
            request_params = {
                "svc": svc,
                "params": str(params).replace("'", '"'),  # Convert to JSON string
                "sid": self.session_id,
            }

            response = requests.post(self.base_url, params=request_params, timeout=30)
            return response.json()

        except Exception as e:
            logger.error(f"❌ Wialon API call failed ({svc}): {e}")
            # Try re-login once
            self._login()
            raise

    def get_unit_last_message(
        self, unit_id: int, max_messages: int = 1
    ) -> Optional[Dict]:
        """
        Get last message(s) from a unit

        Args:
            unit_id: Wialon unit ID
            max_messages: Number of messages to retrieve

        Returns:
            Last message dict or None if no data
        """
        try:
            params = {
                "itemId": unit_id,
                "timeFrom": 0,
                "timeTo": 0,
                "flags": 0x0000,
                "flagsMask": 0xFF00,
                "loadCount": max_messages,
            }

            result = self._call_api("messages/load_interval", params)

            if result and "messages" in result and len(result["messages"]) > 0:
                return result["messages"][0]  # Most recent

            return None

        except Exception as e:
            logger.warning(f"⚠️ Failed to get messages for unit {unit_id}: {e}")
            return None

    def get_units_batch(self, unit_ids: List[int]) -> Dict[int, Optional[Dict]]:
        """
        Get last messages for multiple units in batch

        This is MORE EFFICIENT than calling get_unit_last_message repeatedly.

        Args:
            unit_ids: List of unit IDs

        Returns:
            Dict mapping unit_id -> last_message (or None if no data)
        """
        results = {}

        # Wialon API doesn't have native batch endpoint, but we can parallelize
        # For now, call sequentially with small delay to avoid rate limits
        for unit_id in unit_ids:
            message = self.get_unit_last_message(unit_id, max_messages=1)
            results[unit_id] = message
            time.sleep(0.05)  # 50ms delay between calls to avoid rate limit

        return results

    def parse_message_to_sensors(self, message: Dict, unit_id: int) -> Dict[str, Any]:
        """
        Parse Wialon message into sensor dict format

        Args:
            message: Wialon message dict
            unit_id: Unit ID

        Returns:
            Dict with sensor values in our standard format
        """
        if not message:
            return {}

        # Extract timestamp
        timestamp_epoch = message.get("t", 0)
        timestamp_utc = datetime.fromtimestamp(timestamp_epoch, tz=timezone.utc)

        # Extract position data
        pos = message.get("pos", {})
        lat = pos.get("y")
        lon = pos.get("x")
        speed_kmh = pos.get("s", 0)
        speed_mph = speed_kmh * 0.621371 if speed_kmh else 0
        altitude = pos.get("z", 0)
        course = pos.get("c", 0)
        sats = pos.get("sc", 0)

        # Extract parameters (sensors)
        params = message.get("p", {})

        # Build sensor dict
        sensors = {
            "unit_id": unit_id,
            "timestamp_epoch": timestamp_epoch,
            "timestamp_utc": timestamp_utc,
            "latitude": lat,
            "longitude": lon,
            "speed_mph": speed_mph,
            "altitude_ft": altitude * 3.28084 if altitude else 0,  # meters to feet
            "course": course,
            "sats": sats,
        }

        # Map common sensor parameters
        # These keys match what wialon_collect uses
        sensor_mapping = {
            "fuel_lvl": "fuel_lvl",
            "fuel_rate": "fuel_rate",
            "speed": "obd_speed",
            "rpm": "rpm",
            "odom": "odometer",
            "engine_hours": "engine_hours",
            "idle_hours": "idle_hours",
            "total_fuel_used": "total_fuel_used",
            "total_idle_fuel": "total_idle_fuel",
            "engine_load": "engine_load",
            "cool_temp": "coolant_temp",
            "oil_press": "oil_press",
            "oil_temp": "oil_temp",
            "def_level": "def_level",
            "air_temp": "ambient_temp",
            "pwr_ext": "pwr_ext",
            "pwr_int": "pwr_int",
            "hdop": "hdop",
            "fuel_economy": "fuel_economy",
            "gear": "gear",
            "barometer": "barometer",
            "dtc": "dtc",
            "j1939_spn": "j1939_spn",
            "j1939_fmi": "j1939_fmi",
        }

        # Add sensor values
        for wialon_key, our_key in sensor_mapping.items():
            if wialon_key in params:
                sensors[our_key] = params[wialon_key]

        return sensors

    def logout(self):
        """Logout from Wialon API"""
        if self.session_id:
            try:
                params = {}
                self._call_api("core/logout", params)
                logger.info("✅ Logged out from Wialon API")
            except Exception as e:
                logger.debug(f"Error during logout: {e}")
            finally:
                self.session_id = None
                self.session_created_at = None
