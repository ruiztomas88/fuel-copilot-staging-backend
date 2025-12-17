"""
Unit Tests for BUG-003: Geofence System
═══════════════════════════════════════════════════════════════════════════════

Tests for productive idle detection using geofences.

Run with: pytest tests/test_geofence_system.py -v
"""

import pytest
from unittest.mock import Mock, patch
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from fleet_utilization_engine import FleetUtilizationEngine


class TestGeofenceSystem:
    """Tests for BUG-003: Geofence-based productive idle detection"""

    def test_haversine_distance_calculation(self):
        """Haversine formula should calculate correct distances"""
        analyzer = FleetUtilizationEngine()
        
        # Dallas to Houston (approx 362 km)
        dallas = (32.7767, -96.7970)
        houston = (29.7604, -95.3698)
        
        distance = analyzer._haversine_distance(*dallas, *houston)
        
        # Should be around 362,000 meters (±10km tolerance)
        assert 352000 < distance < 372000

    def test_inside_geofence_circular(self):
        """Point inside circular geofence should return True"""
        # Mock database with Walmart DC geofence
        mock_result = [
            (1, 'Walmart DC', 'customer', True, 36.3729, -94.2088, 500)  # 500m radius
        ]
        
        mock_conn = Mock()
        mock_conn.execute = Mock(return_value=mock_result)
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)
        
        mock_engine = Mock()
        mock_engine.connect = Mock(return_value=mock_conn)
        
        with patch('database_pool.get_local_engine', return_value=mock_engine):
            analyzer = FleetUtilizationEngine()
            
            # Point 200m from center (inside 500m radius)
            # Approximate: 0.0018 degrees ≈ 200m
            test_location = (36.3747, -94.2088)
            
            is_productive = analyzer._is_productive_location(test_location)
            assert is_productive is True

    def test_outside_geofence_circular(self):
        """Point outside all geofences should return False"""
        # Mock database with Walmart DC geofence
        mock_result = [
            (1, 'Walmart DC', 'customer', True, 36.3729, -94.2088, 500)
        ]
        
        mock_conn = Mock()
        mock_conn.execute = Mock(return_value=mock_result)
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)
        
        mock_engine = Mock()
        mock_engine.connect = Mock(return_value=mock_conn)
        
        with patch('database_pool.get_local_engine', return_value=mock_engine):
            analyzer = FleetUtilizationEngine()
            
            # Point 2km away (outside 500m radius)
            test_location = (36.3900, -94.2088)
            
            is_productive = analyzer._is_productive_location(test_location)
            assert is_productive is False

    def test_no_geofences_returns_false(self):
        """Empty geofence database should return False"""
        mock_result = []  # No geofences
        
        mock_conn = Mock()
        mock_conn.execute = Mock(return_value=mock_result)
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)
        
        mock_engine = Mock()
        mock_engine.connect = Mock(return_value=mock_engine)
        
        with patch('database_pool.get_local_engine', return_value=mock_engine):
            analyzer = FleetUtilizationEngine()
            
            is_productive = analyzer._is_productive_location((36.3729, -94.2088))
            assert is_productive is False

    def test_invalid_coordinates(self):
        """Invalid coordinates should return False"""
        analyzer = FleetUtilizationEngine()
        
        # Latitude out of range
        assert analyzer._is_productive_location((91.0, -94.2088)) is False
        assert analyzer._is_productive_location((-91.0, -94.2088)) is False
        
        # Longitude out of range
        assert analyzer._is_productive_location((36.3729, 181.0)) is False
        assert analyzer._is_productive_location((36.3729, -181.0)) is False
        
        # None location
        assert analyzer._is_productive_location(None) is False

    def test_db_failure_graceful_fallback(self):
        """DB failure should fallback to False (conservative)"""
        with patch('database_pool.get_local_engine', return_value=None):
            analyzer = FleetUtilizationEngine()
            
            # Should not crash, return False
            is_productive = analyzer._is_productive_location((36.3729, -94.2088))
            assert is_productive is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
