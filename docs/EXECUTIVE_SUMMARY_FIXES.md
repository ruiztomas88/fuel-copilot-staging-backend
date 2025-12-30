# EXECUTIVE SUMMARY - FUEL COPILOT FIXES NEEDED

## December 22, 2025 - 18:50 UTC

## ✅ COMPLETED

1. **Sensor Mapping Audit** - All critical sensors mapped correctly (34/38)
2. **Odometer Fix** - Changed from `odometer_mi` to `odometer` ✓
3. **Data Age Verification** - Confirmed DB is only 2.1 days old ✓
4. **Sensor Availability Check** - 31% have total_fuel_used, 69% don't ✓

## 🔴 CRITICAL ISSUES REQUIRING FIXES

### 1. METRICS TAB - IMPOSSIBLE VALUES

**Symptoms:**

- Miles shown: 4950, 4580 (too high for 2 days)
- Cost per mile: $0.00 AND $0.82 (inconsistent + too low)
- Loss analysis: 199,727,756 miles (that's LC6799's REAL odometer!)

**Root Cause:**

- Using ABSOLUTE odometer values instead of DELTAS
- LC6799 odometer = 1,048,106 mi (lifetime, not trip)
- GS5030 odometer = 774,029 mi (lifetime)
- JR7099 odometer = 936,834 mi (lifetime)

**Fix Required:**

- NEVER show absolute odometer in metrics
- Only use DELTAS for calculations
- Accumulated miles should come from MPG engine state or trips table

### 2. MPG CALCULATION - VALUES TOO HIGH

**Current Code Status:**

- ✅ Already uses delta method
- ✅ Has ECU `total_fuel_used` support
- ❌ MAX_DELTA_MILES = 100 too restrictive
- ❌ Odometer delta limit = 50 mi too low
- ❌ Need to verify it's actually being used

**Available Sensors for MPG:**

- 9 trucks (31%): Have `total_fuel_used` (ECU counter) → BEST
- 20 trucks (69%): Only have `fuel_rate` → Need accumulation

**Fix Required:**

1. Increase `MAX_DELTA_MILES` to 500 (trucks can travel 12h × 65mph = 780mi)
2. Remove 50 mi limit on odometer delta (line 1742)
3. Add logging to see which fuel source is actually being used
4. Verify deltas are within 4-8 MPG range before accepting

### 3. PREDICTIVE MAINTENANCE - CONFIDENCE >100%

**Symptom:** 7500%, 9200% confidence values

**Root Cause:** (Need to find in code)

- Multiplying percentage twice
- OR using count instead of percentage

**Fix Required:**

- Cap all confidence values: `min(100, max(0, value))`

### 4. DTC/SPN - "UNKNOWN" ALERTS

**Symptom:** Emails saying "SPN Unknown" despite 3000+ SPNs in DB

**Root Cause:** (Need to verify)

- `dtc_analyzer.py` not querying `j1939_spn_lookup` table
- OR SPN not in table

**Fix Required:**

- Verify lookup table is populated
- Check `dtc_analyzer.py` uses the table
- Add fallback: Unknown SPN → log but don't spam emails

---

## IMPLEMENTATION PLAN

### PHASE 1: FIX MPG CALCULATION (30 min)

```python
# File: wialon_sync_enhanced.py

# 1. Line ~1742: Remove 50 mi odometer limit
if delta_miles < 0 or delta_miles > 500:  # Change from 50 to 500

# 2. Line ~1793: Increase MAX_DELTA_MILES
MAX_DELTA_MILES = 500  # Change from 100 to 500

# 3. Add MPG range validation BEFORE accepting
if delta_miles > 0 and delta_gallons > 0:
    instant_mpg = delta_miles / delta_gallons

    # Validate against physics (Class 8 loaded: 2-12 MPG max)
    if not (2.0 <= instant_mpg <= 12.0):
        logger.warning(f"[{truck_id}] MPG {instant_mpg:.2f} out of range (2-12), discarding")
        return  # Don't update state with bad data

    # Add detailed logging
    fuel_source = "tank_level" if fuel_from_sensor else \
                  "ecu_cumulative" if fuel_from_ecu else "fuel_rate"
    logger.info(f"[{truck_id}] MPG={instant_mpg:.2f} (Δmi={delta_miles:.1f}, Δgal={delta_gallons:.2f}, source={fuel_source})")
```

### PHASE 2: FIX METRICS DISPLAY (15 min)

```python
# File: api_v2.py or wherever metrics are calculated

# NEVER use absolute odometer for totals
# Use accumulated_miles from mpg_baseline or trip_data

SELECT
    SUM(trip_miles) as total_miles,  -- NOT SUM(odometer)
    SUM(fuel_consumed) as total_fuel
FROM trips
WHERE trip_date >= '2025-12-20'  -- Since DB reset
```

### PHASE 3: FIX CONFIDENCE CAPS (5 min)

```python
# Find all confidence calculations and add:
confidence_pct = min(100.0, max(0.0, confidence_value))
```

### PHASE 4: FIX DTC LOOKUPS (10 min)

```python
# In dtc_analyzer.py - verify it queries j1939_spn_lookup
# Add try/except to not crash on unknown SPNs
```

---

## TESTING CHECKLIST

After fixes:

- [ ] MPG values: 4-8 range for loaded trucks
- [ ] Metrics tab total miles: <500 mi/truck for 2 days
- [ ] Cost per mile: $1.50-$2.50 range
- [ ] Confidence: 0-100%
- [ ] No "Unknown SPN" emails for known SPNs
- [ ] Logs show which fuel source used (tank/ECU/rate)

---

## READY TO IMPLEMENT?

Recommend doing in order:

1. PHASE 1 (MPG) - Most critical
2. PHASE 2 (Metrics) - User-visible
3. PHASE 3 (Confidence) - Quick win
4. PHASE 4 (DTC) - Can be done anytime

Total time: ~60 minutes
