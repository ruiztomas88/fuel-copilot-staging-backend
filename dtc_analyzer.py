"""
DTC (Diagnostic Trouble Code) Analyzer
v3.12.28 - December 2024

Monitors and alerts on engine diagnostic trouble codes.
High ROI feature - can prevent $2,000-$5,000 breakdowns per incident.

DTC codes follow SAE J1939 standard for heavy-duty trucks:
- SPN (Suspect Parameter Number): Identifies component/signal
- FMI (Failure Mode Identifier): Describes failure type (0-31)

Format in Wialon: "SPN.FMI" or "SPN.FMI,SPN.FMI" (comma-separated)
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Set, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class DTCSeverity(Enum):
    """DTC severity levels for prioritization"""

    CRITICAL = "critical"  # Stop truck immediately - potential breakdown/safety
    WARNING = "warning"  # Schedule service soon - within 24-48 hours
    INFO = "info"  # Monitor - can wait until scheduled maintenance


@dataclass
class DTCCode:
    """Parsed DTC code with metadata"""

    spn: int  # Suspect Parameter Number
    fmi: int  # Failure Mode Identifier
    raw: str  # Original string from Wialon
    severity: DTCSeverity = DTCSeverity.WARNING
    description: str = ""
    recommended_action: str = ""
    system: str = (
        "UNKNOWN"  # 🆕 v5.7.1: System classification (ENGINE, TRANSMISSION, etc)
    )

    @property
    def code(self) -> str:
        return f"SPN{self.spn}.FMI{self.fmi}"


@dataclass
class DTCAlert:
    """Alert generated from DTC detection"""

    truck_id: str
    timestamp: datetime
    codes: List[DTCCode]
    severity: DTCSeverity
    message: str
    is_new: bool = True  # First time seeing this code
    hours_active: float = 0.0  # How long code has been present


# ═══════════════════════════════════════════════════════════════════════════════
# CRITICAL DTC CODES - Stop truck, schedule immediate service
# These indicate imminent breakdown risk
# ═══════════════════════════════════════════════════════════════════════════════
CRITICAL_SPNS: Dict[int, str] = {
    # Engine/Fuel System
    91: "Throttle Position Sensor",
    100: "Engine Oil Pressure",
    102: "Manifold Absolute Pressure",
    110: "Engine Coolant Temperature",
    157: "Fuel Rail Pressure",
    190: "Engine Speed",
    520: "Engine Hours",
    # Transmission
    127: "Transmission Oil Pressure",
    177: "Transmission Oil Temperature",
    # Aftertreatment (DEF System) - Can derate engine
    1761: "DEF Tank Level",
    3031: "DEF Quality",
    3216: "DEF System - Inducement",
    3226: "SCR Catalyst Conversion Efficiency",
    4364: "DEF Dosing",
    5246: "DEF Tank Temperature",
    # Safety Critical
    521: "Service Brake Status",
    587: "Engine Idle Speed",
    641: "Variable Geometry Turbo",
    651: "Injector Metering Rail 1 Pressure",
}

# FMI codes that indicate critical failure modes
CRITICAL_FMIS: Set[int] = {
    0,  # Data Valid But Above Normal Operational Range - Most Severe Level
    1,  # Data Valid But Below Normal Operational Range - Most Severe Level
    3,  # Voltage Above Normal, Or Shorted To High Source
    4,  # Voltage Below Normal, Or Shorted To Low Source
    5,  # Current Below Normal Or Open Circuit
    6,  # Current Above Normal Or Grounded Circuit
    12,  # Bad Intelligent Device Or Component
}

# ═══════════════════════════════════════════════════════════════════════════════
# WARNING DTC CODES - Schedule service within 24-48 hours
# ═══════════════════════════════════════════════════════════════════════════════
WARNING_SPNS: Dict[int, str] = {
    # Engine Sensors
    94: "Fuel Delivery Pressure",
    105: "Intake Manifold Temperature",
    108: "Barometric Pressure",
    111: "Coolant Level",
    171: "Ambient Air Temperature",
    # Exhaust/Emissions
    411: "EGR Temperature",
    412: "EGR Differential Pressure",
    1127: "DPF Outlet Temperature",
    1173: "Exhaust Gas Recirculation Mass Flow Rate",
    3242: "DPF Pressure Differential",
    3246: "DPF Soot Load",
    3251: "DPF Regeneration",
    # Electrical
    158: "Battery Potential / Power Input",
    167: "Alternator Charging Voltage",
    168: "Battery Potential",
    # HVAC (driver comfort but not critical)
    441: "Air Conditioner High Pressure",
    464: "Air Conditioning Refrigerant Pressure",
}


class DTCAnalyzer:
    """
    Analyzes DTC codes from trucks and generates actionable alerts.

    Usage:
        analyzer = DTCAnalyzer()
        alerts = analyzer.process_truck_dtc(truck_id, dtc_string, timestamp)
        for alert in alerts:
            if alert.severity == DTCSeverity.CRITICAL:
                # Send immediate notification
                pass
    """

    def __init__(self):
        # Track active DTCs per truck to detect new vs existing
        self._active_dtcs: Dict[str, Dict[str, datetime]] = (
            {}
        )  # truck_id -> {dtc_code -> first_seen}
        # Cooldown to avoid duplicate alerts (1 hour)
        self._last_alert_time: Dict[str, Dict[str, datetime]] = (
            {}
        )  # truck_id -> {dtc_code -> last_alert}
        self.alert_cooldown_minutes = 60

    def parse_dtc_string(self, dtc_string: Optional[str]) -> List[DTCCode]:
        """
        Parse DTC string from Wialon into structured codes.

        Args:
            dtc_string: Raw DTC string, e.g. "100.4" or "100.4,157.3"

        Returns:
            List of parsed DTCCode objects
        """
        if not dtc_string or dtc_string.strip() == "":
            return []

        codes = []
        # Split by comma for multiple codes
        parts = dtc_string.split(",")

        for part in parts:
            part = part.strip()
            if not part:
                continue

            try:
                # Format: SPN.FMI or just SPN (assume FMI=0)
                if "." in part:
                    spn_str, fmi_str = part.split(".", 1)
                    spn = int(float(spn_str))
                    fmi = int(float(fmi_str))
                else:
                    spn = int(float(part))
                    fmi = 0

                # Determine severity
                severity = self._determine_severity(spn, fmi)

                # Get description
                description = self._get_spn_description(spn)
                action = self._get_recommended_action(spn, fmi, severity)

                codes.append(
                    DTCCode(
                        spn=spn,
                        fmi=fmi,
                        raw=part,
                        severity=severity,
                        description=description,
                        recommended_action=action,
                    )
                )

            except (ValueError, IndexError) as e:
                logger.warning(f"Failed to parse DTC code '{part}': {e}")
                continue

        return codes

    def _determine_severity(self, spn: int, fmi: int) -> DTCSeverity:
        """Determine severity based on SPN and FMI"""
        # Critical if SPN is critical OR FMI is critical failure mode
        if spn in CRITICAL_SPNS:
            return DTCSeverity.CRITICAL
        if fmi in CRITICAL_FMIS:
            return DTCSeverity.CRITICAL
        if spn in WARNING_SPNS:
            return DTCSeverity.WARNING
        return DTCSeverity.INFO

    def _get_spn_description(self, spn: int) -> str:
        """Get human-readable description for SPN"""
        if spn in CRITICAL_SPNS:
            return CRITICAL_SPNS[spn]
        if spn in WARNING_SPNS:
            return WARNING_SPNS[spn]
        return f"Unknown component (SPN {spn})"

    def _get_recommended_action(self, spn: int, fmi: int, severity: DTCSeverity) -> str:
        """Get recommended action based on DTC"""
        if severity == DTCSeverity.CRITICAL:
            if spn == 100:  # Oil pressure
                return "⛔ STOP immediately. Check oil level. Do not run engine if oil pressure is low."
            if spn == 110:  # Coolant temp
                return "⛔ STOP and let engine cool. Check coolant level. Risk of engine damage."
            if spn in [1761, 3031, 3216, 4364]:  # DEF system
                return "⚠️ DEF system issue. Engine may derate to 5 MPH. Service within 24 hours."
            if spn == 157:  # Fuel rail pressure
                return "⛔ Fuel system issue. May cause engine shutdown. Schedule immediate service."
            return "⛔ Critical issue detected. Schedule service ASAP to prevent breakdown."

        if severity == DTCSeverity.WARNING:
            if spn in [3242, 3246, 3251]:  # DPF issues
                return "🔧 DPF attention needed. May need forced regen. Schedule service within 48 hours."
            if spn in [158, 167, 168]:  # Battery/alternator
                return "🔋 Electrical system issue. Check battery and alternator. May cause starting issues."
            return "🔧 Schedule service within 24-48 hours."

        return "📋 Monitor during next scheduled maintenance."

    def process_truck_dtc(
        self, truck_id: str, dtc_string: Optional[str], timestamp: datetime
    ) -> List[DTCAlert]:
        """
        Process DTC string from a truck and generate alerts.

        Args:
            truck_id: Truck identifier
            dtc_string: Raw DTC string from Wialon
            timestamp: When the DTC was read

        Returns:
            List of DTCAlert objects (may be empty if no new/actionable DTCs)
        """
        if not dtc_string:
            # Clear active DTCs if truck reports no codes
            if truck_id in self._active_dtcs:
                self._active_dtcs[truck_id] = {}
            return []

        codes = self.parse_dtc_string(dtc_string)
        if not codes:
            return []

        # Initialize tracking for this truck
        if truck_id not in self._active_dtcs:
            self._active_dtcs[truck_id] = {}
        if truck_id not in self._last_alert_time:
            self._last_alert_time[truck_id] = {}

        alerts = []
        current_codes = set()

        for code in codes:
            code_key = code.code
            current_codes.add(code_key)

            # Check if this is a new code
            is_new = code_key not in self._active_dtcs[truck_id]

            if is_new:
                self._active_dtcs[truck_id][code_key] = timestamp

            first_seen = self._active_dtcs[truck_id].get(code_key, timestamp)
            hours_active = (timestamp - first_seen).total_seconds() / 3600

            # Check cooldown
            last_alert = self._last_alert_time[truck_id].get(code_key)
            cooldown_passed = (
                last_alert is None
                or (timestamp - last_alert).total_seconds() / 60
                >= self.alert_cooldown_minutes
            )

            # Generate alert if:
            # 1. It's a new code (first detection)
            # 2. It's critical severity (always alert)
            # 3. Cooldown has passed for repeat alerts
            should_alert = is_new or (
                code.severity == DTCSeverity.CRITICAL and cooldown_passed
            )

            if should_alert:
                message = self._format_alert_message(
                    truck_id, code, is_new, hours_active
                )

                alert = DTCAlert(
                    truck_id=truck_id,
                    timestamp=timestamp,
                    codes=[code],
                    severity=code.severity,
                    message=message,
                    is_new=is_new,
                    hours_active=hours_active,
                )
                alerts.append(alert)
                self._last_alert_time[truck_id][code_key] = timestamp

        # Clean up codes that are no longer active
        for old_code in list(self._active_dtcs[truck_id].keys()):
            if old_code not in current_codes:
                del self._active_dtcs[truck_id][old_code]
                if old_code in self._last_alert_time[truck_id]:
                    del self._last_alert_time[truck_id][old_code]
                logger.info(f"[{truck_id}] DTC {old_code} cleared")

        return alerts

    def _format_alert_message(
        self, truck_id: str, code: DTCCode, is_new: bool, hours_active: float
    ) -> str:
        """Format alert message for notification"""
        severity_emoji = {
            DTCSeverity.CRITICAL: "🚨",
            DTCSeverity.WARNING: "⚠️",
            DTCSeverity.INFO: "ℹ️",
        }

        emoji = severity_emoji.get(code.severity, "📋")
        status = "NEW" if is_new else f"Active for {hours_active:.1f}h"

        return (
            f"{emoji} DTC Alert - {truck_id}\n"
            f"Code: {code.code}\n"
            f"Component: {code.description}\n"
            f"Status: {status}\n"
            f"Action: {code.recommended_action}"
        )

    def get_active_dtcs(self, truck_id: Optional[str] = None) -> Dict[str, List[str]]:
        """Get currently active DTCs for truck(s)"""
        if truck_id:
            return {truck_id: list(self._active_dtcs.get(truck_id, {}).keys())}
        return {tid: list(codes.keys()) for tid, codes in self._active_dtcs.items()}

    def get_fleet_dtc_summary(self) -> Dict[str, Any]:
        """Get summary of DTC status across fleet"""
        total_dtcs = 0
        trucks_with_dtcs = 0
        critical_count = 0
        warning_count = 0

        for truck_id, codes in self._active_dtcs.items():
            if codes:
                trucks_with_dtcs += 1
                total_dtcs += len(codes)

        return {
            "trucks_with_dtcs": trucks_with_dtcs,
            "total_active_dtcs": total_dtcs,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


# ═══════════════════════════════════════════════════════════════════════════════
# INTEGRATION HELPER
# ═══════════════════════════════════════════════════════════════════════════════

# Global instance for use in main loop
_dtc_analyzer: Optional[DTCAnalyzer] = None


def get_dtc_analyzer() -> DTCAnalyzer:
    """Get or create global DTC analyzer instance"""
    global _dtc_analyzer
    if _dtc_analyzer is None:
        _dtc_analyzer = DTCAnalyzer()
    return _dtc_analyzer


def process_dtc_from_sensor_data(
    truck_id: str, dtc_value: Optional[str], timestamp: datetime
) -> List[DTCAlert]:
    """
    Convenience function to process DTC from wialon_reader sensor data.

    Usage in main.py or estimator.py:
        from dtc_analyzer import process_dtc_from_sensor_data

        for truck_data in wialon_data:
            alerts = process_dtc_from_sensor_data(
                truck_data.truck_id,
                truck_data.dtc,
                truck_data.timestamp
            )
            for alert in alerts:
                if alert.severity == DTCSeverity.CRITICAL:
                    send_critical_notification(alert)
    """
    analyzer = get_dtc_analyzer()
    return analyzer.process_truck_dtc(truck_id, dtc_value, timestamp)


if __name__ == "__main__":
    # Test the DTC analyzer
    logging.basicConfig(level=logging.DEBUG)

    analyzer = DTCAnalyzer()

    # Test cases
    test_cases = [
        ("CO0681", "100.4", "Critical oil pressure"),
        ("CO0681", "100.4,157.3", "Multiple critical codes"),
        ("PC1280", "3246.7", "DPF soot warning"),
        ("OG2033", "411.2", "EGR temperature warning"),
        ("YM6023", "", "No codes"),
        ("DO9356", None, "None value"),
    ]

    now = datetime.now(timezone.utc)

    print("\n" + "=" * 60)
    print("DTC ANALYZER TEST")
    print("=" * 60)

    for truck_id, dtc_string, description in test_cases:
        print(f"\n--- Test: {description} ---")
        print(f"Input: truck={truck_id}, dtc='{dtc_string}'")

        alerts = analyzer.process_truck_dtc(truck_id, dtc_string, now)

        if alerts:
            for alert in alerts:
                print(f"\n{alert.message}")
        else:
            print("No alerts generated")

    print("\n" + "=" * 60)
    print("Fleet Summary:", analyzer.get_fleet_dtc_summary())
    print("=" * 60)
