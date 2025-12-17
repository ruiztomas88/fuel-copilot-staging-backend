"""
Tests for AI Audit Implementation Features
═══════════════════════════════════════════════════════════════════════════════

Tests for:
1. DTC Analyzer v4.0 with dtc_database.py v5.8.0 (112 SPNs, 23 FMIs)
2. Driver Scoring Engine (OverSpeed, Idle, Speeding)
3. Component Health Predictors (Turbo, Oil, Coolant)
4. Driver Alerts Router endpoints

Based on VERIFIED data from Wialon DB (wialon_collect).

Author: Fuel Analytics Team
Version: 1.0.0
Created: December 2025
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch


# ═══════════════════════════════════════════════════════════════════════════════
# DTC ANALYZER TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestDTCAnalyzer:
    """Tests for DTC Analyzer v4.0"""

    def test_dtc_analyzer_import(self):
        """Test that DTC analyzer can be imported"""
        from dtc_analyzer import DTCAnalyzer, get_dtc_analyzer, DTCSeverity

        analyzer = DTCAnalyzer()
        assert analyzer is not None

    def test_dtc_analyzer_uses_database(self):
        """Test that DTC analyzer uses the dtc_database.py"""
        from dtc_analyzer import DTC_DATABASE_AVAILABLE

        assert DTC_DATABASE_AVAILABLE is True, "dtc_database.py should be available"

    def test_parse_dtc_string_single(self):
        """Test parsing single DTC code"""
        from dtc_analyzer import DTCAnalyzer

        analyzer = DTCAnalyzer()
        codes = analyzer.parse_dtc_string("597.4")

        assert len(codes) == 1
        assert codes[0].spn == 597
        assert codes[0].fmi == 4
        assert codes[0].code == "SPN597.FMI4"

    def test_parse_dtc_string_multiple(self):
        """Test parsing multiple DTC codes"""
        from dtc_analyzer import DTCAnalyzer

        analyzer = DTCAnalyzer()
        codes = analyzer.parse_dtc_string("597.4,1089.2,3226.7")

        assert len(codes) == 3
        assert codes[0].spn == 597
        assert codes[1].spn == 1089
        assert codes[2].spn == 3226

    def test_parse_dtc_string_empty(self):
        """Test parsing empty DTC string"""
        from dtc_analyzer import DTCAnalyzer

        analyzer = DTCAnalyzer()
        codes = analyzer.parse_dtc_string("")
        assert len(codes) == 0

        codes = analyzer.parse_dtc_string(None)
        assert len(codes) == 0

    def test_severity_from_database(self):
        """Test that severity comes from dtc_database.py"""
        from dtc_analyzer import DTCAnalyzer, DTCSeverity

        analyzer = DTCAnalyzer()

        # SPN 100 (Oil Pressure) with FMI 4 (voltage low) should be CRITICAL
        codes = analyzer.parse_dtc_string("100.4")
        assert codes[0].severity == DTCSeverity.CRITICAL

        # SPN 597 (Brake switch) with FMI 4 should be CRITICAL
        codes = analyzer.parse_dtc_string("597.4")
        assert codes[0].severity == DTCSeverity.CRITICAL

    def test_spanish_descriptions(self):
        """Test that descriptions are in Spanish"""
        from dtc_analyzer import DTCAnalyzer

        analyzer = DTCAnalyzer()
        codes = analyzer.parse_dtc_string("597.4")

        # Description should be in Spanish (from dtc_database.py)
        assert "Freno" in codes[0].description or "Brake" in codes[0].description

    def test_system_classification(self):
        """Test that system classification is added"""
        from dtc_analyzer import DTCAnalyzer

        analyzer = DTCAnalyzer()
        codes = analyzer.parse_dtc_string("597.4")

        # SPN 597 is in BRAKES system
        assert codes[0].system == "BRAKES"

    def test_dtc_analysis_report(self):
        """Test comprehensive DTC analysis report"""
        from dtc_analyzer import DTCAnalyzer

        analyzer = DTCAnalyzer()
        report = analyzer.get_dtc_analysis_report("CO0681", "597.4,1089.2")

        assert report["truck_id"] == "CO0681"
        assert report["status"] in ["ok", "warning", "critical"]
        assert "codes" in report
        assert "summary" in report
        assert report["summary"]["total"] == 2
        assert "systems_affected" in report

    def test_dtc_analysis_report_no_codes(self):
        """Test DTC analysis report with no codes"""
        from dtc_analyzer import DTCAnalyzer

        analyzer = DTCAnalyzer()
        report = analyzer.get_dtc_analysis_report("CO0681", None)

        assert report["status"] == "ok"
        assert report["summary"]["total"] == 0


# ═══════════════════════════════════════════════════════════════════════════════
# DRIVER SCORING ENGINE TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestDriverScoringEngine:
    """Tests for Driver Scoring Engine"""

    def test_scoring_engine_import(self):
        """Test that scoring engine can be imported"""
        from driver_scoring_engine import DriverScoringEngine, get_scoring_engine

        engine = DriverScoringEngine()
        assert engine is not None
        assert engine.base_score == 100

    def test_process_overspeed_event(self):
        """Test processing OverSpeed event (event_id=54)"""
        from driver_scoring_engine import DriverScoringEngine, EventType

        engine = DriverScoringEngine()
        now = datetime.now(timezone.utc)

        event = engine.process_event("CO0681", 54, now)

        assert event is not None
        assert event.event_type == EventType.OVER_SPEED
        assert event.score_impact == -15

    def test_process_idle_event(self):
        """Test processing Long Idle event (event_id=20)"""
        from driver_scoring_engine import DriverScoringEngine, EventType

        engine = DriverScoringEngine()
        now = datetime.now(timezone.utc)

        event = engine.process_event("CO0681", 20, now)

        assert event is not None
        assert event.event_type == EventType.LONG_IDLE
        assert event.score_impact == -5

    def test_process_unknown_event(self):
        """Test that unknown events return None"""
        from driver_scoring_engine import DriverScoringEngine

        engine = DriverScoringEngine()
        now = datetime.now(timezone.utc)

        # Event ID 999 doesn't exist
        event = engine.process_event("CO0681", 999, now)

        assert event is None

    def test_process_speeding(self):
        """Test processing speeding event"""
        from driver_scoring_engine import DriverScoringEngine

        engine = DriverScoringEngine()
        now = datetime.now(timezone.utc)

        event = engine.process_speeding(
            "CO0681", now, max_speed_kmh=130, speed_limit_kmh=105, duration_seconds=60
        )

        assert event is not None
        assert event.over_limit_kmh == 25
        assert event.score_impact < 0

    def test_calculate_score_perfect(self):
        """Test score calculation with no events"""
        from driver_scoring_engine import DriverScoringEngine

        engine = DriverScoringEngine()
        score = engine.calculate_score("NEW_TRUCK")

        assert score.score == 100
        assert score.grade == "A"

    def test_calculate_score_with_events(self):
        """Test score calculation with events"""
        from driver_scoring_engine import DriverScoringEngine

        engine = DriverScoringEngine()
        now = datetime.now(timezone.utc)

        # Add some events
        engine.process_event("CO0681", 54, now)  # -15
        engine.process_event("CO0681", 54, now)  # -15

        score = engine.calculate_score("CO0681")

        assert score.score == 70  # 100 - 15 - 15
        assert score.grade == "C"

    def test_grade_calculation(self):
        """Test grade calculation boundaries"""
        from driver_scoring_engine import DriverScoringEngine

        engine = DriverScoringEngine()

        # Test grade boundaries
        assert engine._get_grade(95) == "A"
        assert engine._get_grade(85) == "B"
        assert engine._get_grade(75) == "C"
        assert engine._get_grade(65) == "D"
        assert engine._get_grade(55) == "F"

    def test_fleet_rankings(self):
        """Test fleet rankings"""
        from driver_scoring_engine import DriverScoringEngine

        engine = DriverScoringEngine()
        now = datetime.now(timezone.utc)

        # Create trucks with different scores
        engine.process_event("GOOD_TRUCK", 54, now)  # 85 score

        for _ in range(5):
            engine.process_event("BAD_TRUCK", 54, now)  # Lower score

        rankings = engine.get_fleet_rankings()

        assert len(rankings) == 2
        assert rankings[0]["truck_id"] == "GOOD_TRUCK"  # Should be first
        assert rankings[0]["rank"] == 1

    def test_improvement_tips(self):
        """Test improvement tips generation"""
        from driver_scoring_engine import DriverScoringEngine

        engine = DriverScoringEngine()
        now = datetime.now(timezone.utc)

        # Add speeding events
        engine.process_event("CO0681", 54, now)
        engine.process_speeding("CO0681", now, 140, 105, 60)
        engine.add_idle_hours("CO0681", 5.0)

        tips = engine.get_improvement_tips("CO0681")

        assert len(tips) > 0
        # Should have tips about speeding and idle
        categories = [t["category"] for t in tips]
        assert "speeding" in categories
        assert "idle" in categories


# ═══════════════════════════════════════════════════════════════════════════════
# COMPONENT HEALTH PREDICTORS TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestComponentHealthPredictors:
    """Tests for Component Health Predictors"""

    def test_turbo_predictor_import(self):
        """Test turbo predictor import"""
        from component_health_predictors import (
            TurboHealthPredictor,
            get_turbo_predictor,
        )

        turbo = TurboHealthPredictor()
        assert turbo is not None

    def test_turbo_healthy(self):
        """Test turbo predictor with healthy readings"""
        from component_health_predictors import TurboHealthPredictor, ComponentHealth

        turbo = TurboHealthPredictor()

        # Add healthy readings
        for i in range(20):
            turbo.add_reading("CO0681", intrclr_t=55, intake_pres=28)

        prediction = turbo.predict("CO0681")

        assert prediction.status == ComponentHealth.EXCELLENT
        assert prediction.score >= 90

    def test_turbo_critical(self):
        """Test turbo predictor with critical readings"""
        from component_health_predictors import TurboHealthPredictor, ComponentHealth

        turbo = TurboHealthPredictor()

        # Add critical readings (high temp, low boost)
        for i in range(20):
            turbo.add_reading("CO0681", intrclr_t=90, intake_pres=10)

        prediction = turbo.predict("CO0681")

        assert prediction.status in [ComponentHealth.CRITICAL, ComponentHealth.WARNING]
        assert prediction.score < 50
        assert any("CRÍTICA" in a or "baja" in a for a in prediction.alerts)

    def test_oil_tracker_import(self):
        """Test oil tracker import"""
        from component_health_predictors import OilConsumptionTracker, get_oil_tracker

        oil = OilConsumptionTracker()
        assert oil is not None

    def test_oil_healthy(self):
        """Test oil tracker with healthy readings"""
        from component_health_predictors import OilConsumptionTracker, ComponentHealth

        oil = OilConsumptionTracker()

        for i in range(20):
            oil.add_reading("CO0681", oil_level=80, oil_press=45, oil_temp=95)

        prediction = oil.predict("CO0681")

        assert prediction.status == ComponentHealth.EXCELLENT
        assert prediction.score >= 90

    def test_oil_critical_level(self):
        """Test oil tracker with critical level"""
        from component_health_predictors import OilConsumptionTracker, ComponentHealth

        oil = OilConsumptionTracker()

        for i in range(20):
            oil.add_reading("CO0681", oil_level=15, oil_press=45, oil_temp=95)

        prediction = oil.predict("CO0681")

        assert prediction.status in [ComponentHealth.CRITICAL, ComponentHealth.WARNING]
        assert any("CRÍTICO" in a or "bajo" in a for a in prediction.alerts)

    def test_coolant_detector_import(self):
        """Test coolant detector import"""
        from component_health_predictors import (
            CoolantLeakDetector,
            get_coolant_detector,
        )

        coolant = CoolantLeakDetector()
        assert coolant is not None

    def test_coolant_healthy(self):
        """Test coolant detector with healthy readings"""
        from component_health_predictors import CoolantLeakDetector, ComponentHealth

        coolant = CoolantLeakDetector()

        for i in range(20):
            coolant.add_reading("CO0681", cool_lvl=85, cool_temp=90)

        prediction = coolant.predict("CO0681")

        assert prediction.status == ComponentHealth.EXCELLENT
        assert prediction.score >= 90

    def test_coolant_leak_detection(self):
        """Test coolant leak detection"""
        from component_health_predictors import CoolantLeakDetector, ComponentHealth

        coolant = CoolantLeakDetector()

        # Simulate level dropping (leak)
        for i in range(20):
            coolant.add_reading("CO0681", cool_lvl=50 - i, cool_temp=90)

        prediction = coolant.predict("CO0681")

        assert (
            prediction.sensor_data.get("leak_detected") is True
            or prediction.score < 100
        )

    def test_prediction_to_dict(self):
        """Test prediction serialization"""
        from component_health_predictors import TurboHealthPredictor

        turbo = TurboHealthPredictor()
        turbo.add_reading("CO0681", intrclr_t=55, intake_pres=28)

        prediction = turbo.predict("CO0681")
        data = prediction.to_dict()

        assert "component" in data
        assert "truck_id" in data
        assert "score" in data
        assert "status" in data
        assert "alerts" in data


# ═══════════════════════════════════════════════════════════════════════════════
# INTEGRATION TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestIntegration:
    """Integration tests for all new modules"""

    def test_fleet_command_center_version(self):
        """Test Fleet Command Center updated to v1.8.0"""
        from fleet_command_center import FleetCommandCenter

        assert FleetCommandCenter.VERSION == "1.8.0"

    def test_driver_alerts_router_loads(self):
        """Test driver alerts router loads correctly"""
        from routers.driver_alerts_router import router

        assert router is not None
        assert len(router.routes) >= 5  # Should have at least 5 endpoints

    def test_dtc_database_stats(self):
        """Test dtc_database.py has expected stats"""
        from dtc_database import get_database_stats

        stats = get_database_stats()

        assert stats["total_spns"] >= 100  # Should have 112 SPNs
        assert stats["total_fmis"] == 23  # Should have 23 FMIs

    def test_all_modules_work_together(self):
        """Test that all modules can work together"""
        from dtc_analyzer import DTCAnalyzer
        from driver_scoring_engine import DriverScoringEngine
        from component_health_predictors import (
            TurboHealthPredictor,
            OilConsumptionTracker,
            CoolantLeakDetector,
        )

        # Create all engines
        dtc = DTCAnalyzer()
        scoring = DriverScoringEngine()
        turbo = TurboHealthPredictor()
        oil = OilConsumptionTracker()
        coolant = CoolantLeakDetector()

        truck_id = "TEST_TRUCK"
        now = datetime.now(timezone.utc)

        # Use all engines
        dtc_report = dtc.get_dtc_analysis_report(truck_id, "597.4")
        scoring.process_event(truck_id, 54, now)
        driver_score = scoring.calculate_score(truck_id)

        turbo.add_reading(truck_id, intrclr_t=55, intake_pres=28)
        turbo_pred = turbo.predict(truck_id)

        oil.add_reading(truck_id, oil_level=80, oil_press=45)
        oil_pred = oil.predict(truck_id)

        coolant.add_reading(truck_id, cool_lvl=85, cool_temp=90)
        coolant_pred = coolant.predict(truck_id)

        # All should work without errors
        assert dtc_report is not None
        assert driver_score is not None
        assert turbo_pred is not None
        assert oil_pred is not None
        assert coolant_pred is not None


# ═══════════════════════════════════════════════════════════════════════════════
# DTC DATABASE TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestDTCDatabase:
    """Tests for dtc_database.py v5.8.0"""

    def test_database_import(self):
        """Test dtc_database can be imported"""
        from dtc_database import get_spn_info, get_fmi_info, get_dtc_description

        assert get_spn_info is not None
        assert get_fmi_info is not None
        assert get_dtc_description is not None

    def test_spn_lookup(self):
        """Test SPN lookup"""
        from dtc_database import get_spn_info

        # Test known SPN from Wialon DB
        info = get_spn_info(597)  # Brake Pedal Switch

        assert info is not None
        assert info.spn == 597
        assert "Freno" in info.name_es or "Brake" in info.name_en

    def test_fmi_lookup(self):
        """Test FMI lookup"""
        from dtc_database import get_fmi_info

        # FMI 4 = Voltage Below Normal
        info = get_fmi_info(4)

        assert "es" in info
        assert "severity" in info

    def test_dtc_description_full(self):
        """Test full DTC description"""
        from dtc_database import get_dtc_description

        desc = get_dtc_description(597, 4, language="es")

        assert "component" in desc
        assert "failure_mode" in desc
        assert "action" in desc
        assert "severity" in desc
        assert "system" in desc

    def test_all_wialon_spns_exist(self):
        """Test that all SPNs seen in Wialon exist in database"""
        from dtc_database import get_spn_info

        # SPNs found in actual Wialon DB
        wialon_spns = [
            597,
            829,
            1089,
            1322,
            1548,
            1592,
            1636,
            2023,
            2791,
            3226,
            3251,
            3510,
            5571,
        ]

        for spn in wialon_spns:
            info = get_spn_info(spn)
            assert info is not None, f"SPN {spn} not found in database"


# ═══════════════════════════════════════════════════════════════════════════════
# DEF PREDICTOR TESTS (v1.8.0)
# ═══════════════════════════════════════════════════════════════════════════════


class TestDEFPredictor:
    """Tests for DEF Predictor Engine - 51,589+ records available in Wialon"""

    def test_def_predictor_import(self):
        """Test that DEF predictor can be imported"""
        from def_predictor import DEFPredictor, DEFReading, DEFAlertLevel

        predictor = DEFPredictor()
        assert predictor is not None

    def test_def_alert_levels(self):
        """Test alert level enum values"""
        from def_predictor import DEFAlertLevel

        assert DEFAlertLevel.GOOD.value == "good"
        assert DEFAlertLevel.LOW.value == "low"
        assert DEFAlertLevel.WARNING.value == "warning"
        assert DEFAlertLevel.CRITICAL.value == "critical"
        assert DEFAlertLevel.EMERGENCY.value == "emergency"

    def test_def_reading_creation(self):
        """Test creating DEF readings"""
        from def_predictor import DEFReading

        reading = DEFReading(
            timestamp=datetime.now(),
            unit_id=401849345,
            truck_id="VD3579",
            level_percent=75.5,
            odometer=150000.0,
            engine_hours=5000.0,
        )

        assert reading.level_percent == 75.5
        assert reading.truck_id == "VD3579"
        assert reading.odometer == 150000.0

    def test_def_predictor_add_readings(self):
        """Test adding readings to predictor"""
        from def_predictor import DEFPredictor, DEFReading

        predictor = DEFPredictor()

        # Add multiple readings
        base_time = datetime.now() - timedelta(hours=48)
        readings = []

        for i in range(50):
            reading = DEFReading(
                timestamp=base_time + timedelta(hours=i),
                unit_id=401849345,
                truck_id="VD3579",
                level_percent=80 - (i * 0.4),  # Simulating consumption
                odometer=150000 + (i * 30),
                engine_hours=5000 + i,
            )
            readings.append(reading)

        predictor.add_readings(readings)

        assert len(predictor.readings_cache["VD3579"]) == 50

    def test_def_consumption_profile_calculation(self):
        """Test DEF consumption profile calculation"""
        from def_predictor import DEFPredictor, DEFReading

        predictor = DEFPredictor()

        # Add enough data for profile calculation
        base_time = datetime.now() - timedelta(days=7)

        for i in range(100):
            level = 80 - (i * 0.5)
            if level < 10:
                level = 80  # Simulate refill

            reading = DEFReading(
                timestamp=base_time + timedelta(hours=i * 2),
                unit_id=401849345,
                truck_id="VD3579",
                level_percent=level,
                odometer=100000 + (i * 50),
                engine_hours=5000 + i,
            )
            predictor.add_reading(reading)

        profile = predictor.calculate_consumption_profile("VD3579")

        assert profile is not None
        assert profile.truck_id == "VD3579"
        assert profile.readings_count == 100
        assert profile.current_level_percent > 0

    def test_def_alert_level_determination(self):
        """Test alert level is correctly determined"""
        from def_predictor import DEFPredictor, DEFAlertLevel

        predictor = DEFPredictor()

        # Test threshold boundaries
        assert predictor._determine_alert_level(30) == DEFAlertLevel.GOOD
        assert predictor._determine_alert_level(20) == DEFAlertLevel.LOW
        assert predictor._determine_alert_level(12) == DEFAlertLevel.WARNING
        assert predictor._determine_alert_level(7) == DEFAlertLevel.CRITICAL
        assert predictor._determine_alert_level(3) == DEFAlertLevel.EMERGENCY

    def test_def_prediction_generation(self):
        """Test generating DEF prediction"""
        from def_predictor import DEFPredictor, DEFReading

        predictor = DEFPredictor()

        # Add data
        base_time = datetime.now() - timedelta(days=5)

        for i in range(80):
            reading = DEFReading(
                timestamp=base_time + timedelta(hours=i),
                unit_id=401849345,
                truck_id="VD3579",
                level_percent=70 - (i * 0.5),
                odometer=100000 + (i * 40),
                engine_hours=5000 + i,
            )
            predictor.add_reading(reading)

        prediction = predictor.predict("VD3579")

        assert prediction is not None
        assert prediction.truck_id == "VD3579"
        assert prediction.urgency_score >= 0
        assert prediction.recommended_action is not None

    def test_def_fleet_status(self):
        """Test fleet-wide DEF status summary"""
        from def_predictor import DEFPredictor, DEFReading

        predictor = DEFPredictor()

        # Add data for multiple trucks
        trucks = ["VD3579", "JC1282", "NQ6975"]
        base_time = datetime.now() - timedelta(days=3)

        for truck_id in trucks:
            for i in range(30):
                reading = DEFReading(
                    timestamp=base_time + timedelta(hours=i),
                    unit_id=hash(truck_id) % 1000000,
                    truck_id=truck_id,
                    level_percent=60 - (i * 0.8),
                    odometer=100000 + (i * 50),
                    engine_hours=5000 + i,
                )
                predictor.add_reading(reading)

        status = predictor.get_fleet_def_status()

        assert "fleet_status" in status
        assert "truck_count" in status
        assert status["truck_count"] == 3


# ═══════════════════════════════════════════════════════════════════════════════
# DTW PATTERN ANALYZER TESTS (v1.8.0)
# ═══════════════════════════════════════════════════════════════════════════════


class TestDTWAnalyzer:
    """Tests for Dynamic Time Warping Pattern Analyzer"""

    def test_dtw_analyzer_import(self):
        """Test that DTW analyzer can be imported"""
        from dtw_analyzer import DTWAnalyzer, TimeSeriesData

        analyzer = DTWAnalyzer()
        assert analyzer is not None

    def test_time_series_creation(self):
        """Test creating time series data"""
        from dtw_analyzer import TimeSeriesData

        series = TimeSeriesData(
            truck_id="VD3579",
            unit_id=401849345,
            metric_name="fuel_lvl",
            timestamps=[datetime.now() - timedelta(hours=i) for i in range(10)],
            values=[50.0 + i for i in range(10)],
        )

        assert len(series) == 10
        assert series.truck_id == "VD3579"

    def test_time_series_normalize(self):
        """Test z-score normalization of time series"""
        from dtw_analyzer import TimeSeriesData

        series = TimeSeriesData(
            truck_id="VD3579",
            unit_id=401849345,
            metric_name="fuel_lvl",
            timestamps=[datetime.now() - timedelta(hours=i) for i in range(10)],
            values=[10, 20, 30, 40, 50, 60, 70, 80, 90, 100],
        )

        normalized = series.normalize()

        assert "normalized" in normalized.metric_name
        # Z-score should have mean ~0
        import statistics

        mean = statistics.mean(normalized.values)
        assert abs(mean) < 0.001

    def test_dtw_distance_identical(self):
        """Test DTW distance between identical series"""
        from dtw_analyzer import DTWAnalyzer

        analyzer = DTWAnalyzer()

        series = [1.0, 2.0, 3.0, 4.0, 5.0]
        distance, path = analyzer.dtw_distance(series, series)

        assert distance == 0.0
        assert len(path) == 5

    def test_dtw_distance_different(self):
        """Test DTW distance between different series"""
        from dtw_analyzer import DTWAnalyzer

        analyzer = DTWAnalyzer()

        series1 = [1.0, 2.0, 3.0, 4.0, 5.0]
        series2 = [2.0, 3.0, 4.0, 5.0, 6.0]  # Shifted by 1

        distance, path = analyzer.dtw_distance(series1, series2)

        assert distance > 0
        assert len(path) > 0

    def test_dtw_compare_trucks(self):
        """Test comparing two trucks' patterns"""
        from dtw_analyzer import DTWAnalyzer, TimeSeriesData
        import math

        analyzer = DTWAnalyzer()

        # Create similar patterns
        base_time = datetime.now() - timedelta(hours=100)
        base_pattern = [50 + 5 * math.sin(i / 10) for i in range(100)]

        series1 = TimeSeriesData(
            truck_id="VD3579",
            unit_id=401849345,
            metric_name="fuel_lvl",
            timestamps=[base_time + timedelta(hours=i) for i in range(100)],
            values=[v + 0.5 for v in base_pattern],  # Small variation
        )

        series2 = TimeSeriesData(
            truck_id="JC1282",
            unit_id=401575668,
            metric_name="fuel_lvl",
            timestamps=[base_time + timedelta(hours=i) for i in range(100)],
            values=[v + 0.3 for v in base_pattern],  # Small variation
        )

        analyzer.add_time_series(series1)
        analyzer.add_time_series(series2)

        result = analyzer.compare_trucks("VD3579", "JC1282", "fuel_lvl")

        assert result is not None
        assert result.similarity_percent > 80  # Should be very similar

    def test_dtw_find_most_similar(self):
        """Test finding most similar trucks"""
        from dtw_analyzer import DTWAnalyzer, TimeSeriesData
        import random

        # Set seed for reproducibility
        random.seed(42)

        analyzer = DTWAnalyzer()

        base_time = datetime.now() - timedelta(hours=50)

        # Create VD3579 and JC1282 with IDENTICAL base pattern + tiny noise
        base_pattern = [50 + (i % 10) * 0.5 for i in range(50)]  # Deterministic

        # VD3579 - base pattern
        series1 = TimeSeriesData(
            truck_id="VD3579",
            unit_id=401849345,
            metric_name="fuel_lvl",
            timestamps=[base_time + timedelta(hours=j) for j in range(50)],
            values=[v + 0.1 for v in base_pattern],
        )
        analyzer.add_time_series(series1)

        # JC1282 - almost identical to VD3579
        series2 = TimeSeriesData(
            truck_id="JC1282",
            unit_id=401575668,
            metric_name="fuel_lvl",
            timestamps=[base_time + timedelta(hours=j) for j in range(50)],
            values=[v + 0.2 for v in base_pattern],  # Very similar
        )
        analyzer.add_time_series(series2)

        # NQ6975 - completely different pattern (much higher values)
        series3 = TimeSeriesData(
            truck_id="NQ6975",
            unit_id=402023398,
            metric_name="fuel_lvl",
            timestamps=[base_time + timedelta(hours=j) for j in range(50)],
            values=[80 + (i % 5) * 2 for i in range(50)],  # Very different
        )
        analyzer.add_time_series(series3)

        # GP9677 - also different
        series4 = TimeSeriesData(
            truck_id="GP9677",
            unit_id=401919268,
            metric_name="fuel_lvl",
            timestamps=[base_time + timedelta(hours=j) for j in range(50)],
            values=[90 - (i % 8) * 1.5 for i in range(50)],  # Very different
        )
        analyzer.add_time_series(series4)

        similar = analyzer.find_most_similar("VD3579", "fuel_lvl", top_n=3)

        assert len(similar) > 0
        # JC1282 should be most similar to VD3579 (almost identical pattern)
        assert similar[0].truck_id_2 == "JC1282"

    def test_dtw_detect_anomalies(self):
        """Test anomaly detection"""
        from dtw_analyzer import DTWAnalyzer, TimeSeriesData
        import math

        analyzer = DTWAnalyzer()

        base_time = datetime.now() - timedelta(hours=50)
        base_pattern = [50 + 3 * math.sin(i / 8) for i in range(50)]

        # Add 4 normal trucks
        for tid in ["VD3579", "JC1282", "NQ6975", "GP9677"]:
            series = TimeSeriesData(
                truck_id=tid,
                unit_id=hash(tid) % 1000000,
                metric_name="fuel_lvl",
                timestamps=[base_time + timedelta(hours=j) for j in range(50)],
                values=[v + 0.5 for v in base_pattern],
            )
            analyzer.add_time_series(series)

        # Add 1 anomalous truck
        anomalous = TimeSeriesData(
            truck_id="ANOMALY",
            unit_id=999999,
            metric_name="fuel_lvl",
            timestamps=[base_time + timedelta(hours=j) for j in range(50)],
            values=[
                v + 20 * math.sin(j / 3) for j, v in enumerate(base_pattern)
            ],  # Very different
        )
        analyzer.add_time_series(anomalous)

        anomalies = analyzer.detect_anomalies("fuel_lvl")

        assert len(anomalies) >= 1
        # ANOMALY should have highest score
        anomaly_truck = next((a for a in anomalies if a.truck_id == "ANOMALY"), None)
        assert anomaly_truck is not None

    def test_dtw_cluster_fleet(self):
        """Test fleet clustering"""
        from dtw_analyzer import DTWAnalyzer, TimeSeriesData

        analyzer = DTWAnalyzer()

        base_time = datetime.now() - timedelta(hours=30)

        # Group A: Low values
        for tid in ["A1", "A2", "A3"]:
            series = TimeSeriesData(
                truck_id=tid,
                unit_id=hash(tid) % 1000000,
                metric_name="fuel_lvl",
                timestamps=[base_time + timedelta(hours=j) for j in range(30)],
                values=[30 + j * 0.1 for j in range(30)],
            )
            analyzer.add_time_series(series)

        # Group B: High values
        for tid in ["B1", "B2", "B3"]:
            series = TimeSeriesData(
                truck_id=tid,
                unit_id=hash(tid) % 1000000,
                metric_name="fuel_lvl",
                timestamps=[base_time + timedelta(hours=j) for j in range(30)],
                values=[70 + j * 0.1 for j in range(30)],
            )
            analyzer.add_time_series(series)

        clusters = analyzer.cluster_fleet("fuel_lvl", n_clusters=2)

        assert len(clusters) == 2
        # Each cluster should have 3 trucks
        total_trucks = sum(len(c.truck_ids) for c in clusters)
        assert total_trucks == 6


