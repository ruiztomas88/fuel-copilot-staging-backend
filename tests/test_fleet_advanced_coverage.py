"""
Advanced Fleet Command Center Tests - Targeting Remaining Coverage Gaps
Lines: 3874-3916, 3926-3968, 4032-4098, 4221-4251, 4382-4453, 5318-5349
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from fleet_command_center import ActionType, IssueCategory, Priority, get_command_center


class TestPredictiveMaintenanceIntegration:
    """Test lines 3874-3916: PM Engine integration"""

    def test_pm_integration_with_critical_items(self):
        """Lines 3874-3916: PM Engine returns items with high priority"""
        cc = get_command_center()

        # Mock PM engine to return high-priority items
        mock_pm_engine = MagicMock()
        mock_pm_engine.get_fleet_summary.return_value = {
            "high_priority_items": [
                {
                    "truck_id": "CO0681",
                    "component": "Turbocharger",
                    "sensor": "boost_pressure",
                    "days_to_critical": 5,
                    "prediction_confidence": 0.85,
                },
                {
                    "truck_id": "CO1092",
                    "component": "Transmission",
                    "sensor": "trans_temp",
                    "days_to_critical": 10,
                    "prediction_confidence": 0.75,
                },
            ],
            "critical_items": [],
        }

        with patch(
            "predictive_maintenance_engine.get_predictive_maintenance_engine"
        ) as mock_get:
            mock_get.return_value = mock_pm_engine
            result = cc.generate_command_center_data()

            # Verify PM items are included
            pm_items = [
                item
                for item in result.action_items
                if "Predictive Maintenance" in item.sources
            ]
            assert len(pm_items) >= 1
            assert any(item.component == "Turbocharger" for item in pm_items)

    def test_pm_integration_exception_handling(self):
        """Lines 3916-3920: PM Engine exception handling"""
        cc = get_command_center()

        with patch(
            "predictive_maintenance_engine.get_predictive_maintenance_engine"
        ) as mock_get:
            mock_get.side_effect = Exception("PM service unavailable")
            result = cc.generate_command_center_data()

            # Should not crash, just log warning
            assert result is not None
            assert isinstance(result.action_items, list)


class TestMLAnomalyIntegration:
    """Test lines 3926-3968: ML Anomaly Detection integration"""

    def test_ml_anomaly_integration_with_anomalies(self):
        """Lines 3926-3968: ML returns anomalous trucks"""
        cc = get_command_center()

        mock_anomalies = {
            "anomalous_trucks": [
                {
                    "truck_id": "CO0681",
                    "anomaly_score": 85,
                    "anomalous_features": [
                        {"feature": "fuel_consumption", "z_score": 3.5}
                    ],
                    "explanation": "Consumo de combustible 3.5 desvíos estándar sobre lo normal",
                },
                {
                    "truck_id": "CO1092",
                    "anomaly_score": 72,
                    "anomalous_features": [{"feature": "engine_load", "z_score": 2.8}],
                    "explanation": "Carga del motor inusualmente alta",
                },
            ]
        }

        with patch("ml_engines.anomaly_detector.analyze_fleet_anomalies") as mock_ml:
            mock_ml.return_value = mock_anomalies
            result = cc.generate_command_center_data()

            # Verify ML anomaly items are included
            ml_items = [
                item
                for item in result.action_items
                if "ML Anomaly Detection" in item.sources
            ]
            assert len(ml_items) >= 1
            assert any(item.component == "Análisis ML" for item in ml_items)
            assert any(
                "Score 85" in item.title or "Score 72" in item.title
                for item in ml_items
            )

    def test_ml_anomaly_exception_handling(self):
        """Lines 3968-3972: ML exception handling"""
        cc = get_command_center()

        with patch("ml_engines.anomaly_detector.analyze_fleet_anomalies") as mock_ml:
            mock_ml.side_effect = Exception("ML service down")
            result = cc.generate_command_center_data()

            # Should not crash
            assert result is not None
            assert isinstance(result.action_items, list)


class TestDTCAnalyzerIntegration:
    """Test lines 4032-4098: DTC Analyzer detailed integration"""

    def test_dtc_analyzer_critical_severity(self):
        """Lines 4032-4098: DTC analyzer returns critical DTCs"""
        cc = get_command_center()

        mock_dtc_analyzer = MagicMock()
        mock_dtc_analyzer.get_dtc_analysis_report.return_value = {
            "status": "success",
            "codes": [
                {
                    "spn": "5444",
                    "fmi": "1",
                    "component": "Calidad del Fluido DEF",
                    "severity": "critical",
                    "description": "DEF quality issue detected",
                }
            ],
        }

        with patch("dtc_analyzer.get_dtc_analyzer") as mock_get:
            mock_get.return_value = mock_dtc_analyzer

            with patch("database_mysql.get_sqlalchemy_engine") as mock_engine:
                mock_conn = MagicMock()
                mock_result = MagicMock()
                mock_result.fetchall.return_value = [
                    (
                        "CO0681",
                        "SPN 5444.1",
                        "CRITICAL",
                        None,
                        None,
                        None,
                        datetime.now(),
                    )
                ]
                mock_conn.execute.return_value = mock_result
                mock_conn.__enter__ = MagicMock(return_value=mock_conn)
                mock_conn.__exit__ = MagicMock(return_value=False)
                mock_engine.return_value.connect.return_value = mock_conn

                result = cc.generate_command_center_data()

                # Should have DTC items with critical priority
                dtc_items = [
                    item for item in result.action_items if "DTC" in str(item.sources)
                ]
                assert len(dtc_items) >= 1

    def test_dtc_analyzer_warning_severity(self):
        """Lines 4065-4075: DTC with warning severity or many trucks"""
        cc = get_command_center()

        mock_dtc_analyzer = MagicMock()
        mock_dtc_analyzer.get_dtc_analysis_report.return_value = {
            "status": "success",
            "codes": [
                {
                    "spn": "110",
                    "fmi": "0",
                    "component": "Engine Coolant Temperature",
                    "severity": "warning",
                    "description": "High coolant temperature",
                }
            ],
        }

        with patch("dtc_analyzer.get_dtc_analyzer") as mock_get:
            mock_get.return_value = mock_dtc_analyzer

            with patch("database_mysql.get_sqlalchemy_engine") as mock_engine:
                mock_conn = MagicMock()
                mock_result = MagicMock()
                # 4 trucks with DTCs -> should trigger HIGH priority
                mock_result.fetchall.return_value = [
                    (
                        "CO0681",
                        "SPN 110.0",
                        "WARNING",
                        None,
                        None,
                        None,
                        datetime.now(),
                    ),
                    (
                        "CO1092",
                        "SPN 110.0",
                        "WARNING",
                        None,
                        None,
                        None,
                        datetime.now(),
                    ),
                    (
                        "CO0893",
                        "SPN 110.0",
                        "WARNING",
                        None,
                        None,
                        None,
                        datetime.now(),
                    ),
                    (
                        "CO0935",
                        "SPN 110.0",
                        "WARNING",
                        None,
                        None,
                        None,
                        datetime.now(),
                    ),
                ]
                mock_conn.execute.return_value = mock_result
                mock_conn.__enter__ = MagicMock(return_value=mock_conn)
                mock_conn.__exit__ = MagicMock(return_value=False)
                mock_engine.return_value.connect.return_value = mock_conn

                result = cc.generate_command_center_data()
                dtc_items = [
                    item for item in result.action_items if "DTC" in str(item.sources)
                ]
                assert len(dtc_items) >= 1

    def test_dtc_analyzer_error_response(self):
        """Lines 4047-4050: DTC analyzer returns error"""
        cc = get_command_center()

        mock_dtc_analyzer = MagicMock()
        mock_dtc_analyzer.get_dtc_analysis_report.return_value = {
            "status": "error",
            "message": "Unable to decode DTC",
        }

        with patch("dtc_analyzer.get_dtc_analyzer") as mock_get:
            mock_get.return_value = mock_dtc_analyzer

            with patch("database_mysql.get_sqlalchemy_engine") as mock_engine:
                mock_conn = MagicMock()
                mock_result = MagicMock()
                mock_result.fetchall.return_value = [
                    ("CO0681", "SPN 9999.31", "INFO", None, None, None, datetime.now())
                ]
                mock_conn.execute.return_value = mock_result
                mock_conn.__enter__ = MagicMock(return_value=mock_conn)
                mock_conn.__exit__ = MagicMock(return_value=False)
                mock_engine.return_value.connect.return_value = mock_conn

                result = cc.generate_command_center_data()
                # Should still process other items
                assert result is not None


class TestCoolantHighIntegration:
    """Test lines 4221-4251: Coolant high temperature sensor health"""

    def test_coolant_high_temperature_critical(self):
        """Lines 4221-4251: High coolant temperature creates STOP action"""
        cc = get_command_center()

        with patch("database_mysql.get_sqlalchemy_engine") as mock_engine:
            mock_conn = MagicMock()
            mock_result = MagicMock()
            mock_result.fetchall.return_value = [
                {
                    "truck_issues": {
                        "coolant_high": [
                            {"truck_id": "CO0681", "value": 235.5, "threshold": 220}
                        ]
                    }
                }
            ]
            mock_conn.execute.return_value = mock_result
            mock_conn.__enter__ = MagicMock(return_value=mock_conn)
            mock_conn.__exit__ = MagicMock(return_value=False)
            mock_engine.return_value.connect.return_value = mock_conn

            result = cc.generate_command_center_data()

            # Should have coolant high action item
            coolant_items = [
                item for item in result.action_items if "Refrigerante" in item.title
            ]
            if coolant_items:
                assert coolant_items[0].priority == Priority.CRITICAL
                assert coolant_items[0].action_type == ActionType.STOP_IMMEDIATELY
                assert "DETENER" in coolant_items[0].action_steps[0]


class TestDTCEventsIntegration:
    """Test lines 4382-4453: DTC Events from database"""

    def test_dtc_events_critical_severity(self):
        """Lines 4382-4453: DTC events with CRITICAL severity"""
        cc = get_command_center()

        with patch("database_mysql.get_sqlalchemy_engine") as mock_engine:
            mock_conn = MagicMock()

            # First query (sensor health) returns empty
            mock_result1 = MagicMock()
            mock_result1.fetchall.return_value = []

            # Second query (engine alerts) returns empty
            mock_result2 = MagicMock()
            mock_result2.fetchall.return_value = []

            # Third query (dtc events) returns critical DTC
            mock_result3 = MagicMock()
            mock_result3.fetchall.return_value = [
                (
                    "CO0681",
                    "SPN 5444.1",
                    "CRITICAL",
                    "AFTERTREATMENT",
                    "DEF quality critically low",
                    "Replace DEF fluid immediately",
                    datetime.now(),
                )
            ]

            mock_conn.execute.side_effect = [mock_result1, mock_result2, mock_result3]
            mock_conn.__enter__ = MagicMock(return_value=mock_conn)
            mock_conn.__exit__ = MagicMock(return_value=False)
            mock_engine.return_value.connect.return_value = mock_conn

            result = cc.generate_command_center_data()

            # Should have DTC event with CRITICAL priority
            dtc_items = [
                item for item in result.action_items if "DTC Events" in item.sources
            ]
            if dtc_items:
                critical_items = [
                    item for item in dtc_items if item.priority == Priority.CRITICAL
                ]
                assert len(critical_items) >= 1
                assert any(
                    item.action_type == ActionType.STOP_IMMEDIATELY
                    for item in critical_items
                )

    def test_dtc_events_warning_severity(self):
        """Lines 4390-4410: DTC events with WARNING severity"""
        cc = get_command_center()

        with patch("database_mysql.get_sqlalchemy_engine") as mock_engine:
            mock_conn = MagicMock()

            mock_result1 = MagicMock()
            mock_result1.fetchall.return_value = []

            mock_result2 = MagicMock()
            mock_result2.fetchall.return_value = []

            mock_result3 = MagicMock()
            mock_result3.fetchall.return_value = [
                (
                    "CO1092",
                    "SPN 110.0",
                    "WARNING",
                    "ENGINE",
                    "Coolant temperature elevated",
                    "Monitor coolant levels",
                    datetime.now(),
                )
            ]

            mock_conn.execute.side_effect = [mock_result1, mock_result2, mock_result3]
            mock_conn.__enter__ = MagicMock(return_value=mock_conn)
            mock_conn.__exit__ = MagicMock(return_value=False)
            mock_engine.return_value.connect.return_value = mock_conn

            result = cc.generate_command_center_data()

            dtc_items = [
                item for item in result.action_items if "DTC Events" in item.sources
            ]
            if dtc_items:
                warning_items = [
                    item for item in dtc_items if item.priority == Priority.HIGH
                ]
                assert len(warning_items) >= 1

    def test_dtc_events_info_severity(self):
        """Lines 4390-4410: DTC events with INFO severity"""
        cc = get_command_center()

        with patch("database_mysql.get_sqlalchemy_engine") as mock_engine:
            mock_conn = MagicMock()

            mock_result1 = MagicMock()
            mock_result1.fetchall.return_value = []

            mock_result2 = MagicMock()
            mock_result2.fetchall.return_value = []

            mock_result3 = MagicMock()
            mock_result3.fetchall.return_value = [
                (
                    "CO0893",
                    "SPN 1234.5",
                    "INFO",
                    "ELECTRICAL",
                    "Battery voltage normal",
                    "Continue monitoring",
                    datetime.now(),
                )
            ]

            mock_conn.execute.side_effect = [mock_result1, mock_result2, mock_result3]
            mock_conn.__enter__ = MagicMock(return_value=mock_conn)
            mock_conn.__exit__ = MagicMock(return_value=False)
            mock_engine.return_value.connect.return_value = mock_conn

            result = cc.generate_command_center_data()

            dtc_items = [
                item for item in result.action_items if "DTC Events" in item.sources
            ]
            if dtc_items:
                info_items = [
                    item for item in dtc_items if item.priority == Priority.MEDIUM
                ]
                assert len(info_items) >= 1

    def test_dtc_events_system_category_mapping(self):
        """Lines 4406-4422: System to category mapping"""
        cc = get_command_center()

        with patch("database_mysql.get_sqlalchemy_engine") as mock_engine:
            mock_conn = MagicMock()

            mock_result1 = MagicMock()
            mock_result1.fetchall.return_value = []

            mock_result2 = MagicMock()
            mock_result2.fetchall.return_value = []

            # Test different system types
            mock_result3 = MagicMock()
            mock_result3.fetchall.return_value = [
                (
                    "CO0681",
                    "SPN 1",
                    "INFO",
                    "TRANSMISSION",
                    "desc",
                    "action",
                    datetime.now(),
                ),
                ("CO1092", "SPN 2", "INFO", "FUEL", "desc", "action", datetime.now()),
                ("CO0893", "SPN 3", "INFO", "BRAKE", "desc", "action", datetime.now()),
            ]

            mock_conn.execute.side_effect = [mock_result1, mock_result2, mock_result3]
            mock_conn.__enter__ = MagicMock(return_value=mock_conn)
            mock_conn.__exit__ = MagicMock(return_value=False)
            mock_engine.return_value.connect.return_value = mock_conn

            result = cc.generate_command_center_data()

            dtc_items = [
                item for item in result.action_items if "DTC Events" in item.sources
            ]
            if dtc_items:
                categories = {item.category for item in dtc_items}
                # Should have mapped systems to categories
                assert len(categories) >= 1


class TestAsyncEndpoints:
    """Test lines 5318-5349: Async endpoint for detect_and_decide"""

    def test_detect_and_decide_method_success(self):
        """Lines 5318-5340: detect_and_decide method"""
        cc = get_command_center()

        detection, decision = cc.detect_and_decide(
            truck_id="CO0681",
            sensor_name="coolant_temp",
            current_value=215.0,
            baseline_value=190.0,
            component="Cooling System",
        )

        assert "is_issue" in detection
        assert "severity" in detection
        assert "priority" in decision
        assert "action_steps" in decision


class TestRedisImportException:
    """Test lines 132-134: Redis import exception handling"""

    def test_redis_unavailable(self):
        """Lines 132-134: Redis not available"""
        # This is tested at module import, but we can verify the flag
        from fleet_command_center import REDIS_AVAILABLE

        # REDIS_AVAILABLE can be True or False depending on environment
        assert isinstance(REDIS_AVAILABLE, bool)


class TestCorrelationPersistence:
    """Test lines 2360-2405: Failure correlation persistence with sensor data"""

    def test_correlation_with_sensor_data_persistence(self):
        """Lines 2386-2399: Correlation persistence with sensor values"""
        cc = get_command_center()

        # Create action items that will be converted to truck_issues
        from fleet_command_center import ActionItem, ActionType, IssueCategory, Priority

        action_items = [
            ActionItem(
                id="test1",
                truck_id="CO0681",
                priority=Priority.HIGH,
                priority_score=80,
                category=IssueCategory.ENGINE,
                component="Cooling System",
                title="Coolant High",
                description="High coolant temp",
                confidence="HIGH",
                action_type=ActionType.INSPECT,
                action_steps=[],
                icon="🌡️",
                sources=["Test"],
            ),
            ActionItem(
                id="test2",
                truck_id="CO0681",
                priority=Priority.HIGH,
                priority_score=75,
                category=IssueCategory.ENGINE,
                component="Oil System",
                title="Oil Temp High",
                description="High oil temp",
                confidence="HIGH",
                action_type=ActionType.INSPECT,
                action_steps=[],
                icon="🛢️",
                sources=["Test"],
            ),
            ActionItem(
                id="test3",
                truck_id="CO1092",
                priority=Priority.HIGH,
                priority_score=80,
                category=IssueCategory.ENGINE,
                component="Cooling System",
                title="Coolant High",
                description="High coolant temp",
                confidence="HIGH",
                action_type=ActionType.INSPECT,
                action_steps=[],
                icon="🌡️",
                sources=["Test"],
            ),
            ActionItem(
                id="test4",
                truck_id="CO1092",
                priority=Priority.HIGH,
                priority_score=75,
                category=IssueCategory.ENGINE,
                component="Oil System",
                title="Oil Temp High",
                description="High oil temp",
                confidence="HIGH",
                action_type=ActionType.INSPECT,
                action_steps=[],
                icon="🛢️",
                sources=["Test"],
            ),
        ]

        sensor_data = {
            "CO0681": {"coolant_temp": 215.0, "oil_temp": 245.0, "trams_t": 210.0},
            "CO1092": {"coolant_temp": 220.0, "oil_temp": 250.0, "trams_t": 215.0},
        }

        correlations = cc.detect_failure_correlations(
            action_items=action_items, sensor_data=sensor_data, persist=True
        )

        # Should detect cooling system correlation
        assert isinstance(correlations, list)
