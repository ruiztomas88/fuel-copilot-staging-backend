"""
J1939 SPN Decoder - Fuel Copilot Edition
=========================================
Decodes J1939 Suspect Parameter Numbers (SPNs) with DETAILED explanations
for Class 8 trucks.

Features:
- ~111 SPNs with REAL detailed information
- Intelligent UNKNOWN handling for unrecognized codes
- OEM-specific code detection (Freightliner, Detroit, Volvo, etc.)
- Data validation and value checking
- Performance optimized with LRU caching

Author: Tomas - Fleet Booster Fuel Copilot
Version: 2.0.0 DETAILED
Date: December 26, 2025
"""

import csv
import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Dict, Optional


@dataclass
class SPNInfo:
    """
    Complete information about a J1939 SPN code

    Attributes:
        spn: SPN number
        description: Short description
        category: Category (Engine, Fuel, Emissions, etc.)
        unit: Measurement unit
        min_value: Minimum valid value
        max_value: Maximum valid value
        priority: 1=Critical, 2=High, 3=Low
        oem: OEM manufacturer
        detailed_explanation: DETAILED explanation of what it means and what to do
    """

    spn: int
    description: str
    category: str
    unit: str
    min_value: Optional[float]
    max_value: Optional[float]
    priority: int
    oem: str
    detailed_explanation: str = ""

    def is_critical(self) -> bool:
        """Check if this SPN is critical (priority 1)"""
        return self.priority == 1

    def is_proprietary(self) -> bool:
        """Check if this is a proprietary (non-standard) SPN"""
        return self.oem != "Standard"

    def __str__(self):
        return f"SPN {self.spn}: {self.description} ({self.category}, Priority {self.priority})"


