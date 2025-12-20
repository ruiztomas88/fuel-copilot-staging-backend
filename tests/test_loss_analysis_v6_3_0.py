"""
Tests for Enhanced Loss Analysis v6.3.0
Tests the 5-category fuel loss analysis system
"""

from unittest.mock import MagicMock, patch

import pytest

from database_mysql import _empty_loss_response, get_loss_analysis


class TestLossAnalysisV6_3_0:
    """Test suite for enhanced loss analysis with 5 categories"""

    def test_empty_loss_response_structure(self):
        """Test empty response has all 5 categories"""
        result = _empty_loss_response(days=1, price=3.5)

        assert result["period_days"] == 1
        assert result["fuel_price_per_gal"] == 3.5
        assert result["truck_count"] == 0
        assert result["summary"]["total_loss_gal"] == 0
        assert result["summary"]["total_loss_usd"] == 0

        # Verify all 5 categories exist
        by_cause = result["summary"]["by_cause"]
        assert "idle" in by_cause
        assert "high_rpm" in by_cause
        assert "speeding" in by_cause
        assert "altitude" in by_cause
        assert "mechanical" in by_cause

        # Each category should have gallons, usd, percentage
        for category in by_cause.values():
            assert "gallons" in category
            assert "usd" in category
            assert "percentage" in category
            assert category["gallons"] == 0
            assert category["usd"] == 0
            assert category["percentage"] == 0

    @patch("database_mysql.get_sqlalchemy_engine")
    def test_loss_analysis_with_idle_only(self, mock_engine):
        """Test loss analysis when only idle losses exist"""
        # Mock database response
        mock_conn = MagicMock()
        mock_result = MagicMock()

        # Simulated row: truck with only idle consumption
        mock_row = [
            "TEST001",  # truck_id
            10.0,  # idle_consumption_sum
            60,  # idle_records (60 minutes = 1 hour)
            0.0,  # high_rpm_loss_sum
            0,  # high_rpm_records
            0.0,  # speeding_loss_sum
            0,  # speeding_records
            0.0,  # altitude_loss_sum
            0,  # altitude_records
            5.7,  # mpg_sum
            1,  # mpg_count
            10.0,  # moving_consumption_sum
            60,  # moving_records
            500.0,  # avg_altitude
            55.0,  # avg_speed
            1200.0,  # avg_rpm
        ]

        mock_result.fetchall.return_value = [mock_row]
        mock_conn.execute.return_value = mock_result
        mock_engine.return_value.connect.return_value.__enter__.return_value = mock_conn

        result = get_loss_analysis(days_back=1)

        # Verify structure
        assert "summary" in result
        assert "trucks" in result
        assert result["truck_count"] == 1

        # Verify 5 categories exist
        by_cause = result["summary"]["by_cause"]
        assert "idle" in by_cause
        assert "high_rpm" in by_cause
        assert "speeding" in by_cause
        assert "altitude" in by_cause
        assert "mechanical" in by_cause

        # Idle should have value, others should be 0
        assert by_cause["idle"]["gallons"] > 0
        assert by_cause["high_rpm"]["gallons"] == 0
        assert by_cause["speeding"]["gallons"] == 0
        assert by_cause["altitude"]["gallons"] == 0

    @patch("database_mysql.get_sqlalchemy_engine")
    def test_loss_analysis_with_speeding(self, mock_engine):
        """Test loss analysis detects speeding losses"""
        mock_conn = MagicMock()
        mock_result = MagicMock()

        # Row with speeding losses
        mock_row = [
            "TEST002",  # truck_id
            2.0,  # idle_consumption_sum
            30,  # idle_records
            0.0,  # high_rpm_loss_sum
            0,  # high_rpm_records
            5.0,  # speeding_loss_sum (speed > 70)
            120,  # speeding_records (2 hours speeding)
            0.0,  # altitude_loss_sum
            0,  # altitude_records
            5.7,  # mpg_sum
            1,  # mpg_count
            20.0,  # moving_consumption_sum
            240,  # moving_records
            200.0,  # avg_altitude
            75.0,  # avg_speed (over 70!)
            1500.0,  # avg_rpm
        ]

        mock_result.fetchall.return_value = [mock_row]
        mock_conn.execute.return_value = mock_result
        mock_engine.return_value.connect.return_value.__enter__.return_value = mock_conn

        result = get_loss_analysis(days_back=1)

        by_cause = result["summary"]["by_cause"]

        # Speeding should have value
        assert by_cause["speeding"]["gallons"] > 0
        assert by_cause["speeding"]["usd"] > 0

        # Truck details should show speeding as probable cause
        truck = result["trucks"][0]
        assert truck["truck_id"] == "TEST002"
        assert truck["speeding_loss_gal"] > 0

    @patch("database_mysql.get_sqlalchemy_engine")
    def test_loss_analysis_percentages_sum_to_100(self, mock_engine):
        """Test that loss percentages sum to approximately 100%"""
        mock_conn = MagicMock()
        mock_result = MagicMock()

        # Row with multiple loss types
        mock_row = [
            "TEST003",
            5.0,  # idle
            60,
            2.0,  # high_rpm
            30,
            3.0,  # speeding
            45,
            1.0,  # altitude
            15,
            5.7,
            1,
            15.0,
            180,
            3500.0,  # high altitude
            72.0,  # speeding
            1900.0,  # high rpm
        ]

        mock_result.fetchall.return_value = [mock_row]
        mock_conn.execute.return_value = mock_result
        mock_engine.return_value.connect.return_value.__enter__.return_value = mock_conn

        result = get_loss_analysis(days_back=1)

        by_cause = result["summary"]["by_cause"]

        # Sum percentages (allowing for mechanical/other)
        total_percentage = (
            by_cause["idle"]["percentage"]
            + by_cause["high_rpm"]["percentage"]
            + by_cause["speeding"]["percentage"]
            + by_cause["altitude"]["percentage"]
            + by_cause["mechanical"]["percentage"]
        )

        # Should be approximately 100%
        assert 99.0 <= total_percentage <= 101.0

    @patch("database_mysql.get_sqlalchemy_engine")
    def test_loss_analysis_probable_cause_detection(self, mock_engine):
        """Test that probable cause is correctly identified"""
        mock_conn = MagicMock()
        mock_result = MagicMock()

        # Row where speeding is the max loss
        mock_row = [
            "TEST004",
            1.0,  # idle (small)
            15,
            0.5,  # high_rpm (small)
            10,
            10.0,  # speeding (LARGE - should be probable cause)
            180,
            0.2,  # altitude (tiny)
            5,
            5.7,
            1,
            20.0,
            240,
            100.0,
            75.0,  # high speed
            1200.0,
        ]

        mock_result.fetchall.return_value = [mock_row]
        mock_conn.execute.return_value = mock_result
        mock_engine.return_value.connect.return_value.__enter__.return_value = mock_conn

        result = get_loss_analysis(days_back=1)

        truck = result["trucks"][0]

        # Probable cause should be "EXCESO DE VELOCIDAD" since speeding is max
        assert "VELOCIDAD" in truck["probable_cause"]

    @patch("database_mysql.get_sqlalchemy_engine")
    def test_loss_analysis_usd_calculation(self, mock_engine):
        """Test USD conversion from gallons"""
        mock_conn = MagicMock()
        mock_result = MagicMock()

        mock_row = [
            "TEST005",
            10.0,  # 10 gallons idle
            120,
            0.0,
            0,
            0.0,
            0,
            0.0,
            0,
            5.7,
            1,
            10.0,
            120,
            100.0,
            50.0,
            1000.0,
        ]

        mock_result.fetchall.return_value = [mock_row]
        mock_conn.execute.return_value = mock_result
        mock_engine.return_value.connect.return_value.__enter__.return_value = mock_conn

        result = get_loss_analysis(days_back=1)

        truck = result["trucks"][0]

        # At $3.50/gal, 10 gallons should be $35
        # (actual may vary due to record_interval calculation)
        assert truck["idle_loss_usd"] > 0
        assert truck["total_loss_usd"] > 0

        # Verify total_loss_usd matches sum of individual USD losses
        expected_total = (
            truck["idle_loss_usd"]
            + truck["high_rpm_loss_usd"]
            + truck["speeding_loss_usd"]
            + truck["altitude_loss_usd"]
            + truck["mechanical_loss_usd"]
        )
        assert abs(truck["total_loss_usd"] - expected_total) < 0.01

    @patch("database_mysql.get_sqlalchemy_engine")
    def test_loss_analysis_handles_no_data(self, mock_engine):
        """Test graceful handling when no data exists"""
        mock_conn = MagicMock()
        mock_result = MagicMock()

        mock_result.fetchall.return_value = []
        mock_conn.execute.return_value = mock_result
        mock_engine.return_value.connect.return_value.__enter__.return_value = mock_conn

        result = get_loss_analysis(days_back=7)

        # Should return empty response
        assert result["truck_count"] == 0
        assert result["summary"]["total_loss_gal"] == 0
        assert len(result["trucks"]) == 0

    def test_loss_analysis_days_parameter(self):
        """Test that days_back parameter is respected"""
        # This would require a real DB connection, so we'll just verify the parameter exists
        import inspect

        sig = inspect.signature(get_loss_analysis)
        assert "days_back" in sig.parameters
        assert sig.parameters["days_back"].default == 1


