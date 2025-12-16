"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                    📊 WIALON SENSOR MAPPING v1.0                               ║
║                                                                                ║
║    Maps Wialon sensors to fuel_metrics columns and identifies gaps            ║
╚═══════════════════════════════════════════════════════════════════════════════╝

WIALON SENSORS AVAILABLE (December 2025):
=========================================

✅ = Already mapped to fuel_metrics
🆕 = Should add to fuel_metrics
❌ = Not needed / redundant

MOTOR / ENGINE:
  ✅ Engine Speed (RPM)          → rpm
  ✅ Engine Hours                → engine_hours
  🆕 Engine Load                 → engine_load_pct (NEW - for efficiency analysis)
  ✅ Coolant Temperature         → coolant_temp_f
  🆕 Oil Pressure                → oil_pressure_psi (NEW - predictive maintenance)
  🆕 Oil Temperature             → oil_temp_f (NEW - predictive maintenance)
  🆕 Oil Level                   → oil_level_pct (NEW - maintenance alerts)
  🆕 Intake Pressure             → intake_pressure_psi (NEW - turbo health)
  🆕 Intake Temperature          → intake_temp_f (NEW - efficiency)
  ❌ Engine efficiency sensor    → (calculated from other sensors)

COMBUSTIBLE / FUEL:
  ✅ Fuel Level                  → sensor_pct, sensor_liters, sensor_gallons
  ✅ Fuel Rate                   → consumption_lph, consumption_gph
  🆕 Fuel Temperature            → fuel_temp_f (NEW - density correction)
  ✅ Total Fuel Used             → (calculated from consumption)
  🆕 Total Idle Fuel             → total_idle_fuel_gal (NEW - idle cost tracking)
  ✅ Average Fuel Economy        → mpg_current, mpg_avg_24h
  🆕 DEF Level                   → def_level_pct (NEW - emissions compliance)

UBICACIÓN / LOCATION:
  ✅ GPS                         → latitude, longitude
  ✅ GPS Speed                   → speed_mph
  ✅ Speed                       → speed_mph
  ✅ Heading                     → (not stored, but available)
  ✅ Altitude                    → altitude_ft
  ✅ Odometer                    → odometer_mi
  ✅ Mileage sensor              → odometer_mi

ELÉCTRICO / ELECTRICAL:
  ✅ Battery                     → battery_voltage
  🆕 Backup Battery              → backup_battery_v (NEW - safety)
  ✅ Voltage sensor              → pwr_ext, pwr_int

DIAGNÓSTICO / DIAGNOSTICS:
  ✅ # of DTC                    → dtc (count)
  ✅ VIN                         → (stored in tanks.yaml)

TRANSMISIÓN / TRANSMISSION:
  🆕 Gear                        → gear_position (NEW - efficiency analysis)
  🆕 Brake Switch                → brake_active (NEW - driver behavior)
  🆕 PTO Hours                   → pto_hours (NEW - equipment usage)

AMBIENTE / ENVIRONMENT:
  🆕 Ambient Temperature         → ambient_temp_f (NEW - climate impact)
  🆕 Barometer                   → barometric_pressure (NEW - altitude correction)

GPS CALIDAD / GPS QUALITY:
  ✅ DOP                         → hdop
  ✅ Sat #                       → sats (satellite count)
  ❌ GPS Fix Quality             → (derived from DOP/sats)

CONECTIVIDAD / CONNECTIVITY:
  ❌ Cell Mode                   → (not needed for analytics)
  ❌ LAC, MCC, MNC               → (cellular info, not needed)
  ❌ Roaming                     → (not needed)
  ❌ RSSI                        → (signal strength, not critical)
  ❌ Bus type                    → (internal)

TIEMPOS / TIME TRACKING:
  ✅ Engine Hours                → engine_hours
  ✅ Idle Hours                  → (calculated from idle_duration)
  🆕 PTO Hours                   → pto_hours

EVENTOS / EVENTS:
  ❌ Event                       → (generic event, handled separately)

=============================================================================
COLUMNS TO ADD TO fuel_metrics:
=============================================================================

Priority 1 (High Impact - Predictive Maintenance):
  - engine_load_pct      FLOAT      - Engine load percentage (0-100)
  - oil_pressure_psi     FLOAT      - Oil pressure
  - oil_temp_f           FLOAT      - Oil temperature
  - oil_level_pct        FLOAT      - Oil level percentage
  - intake_pressure_psi  FLOAT      - Intake manifold pressure
  - intake_temp_f        FLOAT      - Intake air temperature

Priority 2 (Cost Tracking):
  - def_level_pct        FLOAT      - DEF/AdBlue level (emissions)
  - total_idle_fuel_gal  FLOAT      - Cumulative idle fuel used
  - fuel_temp_f          FLOAT      - Fuel temperature (density)
  - ambient_temp_f       FLOAT      - Outside temperature

