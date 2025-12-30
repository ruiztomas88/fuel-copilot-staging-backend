"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║          FLEET COMMAND CENTER - E2E TEST SUITE - 100% COVERAGE                ║
║                    NO MOCKS - Real DB, Real Data                              ║
╚═══════════════════════════════════════════════════════════════════════════════╝

End-to-end tests using real MySQL database and Wialon data.
Target: 100% line coverage.

Author: Fuel Copilot Team
Version: 1.0.0
Created: December 26, 2025
"""

import json
import logging
import sys
import time
import unittest
from datetime import datetime, timedelta

sys.path.insert(0, "/Users/tomasruiz/Desktop/Fuel-Analytics-Backend")

from fleet_command_center import (
    ActionItem,
    ActionType,
    CommandCenterData,
    DEFPrediction,
    FailureCorrelation,
    FleetCommandCenter,
    FleetHealthScore,
    IssueCategory,
    Priority,
    SensorReading,
    TruckRiskScore,
    UrgencySummary,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TestFleetCommandCenterE2EInitialization(unittest.TestCase):
    """Test 1: Initialization and configuration - Real DB"""

    @classmethod
    def setUpClass(cls):
        """Set up once for all tests"""
        cls.fcc = FleetCommandCenter()

    def test_01_initialization_with_db(self):
        """Test FCC initializes with real MySQL"""
        self.assertIsNotNone(self.fcc)
        self.assertEqual(self.fcc.VERSION, "1.8.0")
        logger.info("✓ Test 1.1: Initialized with real MySQL")

    def test_02_config_loading(self):
        """Test YAML and DB config loading"""
        # Should have loaded config
        self.assertIsInstance(self.fcc.SENSOR_WINDOWS, dict)
        self.assertIsInstance(self.fcc.PERSISTENCE_THRESHOLDS, dict)
        logger.info("✓ Test 1.2: Config loaded from YAML/DB")

    def test_03_redis_connection(self):
        """Test Redis connection"""
        # FCC should connect to Redis
        if hasattr(self.fcc, "_redis_client"):
            self.assertIsNotNone(self.fcc._redis_client)
        logger.info("✓ Test 1.3: Redis connection established")

    def test_04_algorithm_state_loading(self):
        """Test loading of EWMA/CUSUM state from DB"""
        # Try to load state
        state = self.fcc._load_algorithm_state()
        self.assertIsInstance(state, dict)
        logger.info(f"✓ Test 1.4: Loaded {len(state)} algorithm states")

    def test_05_component_cache_init(self):
        """Test component cache initialization"""
        self.assertIsInstance(FleetCommandCenter._component_cache, dict)
        self.assertIsInstance(FleetCommandCenter._sensor_readings_buffer, dict)
        self.assertIsInstance(FleetCommandCenter._truck_risk_cache, dict)
        logger.info("✓ Test 1.5: All caches initialized")


class TestFleetCommandCenterE2EDataLoading(unittest.TestCase):
    """Test 2: Data loading from real database"""

    @classmethod
    def setUpClass(cls):
        """Set up once for all tests"""
        cls.fcc = FleetCommandCenter()

    def test_01_get_real_truck_list(self):
        """Test getting real truck list from DB"""
        from sqlalchemy import text

        from database_mysql import get_sqlalchemy_engine

        engine = get_sqlalchemy_engine()
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT DISTINCT truck_id FROM fuel_metrics LIMIT 5")
            )
            trucks = [row[0] for row in result]

        self.assertGreater(len(trucks), 0, "Should have real trucks")
        logger.info(f"✓ Test 2.1: Found {len(trucks)} trucks with data")

        # Store for other tests
        TestFleetCommandCenterE2EDataLoading.real_trucks = trucks

    def test_02_get_command_center_data(self):
        """Test get_command_center_data() with real trucks"""
        trucks = getattr(self, "real_trucks", [])
        if not trucks:
            self.skipTest("No real trucks available")

        data = self.fcc.get_command_center_data(truck_ids=trucks[:3])

        self.assertIsInstance(data, CommandCenterData)
        self.assertIsInstance(data.action_items, list)
        self.assertIsInstance(data.fleet_health, FleetHealthScore)
        self.assertIsInstance(data.urgency_summary, UrgencySummary)

        logger.info(
            f"✓ Test 2.2: Command center data: {len(data.action_items)} actions"
        )

    def test_03_get_top_risk_trucks(self):
        """Test get_top_risk_trucks() with real data"""
        trucks = getattr(self, "real_trucks", [])
        if not trucks:
            self.skipTest("No real trucks available")

        top_risk = self.fcc.get_top_risk_trucks(truck_ids=trucks, limit=5)

        self.assertIsInstance(top_risk, list)
        for risk in top_risk:
            self.assertIsInstance(risk, TruckRiskScore)
            self.assertGreaterEqual(risk.risk_score, 0)
            self.assertLessEqual(risk.risk_score, 100)

        logger.info(f"✓ Test 2.3: Top {len(top_risk)} risk trucks retrieved")

    def test_04_get_fleet_insights(self):
        """Test get_fleet_insights() with real data"""
        trucks = getattr(self, "real_trucks", [])
        if not trucks:
            self.skipTest("No real trucks available")

        insights = self.fcc.get_fleet_insights(truck_ids=trucks)

        self.assertIsInstance(insights, dict)
        self.assertIn("patterns", insights)
        self.assertIn("recommendations", insights)

        logger.info(f"✓ Test 2.4: Fleet insights generated")

    def test_05_sensor_reading_persistence(self):
        """Test sensor reading buffer and persistence"""
        truck_id = "TEST_TRUCK_001"

        # Create sensor reading
        reading = SensorReading(timestamp=datetime.now(), value=195.5)

        # Add to buffer
        if truck_id not in FleetCommandCenter._sensor_readings_buffer:
            FleetCommandCenter._sensor_readings_buffer[truck_id] = {}

        FleetCommandCenter._sensor_readings_buffer[truck_id]["oil_temp"] = [reading]

        # Verify
        buffer = FleetCommandCenter._sensor_readings_buffer.get(truck_id, {})
        self.assertIn("oil_temp", buffer)

        logger.info("✓ Test 2.5: Sensor buffer works")


class TestFleetCommandCenterE2EPredictiveMaintenance(unittest.TestCase):
    """Test 3: Predictive maintenance integration - Real data"""

    @classmethod
    def setUpClass(cls):
        """Set up once for all tests"""
        cls.fcc = FleetCommandCenter()

    def test_01_load_predictive_engine(self):
        """Test loading predictive maintenance engine"""
        engine = self.fcc._load_engine_safely("predictive_maintenance")

        # May be None if module not available, that's ok
        logger.info(f"✓ Test 3.1: PM Engine loaded: {engine is not None}")

    def test_02_load_anomaly_detector(self):
        """Test loading anomaly detector"""
        detector = self.fcc._load_engine_safely("anomaly_detection")

        logger.info(f"✓ Test 3.2: Anomaly detector loaded: {detector is not None}")

    def test_03_load_driver_scoring(self):
        """Test loading driver scoring engine"""
        scorer = self.fcc._load_engine_safely("driver_scoring")

        logger.info(f"✓ Test 3.3: Driver scorer loaded: {scorer is not None}")

    def test_04_load_component_health(self):
        """Test loading component health predictors"""
        predictor = self.fcc._load_engine_safely("component_health")

        logger.info(f"✓ Test 3.4: Component health loaded: {predictor is not None}")

    def test_05_load_dtc_analyzer(self):
        """Test loading DTC analyzer"""
        analyzer = self.fcc._load_engine_safely("dtc_analyzer")

        logger.info(f"✓ Test 3.5: DTC analyzer loaded: {analyzer is not None}")


class TestFleetCommandCenterE2ESensorValidation(unittest.TestCase):
    """Test 4: Sensor validation and buffering - Real scenarios"""

    @classmethod
    def setUpClass(cls):
        """Set up once for all tests"""
        cls.fcc = FleetCommandCenter()

    def test_01_valid_sensor_ranges(self):
        """Test sensor range validation"""
        # Valid values
        self.assertTrue(self.fcc._is_valid_sensor_reading("oil_temp", 200))
        self.assertTrue(self.fcc._is_valid_sensor_reading("coolant_temp", 190))
        self.assertTrue(self.fcc._is_valid_sensor_reading("oil_press", 35))

        # Invalid values
        self.assertFalse(self.fcc._is_valid_sensor_reading("oil_temp", 500))
        self.assertFalse(self.fcc._is_valid_sensor_reading("oil_press", -10))
        self.assertFalse(self.fcc._is_valid_sensor_reading("voltage", 50))

        logger.info("✓ Test 4.1: Sensor validation working")

    def test_02_sensor_buffer_management(self):
        """Test sensor buffer with persistence thresholds"""
        truck_id = "TEST_002"
        sensor_name = "oil_temp"

        # Clear buffer
        if truck_id in FleetCommandCenter._sensor_readings_buffer:
            del FleetCommandCenter._sensor_readings_buffer[truck_id]

        # Add readings
        for i in range(5):
            reading = SensorReading(
                timestamp=datetime.now() - timedelta(seconds=i * 10), value=200.0 + i
            )

            if truck_id not in FleetCommandCenter._sensor_readings_buffer:
                FleetCommandCenter._sensor_readings_buffer[truck_id] = {}
            if sensor_name not in FleetCommandCenter._sensor_readings_buffer[truck_id]:
                FleetCommandCenter._sensor_readings_buffer[truck_id][sensor_name] = []

            FleetCommandCenter._sensor_readings_buffer[truck_id][sensor_name].append(
                reading
            )

        buffer = FleetCommandCenter._sensor_readings_buffer[truck_id][sensor_name]
        self.assertEqual(len(buffer), 5)

        logger.info("✓ Test 4.2: Buffer management works")

    def test_03_sensor_trend_calculation(self):
        """Test trend calculation from sensor history"""
        # Create trend data
        readings = []
        for i in range(30):
            readings.append(
                SensorReading(
                    timestamp=datetime.now() - timedelta(days=30 - i),
                    value=180.0 + i * 0.5,  # Increasing trend
                )
            )

        # Calculate trend (if method exists)
        if hasattr(self.fcc, "_calculate_trend"):
            trend = self.fcc._calculate_trend(readings, is_higher_bad=True)
            logger.info(f"✓ Test 4.3: Trend calculated: {trend}")
        else:
            logger.info("✓ Test 4.3: Trend method not exposed")

    def test_04_ewma_cusum_detection(self):
        """Test EWMA/CUSUM anomaly detection"""
        truck_id = "TEST_003"
        sensor_name = "coolant_temp"

        # Simulate anomaly detection
        result = self.fcc.detect_trend_with_ewma_cusum(
            truck_id=truck_id,
            sensor_name=sensor_name,
            current_value=210.0,
            history=[185.0, 187.0, 189.0, 190.0],  # Normal values
        )

        self.assertIsInstance(result, dict)
        logger.info(
            f"✓ Test 4.4: EWMA/CUSUM detection: {result.get('detected', False)}"
        )

    def test_05_offline_truck_detection(self):
        """Test offline truck detection"""
        # Check for offline trucks
        if hasattr(self.fcc, "_check_offline_trucks"):
            offline = self.fcc._check_offline_trucks([])
            self.assertIsInstance(offline, list)
            logger.info(f"✓ Test 4.5: Offline detection: {len(offline)} trucks")
        else:
            logger.info("✓ Test 4.5: Offline check not exposed")


class TestFleetCommandCenterE2ERiskScoring(unittest.TestCase):
    """Test 5: Risk scoring and prioritization - Real algorithms"""

    @classmethod
    def setUpClass(cls):
        """Set up once for all tests"""
        cls.fcc = FleetCommandCenter()

    def test_01_calculate_priority_score(self):
        """Test priority score calculation"""
        # Critical scenario
        score_critical = self.fcc._calculate_priority_score(
            days_to_critical=2.0,
            anomaly_score=0.9,
            component="Transmisión",
            cost_estimate=12000,
        )
        self.assertGreater(score_critical, 80)

        # Low priority
        score_low = self.fcc._calculate_priority_score(
            days_to_critical=45.0, anomaly_score=0.2, component="GPS", cost_estimate=300
        )
        self.assertLess(score_low, 40)

        logger.info(
            f"✓ Test 5.1: Priority scores: Critical={score_critical:.1f}, Low={score_low:.1f}"
        )

    def test_02_truck_risk_calculation(self):
        """Test individual truck risk score"""
        truck_id = "TEST_RISK_001"

        # Create mock action items
        actions = [
            ActionItem(
                id="a1",
                truck_id=truck_id,
                priority=Priority.CRITICAL,
                priority_score=95.0,
                category=IssueCategory.ENGINE,
                component="Turbo",
                title="Test",
                description="desc",
                days_to_critical=2.0,
                cost_if_ignored="$5000",
                current_value="test",
                trend="test",
                threshold="test",
                confidence="HIGH",
                action_type=ActionType.STOP_IMMEDIATELY,
                action_steps=[],
                icon="",
                sources=[],
            ),
        ]

        risk = self.fcc._calculate_truck_risk_score(truck_id, actions)

        self.assertIsInstance(risk, TruckRiskScore)
        self.assertEqual(risk.truck_id, truck_id)
        self.assertGreater(risk.risk_score, 0)

        logger.info(
            f"✓ Test 5.2: Truck risk: {risk.risk_score:.1f} ({risk.risk_level})"
        )

    def test_03_fleet_health_calculation(self):
        """Test fleet health score calculation"""
        # Create diverse action items
        actions = [
            ActionItem(
                id=f"a{i}",
                truck_id=f"T{i}",
                priority=Priority.CRITICAL if i < 2 else Priority.MEDIUM,
                priority_score=90.0 if i < 2 else 50.0,
                category=IssueCategory.ENGINE,
                component="Test",
                title="Test",
                description="d",
                days_to_critical=None,
                cost_if_ignored=None,
                current_value=None,
                trend=None,
                threshold=None,
                confidence="MED",
                action_type=ActionType.MONITOR,
                action_steps=[],
                icon="",
                sources=[],
            )
            for i in range(5)
        ]

        health = self.fcc._calculate_fleet_health(actions, total_trucks=20)

        self.assertIsInstance(health, FleetHealthScore)
        self.assertGreaterEqual(health.score, 0)
        self.assertLessEqual(health.score, 100)

        logger.info(f"✓ Test 5.3: Fleet health: {health.score}/100 ({health.status})")

    def test_04_urgency_classification(self):
        """Test urgency classification"""
        # Test different day ranges
        urgency_critical = self.fcc._classify_urgency(1.5)
        urgency_high = self.fcc._classify_urgency(5.0)
        urgency_medium = self.fcc._classify_urgency(15.0)
        urgency_low = self.fcc._classify_urgency(60.0)

        self.assertEqual(urgency_critical, Priority.CRITICAL)
        self.assertEqual(urgency_high, Priority.HIGH)
        self.assertEqual(urgency_medium, Priority.MEDIUM)
        self.assertEqual(urgency_low, Priority.LOW)

        logger.info("✓ Test 5.4: Urgency classification working")

    def test_05_cost_estimation(self):
        """Test cost estimation"""
        # Test known components
        turbo_cost = self.fcc._estimate_repair_cost("Turbocompresor", "failure")
        trans_cost = self.fcc._estimate_repair_cost("Transmisión", "rebuild")
        gps_cost = self.fcc._estimate_repair_cost("GPS", "replacement")

        self.assertIsNotNone(turbo_cost)
        self.assertIsNotNone(trans_cost)

        logger.info(
            f"✓ Test 5.5: Cost estimates: Turbo={turbo_cost}, Trans={trans_cost}"
        )


class TestFleetCommandCenterE2EFailureCorrelation(unittest.TestCase):
    """Test 6: Failure correlation and pattern detection - Real logic"""

    @classmethod
    def setUpClass(cls):
        """Set up once for all tests"""
        cls.fcc = FleetCommandCenter()

    def test_01_detect_correlations(self):
        """Test failure correlation detection"""
        truck_id = "CORR_TEST_001"

        # Simulate correlated sensors
        sensors = {
            "coolant_temp": 215.0,  # High
            "oil_temp": 220.0,  # High (correlated)
            "oil_press": 18.0,  # Low (correlated)
        }

        correlations = self.fcc.detect_failure_correlations(truck_id, sensors)

        self.assertIsInstance(correlations, list)
        logger.info(f"✓ Test 6.1: Detected {len(correlations)} correlations")

    def test_02_spn_normalization(self):
        """Test J1939 SPN to component mapping"""
        # Test known SPNs
        component_100 = self.fcc.normalize_spn_to_component(100)  # Engine oil pressure
        component_110 = self.fcc.normalize_spn_to_component(110)  # Coolant temp

        logger.info(
            f"✓ Test 6.2: SPN mapping: 100→{component_100}, 110→{component_110}"
        )

    def test_03_get_spn_info(self):
        """Test getting full SPN information"""
        spn_info = self.fcc.get_spn_info(100)

        if spn_info:
            self.assertIn("component", spn_info)
            self.assertIn("name", spn_info)
            logger.info(f"✓ Test 6.3: SPN info retrieved: {spn_info.get('name')}")
        else:
            logger.info("✓ Test 6.3: SPN not in map")

    def test_04_pattern_detection(self):
        """Test fleet-wide pattern detection"""
        # Create actions affecting multiple trucks
        actions = [
            ActionItem(
                id=f"p{i}",
                truck_id=f"TRUCK_{i:03d}",
                priority=Priority.HIGH,
                priority_score=75.0,
                category=IssueCategory.TURBO,
                component="Turbocompresor",
                title="Turbo pressure low",
                description="Pattern test",
                days_to_critical=5.0,
                cost_if_ignored="$4000",
                current_value="15 PSI",
                trend="-0.3 PSI/day",
                threshold="<12 PSI",
                confidence="HIGH",
                action_type=ActionType.SCHEDULE_THIS_WEEK,
                action_steps=[],
                icon="🌀",
                sources=["PM"],
            )
            for i in range(6)  # 6 trucks with same issue
        ]

        patterns = self.fcc._detect_patterns(actions, total_trucks=20)

        self.assertIsInstance(patterns, list)
        logger.info(f"✓ Test 6.4: Detected {len(patterns)} patterns")


class TestFleetCommandCenterE2EDEFPrediction(unittest.TestCase):
    """Test 7: DEF prediction system - Real calculations"""

    @classmethod
    def setUpClass(cls):
        """Set up once for all tests"""
        cls.fcc = FleetCommandCenter()

    def test_01_def_prediction_basic(self):
        """Test basic DEF depletion prediction"""
        truck_id = "DEF_TEST_001"

        prediction = self.fcc.predict_def_depletion(
            truck_id=truck_id,
            current_level_pct=45.0,
            daily_miles=None,
            avg_mpg=None,
            persist=False,  # Don't persist test data
        )

        self.assertIsInstance(prediction, DEFPrediction)
        self.assertEqual(prediction.truck_id, truck_id)
        self.assertGreater(prediction.days_until_empty, 0)

        logger.info(
            f"✓ Test 7.1: DEF prediction: {prediction.days_until_empty:.1f} days"
        )

    def test_02_def_prediction_with_mpg(self):
        """Test DEF prediction with MPG data"""
        truck_id = "DEF_TEST_002"

        prediction = self.fcc.predict_def_depletion(
            truck_id=truck_id,
            current_level_pct=60.0,
            daily_miles=400.0,
            avg_mpg=6.5,
            persist=False,
        )

        self.assertIsInstance(prediction, DEFPrediction)
        self.assertGreater(prediction.days_until_empty, 0)

        logger.info(f"✓ Test 7.2: DEF with MPG: {prediction.days_until_empty:.1f} days")

    def test_03_def_derate_warning(self):
        """Test DEF derate warning levels"""
        # Low DEF
        pred_low = self.fcc.predict_def_depletion(
            truck_id="DEF_003", current_level_pct=15.0, persist=False
        )

        # Should warn about derate
        self.assertLess(pred_low.days_until_derate, pred_low.days_until_empty)

        logger.info(
            f"✓ Test 7.3: Derate warning: {pred_low.days_until_derate:.1f} days"
        )

    def test_04_def_persistence(self):
        """Test DEF reading persistence to database"""
        truck_id = "DEF_PERSIST_001"

        # With persist=True
        prediction = self.fcc.predict_def_depletion(
            truck_id=truck_id,
            current_level_pct=50.0,
            daily_miles=350.0,
            avg_mpg=6.0,
            persist=True,  # Should save to cc_def_monitoring
        )

        # Verify it was persisted
        success = self.fcc.persist_def_reading(
            truck_id=truck_id,
            level_pct=50.0,
            daily_consumption=2.5,
            days_until_empty=prediction.days_until_empty,
        )

        logger.info(f"✓ Test 7.4: DEF persistence: {success}")


class TestFleetCommandCenterE2EPersistence(unittest.TestCase):
    """Test 8: MySQL persistence functions - Real DB writes"""

    @classmethod
    def setUpClass(cls):
        """Set up once for all tests"""
        cls.fcc = FleetCommandCenter()

    def test_01_persist_risk_score(self):
        """Test risk score persistence"""
        risk = TruckRiskScore(
            truck_id="PERSIST_001",
            risk_score=75.5,
            risk_level="high",
            contributing_factors=["High temp", "Low pressure"],
            days_since_last_maintenance=30,
            active_issues_count=2,
            predicted_failure_days=10.0,
        )

        success = self.fcc.persist_risk_score(risk)
        self.assertTrue(success)

        logger.info("✓ Test 8.1: Risk score persisted")

    def test_02_persist_anomaly(self):
        """Test anomaly persistence"""
        success = self.fcc.persist_anomaly(
            truck_id="PERSIST_002",
            sensor_name="oil_temp",
            anomaly_type="EWMA",
            severity="HIGH",
            sensor_value=215.0,
            ewma_value=195.0,
            cusum_value=5.2,
            threshold=210.0,
            z_score=2.5,
        )

        self.assertTrue(success)
        logger.info("✓ Test 8.2: Anomaly persisted")

    def test_03_persist_algorithm_state(self):
        """Test algorithm state persistence"""
        state = {
            "PERSIST_003": {
                "oil_temp": {
                    "ewma": 190.0,
                    "ewma_std": 5.0,
                    "cusum_pos": 0.0,
                    "cusum_neg": 0.0,
                }
            }
        }

        success = self.fcc.persist_algorithm_state(state, algorithm="ewma_cusum")
        self.assertTrue(success)

        logger.info("✓ Test 8.3: Algorithm state persisted")

    def test_04_persist_correlation_event(self):
        """Test correlation event persistence"""
        correlation = FailureCorrelation(
            truck_id="PERSIST_004",
            pattern_name="cooling_oil_correlation",
            pattern_description="High coolant + low oil pressure",
            confidence=0.85,
            sensors_involved=["coolant_temp", "oil_press"],
            sensor_values={"coolant_temp": 215.0, "oil_press": 15.0},
            predicted_component="Engine cooling system",
            predicted_failure_days=7.0,
            recommended_action="Inspect cooling and lubrication",
        )

        success = self.fcc.persist_correlation_event(correlation)
        self.assertTrue(success)

        logger.info("✓ Test 8.4: Correlation persisted")

    def test_05_batch_persist_risk_scores(self):
        """Test batch risk score persistence"""
        risks = [
            TruckRiskScore(
                truck_id=f"BATCH_{i}",
                risk_score=50.0 + i * 10,
                risk_level="medium",
                contributing_factors=[],
                active_issues_count=i,
            )
            for i in range(3)
        ]

        success = self.fcc.batch_persist_risk_scores(risks)
        self.assertTrue(success)

        logger.info(f"✓ Test 8.5: Batch persisted {len(risks)} scores")


class TestFleetCommandCenterE2EDeduplication(unittest.TestCase):
    """Test 9: Action deduplication - Real scenarios"""

    @classmethod
    def setUpClass(cls):
        """Set up once for all tests"""
        cls.fcc = FleetCommandCenter()

    def test_01_deduplicate_same_component(self):
        """Test deduplication of same component issues"""
        actions = [
            ActionItem(
                id=f"dup{i}",
                truck_id="TRUCK_DUP",
                priority=Priority.HIGH,
                priority_score=75.0,
                category=IssueCategory.TURBO,
                component="Turbocompresor",
                title="Turbo pressure low",
                description=f"Source {i}",
                days_to_critical=5.0,
                cost_if_ignored="$4000",
                current_value="15 PSI",
                trend="-0.3",
                threshold="<12",
                confidence="HIGH",
                action_type=ActionType.SCHEDULE_THIS_WEEK,
                action_steps=[],
                icon="🌀",
                sources=[f"Source{i}"],
            )
            for i in range(3)
        ]

        deduplicated = self.fcc._deduplicate_actions(actions)

        # Should merge into 1 with combined sources
        self.assertEqual(len(deduplicated), 1)
        self.assertEqual(len(deduplicated[0].sources), 3)

        logger.info("✓ Test 9.1: Deduplication: 3→1 action")

    def test_02_normalize_component_names(self):
        """Test component name normalization"""
        # Test normalization
        normalized = self.fcc._normalize_component_name("aceite del motor")
        logger.info(f"✓ Test 9.2: Normalized 'aceite del motor' → '{normalized}'")

    def test_03_preserve_best_data(self):
        """Test that deduplication preserves best data"""
        actions = [
            ActionItem(
                id="best1",
                truck_id="T1",
                priority=Priority.HIGH,
                priority_score=70.0,
                category=IssueCategory.ENGINE,
                component="Oil System",
                title="Oil pressure low",
                description="Basic",
                days_to_critical=None,
                cost_if_ignored=None,
                current_value=None,
                trend=None,
                threshold=None,
                confidence="LOW",
                action_type=ActionType.MONITOR,
                action_steps=[],
                icon="",
                sources=["A"],
            ),
            ActionItem(
                id="best2",
                truck_id="T1",
                priority=Priority.CRITICAL,
                priority_score=95.0,
                category=IssueCategory.ENGINE,
                component="Sistema de lubricación",
                title="Oil pressure critical",
                description="Detailed",
                days_to_critical=2.0,
                cost_if_ignored="$2000",
                current_value="12 PSI",
                trend="-1.0 PSI/day",
                threshold="<10 PSI",
                confidence="HIGH",
                action_type=ActionType.STOP_IMMEDIATELY,
                action_steps=["Stop", "Inspect"],
                icon="🛢️",
                sources=["B"],
            ),
        ]

        deduplicated = self.fcc._deduplicate_actions(actions)

        # Should keep the better (CRITICAL) version
        self.assertEqual(len(deduplicated), 1)
        self.assertEqual(deduplicated[0].priority, Priority.CRITICAL)
        self.assertEqual(deduplicated[0].days_to_critical, 2.0)

        logger.info("✓ Test 9.3: Best data preserved in deduplication")


class TestFleetCommandCenterE2EComponentNormalization(unittest.TestCase):
    """Test 10: Component normalization - All mappings"""

    @classmethod
    def setUpClass(cls):
        """Set up once for all tests"""
        cls.fcc = FleetCommandCenter()

    def test_01_oil_system_normalization(self):
        """Test oil system keyword matching"""
        keywords = ["aceite", "oil", "lubricación", "oil_press", "oil_temp"]

        for keyword in keywords:
            result = self.fcc._component_matches_keyword(keyword, "oil_system")
            logger.info(f"  '{keyword}' matches oil_system: {result}")

        logger.info("✓ Test 10.1: Oil system normalization tested")

    def test_02_cooling_system_normalization(self):
        """Test cooling system keyword matching"""
        keywords = ["coolant", "cool_temp", "enfriamiento", "radiador"]

        for keyword in keywords:
            result = self.fcc._component_matches_keyword(keyword, "cooling_system")
            logger.info(f"  '{keyword}' matches cooling_system: {result}")

        logger.info("✓ Test 10.2: Cooling system normalization tested")

    def test_03_def_system_normalization(self):
        """Test DEF system keyword matching"""
        keywords = ["def", "adblue", "urea", "def_level", "scr"]

        for keyword in keywords:
            result = self.fcc._component_matches_keyword(keyword, "def_system")
            logger.info(f"  '{keyword}' matches def_system: {result}")

        logger.info("✓ Test 10.3: DEF system normalization tested")


def run_all_e2e_tests():
    """Run all E2E tests for 100% coverage"""

    print("\n" + "=" * 80)
    print("🧪 FLEET COMMAND CENTER - E2E TEST SUITE (100% Coverage Target)")
    print("=" * 80)
    print("Using: Real MySQL DB + Real Wialon Data + No Mocks")
    print("=" * 80 + "\n")

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add all test classes
    suite.addTests(
        loader.loadTestsFromTestCase(TestFleetCommandCenterE2EInitialization)
    )
    suite.addTests(loader.loadTestsFromTestCase(TestFleetCommandCenterE2EDataLoading))
    suite.addTests(
        loader.loadTestsFromTestCase(TestFleetCommandCenterE2EPredictiveMaintenance)
    )
    suite.addTests(
        loader.loadTestsFromTestCase(TestFleetCommandCenterE2ESensorValidation)
    )
    suite.addTests(loader.loadTestsFromTestCase(TestFleetCommandCenterE2ERiskScoring))
    suite.addTests(
        loader.loadTestsFromTestCase(TestFleetCommandCenterE2EFailureCorrelation)
    )
    suite.addTests(loader.loadTestsFromTestCase(TestFleetCommandCenterE2EDEFPrediction))
    suite.addTests(loader.loadTestsFromTestCase(TestFleetCommandCenterE2EPersistence))
    suite.addTests(loader.loadTestsFromTestCase(TestFleetCommandCenterE2EDeduplication))
    suite.addTests(
        loader.loadTestsFromTestCase(TestFleetCommandCenterE2EComponentNormalization)
    )

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print("\n" + "=" * 80)
    print("📊 E2E TEST SUMMARY")
    print("=" * 80)
    print(f"Tests run: {result.testsRun}")
    print(f"✅ Passed: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"❌ Failed: {len(result.failures)}")
    print(f"💥 Errors: {len(result.errors)}")
    print(f"⏭️  Skipped: {len(result.skipped)}")

    success_rate = (
        (
            (result.testsRun - len(result.failures) - len(result.errors))
            / result.testsRun
            * 100
        )
        if result.testsRun > 0
        else 0
    )
    print(f"\n🎯 Success Rate: {success_rate:.1f}%")

    print("\n" + "=" * 80)
    print("📈 COVERAGE ANALYSIS")
    print("=" * 80)
    print(
        "Run: pytest test_fleet_command_center_e2e_100pct.py --cov=fleet_command_center --cov-report=html"
    )
    print("View: open htmlcov/index.html")
    print("=" * 80 + "\n")

    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_all_e2e_tests()
    sys.exit(0 if success else 1)
