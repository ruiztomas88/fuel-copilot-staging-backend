#!/usr/bin/env python3
"""
integration_tests.py - Test Suite Comprehensivo
═══════════════════════════════════════════════════════════════════════════════
Tests de integración para validar todos los fixes y mejoras de la auditoría
"""

import json
import sys
from datetime import datetime, timedelta
from typing import Dict, List

import pymysql
import requests

# Import our security modules
try:
    from algorithm_improvements import (
        AdaptiveMPGEngine,
        EnhancedTheftDetector,
        ExtendedKalmanFuelEstimator,
    )
    from db_config import get_config, get_connection
    from sql_safe import safe_count, validate_truck_id, whitelist_table

    print("✅ Security modules imported")
except ImportError as e:
    print(f"❌ Import failed: {e}")
    sys.exit(1)


class IntegrationTests:
    """Suite de tests de integración"""

    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
        self.tests_passed = 0
        self.tests_failed = 0
        self.results = []

    def test(self, name: str, func):
        """Ejecutar test y registrar resultado"""
        print(f"\n🧪 {name}...")
        try:
            func()
            print(f"   ✅ PASS")
            self.tests_passed += 1
            self.results.append({"test": name, "status": "PASS"})
        except AssertionError as e:
            print(f"   ❌ FAIL: {e}")
            self.tests_failed += 1
            self.results.append({"test": name, "status": "FAIL", "error": str(e)})
        except Exception as e:
            print(f"   ⚠️  ERROR: {e}")
            self.tests_failed += 1
            self.results.append({"test": name, "status": "ERROR", "error": str(e)})

    def run_all(self):
        """Ejecutar todos los tests"""
        print("=" * 80)
        print("🔬 FUEL COPILOT - INTEGRATION TEST SUITE")
        print("=" * 80)

        # Security Tests
        print("\n" + "=" * 80)
        print("1️⃣  SECURITY TESTS")
        print("=" * 80)

        self.test("Database config loads from .env", self._test_db_config)
        self.test("SQL injection protection - whitelist", self._test_sql_whitelist)
        self.test("SQL injection protection - validation", self._test_sql_validation)
        self.test("Database connection successful", self._test_db_connection)

        # API Tests
        print("\n" + "=" * 80)
        print("2️⃣  API ENDPOINT TESTS")
        print("=" * 80)

        self.test("GET /api/fleet", self._test_api_fleet)
        self.test("GET /api/kpis", self._test_api_kpis)
        self.test("GET /api/truck-costs", self._test_api_truck_costs)
        self.test("GET /api/truck-utilization", self._test_api_truck_utilization)

        # Data Quality Tests
        print("\n" + "=" * 80)
        print("3️⃣  DATA QUALITY TESTS")
        print("=" * 80)

        self.test("Real data in Cost Analysis", self._test_real_cost_data)
        self.test("Real data in Utilization", self._test_real_utilization_data)
        self.test("KPIs include hours metrics", self._test_kpis_hours)

        # Algorithm Tests
        print("\n" + "=" * 80)
        print("4️⃣  ALGORITHM IMPROVEMENT TESTS")
        print("=" * 80)

        self.test("Adaptive MPG engine", self._test_adaptive_mpg)
        self.test("Extended Kalman Filter", self._test_ekf)
        self.test("Enhanced Theft Detection", self._test_theft_detector)

        # Integration Tests
        print("\n" + "=" * 80)
        print("5️⃣  FULL INTEGRATION TESTS")
        print("=" * 80)

        self.test("End-to-end fleet data flow", self._test_e2e_fleet)
        self.test("Real database query with protection", self._test_db_query_protected)

        # Summary
        print("\n" + "=" * 80)
        print("📊 TEST SUMMARY")
        print("=" * 80)
        print(f"Tests Passed: {self.tests_passed}")
        print(f"Tests Failed: {self.tests_failed}")
        print(f"Total Tests:  {self.tests_passed + self.tests_failed}")
        print(
            f"Success Rate: {self.tests_passed / (self.tests_passed + self.tests_failed) * 100:.1f}%"
        )

        if self.tests_failed == 0:
            print("\n🎉 ALL TESTS PASSED!")
            return 0
        else:
            print(f"\n⚠️  {self.tests_failed} TESTS FAILED")
            return 1

    # =========================================================================
    # Security Tests
    # =========================================================================

    def _test_db_config(self):
        """Test database config loads from environment"""
        config = get_config()
        assert config.host != "", "Host must be configured"
        assert config.database != "", "Database must be configured"
        assert config.user != "", "User must be configured"

    def _test_sql_whitelist(self):
        """Test SQL injection whitelist"""
        # Valid table
        safe = whitelist_table("trucks")
        assert safe == "trucks"

        # Invalid table should raise
        try:
            whitelist_table("DROP TABLE users")
            assert False, "Should have rejected malicious table name"
        except ValueError:
            pass  # Expected

    def _test_sql_validation(self):
        """Test SQL validation functions"""
        # Valid truck ID
        truck = validate_truck_id("CO0681")
        assert truck == "CO0681"

        # Invalid truck ID
        try:
            validate_truck_id("'; DROP TABLE trucks; --")
            assert False, "Should have rejected SQL injection"
        except ValueError:
            pass  # Expected

    def _test_db_connection(self):
        """Test database connection works"""
        conn = get_connection()
        assert conn is not None
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        result = cursor.fetchone()
        assert result[0] == 1
        cursor.close()
        conn.close()

    # =========================================================================
    # API Tests
    # =========================================================================

    def _test_api_fleet(self):
        """Test fleet endpoint"""
        response = requests.get(f"{self.base_url}/fuelAnalytics/api/fleet")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "total_trucks" in data
        assert "truck_details" in data
        assert len(data["truck_details"]) > 0

    def _test_api_kpis(self):
        """Test KPIs endpoint"""
        response = requests.get(f"{self.base_url}/fuelAnalytics/api/kpis?days=7")
        assert response.status_code == 200
        data = response.json()
        assert "total_fuel_consumed_gal" in data
        assert "fleet_avg_mpg" in data
        assert "total_distance_mi" in data

    def _test_api_truck_costs(self):
        """Test truck costs endpoint"""
        response = requests.get(f"{self.base_url}/fuelAnalytics/api/truck-costs?days=7")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        if len(data) > 0:
            truck = data[0]
            assert "truckId" in truck
            assert "totalMiles" in truck
            assert "fuelCost" in truck
            assert "costPerMile" in truck

    def _test_api_truck_utilization(self):
        """Test truck utilization endpoint"""
        response = requests.get(
            f"{self.base_url}/fuelAnalytics/api/truck-utilization?days=7"
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        if len(data) > 0:
            truck = data[0]
            assert "truckId" in truck
            assert "activeHours" in truck
            assert "idleHours" in truck
            assert "parkedHours" in truck
            assert "utilizationPct" in truck

    # =========================================================================
    # Data Quality Tests
    # =========================================================================

    def _test_real_cost_data(self):
        """Test that cost data is real and varied"""
        response = requests.get(f"{self.base_url}/fuelAnalytics/api/truck-costs?days=7")
        data = response.json()

        if len(data) >= 2:
            # Check that trucks have different costs (not all identical)
            costs = [t["costPerMile"] for t in data[:5]]
            unique_costs = len(set(costs))
            assert (
                unique_costs > 1
            ), "All trucks have identical costs - likely mock data"

    def _test_real_utilization_data(self):
        """Test that utilization data is real and varied"""
        response = requests.get(
            f"{self.base_url}/fuelAnalytics/api/truck-utilization?days=7"
        )
        data = response.json()

        if len(data) >= 2:
            # Check that trucks have different utilization (not all identical)
            utils = [t["utilizationPct"] for t in data[:5]]
            unique_utils = len(set(utils))
            assert (
                unique_utils > 1
            ), "All trucks have identical utilization - likely mock data"

    def _test_kpis_hours(self):
        """Test that KPIs include new hours metrics"""
        response = requests.get(f"{self.base_url}/fuelAnalytics/api/kpis?days=7")
        data = response.json()

        assert "total_moving_hours" in data, "Missing total_moving_hours"
        assert "total_idle_hours" in data, "Missing total_idle_hours"
        assert "total_active_hours" in data, "Missing total_active_hours"

        # Values should be reasonable
        assert data["total_moving_hours"] >= 0
        assert data["total_idle_hours"] >= 0

    # =========================================================================
    # Algorithm Tests
    # =========================================================================

    def _test_adaptive_mpg(self):
        """Test adaptive MPG engine"""
        engine = AdaptiveMPGEngine()

        # Simulate highway driving
        for i in range(15):
            mpg = engine.process(
                distance_delta_mi=1.0, fuel_delta_gal=0.15, speed_mph=65
            )

        # Should have MPG in reasonable range
        assert mpg is not None, "MPG should be calculated"
        assert 3.5 <= mpg <= 12.0, f"MPG {mpg} out of valid range"

    def _test_ekf(self):
        """Test Extended Kalman Filter"""
        ekf = ExtendedKalmanFuelEstimator(capacity_liters=500)
        state = ekf.initialize(initial_fuel=400)

        # Simulate consumption
        for i in range(10):
            state = ekf.predict(state, dt_hours=0.1, speed_mph=60)
            state = ekf.update(
                state, measurement_pct=state.fuel_liters / 5, is_moving=True
            )

        # Fuel should have decreased
        assert state.fuel_liters < 400, "Fuel should decrease with consumption"
        assert state.fuel_liters > 0, "Fuel should not be negative"

        # Uncertainty should be reasonable
        uncertainty = ekf.get_uncertainty(state)
        assert uncertainty < 50, f"Uncertainty too high: {uncertainty}"

    def _test_theft_detector(self):
        """Test enhanced theft detection"""
        detector = EnhancedTheftDetector()

        # Simulate normal consumption
        normal_readings = [
            {"timestamp": datetime.now(), "fuel_pct": 80, "speed": 50, "distance": 100},
            {"timestamp": datetime.now(), "fuel_pct": 79, "speed": 50, "distance": 101},
        ]

        event = detector.analyze("TEST001", normal_readings)
        # Normal consumption should not trigger alert
        assert event is None or event.classification == "CONSUMPTION_NORMAL"

        # Simulate suspicious drop
        theft_readings = [
            {
                "timestamp": datetime.now(),
                "fuel_pct": 80,
                "speed": 0,
                "distance": 100,
                "tank_capacity_gal": 200,
            },
            {
                "timestamp": datetime.now(),
                "fuel_pct": 60,
                "speed": 0,
                "distance": 100,
                "tank_capacity_gal": 200,
            },
        ]

        event = detector.analyze("TEST001", theft_readings)
        assert event is not None, "Should detect suspicious drop"
        assert event.classification in ["THEFT_CONFIRMED", "THEFT_SUSPECTED"]

    # =========================================================================
    # Integration Tests
    # =========================================================================

    def _test_e2e_fleet(self):
        """Test end-to-end fleet data flow"""
        # Get fleet from API
        response = requests.get(f"{self.base_url}/fuelAnalytics/api/fleet")
        fleet_data = response.json()

        # Get KPIs
        response = requests.get(f"{self.base_url}/fuelAnalytics/api/kpis?days=7")
        kpi_data = response.json()

        # Get costs
        response = requests.get(f"{self.base_url}/fuelAnalytics/api/truck-costs?days=7")
        cost_data = response.json()

        # Verify data consistency
        assert fleet_data["total_trucks"] > 0
        assert kpi_data["truck_count"] > 0
        assert len(cost_data) > 0

    def _test_db_query_protected(self):
        """Test database query with SQL injection protection"""
        from database_mysql import get_sqlalchemy_engine

        engine = get_sqlalchemy_engine()

        # Use safe_count with SQLAlchemy connection
        with engine.connect() as conn:
            # Test valid table
            try:
                count = safe_count(conn, "fuel_metrics")
                assert count > 0, "Should have fuel_metrics data"
            except Exception as e:
                raise e

            # Try malicious table name
            try:
                count = safe_count(conn, "DROP TABLE users")
                assert False, "Should have prevented SQL injection"
            except ValueError:
                pass  # Expected


if __name__ == "__main__":
    tests = IntegrationTests()
    exit_code = tests.run_all()
    sys.exit(exit_code)