Priority 3 (Driver Behavior):
  - gear_position        TINYINT    - Current gear (0-18)
  - brake_active         BOOLEAN    - Brake pedal pressed
  - pto_hours            FLOAT      - Power take-off hours

Priority 4 (Safety/Other):
  - backup_battery_v     FLOAT      - Backup battery voltage
  - barometric_pressure  FLOAT      - Barometric pressure (inHg)

=============================================================================
RECOMMENDED NEW FEATURES:
=============================================================================

1. COMMAND CENTER ENHANCEMENTS:
   - Oil pressure warnings (< 25 psi at idle, < 40 psi driving)
   - Engine load alerts (sustained > 90%)
   - DEF level warnings (< 15%)
   - Intake temperature alerts (> 150°F)

2. COST ANALYSIS IMPROVEMENTS:
   - Idle fuel cost tracking from total_idle_fuel
   - DEF consumption costs
   - Temperature-adjusted MPG calculations

3. DRIVER BEHAVIOR:
   - Gear selection efficiency (using gear + rpm + speed)
   - Brake usage patterns
   - Engine load patterns

4. PREDICTIVE MAINTENANCE:
   - Oil degradation model (temp, hours, level)
   - Turbo health (intake pressure trends)
   - Cooling system (coolant temp patterns)
"""

# Migration SQL to add new columns
MIGRATION_SQL = """
-- Priority 1: Predictive Maintenance
ALTER TABLE fuel_metrics ADD COLUMN IF NOT EXISTS engine_load_pct FLOAT DEFAULT NULL COMMENT 'Engine load %';
ALTER TABLE fuel_metrics ADD COLUMN IF NOT EXISTS oil_pressure_psi FLOAT DEFAULT NULL COMMENT 'Oil pressure PSI';
ALTER TABLE fuel_metrics ADD COLUMN IF NOT EXISTS oil_temp_f FLOAT DEFAULT NULL COMMENT 'Oil temperature F';
ALTER TABLE fuel_metrics ADD COLUMN IF NOT EXISTS oil_level_pct FLOAT DEFAULT NULL COMMENT 'Oil level %';
ALTER TABLE fuel_metrics ADD COLUMN IF NOT EXISTS intake_pressure_psi FLOAT DEFAULT NULL COMMENT 'Intake pressure PSI';
ALTER TABLE fuel_metrics ADD COLUMN IF NOT EXISTS intake_temp_f FLOAT DEFAULT NULL COMMENT 'Intake temp F';

-- Priority 2: Cost Tracking
ALTER TABLE fuel_metrics ADD COLUMN IF NOT EXISTS def_level_pct FLOAT DEFAULT NULL COMMENT 'DEF level %';
ALTER TABLE fuel_metrics ADD COLUMN IF NOT EXISTS total_idle_fuel_gal FLOAT DEFAULT NULL COMMENT 'Total idle fuel gallons';
ALTER TABLE fuel_metrics ADD COLUMN IF NOT EXISTS fuel_temp_f FLOAT DEFAULT NULL COMMENT 'Fuel temperature F';
ALTER TABLE fuel_metrics ADD COLUMN IF NOT EXISTS ambient_temp_f FLOAT DEFAULT NULL COMMENT 'Ambient temperature F';

-- Priority 3: Driver Behavior
ALTER TABLE fuel_metrics ADD COLUMN IF NOT EXISTS gear_position TINYINT DEFAULT NULL COMMENT 'Current gear';
ALTER TABLE fuel_metrics ADD COLUMN IF NOT EXISTS brake_active BOOLEAN DEFAULT NULL COMMENT 'Brake pedal active';
ALTER TABLE fuel_metrics ADD COLUMN IF NOT EXISTS pto_hours FLOAT DEFAULT NULL COMMENT 'PTO hours';

-- Priority 4: Safety
ALTER TABLE fuel_metrics ADD COLUMN IF NOT EXISTS backup_battery_v FLOAT DEFAULT NULL COMMENT 'Backup battery voltage';
ALTER TABLE fuel_metrics ADD COLUMN IF NOT EXISTS barometric_pressure FLOAT DEFAULT NULL COMMENT 'Barometric pressure inHg';

-- Add indexes for new columns used in queries
CREATE INDEX IF NOT EXISTS idx_engine_load ON fuel_metrics(engine_load_pct);
CREATE INDEX IF NOT EXISTS idx_def_level ON fuel_metrics(def_level_pct);
CREATE INDEX IF NOT EXISTS idx_oil_pressure ON fuel_metrics(oil_pressure_psi);
"""

if __name__ == "__main__":
    print(__doc__)
    print("\n" + "=" * 60)
    print("SQL Migration Script:")
    print("=" * 60)
    print(MIGRATION_SQL)
