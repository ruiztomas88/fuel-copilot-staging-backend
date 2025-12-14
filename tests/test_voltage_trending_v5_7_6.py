"""
Tests for Voltage Trending Service v5.7.6
═══════════════════════════════════════════════════════════════════════════════

Test coverage for voltage history and trend analysis.
"""

import pytest
from datetime import datetime, timedelta

from voltage_trending import (
    VoltageDataPoint,
    VoltageStats,
    VoltageTrend,
    VoltageHistoryResponse,
    VoltageTrendingService,
    VOLTAGE_THRESHOLDS,
    analyze_voltage_list,
    get_voltage_status_simple,
)


# ═══════════════════════════════════════════════════════════════════════════════
# DATACLASS TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestVoltageDataPoint:
    """Test VoltageDataPoint dataclass"""

    def test_basic_creation(self):
        """Should create data point with basic values"""
        dp = VoltageDataPoint(timestamp=datetime.utcnow(), voltage=13.5)
        assert dp.voltage == 13.5
        assert dp.engine_running == False

    def test_with_rpm(self):
        """Should detect engine running from RPM"""
        dp = VoltageDataPoint(
            timestamp=datetime.utcnow(), voltage=14.2, rpm=650, engine_running=True
        )
        assert dp.engine_running == True
        assert dp.rpm == 650

    def test_to_dict(self):
        """Should serialize to dict"""
        dp = VoltageDataPoint(
            timestamp=datetime(2024, 1, 15, 10, 30, 0),
            voltage=13.8,
            rpm=1200,
            engine_running=True,
        )
        d = dp.to_dict()
        assert "timestamp" in d
        assert d["voltage"] == 13.8
        assert d["rpm"] == 1200


class TestVoltageStats:
    """Test VoltageStats dataclass"""

    def test_default_values(self):
        """Should have sensible defaults"""
        stats = VoltageStats(truck_id="TEST001", period_hours=24, sample_count=0)
        assert stats.avg_voltage == 0.0
        assert stats.sample_count == 0

    def test_to_dict(self):
        """Should serialize correctly"""
        stats = VoltageStats(
            truck_id="TEST001",
            period_hours=24,
            sample_count=100,
            avg_voltage=13.65,
            min_voltage=12.8,
            max_voltage=14.5,
        )
        d = stats.to_dict()
        assert d["truck_id"] == "TEST001"
        assert d["avg_voltage"] == 13.65


class TestVoltageTrend:
    """Test VoltageTrend dataclass"""

    def test_default_values(self):
        """Should have sensible defaults"""
        trend = VoltageTrend(truck_id="TEST001", period_hours=24)
        assert trend.direction == "stable"
        assert trend.status == "NORMAL"

    def test_to_dict(self):
        """Should serialize correctly"""
        trend = VoltageTrend(
            truck_id="TEST001",
            period_hours=24,
            direction="decreasing",
            status="LOW",
            message="Voltaje bajando",
        )
        d = trend.to_dict()
        assert d["direction"] == "decreasing"
        assert d["status"] == "LOW"


# ═══════════════════════════════════════════════════════════════════════════════
# THRESHOLD TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestVoltageThresholds:
    """Test voltage threshold values"""

    def test_thresholds_defined(self):
        """Should have all required thresholds"""
        required = [
            "critical_low",
            "low",
            "normal_min",
            "normal_max",
            "high",
            "critical_high",
        ]
        for key in required:
            assert key in VOLTAGE_THRESHOLDS

    def test_thresholds_order(self):
        """Thresholds should be in logical order"""
        assert VOLTAGE_THRESHOLDS["critical_low"] < VOLTAGE_THRESHOLDS["low"]
        assert VOLTAGE_THRESHOLDS["low"] <= VOLTAGE_THRESHOLDS["normal_min"]
        assert VOLTAGE_THRESHOLDS["normal_max"] < VOLTAGE_THRESHOLDS["high"]
        assert VOLTAGE_THRESHOLDS["high"] < VOLTAGE_THRESHOLDS["critical_high"]