class SPNDecoder:
    """
    Intelligent J1939 SPN Decoder with fallback for unknown codes

    Usage:
        decoder = SPNDecoder()
        info = decoder.decode(523002)  # Your ICU EEPROM code
        print(info.detailed_explanation)
    """

    def __init__(self, csv_path: Optional[str] = None):
        """
        Initialize decoder with SPN database

        Args:
            csv_path: Path to CSV database. If None, uses default location
        """
        if csv_path is None:
            # Default path relative to this file
            base_dir = os.path.dirname(os.path.abspath(__file__))
            csv_path = os.path.join(
                base_dir, "data", "spn", "j1939_spn_database_detailed.csv"
            )

        self.csv_path = csv_path
        self.spn_database: Dict[int, SPNInfo] = {}
        self._load_database()

        print(f"✅ SPN Decoder initialized with {len(self.spn_database):,} SPNs")

    def _load_database(self):
        """Load SPN database from CSV file"""
        if not os.path.exists(self.csv_path):
            print(f"⚠️ WARNING: SPN database not found at {self.csv_path}")
            print(f"   Creating empty database. Only UNKNOWN SPNs will be returned.")
            return

        try:
            with open(self.csv_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        spn = int(row["SPN"])

                        # Parse min/max values (can be empty)
                        min_val = None
                        max_val = None
                        if row.get("Min"):
                            try:
                                min_val = float(row["Min"])
                            except ValueError:
                                pass
                        if row.get("Max"):
                            try:
                                max_val = float(row["Max"])
                            except ValueError:
                                pass

                        info = SPNInfo(
                            spn=spn,
                            description=row.get("Description", f"Parameter {spn}"),
                            category=row.get("Category", "Unknown"),
                            unit=row.get("Unit", ""),
                            min_value=min_val,
                            max_value=max_val,
                            priority=int(row.get("Priority", 3)),
                            oem=row.get("OEM", "Unknown"),
                            detailed_explanation=row.get("Detailed_Explanation", ""),
                        )

                        self.spn_database[spn] = info

                    except (ValueError, KeyError) as e:
                        print(f"   ⚠️ Skipping invalid row: {e}")
                        continue

        except Exception as e:
            print(f"❌ ERROR loading SPN database: {e}")
            print(f"   Database will be empty.")

    @lru_cache(maxsize=1000)
    def decode(self, spn: int) -> SPNInfo:
        """
        Decode an SPN code with intelligent fallback

        Args:
            spn: SPN number to decode

        Returns:
            SPNInfo with complete information
        """
        # Check if we have this SPN in database
        if spn in self.spn_database:
            return self.spn_database[spn]

        # Not found - create intelligent UNKNOWN entry
        return self._create_unknown_spn(spn)

    def _create_unknown_spn(self, spn: int) -> SPNInfo:
        """
        Create intelligent UNKNOWN SPN entry with OEM detection

        Detects OEM based on SPN range:
        - 0-7500: Standard J1939
        - 520000-523999: Freightliner
        - 521000-521999: Detroit Diesel
        - 80000-84999, 600000-600999: Volvo
        - 85000-89999: Paccar (Kenworth/Peterbilt)
        - 90000-94999: Mack
        - 100000-104999: International/Navistar
        """
        oem = "Unknown"
        category = "Unknown"

        # OEM range detection
        if 0 <= spn <= 7500:
            oem = "Standard"
            category = "Standard J1939"
        elif 520000 <= spn <= 523999:
            oem = "Freightliner"
            category = "Proprietary"
        elif 521000 <= spn <= 521999:
            oem = "Detroit"
            category = "Proprietary"
        elif (80000 <= spn <= 84999) or (600000 <= spn <= 600999):
            oem = "Volvo"
            category = "Proprietary"
        elif 85000 <= spn <= 89999:
            oem = "Paccar"
            category = "Proprietary"
        elif 90000 <= spn <= 94999:
            oem = "Mack"
            category = "Proprietary"
        elif 100000 <= spn <= 104999:
            oem = "International"
            category = "Proprietary"

        return SPNInfo(
            spn=spn,
            description=f"Unknown Parameter {spn}",
            category=category,
            unit="",
            min_value=None,
            max_value=None,
            priority=3,  # Low priority for unknown
            oem=oem,
            detailed_explanation=f"SPN {spn} no está en la base de datos detallada. OEM detectado: {oem}. Consultar manual del fabricante para más información.",
        )

    def decode_multiple(self, spn_list: list) -> Dict[int, SPNInfo]:
        """
        Decode multiple SPNs at once

        Args:
            spn_list: List of SPN numbers

        Returns:
            Dictionary mapping SPN -> SPNInfo
        """
        return {spn: self.decode(spn) for spn in spn_list}

    def get_critical_spns(self) -> Dict[int, SPNInfo]:
        """
        Get all critical SPNs (priority 1) from database

        Returns:
            Dictionary of critical SPNs
        """
        return {
            spn: info for spn, info in self.spn_database.items() if info.is_critical()
        }

    def get_oem_spns(self, oem: str) -> Dict[int, SPNInfo]:
        """
        Get all SPNs for a specific OEM

        Args:
            oem: OEM name (e.g., "Freightliner", "Detroit", "Standard")

        Returns:
            Dictionary of SPNs for that OEM
        """
        return {
            spn: info
            for spn, info in self.spn_database.items()
            if info.oem.lower() == oem.lower()
        }

    def search_by_description(self, search_term: str) -> Dict[int, SPNInfo]:
        """
        Search SPNs by description text

        Args:
            search_term: Text to search for

        Returns:
            Dictionary of matching SPNs
        """
        search_lower = search_term.lower()
        return {
            spn: info
            for spn, info in self.spn_database.items()
            if search_lower in info.description.lower()
            or search_lower in info.detailed_explanation.lower()
        }

    def validate_value(self, spn: int, value: float) -> bool:
        """
        Validate that a value is within acceptable range for an SPN

        Args:
            spn: SPN number
            value: Value to validate

        Returns:
            True if valid, False otherwise
        """
        info = self.decode(spn)

        if info.min_value is None or info.max_value is None:
            return True  # No range defined, assume valid

        return info.min_value <= value <= info.max_value

    def format_value(self, spn: int, value: float) -> str:
        """
        Format a value with its unit

        Args:
            spn: SPN number
            value: Value to format

        Returns:
            Formatted string like "1800 RPM"
        """
        info = self.decode(spn)
        if info.unit:
            return f"{value} {info.unit}"
        return str(value)

    def get_statistics(self) -> Dict[str, int]:
        """Get statistics about the loaded database"""
        stats = {
            "total_spns": len(self.spn_database),
            "critical_spns": len(self.get_critical_spns()),
        }

        # Count by OEM
        oems = {}
        for info in self.spn_database.values():
            oems[info.oem] = oems.get(info.oem, 0) + 1
        stats["by_oem"] = oems

        # Count by category
        categories = {}
        for info in self.spn_database.values():
            categories[info.category] = categories.get(info.category, 0) + 1
        stats["by_category"] = categories

        return stats


# ============================================================================
# INTEGRATION WITH FUEL COPILOT
# ============================================================================


class FuelCopilotSPNHandler:
    """
    High-level handler for SPN processing in Fuel Copilot

    Usage:
        handler = FuelCopilotSPNHandler()
        result = handler.process_spn_from_wialon(523002)

        if handler.should_alert_driver(523002):
            send_alert(result['description'])
    """

    def __init__(self):
        self.decoder = SPNDecoder()

    def process_spn_from_wialon(self, spn: int, value: Optional[float] = None) -> dict:
        """
        Process an SPN code received from Wialon

        Args:
            spn: SPN number
            value: Optional sensor value

        Returns:
            Dictionary with complete SPN information
        """
        info = self.decoder.decode(spn)

        result = {
            "spn": info.spn,
            "description": info.description,
            "detailed_explanation": info.detailed_explanation,
            "category": info.category,
            "priority": info.priority,
            "oem": info.oem,
            "is_critical": info.is_critical(),
            "is_proprietary": info.is_proprietary(),
        }

        # Add value info if provided
        if value is not None:
            result["value"] = value
            result["formatted_value"] = self.decoder.format_value(spn, value)
            result["is_valid"] = self.decoder.validate_value(spn, value)

        # Add alert level
        if info.is_critical():
            result["alert_level"] = "CRITICAL"
            result["action_required"] = "IMMEDIATE"
        elif info.priority == 2:
            result["alert_level"] = "HIGH"
            result["action_required"] = "SOON"
        else:
            result["alert_level"] = "LOW"
            result["action_required"] = "MONITOR"

        return result

    def should_alert_driver(self, spn: int) -> bool:
        """
        Determine if driver should be alerted for this SPN

        Args:
            spn: SPN number

        Returns:
            True if alert should be sent
        """
        info = self.decoder.decode(spn)
        return info.is_critical()

    def get_dashboard_summary(self, spn_list: list) -> dict:
        """
        Get summary for dashboard display

        Args:
            spn_list: List of active SPN codes

        Returns:
            Summary with counts and critical alerts
        """
        critical = []
        high = []
        low = []

        for spn in spn_list:
            info = self.decoder.decode(spn)
            if info.priority == 1:
                critical.append(info)
            elif info.priority == 2:
                high.append(info)
            else:
                low.append(info)

        return {
            "total_codes": len(spn_list),
            "critical_count": len(critical),
            "high_count": len(high),
            "low_count": len(low),
            "critical_codes": [
                {
                    "spn": info.spn,
                    "description": info.description,
                    "explanation": info.detailed_explanation,
                }
                for info in critical
            ],
        }


# ============================================================================
# MAIN - Run demo if executed directly
# ============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("J1939 SPN DECODER - FUEL COPILOT EDITION")
    print("=" * 70)
    print()

    # Initialize
    decoder = SPNDecoder()
    print()

    # Example: Decode your ICU code
    print("🔍 DECODING SPN 523002 (ICU EEPROM):")
    print("-" * 70)
    info = decoder.decode(523002)
    print(f"   {info}")
    print(f"   OEM: {info.oem}")
    print(f"   Critical: {info.is_critical()}")
    print(f"\n   📝 DETAILED EXPLANATION:")
    print(f"   {info.detailed_explanation}")
    print()

    # Stats
    stats = decoder.get_statistics()
    print("📊 DATABASE STATISTICS:")
    print("-" * 70)
    print(f"   Total SPNs: {stats['total_spns']}")
    print(f"   Critical: {stats['critical_spns']}")
    print()

    # Integration example
    print("🚀 FUEL COPILOT INTEGRATION EXAMPLE:")
    print("-" * 70)
    handler = FuelCopilotSPNHandler()
    result = handler.process_spn_from_wialon(523002)
    print(f"   Alert Level: {result['alert_level']}")
    print(f"   Action Required: {result['action_required']}")
    print(f"   Should Alert Driver: {handler.should_alert_driver(523002)}")
    print()
