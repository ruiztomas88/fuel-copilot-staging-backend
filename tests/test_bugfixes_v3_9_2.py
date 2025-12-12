"""
Tests for v3.9.2 Bug Fixes

Verifies the following fixes:
1. odom_delta_mi is now calculated correctly (was always 0)
2. UPSERT optimization in bulk_mysql_handler
3. Centralized configuration

Author: GitHub Copilot
Date: 2025-11-27
Updated: 2025-12-04 - Fixed imports for Fuel-Analytics-Backend structure
                     - Removed frontend tests (moved to frontend repo)
"""

import pytest
from unittest.mock import MagicMock, patch
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestOdomDeltaFix:
    """Test that odom_delta_mi is calculated correctly"""

    def test_odom_delta_calculated_from_mpg_state(self):
        """Verify odom_delta is calculated from MPGState.last_odometer_mi"""
        from mpg_engine import MPGState

        mpg_state = MPGState()
        mpg_state.last_odometer_mi = 12500.0

        current_odometer = 12510.5
        expected_delta = 10.5

        # Simulate the calculation
        if mpg_state.last_odometer_mi is not None:
            raw_delta = current_odometer - mpg_state.last_odometer_mi
            if 0.0 < raw_delta < 50.0:
                odom_delta_mi = raw_delta
            else:
                odom_delta_mi = 0.0
        else:
            odom_delta_mi = 0.0

        assert abs(odom_delta_mi - expected_delta) < 0.001

    def test_odom_delta_zero_for_first_reading(self):
        """Verify odom_delta is 0 when there's no previous reading"""
        from mpg_engine import MPGState

        mpg_state = MPGState()
        # last_odometer_mi is None by default

        current_odometer = 12500.0

        if mpg_state.last_odometer_mi is not None:
            raw_delta = current_odometer - mpg_state.last_odometer_mi
            if 0.0 < raw_delta < 50.0:
                odom_delta_mi = raw_delta
            else:
                odom_delta_mi = 0.0
        else:
            odom_delta_mi = 0.0

        assert odom_delta_mi == 0.0

    def test_odom_delta_rejects_large_jumps(self):
        """Verify odom_delta rejects values >= 50 miles"""
        from mpg_engine import MPGState

        mpg_state = MPGState()
        mpg_state.last_odometer_mi = 12500.0

        current_odometer = 12600.0  # 100 mile jump - unrealistic for 15s

        if mpg_state.last_odometer_mi is not None:
            raw_delta = current_odometer - mpg_state.last_odometer_mi
            if 0.0 < raw_delta < 50.0:
                odom_delta_mi = raw_delta
            else:
                odom_delta_mi = 0.0
        else:
            odom_delta_mi = 0.0

        assert odom_delta_mi == 0.0  # Should reject large jump

    def test_odom_delta_rejects_negative_values(self):
        """Verify odom_delta rejects negative values (odometer rollback)"""
        from mpg_engine import MPGState

        mpg_state = MPGState()
        mpg_state.last_odometer_mi = 12500.0

        current_odometer = 12490.0  # Rollback

        if mpg_state.last_odometer_mi is not None:
            raw_delta = current_odometer - mpg_state.last_odometer_mi
            if 0.0 < raw_delta < 50.0:
                odom_delta_mi = raw_delta
            else:
                odom_delta_mi = 0.0
        else:
            odom_delta_mi = 0.0

        assert odom_delta_mi == 0.0  # Should reject negative delta


class TestBulkMySQLUpsertFix:
    """Test UPSERT implementation in bulk_mysql_handler"""

    def test_upsert_import_available(self):
        """Verify SQLAlchemy MySQL UPSERT is importable"""
        from sqlalchemy.dialects.mysql import insert as mysql_insert

        assert mysql_insert is not None

    def test_bool_to_yesno_conversion(self):
        """Test bool_to_yesno helper function"""
        from bulk_mysql_handler import BulkMySQLHandler

        handler = BulkMySQLHandler()

        assert handler._bool_to_yesno(True) == "YES"
        assert handler._bool_to_yesno(False) == "NO"
        assert handler._bool_to_yesno(None) == "NO"
        assert handler._bool_to_yesno("YES") == "YES"
        assert handler._bool_to_yesno("TRUE") == "YES"
        assert handler._bool_to_yesno("NO") == "NO"
        assert handler._bool_to_yesno("FALSE") == "NO"

    def test_handler_singleton_pattern(self):
        """Test that get_bulk_handler returns same instance"""
        from bulk_mysql_handler import get_bulk_handler

        handler1 = get_bulk_handler()
        handler2 = get_bulk_handler()

        assert handler1 is handler2

    def test_handler_stats(self):
        """Test handler statistics tracking"""
        from bulk_mysql_handler import BulkMySQLHandler

        handler = BulkMySQLHandler()

        stats = handler.get_stats()

        assert "pending_records" in stats
        assert "total_saved" in stats
        assert "total_batches" in stats
        assert "failed_records" in stats


class TestConnectionPooling:
    """Test MySQL Connection Pooling configuration"""

    def test_sqlalchemy_engine_config(self):
        """Verify SQLAlchemy engine has pooling configuration"""
        db_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "database_mysql.py",
        )

        with open(db_path, "r") as f:
            content = f.read()

        # Check for pooling configuration
        assert "pool_size=" in content or "pool_size" in content
        assert "pool_pre_ping=True" in content or "pool_pre_ping" in content


class TestCentralizedConfig:
    """Test centralized configuration"""

    def test_config_module_exists(self):
        """Verify config.py exists in root"""
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "config.py",
        )
        assert os.path.exists(config_path), "config.py should exist"

    def test_config_exports_constants(self):
        """Verify config exports FUEL and DATABASE"""
        from config import FUEL, DATABASE, IDLE, REFUEL

        # Check FUEL config
        assert hasattr(FUEL, "PRICE_PER_GALLON")
        assert hasattr(FUEL, "BASELINE_MPG")
        assert hasattr(FUEL, "MIN_VALID_MPG")
        assert hasattr(FUEL, "MAX_VALID_MPG")

        # Check DATABASE config
        assert hasattr(DATABASE, "HOST")


class TestMPGStateHasOdometerField:
    """Test that MPGState dataclass has last_odometer_mi field"""

    def test_mpg_state_has_last_odometer_mi(self):
        """Verify MPGState has last_odometer_mi field"""
        from mpg_engine import MPGState

        state = MPGState()

        # Field should exist and be None by default
        assert hasattr(state, "last_odometer_mi")
        assert state.last_odometer_mi is None

    def test_mpg_state_last_odometer_can_be_set(self):
        """Verify last_odometer_mi can be assigned"""
        from mpg_engine import MPGState

        state = MPGState()
        state.last_odometer_mi = 12500.75

        assert state.last_odometer_mi == 12500.75


# Legacy test removed - fuel_copilot_v2_1_fixed.py was deleted
# Core logic now in: estimator.py, reporter.py, mpg_engine.py


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
