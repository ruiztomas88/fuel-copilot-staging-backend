# 🚨 Refuel Detection Issue - Root Cause Analysis

## Problem
- MR7679 just had a refuel event that wasn't detected/saved
- The refuel appeared on the dashboard (69.0% → 80.4%) but wasn't recorded in the system

## Root Causes Found

### 1. **Column Name Mismatch in `save_refuel_event()` - FIXED ✅**

**Issue**: The function was using wrong column names when inserting refuel events:
```python
# ❌ WRONG (was trying to insert these columns):
INSERT INTO refuel_events 
(timestamp_utc, truck_id, carrier_id, fuel_before, fuel_after, ...)

# ✅ CORRECT (should be):
INSERT INTO refuel_events 
(refuel_time, truck_id, carrier_id, before_pct, after_pct, ...)
```

**Table actual schema:**
```sql
- refuel_time (datetime) - NOT timestamp_utc
- before_pct (decimal) - NOT fuel_before
- after_pct (decimal) - NOT fuel_after
```

**File affected**: `wialon_sync_enhanced.py`, line 1473

**Fix applied**: Updated INSERT query to use correct column names:
- `timestamp_utc` → `refuel_time`
- `fuel_before` → `before_pct`
- `fuel_after` → `after_pct`

### 2. **wialon_sync Not Running**

When checking the logs at 01:24:00, wialon_sync was still processing the fleet, but MR7679 wasn't being monitored. The sync process needs to be running continuously to detect refuel events in real-time.

**Status check**: `ps aux | grep wialon_sync_enhanced.py`

**If not running**: Start with:
```bash
cd /Users/tomasruiz/Desktop/Fuel-Analytics-Backend
nohup python3 wialon_sync_enhanced.py > logs/wialon_sync.log 2>&1 &
```

Or use: `bash /Users/tomasruiz/Desktop/Fuel-Analytics-Backend/restart_sync.sh`

## Refuel Detection Logic Overview

### Detection Methods:
1. **Kalman Method**: Compares current sensor vs Kalman estimate (expected fuel)
2. **Sensor Method**: Compares current vs last sensor reading (fallback for Kalman drift)

### Thresholds:
- Minimum increase: 10% OR 5 gallons
- Time gap: 5 minutes to 96 hours
- Tank capacity: Per-truck configuration

### Pending Refuel Buffering:
Multiple rapid fuel jumps (e.g., 10%→40%→80%→100%) are buffered into a single refuel event with a 10-minute window

### Duplicate Prevention:
- Checks for existing refuel within ±2 minutes
- Tolerance: 5 gallons

## How to Verify It's Working

```bash
# 1. Check if sync is running
ps aux | grep wialon_sync_enhanced.py

# 2. Check recent refuel logs
tail -100 /Users/tomasruiz/Desktop/Fuel-Analytics-Backend/logs/wialon_sync.log | grep -i "refuel\|MR7679"

# 3. Check database for recent refuel
mysql -u root fuel_copilot_local -e "SELECT * FROM refuel_events WHERE truck_id = 'MR7679' ORDER BY refuel_time DESC LIMIT 5;"
```

## Expected Log Messages for Detected Refuel

```
⛽ [MR7679] REFUEL DETECTED (KALMAN): Baseline=69.0% → Sensor=80.4% (+11.4%, +15.2 gal) over 5 min gap
💧 REFUEL DETECTED [MR7679] gallons=15.2 (69.0% → 80.4%) detection_method=KALMAN confidence=90% location=...
✅ [MR7679] Refuel SAVED: 69.0% → 80.4% (+15.2 gal)
💾 Refuel saved to DB: MR7679 +15.2 gal
```

## To-Do
- [ ] Restart wialon_sync service
- [ ] Monitor logs for refuel detection
- [ ] Verify refuels are being saved to database
- [ ] Check frontend shows refuel events correctly
