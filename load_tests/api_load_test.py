"""
Load Testing Script for Async API
==================================

Tests performance under load using Locust.

Install:
    pip install locust

Run:
    locust -f load_tests/api_load_test.py --host=http://localhost:8000

Then visit http://localhost:8089 to configure load parameters.

Author: Fuel Copilot Team
Date: December 27, 2025
"""

from locust import HttpUser, task, between
import random


class FuelCopilotUser(HttpUser):
    """Simulates a user making requests to the API"""

    # Wait 1-3 seconds between requests
    wait_time = between(1, 3)

    # Sample truck IDs
    truck_ids = ["CO0681", "FL0208", "TX1234", "CA5678", "NY9999"]

    def on_start(self):
        """Called when a user starts"""
        print("🚀 Starting load test user...")

    @task(10)
    def get_truck_sensors(self):
        """Most common endpoint - 10x weight"""
        truck_id = random.choice(self.truck_ids)
        self.client.get(
            f"/fuelAnalytics/api/v2/trucks/{truck_id}/sensors",
            name="/trucks/[id]/sensors",
        )

    @task(5)
    def get_fleet_summary(self):
        """Fleet summary - 5x weight"""
        self.client.get("/fuelAnalytics/api/v2/fleet/summary")

    @task(3)
    def get_truck_trips(self):
        """Trip history - 3x weight"""
        truck_id = random.choice(self.truck_ids)
        self.client.get(
            f"/fuelAnalytics/api/v2/trucks/{truck_id}/trips?days=7&limit=10",
            name="/trucks/[id]/trips",
        )

    @task(2)
    def get_speeding_events(self):
        """Speeding events - 2x weight"""
        truck_id = random.choice(self.truck_ids)
        self.client.get(
            f"/fuelAnalytics/api/v2/trucks/{truck_id}/speeding-events?days=7",
            name="/trucks/[id]/speeding-events",
        )

    @task(1)
    def get_driver_behavior(self):
        """Fleet behavior - 1x weight"""
        self.client.get("/fuelAnalytics/api/v2/fleet/driver-behavior?days=7")


class StressTestUser(HttpUser):
    """Heavy load user for stress testing"""

    wait_time = between(0.1, 0.5)  # Very fast requests

    @task
    def rapid_fire_sensors(self):
        """Rapid fire sensor requests"""
        self.client.get("/fuelAnalytics/api/v2/trucks/CO0681/sensors")


# Load test scenarios:
# 1. Normal load:      locust -f load_tests/api_load_test.py --users 50 --spawn-rate 5
# 2. High load:        locust -f load_tests/api_load_test.py --users 200 --spawn-rate 20
# 3. Stress test:      locust -f load_tests/api_load_test.py --users 500 --spawn-rate 50
# 4. Pool exhaustion:  locust -f load_tests/api_load_test.py --users 100 --spawn-rate 100