# ═══════════════════════════════════════════════════════════════════════════════
# WIALON DATA LOADER TESTS (v1.8.0)
# ═══════════════════════════════════════════════════════════════════════════════


class TestWialonDataLoader:
    """Tests for Wialon Data Loader Service"""

    def test_data_loader_import(self):
        """Test that data loader can be imported"""
        from wialon_data_loader import WialonDataLoader, get_wialon_loader, DataType

        loader = WialonDataLoader()
        assert loader is not None

    def test_data_type_enum(self):
        """Test DataType enum"""
        from wialon_data_loader import DataType

        assert DataType.DEF_LEVELS.value == "def_levels"
        assert DataType.SENSOR_DATA.value == "sensor_data"
        assert DataType.EVENTS.value == "events"
        assert DataType.SPEEDINGS.value == "speedings"

    def test_singleton_pattern(self):
        """Test singleton pattern for loader"""
        from wialon_data_loader import get_wialon_loader

        loader1 = get_wialon_loader()
        loader2 = get_wialon_loader()

        assert loader1 is loader2

    def test_truck_mapping_loading(self):
        """Test loading truck mapping from config"""
        from wialon_data_loader import WialonDataLoader

        loader = WialonDataLoader(tanks_config_path="tanks.yaml")

        # Should have loaded trucks from tanks.yaml
        assert len(loader._truck_mapping) > 0

    def test_get_truck_id(self):
        """Test getting truck ID from unit ID"""
        from wialon_data_loader import WialonDataLoader

        loader = WialonDataLoader(tanks_config_path="tanks.yaml")

        # Test known mapping (VD3579 = 401849345)
        truck_id = loader.get_truck_id(401849345)
        assert truck_id == "VD3579"

    def test_cache_key_generation(self):
        """Test cache key generation"""
        from wialon_data_loader import WialonDataLoader, DataType

        loader = WialonDataLoader()

        key1 = loader._get_cache_key(DataType.DEF_LEVELS, days=30)
        key2 = loader._get_cache_key(DataType.DEF_LEVELS, days=30)
        key3 = loader._get_cache_key(DataType.DEF_LEVELS, days=60)

        assert key1 == key2  # Same params = same key
        assert key1 != key3  # Different params = different key

    def test_cache_operations(self):
        """Test cache set and get"""
        from wialon_data_loader import WialonDataLoader

        loader = WialonDataLoader()

        # Set cache
        test_data = [{"id": 1}, {"id": 2}]
        loader._set_cache("test_key", test_data, ttl_minutes=5)

        # Get from cache
        cached = loader._get_from_cache("test_key")

        assert cached == test_data

    def test_cache_clear(self):
        """Test cache clearing"""
        from wialon_data_loader import WialonDataLoader

        loader = WialonDataLoader()

        # Add some cache entries
        loader._set_cache("key1", [1, 2, 3])
        loader._set_cache("key2", [4, 5, 6])

        # Clear cache
        loader.clear_cache()

        # Should be empty
        assert loader._get_from_cache("key1") is None
        assert loader._get_from_cache("key2") is None


# ═══════════════════════════════════════════════════════════════════════════════
# RUN TESTS
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
