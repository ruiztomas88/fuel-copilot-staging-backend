# FUEL COPILOT - COMPREHENSIVE FIX PLAN

## December 22, 2025

## PROBLEMS IDENTIFIED

### 1. METRICS TAB ISSUES

- ❌ Cost per mile: Shows 0.82 (too low vs 2.26 benchmark) AND shows 0.00 in one place, 0.82 in another
- ❌ Miles driven: Shows 4950, 4580 miles (IMPOSSIBLE - DB reset 2-3 days ago)
- ❌ Fuel consumed: Unrealistic totals for 2-3 day period
- ❌ Loss analysis: Trucks showing 199,727,756 miles (CORRUPTED DATA)

### 2. COMMAND CENTER - PREDICTIVE MAINTENANCE

- ❌ Confidence values: 7500%, 9200% (mathematically impossible - should be 0-100%)

### 3. DTC/SPN ERRORS

- ❌ Individual truck DTCs showing "SPN Unknown"
- ❌ Email alerts for unknown SPNs despite having 3000+ SPNs in database
- ❌ Need to verify j1939_spn_lookup table is being used

### 4. MPG CALCULATIONS - CRITICAL ISSUE

- ❌ Current values: Often >8 MPG (unrealistic for Class 8 trucks with 44,000 lbs cargo)
- ❌ Expected range: 4.0 - 8.0 MPG max
- ❌ Need physics-based calculation using available sensors
- ❌ Cannot just use min/max caps - must calculate REAL MPG

### 5. SENSOR MAPPING (COMPLETED ✓)

- ✅ Odometer fix: sensor_data.get("odometer") not "odometer_mi"
- ✅ All critical sensors mapped correctly
- ✅ 34/38 Wialon sensors mapped

---

## ROOT CAUSE ANALYSIS

### Issue #1: CORRUPTED ODOMETER IN DB

**Problem:** LC6799 shows 1,048,106 miles (physically impossible)
**Root Cause:** Old data from BEFORE DB reset (Dec 19-22) still in truck_sensors_cache
**Impact:** Inflates total miles, breaks MPG calculations, corrupts cost/mile

### Issue #2: MPG CALCULATION LOGIC FLAWED

**Current Logic (wialon_sync_enhanced.py lines 1738-1820):**

```python
# Priority 1: fuel_level delta → NOT AVAILABLE (no tank level sensor)
# Priority 2: total_fuel_used delta → AVAILABLE but CUMULATIVE (lifetime counter)
# Priority 3: fuel_rate × time → NOISY (instantaneous reading)

# Distance: speed × time OR odometer delta
```

**Problems:**

1. `total_fuel_used` is LIFETIME cumulative gallons (like odometer)
2. Simple delta between readings = fuel used in that interval
3. BUT if corrupted odometer (1M miles), corrupts fuel too
4. fuel_rate_gph varies ±20-40% instantaneously (noisy)

**What we HAVE:**

- ✅ `odom` (odometer in miles) - some trucks
- ✅ `total_fuel_used` (ECU cumulative fuel counter in gallons) - MOST trucks
- ✅ `fuel_rate` (instantaneous GPH) - all trucks
- ✅ `speed` (GPS speed mph) - all trucks
- ✅ `engine_load` (%) - all trucks
- ✅ `engine_hours` - all trucks

### Issue #3: DB NOT ACTUALLY RESET

**Evidence:**

- truck_sensors_cache still has old data (LC6799: 1M+ miles)
- Data should span 2-3 days MAX, not weeks/months

### Issue #4: CONFIDENCE CALCULATION BUG

**Problem:** 7500% confidence (should be 0-100%)
**Likely cause:** Multiplying probability by 100 twice, or using raw count instead of percentage

---

## ACTION PLAN

### PHASE 1: DATA CLEANUP (CRITICAL - DO FIRST)

1. ✅ Verify DB reset date
2. ✅ TRUNCATE tables with corrupted data:
   - `truck_sensors_cache` (has 1M mile odometers)
   - `fleet_summary` (has inflated totals)
   - `daily_truck_metrics` (has old data)
   - `fuel_metrics` (recalculate from clean data)
3. ✅ Let WialonSync rebuild cache from scratch (15-20 min)