class TestLossAnalysisCoverage:
    """Additional coverage tests for edge cases"""

    @patch("database_mysql.get_sqlalchemy_engine")
    def test_high_rpm_detection(self, mock_engine):
        """Test high RPM loss detection (RPM > 1800)"""
        mock_conn = MagicMock()
        mock_result = MagicMock()

        # Row with high RPM
        mock_row = [
            "TEST_RPM",
            1.0,
            15,  # idle
            8.0,
            120,  # high_rpm (significant)
            0.0,
            0,  # speeding
            0.0,
            0,  # altitude
            5.7,
            1,
            15.0,
            180,
            100.0,
            55.0,
            1900.0,  # RPM = 1900 (>1800)
        ]

        mock_result.fetchall.return_value = [mock_row]
        mock_conn.execute.return_value = mock_result
        mock_engine.return_value.connect.return_value.__enter__.return_value = mock_conn

        result = get_loss_analysis(days_back=1)

        truck = result["trucks"][0]
        assert truck["high_rpm_loss_gal"] > 0
        assert truck["avg_rpm"] == 1900.0

    @patch("database_mysql.get_sqlalchemy_engine")
    def test_altitude_loss_detection(self, mock_engine):
        """Test altitude loss detection (altitude > 3000)"""
        mock_conn = MagicMock()
        mock_result = MagicMock()

        # Row with high altitude
        mock_row = [
            "TEST_ALT",
            1.0,
            15,  # idle
            0.0,
            0,  # high_rpm
            0.0,
            0,  # speeding
            5.0,
            90,  # altitude (significant)
            5.7,
            1,
            10.0,
            120,
            5500.0,  # avg_altitude > 3000
            45.0,
            1100.0,
        ]

        mock_result.fetchall.return_value = [mock_row]
        mock_conn.execute.return_value = mock_result
        mock_engine.return_value.connect.return_value.__enter__.return_value = mock_conn

        result = get_loss_analysis(days_back=1)

        truck = result["trucks"][0]
        assert truck["altitude_loss_gal"] > 0
        assert truck["avg_altitude_ft"] == 5500.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
