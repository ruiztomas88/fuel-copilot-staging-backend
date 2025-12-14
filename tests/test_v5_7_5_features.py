"""
Tests for v5.7.5 Features:
- pwr_ext for voltage (not pwr_int)
- dtc_code sensor mapping
- dtc and dtc_code columns in fuel_metrics
- Database enrich with voltage, gps_satellites, gps_quality, voltage_status
- DTC count/codes mapping for frontend

Run with: pytest tests/test_v5_7_5_features.py -v
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone


# =============================================================================
# Test Voltage Monitor uses voltage parameter (renamed from pwr_int)
# =============================================================================

class TestVoltageMonitorParameterRename:
    """Test that voltage_monitor uses generic 'voltage' parameter"""
    
    def test_analyze_voltage_accepts_voltage_param(self):
        """analyze_voltage should accept 'voltage' parameter (not pwr_int)"""
        from voltage_monitor import analyze_voltage
        import inspect
        
        sig = inspect.signature(analyze_voltage)
        params = list(sig.parameters.keys())
        
        # Should have 'voltage' as first param (renamed from pwr_int in v5.7.5)
        assert 'voltage' in params, "analyze_voltage should have 'voltage' parameter"
        assert 'pwr_int' not in params, "pwr_int should be renamed to voltage"
    
    def test_analyze_voltage_with_pwr_ext_value(self):
        """analyze_voltage should work with pwr_ext values (12-14V range)"""
        from voltage_monitor import analyze_voltage
        
        # Test with typical pwr_ext values (truck battery)
        result = analyze_voltage(voltage=13.8, rpm=1200, truck_id="TEST001")
        assert result is not None
        assert result.priority == "OK"  # Normal charging
        
        # Test critical low (dead battery)
        result = analyze_voltage(voltage=10.5, rpm=1200, truck_id="TEST001")
        assert result is not None
        assert result.priority == "CRITICAL"
    
    def test_analyze_voltage_rejects_pwr_int_values(self):
        """Low voltage (like pwr_int ~3.78V) should trigger critical alert"""
        from voltage_monitor import analyze_voltage
        
        # pwr_int is GPS backup battery (~3.78V) - should NOT be used!
        # If someone accidentally passes pwr_int, it should show as critical
        result = analyze_voltage(voltage=3.78, rpm=1200, truck_id="TEST001")
        assert result is not None
        assert result.priority == "CRITICAL"  # Way too low for truck battery


# =============================================================================
# Test WialonReader has dtc_code sensor
# =============================================================================

class TestWialonReaderDTCCode:
    """Test that wialon_reader has dtc_code sensor mapping"""
    
    def test_sensor_params_has_dtc_code(self):
        """WialonConfig.SENSOR_PARAMS should include dtc_code"""
        from wialon_reader import WialonConfig
        
        config = WialonConfig()
        assert "dtc_code" in config.SENSOR_PARAMS, "dtc_code should be in SENSOR_PARAMS"
    
    def test_truck_sensor_data_has_dtc_code_field(self):
        """TruckSensorData should have dtc_code field"""
        from wialon_reader import TruckSensorData
        import dataclasses
        
        fields = {f.name for f in dataclasses.fields(TruckSensorData)}
        assert "dtc_code" in fields, "TruckSensorData should have dtc_code field"
    
    def test_dtc_code_is_optional(self):
        """dtc_code should be Optional[str]"""
        from wialon_reader import TruckSensorData
        
        # Should be able to create with dtc_code=None
        data = TruckSensorData(
            truck_id="TEST001",
            unit_id=12345,
            timestamp=datetime.now(timezone.utc),
            epoch_time=int(datetime.now().timestamp()),
            capacity_gallons=200,
            capacity_liters=757,
            dtc_code=None,
        )
        assert data.dtc_code is None


# =============================================================================
# Test Database Enrichment for Frontend
# =============================================================================

class TestDatabaseEnrichment:
    """Test _enrich_truck_record mappings for frontend compatibility"""
    
    def test_voltage_mapping(self):
        """battery_voltage should be mapped to 'voltage'"""
        from database import DatabaseManager
        import pandas as pd
        
        db = DatabaseManager()
        record = {
            "battery_voltage": 13.8,
            "rpm": 1200,
            "truck_status": "MOVING"
        }
        
        enriched = db._enrich_truck_record(record)
        
        assert "voltage" in enriched
        assert enriched["voltage"] == 13.8
    
    def test_voltage_status_calculation_running(self):
        """voltage_status should be calculated based on RPM"""
        from database import DatabaseManager
        
        db = DatabaseManager()
        
        # Engine running - normal charging
        record = {"battery_voltage": 14.2, "rpm": 1200, "truck_status": "MOVING"}
        enriched = db._enrich_truck_record(record)
        assert enriched.get("voltage_status") == "NORMAL"
        
        # Engine running - low voltage
        record = {"battery_voltage": 12.8, "rpm": 1200, "truck_status": "MOVING"}
        enriched = db._enrich_truck_record(record)
        assert enriched.get("voltage_status") == "LOW"
        
        # Engine running - critical low
        record = {"battery_voltage": 11.5, "rpm": 1200, "truck_status": "MOVING"}
        enriched = db._enrich_truck_record(record)
        assert enriched.get("voltage_status") == "CRITICAL_LOW"
    
    def test_voltage_status_calculation_stopped(self):
        """voltage_status should use different thresholds when engine off"""
        from database import DatabaseManager
        
        db = DatabaseManager()
        
        # Engine off - normal battery
        record = {"battery_voltage": 12.5, "rpm": 0, "truck_status": "STOPPED"}
        enriched = db._enrich_truck_record(record)
        assert enriched.get("voltage_status") == "NORMAL"
        
        # Engine off - low battery
        record = {"battery_voltage": 12.0, "rpm": 0, "truck_status": "STOPPED"}
        enriched = db._enrich_truck_record(record)
        assert enriched.get("voltage_status") == "LOW"
    
    def test_gps_satellites_mapping(self):
        """sats should be mapped to 'gps_satellites'"""
        from database import DatabaseManager
        
        db = DatabaseManager()
        record = {"sats": 12, "truck_status": "MOVING"}
        
        enriched = db._enrich_truck_record(record)
        
        assert "gps_satellites" in enriched
        assert enriched["gps_satellites"] == 12
    
    def test_gps_quality_parsing(self):
        """gps_quality should be parsed from descriptive format"""
        from database import DatabaseManager
        
        db = DatabaseManager()
        
        # Descriptive format from v5.7.3
        record = {"gps_quality": "GOOD|sats=10|acc=3m", "truck_status": "MOVING"}
        enriched = db._enrich_truck_record(record)
        assert enriched.get("gps_quality") == "GOOD"
        
        # Simple format should pass through
        record = {"gps_quality": "EXCELLENT", "truck_status": "MOVING"}
        enriched = db._enrich_truck_record(record)
        assert enriched.get("gps_quality") == "EXCELLENT"
    
    def test_dtc_codes_mapping(self):
        """dtc_code should be mapped to 'dtc_codes'"""
        from database import DatabaseManager
        
        db = DatabaseManager()
        record = {"dtc_code": "100.4,157.3", "truck_status": "MOVING"}
        
        enriched = db._enrich_truck_record(record)
        
        assert "dtc_codes" in enriched
        assert enriched["dtc_codes"] == "100.4,157.3"
        assert enriched.get("dtc_count") == 2
    
    def test_dtc_count_from_flag(self):
        """dtc flag should be converted to dtc_count"""
        from database import DatabaseManager
        
        db = DatabaseManager()
        
        # dtc = 3 means 3 active DTCs
        record = {"dtc": 3, "truck_status": "MOVING"}
        enriched = db._enrich_truck_record(record)
        assert enriched.get("dtc_count") == 3
        
        # dtc = 0 means no DTCs - should be None or not set
        record = {"dtc": 0, "truck_status": "MOVING"}
        enriched = db._enrich_truck_record(record)
        # Either None or 0 is acceptable for no DTCs
        assert enriched.get("dtc_count") is None or enriched.get("dtc_count") == 0


# =============================================================================
# Test Wialon Sync uses pwr_ext for voltage alerts
# =============================================================================

class TestWialonSyncVoltageSource:
    """Test that wialon_sync uses correct voltage source"""
    
    def test_metrics_dict_has_battery_voltage_from_pwr_ext(self):
        """Verify battery_voltage in metrics comes from pwr_ext"""
        # This is a code structure test - verify the assignment exists
        import ast
        
        with open("wialon_sync_enhanced.py", "r") as f:
            source = f.read()
        
        # Check that battery_voltage is assigned from pwr_ext
        assert '"battery_voltage": pwr_ext' in source or "'battery_voltage': pwr_ext" in source, \
            "battery_voltage should be assigned from pwr_ext"
    
    def test_voltage_alert_uses_pwr_ext(self):
        """Verify voltage alerts use pwr_ext not pwr_int"""
        with open("wialon_sync_enhanced.py", "r") as f:
            source = f.read()
        
        # The voltage processing block should check pwr_ext
        assert "truck_data.pwr_ext" in source, \
            "Voltage alerts should use truck_data.pwr_ext"


# =============================================================================
# Test DTC Processing Logic
# =============================================================================

class TestDTCProcessingLogic:
    """Test DTC code vs flag processing"""
    
    def test_dtc_code_preferred_over_flag(self):
        """dtc_code should be preferred over dtc flag"""
        # When dtc_code exists, it should be used instead of dtc flag
        with open("wialon_sync_enhanced.py", "r") as f:
            source = f.read()
        
        # Check that dtc_code is checked first
        assert "truck_data.dtc_code" in source, \
            "Should check dtc_code sensor"
    
    def test_dtc_flag_filter_binary(self):
        """dtc flag values 0/1 should be filtered out as binary flags"""
        with open("wialon_sync_enhanced.py", "r") as f:
            source = f.read()
        
        # Should filter out 0, 1, 0.0, 1.0 as they're just flags
        assert '["0", "1", "0.0", "1.0"]' in source or "['0', '1', '0.0', '1.0']" in source, \
            "Should filter binary dtc flag values"


# =============================================================================
# Test Migration File Exists
# =============================================================================

class TestMigrationFile:
    """Test migration file for DTC columns"""
    
    def test_migration_file_exists(self):
        """Migration file for DTC columns should exist"""
        from pathlib import Path
        
        migration_path = Path("migrations/add_dtc_columns_v5_7_5.sql")
        assert migration_path.exists(), "Migration file should exist"
    
    def test_migration_adds_dtc_columns(self):
        """Migration should add dtc and dtc_code columns"""
        with open("migrations/add_dtc_columns_v5_7_5.sql", "r") as f:
            content = f.read()
        
        assert "dtc FLOAT" in content or "dtc float" in content.lower()
        assert "dtc_code VARCHAR" in content or "dtc_code varchar" in content.lower()


# =============================================================================
# Test INSERT Query has DTC columns
# =============================================================================

class TestInsertQueryDTCColumns:
    """Test that fuel_metrics INSERT includes DTC columns"""
    
    def test_insert_has_dtc_columns(self):
        """INSERT INTO fuel_metrics should include dtc and dtc_code"""
        with open("wialon_sync_enhanced.py", "r") as f:
            source = f.read()
        
        # Find the INSERT statement
        assert "dtc, dtc_code)" in source or "dtc,dtc_code)" in source, \
            "INSERT should include dtc and dtc_code columns"
    
    def test_values_tuple_has_dtc(self):
        """VALUES tuple should include dtc entries"""
        with open("wialon_sync_enhanced.py", "r") as f:
            source = f.read()
        
        assert 'metrics.get("dtc")' in source, \
            "Values should include metrics.get('dtc')"
        assert 'metrics.get("dtc_code")' in source, \
            "Values should include metrics.get('dtc_code')"