### PHASE 2: MPG CALCULATION FIX (CRITICAL)

**New Strategy: ECU-Based MPG**

```python
# Use total_fuel_used (ECU counter) as PRIMARY source
# This is CUMULATIVE like odometer - perfect for MPG!

if last_total_fuel_used is not None and current_total_fuel_used > last_total_fuel_used:
    # Delta method (ACCURATE)
    delta_fuel = current_total_fuel_used - last_total_fuel_used
    delta_miles = odometer_current - odometer_last  # if available
    # OR
    delta_miles = speed * dt_hours  # fallback

    if MIN_DELTA_MILES < delta_miles < MAX_DELTA_MILES and \
       MIN_DELTA_FUEL < delta_fuel < MAX_DELTA_FUEL:
        instant_mpg = delta_miles / delta_fuel

        # Validate against physics
        if 2.0 <= instant_mpg <= 12.0:  # Class 8 range (conservative)
            update_mpg_state(...)
```

**Why this works:**

1. `total_fuel_used` = ECU's internal fuel counter (very accurate)
2. Delta between readings = actual fuel consumed
3. Works same as odometer delta
4. No tank level sensor needed
5. Not affected by instantaneous noise

**Validation layers:**

- Delta validation: 0.1-100 mi, 0.01-25 gal per reading
- MPG range: 2.0-12.0 (conservative, catches 99% of valid readings)
- EMA smoothing: 0.3 alpha (already implemented)
- Engine load correlation: Low load → higher MPG expected

### PHASE 3: FIX COST PER MILE

**Root cause:** Probably dividing by corrupted mileage
**Fix:** After data cleanup + MPG fix, recalculate:

```python
cost_per_mile = (fuel_consumed_gal × fuel_price_per_gal) / miles_driven
# With clean data: (100 gal × $3.50) / 500 mi = $0.70/mi ✓
# Expected range: $1.50-$2.50/mi for Class 8
```

### PHASE 4: FIX CONFIDENCE PERCENTAGES

Find prediction confidence calculation and ensure:

```python
confidence_pct = min(100, max(0, confidence_value * 100))
# OR if already percentage:
confidence_pct = min(100, max(0, confidence_value))
```

### PHASE 5: FIX DTC/SPN LOOKUPS

1. Verify `j1939_spn_lookup` table has data
2. Check `dtc_analyzer.py` uses lookup table
3. Add fallback: If SPN not in table, log but don't spam emails

---

## TESTING CHECKLIST

After fixes, verify:

- [ ] truck_sensors_cache has only 2-3 days of data
- [ ] Odometer values < 2M miles (realistic)
- [ ] MPG values: 4.0-8.0 range for loaded trucks
- [ ] Cost per mile: $1.50-$2.50 range
- [ ] Total miles driven: < 1500 mi per truck (realistic for 2-3 days)
- [ ] Confidence: 0-100%
- [ ] DTC alerts show SPN descriptions

---

## IMPLEMENTATION ORDER

1. **NOW**: Truncate corrupted tables → Clean slate
2. **Wait 20 min**: Let cache rebuild with clean data
3. **Fix MPG**: Implement ECU-based delta calculation
4. **Fix confidence**: Cap at 100%
5. **Fix DTC**: Verify lookup table usage
6. **Test**: Run validation suite

---

## MPG SENSOR AVAILABILITY CHECK

Based on audit:

```
✓ odom (odometer)         - 6/29 trucks (21%)
✓ total_fuel_used         - NEED TO CHECK how many have this
✓ fuel_rate               - ALL trucks
✓ speed                   - ALL trucks
✓ engine_load             - ALL trucks
✓ engine_hours            - MOST trucks
```

**Decision Matrix:**

- IF truck has `total_fuel_used` AND `odom` → Use both deltas (BEST)
- IF truck has `total_fuel_used` ONLY → Use fuel delta + speed×time for miles (GOOD)
- IF truck has NEITHER → Accumulate `fuel_rate` samples over window (ACCEPTABLE)

---

## NEXT STEPS

Ready to execute? Confirm and I'll:

1. Truncate tables
2. Fix MPG calculation code
3. Fix confidence caps
4. Test and verify
