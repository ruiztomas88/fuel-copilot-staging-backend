"""
Wialon API Reader - Direct API integration
Reads data directly from Wialon Remote API instead of MySQL database

✅ BENEFITS:
- No dependency on wialon_collect database
- Automatic sync with tanks.yaml
- Always up-to-date with Wialon
- Simpler infrastructure

🔒 SECURITY:
- Uses Wialon token from environment variables
- HTTPS API calls
"""

import logging
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


class WialonAPIReader:
    """
    Reads data directly from Wialon Remote API

    API Documentation: https://sdk.wialon.com/wiki/en/sidebar/remoteapi/apiref/apiref
    """

    def __init__(self, token: Optional[str] = None):
        """
        Initialize Wialon API Reader

        Args:
            token: Wialon API token (if None, reads from WIALON_TOKEN env var)
        """
        self.token = token or os.getenv("WIALON_TOKEN")
        if not self.token:
            raise ValueError("WIALON_TOKEN not found in environment variables")

        self.base_url = "https://hst-api.wialon.com/wialon/ajax.html"
        self.sid = None  # Session ID
        self._session_created_at = None
        self._session_max_age = 3600  # Refresh session every hour

    def _ensure_session(self) -> bool:
        """Ensure we have a valid Wialon session"""
        try:
            # Check if session needs refresh
            if self.sid and self._session_created_at:
                session_age = time.time() - self._session_created_at
                if session_age > self._session_max_age:
                    logger.info(
                        f"🔄 Session age {session_age/60:.1f} min, refreshing..."
                    )
                    self.sid = None

            if self.sid is None:
                return self._login()

            return True
        except Exception as e:
            logger.error(f"❌ Session error: {e}")
            self.sid = None
            return self._login()

    def _login(self) -> bool:
        """Login to Wialon API and get session ID"""
        try:
            params = {"svc": "token/login", "params": f'{{"token":"{self.token}"}}'}

            response = requests.post(self.base_url, params=params, timeout=10)
            data = response.json()

            if "eid" in data:
                self.sid = data["eid"]
                self._session_created_at = time.time()
                logger.info(f"✅ Wialon API login successful, SID: {self.sid[:20]}...")
                return True
            else:
                logger.error(f"❌ Wialon API login failed: {data}")
                return False

        except Exception as e:
            logger.error(f"❌ Wialon API login exception: {e}")
            return False

    def get_unit_messages(
        self, unit_id: int, time_from: int = 0, time_to: int = 0, count: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get messages (data points) for a specific unit

        Args:
            unit_id: Wialon unit ID
            time_from: Start time (epoch seconds, 0 = from last message)
            time_to: End time (epoch seconds, 0 = current time)
            count: Number of messages to retrieve

        Returns:
            List of message dictionaries with sensor data
        """
        if not self._ensure_session():
            logger.error("❌ No valid Wialon session")
            return []

        try:
            params = {
                "svc": "messages/load_interval",
                "params": f'{{"itemId":{unit_id},"timeFrom":{time_from},"timeTo":{time_to},"flags":4294967295,"flagsMask":65280,"loadCount":{count}}}',
                "sid": self.sid,
            }

            response = requests.post(self.base_url, params=params, timeout=15)
            data = response.json()

            if "messages" in data:
                return data["messages"]
            else:
                # Session might have expired, try re-login
                if "error" in data and data["error"] == 1:
                    logger.warning("⚠️ Session expired, re-logging...")
                    self.sid = None
                    if self._ensure_session():
                        return self.get_unit_messages(
                            unit_id, time_from, time_to, count
                        )

                logger.warning(f"⚠️ No messages for unit {unit_id}: {data}")
                return []

        except Exception as e:
            logger.error(f"❌ Error getting messages for unit {unit_id}: {e}")
            return []

    def get_batch_latest_messages(
        self, unit_ids: List[int], count_per_unit: int = 5
    ) -> Dict[int, List[Dict[str, Any]]]:
        """
        Get latest messages for multiple units efficiently

        Args:
            unit_ids: List of Wialon unit IDs
            count_per_unit: Number of messages per unit

        Returns:
            Dictionary mapping unit_id -> list of messages
        """
        results = {}

        for unit_id in unit_ids:
            messages = self.get_unit_messages(
                unit_id=unit_id,
                time_from=0,  # From last message
                time_to=0,  # To current time
                count=count_per_unit,
            )
            results[unit_id] = messages

        return results

    def parse_message_to_sensor_data(
        self, message: Dict[str, Any], sensor_mapping: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        Parse Wialon message into sensor data dictionary

        Args:
            message: Raw Wialon message
            sensor_mapping: Map of sensor_name -> wialon_param_name

        Returns:
            Dictionary with parsed sensor values
        """
        parsed = {
            "timestamp": message.get("t"),  # Epoch seconds
            "latitude": message.get("pos", {}).get("y"),
            "longitude": message.get("pos", {}).get("x"),
            "speed_kmh": message.get("pos", {}).get("s"),  # Speed in km/h
            "altitude": message.get("pos", {}).get("z"),
            "course": message.get("pos", {}).get("c"),
        }

        # Convert speed from km/h to mph
        if parsed["speed_kmh"] is not None:
            parsed["speed_mph"] = parsed["speed_kmh"] * 0.621371

        # Parse parameters (sensors)
        params = message.get("p", {})

        # Map Wialon parameters to our sensor names
        for our_name, wialon_name in sensor_mapping.items():
            if wialon_name in params:
                parsed[our_name] = params[wialon_name]

        return parsed

    def logout(self):
        """Logout from Wialon API"""
        if self.sid:
            try:
                params = {"svc": "core/logout", "sid": self.sid}
                requests.post(self.base_url, params=params, timeout=5)
                logger.info("✅ Logged out from Wialon API")
            except Exception as e:
                logger.warning(f"⚠️ Logout error: {e}")
            finally:
                self.sid = None
