"""
Truck Specs Engine - Uses VIN-decoded specs for MPG validation
═══════════════════════════════════════════════════════════════════════════════

This module integrates truck_specs data (year, make, model, baseline MPG) into
the fuel analytics system for:
1. Better MPG validation (compare vs truck's real baseline)
2. Anomaly detection (flag when MPG deviates from truck-specific baseline)
3. Fleet insights (compare by make/model/year)
4. Alerts (warn when below expected MPG for truck type)

Author: Fuel Copilot Team
Date: December 24, 2025
"""

import logging
import os
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import pymysql
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

DB_CONFIG = {
    "host": os.getenv("MYSQL_HOST", "localhost"),
    "user": os.getenv("MYSQL_USER", "root"),
    "password": os.getenv("MYSQL_PASSWORD"),
    "database": os.getenv("MYSQL_DATABASE", "fuel_copilot_local"),
    "port": int(os.getenv("MYSQL_PORT", 3306)),
}


@dataclass
class TruckSpecs:
    """Truck specifications from VIN decode"""

    truck_id: str
    vin: str
    year: int
    make: str
    model: str
    baseline_mpg_loaded: float
    baseline_mpg_empty: float
    notes: str

    @property
    def expected_mpg_range(self) -> Tuple[float, float]:
        """Expected MPG range (min loaded, max empty)"""
        return (self.baseline_mpg_loaded, self.baseline_mpg_empty)

    @property
    def age_years(self) -> int:
        """Truck age in years"""
        from datetime import datetime

        return datetime.now().year - self.year


class TruckSpecsEngine:
    """
    Manages truck specifications and provides MPG validation
    """

    def __init__(self):
        self._specs_cache: Dict[str, TruckSpecs] = {}
        self._load_specs()

    def _load_specs(self):
        """Load all truck specs from database into cache"""
        try:
            conn = pymysql.connect(**DB_CONFIG)
            cursor = conn.cursor(pymysql.cursors.DictCursor)

            cursor.execute(
                """
                SELECT truck_id, vin, year, make, model, 
                       baseline_mpg_loaded, baseline_mpg_empty, notes
                FROM truck_specs
            """
            )

            rows = cursor.fetchall()
            for row in rows:
                specs = TruckSpecs(
                    truck_id=row["truck_id"],
                    vin=row["vin"],
                    year=row["year"],
                    make=row["make"],
                    model=row["model"],
                    baseline_mpg_loaded=float(row["baseline_mpg_loaded"]),
                    baseline_mpg_empty=float(row["baseline_mpg_empty"]),
                    notes=row["notes"] or "",
                )
                self._specs_cache[row["truck_id"]] = specs

            logger.info(f"✅ Loaded specs for {len(self._specs_cache)} trucks")
            cursor.close()
            conn.close()

        except Exception as e:
            logger.error(f"❌ Failed to load truck specs: {e}")

    def get_specs(self, truck_id: str) -> Optional[TruckSpecs]:
        """Get specs for a truck"""
        return self._specs_cache.get(truck_id)

    def get_expected_mpg(
        self, truck_id: str, is_loaded: bool = True
    ) -> Optional[float]:
        """
        Get expected MPG for truck based on load status

        Args:
            truck_id: Truck ID
            is_loaded: True if truck is loaded, False if empty

        Returns:
            Expected MPG or None if truck not found
        """
        specs = self.get_specs(truck_id)
        if not specs:
            return None

        return specs.baseline_mpg_loaded if is_loaded else specs.baseline_mpg_empty

    def validate_mpg(
        self,
        truck_id: str,
        current_mpg: float,
        is_loaded: bool = True,
        tolerance_pct: float = 25.0,
    ) -> Dict:
        """
        Validate current MPG against truck-specific baseline

        Args:
            truck_id: Truck ID
            current_mpg: Current MPG reading
            is_loaded: True if truck is loaded
            tolerance_pct: Tolerance percentage below baseline (default 25%)

        Returns:
            Dictionary with validation results:
            {
                'valid': bool,
                'expected_mpg': float,
                'current_mpg': float,
                'deviation_pct': float,
                'status': 'GOOD' | 'WARNING' | 'CRITICAL',
                'message': str
            }
        """
        specs = self.get_specs(truck_id)
        if not specs:
            return {
                "valid": True,  # Don't fail if specs not found
                "expected_mpg": None,
                "current_mpg": current_mpg,
                "deviation_pct": 0.0,
                "status": "UNKNOWN",
                "message": f"No specs found for {truck_id}",
            }

        expected_mpg = (
            specs.baseline_mpg_loaded if is_loaded else specs.baseline_mpg_empty
        )
        deviation_pct = ((current_mpg - expected_mpg) / expected_mpg) * 100

        # Determine status
        if deviation_pct >= 0:
            status = "GOOD"  # Better than expected
        elif deviation_pct >= -tolerance_pct * 0.5:  # Within half tolerance
            status = "NORMAL"
        elif deviation_pct >= -tolerance_pct:  # Within tolerance
            status = "WARNING"
        else:
            status = "CRITICAL"  # Below tolerance

        # Generate message
        if status == "GOOD":
            message = f"MPG {current_mpg:.1f} exceeds baseline {expected_mpg:.1f} (+{abs(deviation_pct):.1f}%)"
        elif status == "NORMAL":
            message = f"MPG {current_mpg:.1f} near baseline {expected_mpg:.1f} ({deviation_pct:.1f}%)"
        elif status == "WARNING":
            message = f"MPG {current_mpg:.1f} below baseline {expected_mpg:.1f} ({deviation_pct:.1f}%)"
        else:
            message = f"⚠️ MPG {current_mpg:.1f} significantly below baseline {expected_mpg:.1f} ({deviation_pct:.1f}%)"

        return {
            "valid": status != "CRITICAL",
            "expected_mpg": expected_mpg,
            "current_mpg": current_mpg,
            "deviation_pct": deviation_pct,
            "status": status,
            "message": message,
            "truck_info": f"{specs.year} {specs.make} {specs.model}",
        }

    def get_fleet_stats(self) -> Dict:
        """Get fleet-wide statistics"""
        if not self._specs_cache:
            return {}

        makes = {}
        total_loaded_mpg = 0.0
        total_empty_mpg = 0.0
        total_age = 0

        for specs in self._specs_cache.values():
            # By make
            if specs.make not in makes:
                makes[specs.make] = {
                    "count": 0,
                    "avg_mpg_loaded": 0.0,
                    "avg_mpg_empty": 0.0,
                    "avg_age": 0,
                }
            makes[specs.make]["count"] += 1
            makes[specs.make]["avg_mpg_loaded"] += specs.baseline_mpg_loaded
            makes[specs.make]["avg_mpg_empty"] += specs.baseline_mpg_empty
            makes[specs.make]["avg_age"] += specs.age_years

            # Fleet totals
            total_loaded_mpg += specs.baseline_mpg_loaded
            total_empty_mpg += specs.baseline_mpg_empty
            total_age += specs.age_years

        # Calculate averages
        count = len(self._specs_cache)
        for make_stats in makes.values():
            make_count = make_stats["count"]
            make_stats["avg_mpg_loaded"] = round(
                make_stats["avg_mpg_loaded"] / make_count, 2
            )
            make_stats["avg_mpg_empty"] = round(
                make_stats["avg_mpg_empty"] / make_count, 2
            )
            make_stats["avg_age"] = round(make_stats["avg_age"] / make_count, 1)

        return {
            "total_trucks": count,
            "fleet_avg_mpg_loaded": round(total_loaded_mpg / count, 2),
            "fleet_avg_mpg_empty": round(total_empty_mpg / count, 2),
            "fleet_avg_age": round(total_age / count, 1),
            "by_make": makes,
        }

    def get_similar_trucks(self, truck_id: str) -> list[TruckSpecs]:
        """Get trucks with similar specs (same make/model)"""
        specs = self.get_specs(truck_id)
        if not specs:
            return []

        similar = []
        for other_specs in self._specs_cache.values():
            if (
                other_specs.truck_id != truck_id
                and other_specs.make == specs.make
                and other_specs.model == specs.model
            ):
                similar.append(other_specs)

        return similar


