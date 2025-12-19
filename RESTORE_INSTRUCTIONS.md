# RESTORE TO DECEMBER 17 WORKING STATE - INSTRUCTIONS

## Problem Summary
- Database was recreated on Dec 19, losing 12 days of historical data
- 5 extra tables were added that weren't in the working system
- sensor_cache_updater was changed from 1h to 12h lookback
- Dashboard shows N/A everywhere despite services running

## Solution: Restore to Dec 17 Configuration

### What Changed
**Database:**
- ❌ BEFORE: 28 tables (Dec 17 - working)
- ❌ AFTER: 32 tables (Dec 19 - broken)
- ✅ FIXING: Remove 5 extra tables, restore to 27 tables

**Extra Tables to Remove:**
1. `truck_ignition_events`
2. `truck_specs`
3. `truck_speeding_events`
4. `truck_trips`
5. `truck_units`

**Service Configuration:**
- ❌ BEFORE: sensor_cache_updater with 1h lookback
- ❌ AFTER: sensor_cache_updater with 12h lookback
- ✅ FIXING: Revert to 1h lookback

---

## Files Created

### 1. restore_db_structure_dec17.sql
SQL script that:
- Drops the 5 extra tables
- Creates/ensures all 27 correct tables exist
- Preserves existing data in fuel_metrics

### 2. restore_to_dec17.sh (Linux/Mac)
Bash script that:
- Stops all services
- Backs up current structure
- Runs SQL restoration
- Restarts services with Dec 17 config
- Verifies everything is working

### 3. restore_to_dec17.ps1 (Windows VM)
PowerShell script that:
- Stops NSSM services
- Backs up current structure
- Runs SQL restoration
- Restarts NSSM services
- Verifies everything is working

### 4. Code Changes
Files reverted to Dec 17 state:
- `wialon_reader.py` - 1h lookback (was 12h)
- `sensor_cache_updater.py` - 1h lookback, 2000 LIMIT (was 12h, 5000)

---

## Execution Steps

### On VM (Windows):

1. **Copy files to VM:**
   ```bash
   # From Mac, copy to VM
   scp restore_db_structure_dec17.sql tomas@20.127.200.135:C:/Users/tomas/fuel-analytics-backend/
   scp restore_to_dec17.ps1 tomas@20.127.200.135:C:/Users/tomas/fuel-analytics-backend/
   ```

2. **On VM, open PowerShell as Administrator:**
   ```powershell
   cd C:\Users\tomas\fuel-analytics-backend
   powershell -ExecutionPolicy Bypass -File restore_to_dec17.ps1
   ```

3. **Monitor logs:**
   ```powershell
   Get-Content logs\wialon_sync.log -Wait
   ```

4. **Verify data is populating:**
   ```powershell
   & "C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe" -ufuel_admin -pFuelCopilot2025! fuel_copilot -e "SELECT MAX(timestamp_utc), COUNT(*) FROM fuel_metrics;"
   ```

### On Mac (if running locally):

1. **Run restoration script:**
   ```bash
   cd /Users/tomasruiz/Desktop/Fuel-Analytics-Backend
   ./restore_to_dec17.sh
   ```

2. **Monitor logs:**
   ```bash
   tail -f logs/wialon_sync.log
   ```

3. **Verify data:**
   ```bash
   mysql -ufuel_admin -p'FuelCopilot2025!' fuel_copilot -e "SELECT MAX(timestamp_utc), COUNT(*) FROM fuel_metrics;"
   ```

---

## What to Expect

### Immediate (0-5 minutes):
- Services start successfully
- Database has 27 tables (verified)
- No errors in logs

### Short-term (5-30 minutes):
- fuel_metrics starts receiving new records
- truck_sensors_cache updates every 30 seconds
- Dashboard starts showing data (refresh may be needed)

### Medium-term (1-24 hours):
- Dashboard fully populated with real-time data
- All sensors showing current values
- MPG, drift, idle calculations working

### Long-term (24-72 hours):
- Enough historical data for accurate trends
- Command Center has baseline data
- Alerts and predictions functioning

---

## Verification Checklist

After running the restoration:

- [ ] Database has 27-28 tables (not 32)
- [ ] Extra tables removed: `SHOW TABLES LIKE 'truck_%';` shows no ignition/specs/speeding/trips/units
- [ ] Services running: `ps aux | grep python` (Mac) or `nssm status` (Windows)
- [ ] Data flowing: `SELECT COUNT(*) FROM fuel_metrics WHERE timestamp_utc > NOW() - INTERVAL 1 HOUR;`
- [ ] sensor_cache_updater using 1h lookback (check logs for "3600" not "43200")
- [ ] Dashboard shows data (may need hard refresh)
- [ ] API endpoints working: `curl http://localhost:8000/api/fleet`

---

## Rollback Plan

If restoration fails:

1. **Restore from backup:**
   ```bash
   mysql -ufuel_admin -p'FuelCopilot2025!' fuel_copilot < fuel_copilot_structure_backup_YYYYMMDD_HHMMSS.sql
   ```

2. **Revert code changes:**
   ```bash
   cd /Users/tomasruiz/Desktop/Fuel-Analytics-Backend
   git checkout HEAD -- wialon_reader.py sensor_cache_updater.py
   ```

3. **Restart services:**
   ```bash
   ./restart_services.sh
   ```

---

## Key Insights

**Why 27 tables instead of 32?**
- The 5 extra tables (`truck_ignition_events`, `truck_specs`, `truck_speeding_events`, `truck_trips`, `truck_units`) were NOT in the working system on Dec 17
- These were added by VM's migration scripts but are breaking the existing code
- The code expects specific table names/structure that matches the 27-table layout

**Why revert to 1h lookback?**
- Dec 17 system used 1h lookback and worked perfectly
- 12h lookback was added to "catch slow sensors" but isn't the issue
- Simpler is better - 1h is sufficient for real-time monitoring

**Why can't we just copy .ibd files?**
- The historic database files are corrupted (MySQL crashes when reading them)
- Even if we could copy them, we'd copy the corruption
- Better to have clean structure and regenerate data going forward

---

## Support

If issues persist after restoration:

1. Check logs in `logs/` directory
2. Verify MySQL is running: `systemctl status mysql` or `services.msc`
3. Check network connectivity to Wialon: `ping 20.127.200.135`
4. Verify credentials: `mysql -ufuel_admin -p'FuelCopilot2025!' -e "SELECT 1;"`
5. Review this conversation for debugging steps

---

**Created:** December 19, 2025
**Author:** Fuel Copilot Team
**Version:** Dec 17 Restoration v1.0
