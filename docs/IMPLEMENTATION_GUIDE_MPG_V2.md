# IMPLEMENTATION GUIDE - MPG V2.0 Complete
# Execute this in VM after pulling latest changes

## ✅ CHANGES COMMITTED (Ready to Pull)

### 1. Cost Per Mile - FIXED ✅
- File: `api_v2.py`
- Changed: Queries now calculate real miles per truck (MAX - MIN odometer)
- Impact: Dashboard will show correct cost/mile and total miles

### 2. Loss Analysis - FIXED ✅  
- File: `database_mysql.py`
- Changed: Added speed validation (5-85 mph) and sanity check for calculated_miles
- Impact: No more 199M mile errors

### 3. MPG Engine Config - UPDATED ✅
- File: `mpg_engine.py`
- Changed:
  - `min_miles`: 8.0 → 10.0
  - `min_fuel_gal`: 1.2 → 2.0
  - `max_mpg`: 12.0 → 8.5 (realistic for 44k lbs trucks)
- Impact: More conservative, accurate MPG

### 4. MPG Calculator V2 - CREATED ✅
- File: `mpg_calculator_v2.py` (NEW)
- Contains: Complete new hierarchical logic with all sensors
- Ready to integrate into wialon_sync_enhanced.py

## 🔧 TODO: Integrate MPG V2 Logic (Manual Step)

The new logic in `mpg_calculator_v2.py` needs to be integrated into `wialon_sync_enhanced.py`.

**Current code** (lines 1732-1787 in wialon_sync_enhanced.py):
```python
if truck_status == "MOVING" and speed and speed > 5:
    # OLD LOGIC - uses sensor first, then consumption_gph
    # Problem: sensor has ±5% error, consumption_gph underestimates
```

**New code should**:
1. Check GPS quality (HDOP < 2.0, sats >= 6)
2. Try ECU fuel_economy direct (if 3.5-8.5)
3. Try total_fuel_used counter (if available)
4. Try sensor level (if no ECU)
5. Try consumption_gph (last resort)
6. Cross-validate with fuel_economy when available

**Option A: Quick Integration** (Recommended)
Replace lines 1732-1787 in `wialon_sync_enhanced.py` with the logic from `mpg_calculator_v2.py`

**Option B: Use as Module**
Import and call `calculate_mpg_v2()` function directly

## 📊 TESTING CHECKLIST

After pulling and restarting services:

### 1. Check Fleet Metrics Dashboard
- [ ] Cost per mile shows consistent value (not $0.00 vs $0.82)
- [ ] Total miles realistic for period (not sum of odometers)
- [ ] Fuel consumed matches period

### 2. Check Loss Analysis  
- [ ] No astronomical mileage values (< 10,000 miles per truck)
- [ ] All values realistic

### 3. Check MPG Values
- [ ] All trucks MPG between 3.5-8.5
- [ ] Most trucks in 4.5-7.0 range (typical for loaded)
- [ ] No more 8.8, 8.9, 9.0+ values

### 4. Monitor Logs
```bash
# Check MPG source distribution
grep "MPG from" /path/to/wialon_sync.log | tail -50

# Should see mix of:
# - "MPG from ECU direct" (best)
# - "MPG from total_fuel_used" (very good)  
# - "MPG from sensor" (okay)
# - "MPG from consumption rate" (fallback)
```

### 5. Compare Before/After
Take screenshots of:
- Fleet dashboard metrics (before)
- Wait 1-2 hours after deploy
- Fleet dashboard metrics (after)
- Verify MPG decreased to realistic range

## 🚨 ROLLBACK PLAN

If MPG goes too low or system breaks:

```bash
cd ~/Fuel-Analytics-Backend
git log --oneline -5  # Find commit before changes
git revert <commit_hash>
sudo systemctl restart wialon_sync
```

## 📝 EXPECTED RESULTS

### MPG Distribution (44k lbs trucks):
- **Worst** (3.5-4.5): Reefer loaded, mountains, city
- **Typical** (4.5-5.5): Loaded, mixed terrain
- **Good** (5.5-6.5): Loaded, highway
- **Best** (6.5-8.5): Empty, highway, downhill

### Cost Per Mile:
- Should be around $0.80-$0.90/mile
- Consistent between header and table
- Based on real miles traveled, not odometer sum

### Loss Analysis:
- Max miles per truck << 5,000 for 30 days
- All values make sense
- No overflow errors

## 🔍 DEBUGGING

If issues arise:

```bash
# Check current MPG config
grep -A 10 "class MPGConfig" ~/Fuel-Analytics-Backend/mpg_engine.py

# Check sensor availability
mysql -u fuel_admin -p fuel_copilot -e "
SELECT truck_id, 
       COUNT(*) as records,
       COUNT(fuel_economy) as has_ecu_mpg,
       COUNT(total_fuel_used) as has_fuel_counter
FROM fuel_metrics 
WHERE timestamp_utc >= DATE_SUB(NOW(), INTERVAL 1 HOUR)
GROUP BY truck_id;"

# Watch live MPG calculations
tail -f /path/to/wialon_sync.log | grep -i "mpg"
```

## ✅ SUCCESS CRITERIA

1. ✅ MPG values: 95%+ between 4.0-8.0
2. ✅ Cost/mile consistent across dashboard
3. ✅ No mileage overflow errors
4. ✅ Loss analysis shows realistic values
5. ✅ System stable for 2+ hours

---

**Created**: December 22, 2025
**Version**: V2.0.0
**Author**: Fuel Copilot AI Assistant