# Global instance
_truck_specs_engine: Optional[TruckSpecsEngine] = None


def get_truck_specs_engine() -> TruckSpecsEngine:
    """Get or create the global TruckSpecsEngine instance"""
    global _truck_specs_engine
    if _truck_specs_engine is None:
        _truck_specs_engine = TruckSpecsEngine()
    return _truck_specs_engine


# Convenience functions
def get_expected_mpg(truck_id: str, is_loaded: bool = True) -> Optional[float]:
    """Get expected MPG for truck"""
    engine = get_truck_specs_engine()
    return engine.get_expected_mpg(truck_id, is_loaded)


def validate_truck_mpg(
    truck_id: str, current_mpg: float, is_loaded: bool = True
) -> Dict:
    """Validate MPG against truck baseline"""
    engine = get_truck_specs_engine()
    return engine.validate_mpg(truck_id, current_mpg, is_loaded)


if __name__ == "__main__":
    # Test the engine
    logging.basicConfig(level=logging.INFO)

    engine = TruckSpecsEngine()

    print("\n📊 Fleet Stats:")
    stats = engine.get_fleet_stats()
    print(f"Total trucks: {stats['total_trucks']}")
    print(f"Fleet avg MPG loaded: {stats['fleet_avg_mpg_loaded']}")
    print(f"Fleet avg MPG empty: {stats['fleet_avg_mpg_empty']}")
    print(f"Fleet avg age: {stats['fleet_avg_age']} years")

    print("\n📋 By Make:")
    for make, make_stats in stats["by_make"].items():
        print(
            f"  {make}: {make_stats['count']} trucks, {make_stats['avg_mpg_loaded']} MPG loaded, {make_stats['avg_age']} years old"
        )

    print("\n🧪 Test validation:")
    # Test MR7679 (2017 Freightliner Cascadia, baseline 6.8 loaded)
    result = engine.validate_mpg("MR7679", 5.5, is_loaded=True)
    print(f"\nMR7679 @ 5.5 MPG: {result['status']}")
    print(f"  {result['message']}")

    result = engine.validate_mpg("MR7679", 6.8, is_loaded=True)
    print(f"\nMR7679 @ 6.8 MPG: {result['status']}")
    print(f"  {result['message']}")

    result = engine.validate_mpg("MR7679", 4.0, is_loaded=True)
    print(f"\nMR7679 @ 4.0 MPG: {result['status']}")
    print(f"  {result['message']}")
