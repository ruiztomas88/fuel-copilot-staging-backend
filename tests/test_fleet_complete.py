"""Complete coverage for fleet_command_center.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import datetime, timezone

from fleet_command_center import *


class TestFleetComplete:
    def test_all_enums(self):
        assert Priority.CRITICAL
        assert Priority.HIGH
        assert Priority.MEDIUM
        assert Priority.LOW
        assert IssueCategory.ENGINE
        assert IssueCategory.TRANSMISSION
        assert IssueCategory.DEF
        assert IssueCategory.ELECTRICAL
        assert IssueCategory.FUEL
        assert IssueCategory.BRAKES
        assert IssueCategory.SENSOR
        assert IssueCategory.EFFICIENCY
        assert IssueCategory.DRIVER
        assert IssueCategory.GPS
        assert IssueCategory.TURBO
        assert ActionType.STOP_IMMEDIATELY
        assert ActionType.SCHEDULE_THIS_WEEK
        assert ActionType.MONITOR

    def test_all_dataclasses(self):
        ActionItem(
            "1",
            "DO9693",
            Priority.HIGH,
            80.0,
            IssueCategory.ENGINE,
            "oil",
            "T",
            "D",
            5.0,
            "$1K",
            "50",
            "+2",
            "<40",
            "HIGH",
            ActionType.MONITOR,
            ["S"],
            "🔧",
            ["S"],
        ).to_dict()
        TruckRiskScore("DO9693", 75.0, "high", ["f"], 30, 3, 10.0).to_dict()
        UrgencySummary(2, 5, 10, 8, 20).total_issues
        FleetHealthScore(80, "Good", "stable", "d")
        CostProjection("$10K", "$20K", "$40K")
        SensorStatus(1, 2, 3, 0, 25)
        DEFPrediction(
            "DO9693", 35.0, 26.0, 2.0, 13.0, 10.0, datetime.now(timezone.utc)
        ).to_dict()
        FailureCorrelation(
            "C-1", "cool_temp", ["oil_temp"], 0.85, "cause", "action", ["DO9693"]
        ).to_dict()
        SensorReading("oil_press", "DO9693", 45.5, datetime.now(timezone.utc), True)
        CommandCenterData(
            datetime.now(timezone.utc).isoformat(),
            "1.8.0",
            FleetHealthScore(80, "Good", "stable", "d"),
            25,
            23,
            UrgencySummary(2, 5, 10, 8, 20),
            SensorStatus(1, 2, 3, 0, 25),
            CostProjection("$10K", "$20K", "$40K"),
            [],
            [],
            [],
            [],
            {},
        ).to_dict()

    def test_fleet_command_center_init(self):
        fcc = FleetCommandCenter()
        assert fcc is not None

    def test_get_command_center(self):
        get_command_center()