# ═══════════════════════════════════════════════════════════════════════════════
# SERVICE TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestVoltageTrendingService:
    """Test VoltageTrendingService class"""

    def test_service_init(self):
        """Should initialize without database"""
        service = VoltageTrendingService()
        assert service.db_pool is None

    def test_calculate_stats_basic(self):
        """Should calculate correct statistics"""
        service = VoltageTrendingService()

        now = datetime.utcnow()
        points = [
            VoltageDataPoint(timestamp=now - timedelta(hours=2), voltage=13.0),
            VoltageDataPoint(timestamp=now - timedelta(hours=1), voltage=13.5),
            VoltageDataPoint(timestamp=now, voltage=14.0),
        ]

        stats = service._calculate_stats("TEST001", points, 24)

        assert stats.sample_count == 3
        assert 13.0 <= stats.avg_voltage <= 14.0
        assert stats.min_voltage == 13.0
        assert stats.max_voltage == 14.0

    def test_calculate_stats_with_engine_states(self):
        """Should separate running vs stopped stats"""
        service = VoltageTrendingService()

        now = datetime.utcnow()
        points = [
            VoltageDataPoint(
                timestamp=now - timedelta(hours=2), voltage=12.5, engine_running=False
            ),
            VoltageDataPoint(
                timestamp=now - timedelta(hours=1), voltage=14.2, engine_running=True
            ),
            VoltageDataPoint(timestamp=now, voltage=14.0, engine_running=True),
        ]

        stats = service._calculate_stats("TEST001", points, 24)

        assert stats.samples_running == 2
        assert stats.samples_stopped == 1
        assert stats.avg_running > stats.avg_stopped

    def test_calculate_trend_stable(self):
        """Should detect stable voltage trend"""
        service = VoltageTrendingService()

        now = datetime.utcnow()
        # Generate stable voltage around 13.5V
        points = [
            VoltageDataPoint(
                timestamp=now - timedelta(hours=24 - i),
                voltage=13.5 + (i % 3) * 0.1 - 0.1,
            )
            for i in range(24)
        ]

        trend = service._calculate_trend("TEST001", points, 24)

        assert trend.direction == "stable"
        assert abs(trend.change_per_hour) < 0.05

    def test_calculate_trend_decreasing(self):
        """Should detect decreasing voltage trend"""
        service = VoltageTrendingService()

        now = datetime.utcnow()
        # Generate decreasing voltage from 14V to 12V over 24 hours
        points = [
            VoltageDataPoint(
                timestamp=now - timedelta(hours=24 - i), voltage=14.0 - (i / 24) * 2.0
            )
            for i in range(24)
        ]

        trend = service._calculate_trend("TEST001", points, 24)

        assert trend.direction == "decreasing"
        assert trend.change_per_hour < 0

    def test_calculate_trend_increasing(self):
        """Should detect increasing voltage trend"""
        service = VoltageTrendingService()

        now = datetime.utcnow()
        # Generate increasing voltage from 12V to 14V
        points = [
            VoltageDataPoint(
                timestamp=now - timedelta(hours=24 - i), voltage=12.0 + (i / 24) * 2.0
            )
            for i in range(24)
        ]

        trend = service._calculate_trend("TEST001", points, 24)

        assert trend.direction == "increasing"
        assert trend.change_per_hour > 0

    def test_detect_anomalies(self):
        """Should detect voltage anomalies"""
        service = VoltageTrendingService()

        now = datetime.utcnow()
        # Need at least 5 points for trend analysis
        points = [
            VoltageDataPoint(timestamp=now - timedelta(hours=5), voltage=13.5),
            VoltageDataPoint(timestamp=now - timedelta(hours=4), voltage=13.6),
            VoltageDataPoint(
                timestamp=now - timedelta(hours=3), voltage=11.0
            ),  # Critical low
            VoltageDataPoint(
                timestamp=now - timedelta(hours=2), voltage=16.0
            ),  # Critical high
            VoltageDataPoint(timestamp=now - timedelta(hours=1), voltage=13.5),
            VoltageDataPoint(timestamp=now, voltage=13.4),
        ]

        trend = service._calculate_trend("TEST001", points, 24)

        assert trend.anomaly_count >= 2

    def test_get_voltage_status_critical_low(self):
        """Should detect critical low status"""
        service = VoltageTrendingService()
        status, message = service._get_voltage_status(11.0, 13.0, "stable")

        assert status == "CRITICAL_LOW"
        assert "crítico" in message.lower() or "arrancará" in message.lower()

    def test_get_voltage_status_normal(self):
        """Should detect normal status"""
        service = VoltageTrendingService()
        status, message = service._get_voltage_status(13.5, 13.5, "stable")

        assert status == "NORMAL"
        assert "normal" in message.lower()


# ═══════════════════════════════════════════════════════════════════════════════
# STANDALONE FUNCTION TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestAnalyzeVoltageList:
    """Test analyze_voltage_list function"""

    def test_analyze_stable_list(self):
        """Should analyze stable voltage list"""
        voltages = [13.5, 13.6, 13.4, 13.5, 13.5, 13.4, 13.6, 13.5]

        trend = analyze_voltage_list(voltages, hours=24)

        assert trend.direction == "stable"

    def test_analyze_empty_list(self):
        """Should handle empty list"""
        trend = analyze_voltage_list([], hours=24)

        assert trend.status == "INSUFFICIENT_DATA"


class TestGetVoltageStatusSimple:
    """Test get_voltage_status_simple function"""

    def test_critical_low(self):
        """Should detect critical low"""
        result = get_voltage_status_simple(11.0)
        assert result["status"] == "CRITICAL_LOW"

    def test_low(self):
        """Should detect low"""
        result = get_voltage_status_simple(12.0)
        assert result["status"] == "LOW"

    def test_normal(self):
        """Should detect normal"""
        result = get_voltage_status_simple(13.5)
        assert result["status"] == "NORMAL"

    def test_high(self):
        """Should detect high"""
        result = get_voltage_status_simple(15.2)
        assert result["status"] == "HIGH"

    def test_critical_high(self):
        """Should detect critical high"""
        result = get_voltage_status_simple(16.0)
        assert result["status"] == "CRITICAL_HIGH"


# ═══════════════════════════════════════════════════════════════════════════════
# MOCK DATA TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestMockData:
    """Test mock data generation"""

    def test_generate_mock_response(self):
        """Should generate valid mock response"""
        service = VoltageTrendingService()

        response = service._generate_mock_response("TEST001", 24)

        assert response.truck_id == "TEST001"
        assert response.period_hours == 24
        assert len(response.data_points) > 0
        assert response.stats is not None
        assert response.trend is not None

    def test_generate_empty_response(self):
        """Should generate empty response"""
        service = VoltageTrendingService()

        response = service._generate_empty_response("TEST001", 24)

        assert response.truck_id == "TEST001"
        assert len(response.data_points) == 0
        assert response.stats.sample_count == 0
        assert response.trend.status == "NO_DATA"


# ═══════════════════════════════════════════════════════════════════════════════
# RESPONSE STRUCTURE TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestVoltageHistoryResponse:
    """Test VoltageHistoryResponse structure"""

    def test_to_dict_complete(self):
        """Should serialize complete response"""
        now = datetime.utcnow()

        response = VoltageHistoryResponse(
            truck_id="TEST001",
            period_hours=24,
            data_points=[VoltageDataPoint(timestamp=now, voltage=13.5)],
            stats=VoltageStats(truck_id="TEST001", period_hours=24, sample_count=1),
            trend=VoltageTrend(truck_id="TEST001", period_hours=24),
        )

        d = response.to_dict()

        assert "truck_id" in d
        assert "data_points" in d
        assert "stats" in d
        assert "trend" in d
        assert len(d["data_points"]) == 1
