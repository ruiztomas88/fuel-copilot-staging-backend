# Wialon Full Data Sync - Deployment Guide

## 📋 Overview

Complete Wialon data synchronization system that brings ALL data from Wialon database to local fuel_copilot database:

- ✅ **Sensors** (oil, DEF, engine, fuel, GPS, etc.) - Every 30 seconds
- ✅ **Trips** (distance, speed, duration, driver behavior) - Every 60 seconds  
- ✅ **Speeding Events** (violations with severity) - Every 60 seconds
- ✅ **Ignition Events** (engine on/off) - Every 60 seconds

**Performance:** 40-60x faster than querying Wialon directly (2-3s → <50ms)

---

## 🚀 Deployment Steps

### Step 1: Create Database Tables

Run the migration to create the new tables:

```bash
cd /Users/tomasruiz/Desktop/Fuel-Analytics-Backend
python3 migrations/create_wialon_sync_tables.py
```

**Expected output:**
```
Creating Wialon sync tables...
✅ Created truck_trips table
✅ Created truck_speeding_events table  
✅ Created truck_ignition_events table
✅ All tables created!
```

**Tables created:**
- `truck_trips` - Trip history with driver behavior metrics
- `truck_speeding_events` - Speeding violations with severity classification
- `truck_ignition_events` - Engine on/off events

### Step 2: Start the Sync Service

**Option A: Run in foreground (for testing)**
```bash
python3 wialon_full_sync_service.py
```

**Option B: Run as background service (production)**
```bash
nohup python3 wialon_full_sync_service.py > wialon_sync.log 2>&1 &
echo $! > wialon_sync.pid
```

**Option C: Stop the service**
```bash
# If running in background
kill $(cat wialon_sync.pid)
rm wialon_sync.pid
```

**Check logs:**
```bash
tail -f wialon_sync.log
```

### Step 3: Verify Sync is Working

Wait 2-3 minutes for initial sync, then check the tables:

```bash
mysql -u root -p fuel_copilot
```

```sql
-- Check trip count
SELECT COUNT(*) as trip_count, 
       MIN(start_time) as earliest, 
       MAX(start_time) as latest
FROM truck_trips;

-- Check speeding events
SELECT COUNT(*) as total_events,
       SUM(CASE WHEN severity='minor' THEN 1 ELSE 0 END) as minor,
       SUM(CASE WHEN severity='moderate' THEN 1 ELSE 0 END) as moderate,
       SUM(CASE WHEN severity='severe' THEN 1 ELSE 0 END) as severe
FROM truck_speeding_events;

-- Check latest sensor data
SELECT COUNT(*) as cached_trucks,
       MAX(cache_timestamp) as last_sync
FROM truck_sensors_cache;

-- Sample trip data for a truck
SELECT truck_id, start_time, distance_miles, avg_speed, 
       speeding_count, harsh_accel_count, harsh_brake_count
FROM truck_trips
WHERE truck_id = 'GS5030'
ORDER BY start_time DESC
LIMIT 5;
```

---

## 🔌 New API Endpoints

### 1. Get Truck Trips

```http
GET /fuelAnalytics/api/v2/trucks/{truck_id}/trips?days=7&limit=50
```

**Example:**
```bash
curl -X GET "http://localhost:8008/fuelAnalytics/api/v2/trucks/GS5030/trips?days=7"
```

**Response:**
```json
{
  "truck_id": "GS5030",
  "trips": [
    {
      "start_time": "2025-01-02T14:30:00",
      "end_time": "2025-01-02T18:45:00",
      "duration_hours": 4.25,
      "distance_miles": 187.5,
      "avg_speed": 44.1,
      "max_speed": 68.3,
      "driver": "John Smith",
      "harsh_accel": 2,
      "harsh_brake": 3,
      "speeding": 5
    }
  ],
  "summary": {
    "total_trips": 23,
    "total_distance_miles": 3421.7,
    "total_hours": 87.3,
    "avg_speed_mph": 39.2,
    "total_speeding_events": 34,
    "total_harsh_accel": 15,
    "total_harsh_brake": 22
  },
  "period_days": 7
}
```

### 2. Get Speeding Events

```http
GET /fuelAnalytics/api/v2/trucks/{truck_id}/speeding-events?days=7&severity=severe
```

**Example:**
```bash
curl -X GET "http://localhost:8008/fuelAnalytics/api/v2/trucks/GS5030/speeding-events?days=7"
```

**Response:**
```json
{
  "truck_id": "GS5030",
  "events": [
    {
      "start_time": "2025-01-02T16:20:00",
      "end_time": "2025-01-02T16:25:00",
      "duration_minutes": 5.2,
      "max_speed": 82.0,
      "speed_limit": 65.0,
      "speed_over_limit": 17.0,
      "distance_miles": 6.8,
      "driver": "John Smith",
      "severity": "severe",
      "location": {
        "lat": 34.0522,
        "lon": -118.2437
      }
    }
  ],
  "summary": {
    "total_events": 5,
    "by_severity": {
      "minor": 2,
      "moderate": 2,
      "severe": 1
    }
  },
  "period_days": 7
}
```

**Severity Classification:**
- `minor`: 1-5 mph over limit
- `moderate`: 6-15 mph over limit  
- `severe`: 16+ mph over limit

### 3. Fleet Driver Behavior Metrics

```http
GET /fuelAnalytics/api/v2/fleet/driver-behavior?days=7
```

**Example:**
```bash
curl -X GET "http://localhost:8008/fuelAnalytics/api/v2/fleet/driver-behavior?days=7"
```

**Response:**
```json
{
  "trucks": [
    {
      "truck_id": "GS5030",
      "trips": 23,
      "total_miles": 3421.7,
      "speeding_events": 34,
      "harsh_accel": 15,
      "harsh_brake": 22,
      "avg_speed": 39.2,
      "safety_score": 72.5,
      "speeding_by_severity": {
        "minor": 20,
        "moderate": 10,
        "severe": 4
      }
    }
  ],
  "fleet_summary": {
    "total_trucks": 45,
    "total_miles": 87532.8,
    "total_speeding_events": 892,
    "total_harsh_accel": 421,
    "total_harsh_brake": 673,
    "avg_safety_score": 78.3,
    "violations_per_100_miles": 1.02
  },
  "period_days": 7,
  "timestamp": "2025-01-03T10:30:00Z"
}
```

**Safety Score Calculation:**
- Base score: 100
- Deductions:
  - Speeding: -10 points per violation per 100 miles (max -30)
  - Harsh accel: -10 points per event per 100 miles (max -20)
  - Harsh brake: -10 points per event per 100 miles (max -20)
- Range: 0-100 (higher is better)

---

## 📊 Data Flow Architecture

```
┌──────────────────┐     Every 30s (sensors)      ┌──────────────────┐
│                  │     Every 60s (events)        │                  │
│  Wialon Database │────────────────────────────>  │  fuel_copilot DB │
│  (20.127.200.135)│   wialon_full_sync_service   │   (localhost)    │
│                  │                               │                  │
└──────────────────┘                               └──────────────────┘
                                                            │
                                                            │ <50ms queries
                                                            ▼
                                                    ┌──────────────────┐
                                                    │                  │
                                                    │   API Endpoints  │
                                                    │   (FastAPI)      │
                                                    │                  │
                                                    └──────────────────┘
                                                            │
                                                            ▼
                                                    ┌──────────────────┐
                                                    │                  │
                                                    │    Dashboard     │
                                                    │    (Frontend)    │
                                                    │                  │
                                                    └──────────────────┘
```

**Benefits:**
1. ⚡ **40-60x faster** - No more 2-3 second Wialon queries
2. 🔄 **Real-time** - Data syncs every 30-60 seconds
3. 📈 **Driver Behavior** - Speeding, harsh events, safety scores
4. 🚗 **Trip History** - Complete trip analysis with driver metrics
5. 🛡️ **Reliability** - Local cache survives Wialon network issues

---

## 🔧 Configuration

Edit `wialon_full_sync_service.py` to adjust:

```python
# Sync intervals
time.sleep(30)  # Sensors every 30 seconds

if self.sync_count % 2 == 0:  # Trips/events every 60 seconds
    self.sync_trips()
    self.sync_speeding_events()

# Database connections
WIALON_CONFIG = {
    'host': '20.127.200.135',
    'port': 3306,
    'user': 'wialonro',
    'password': 'KjmAqwertY1#2024!@Wialon',
    'database': 'wialon_collect',
}

LOCAL_CONFIG = {
    'host': 'localhost',
    'port': 3306,
    'user': 'root',
    'password': 'tomas',
    'database': 'fuel_copilot',
}
```

---

## 🐛 Troubleshooting

### Service not starting

**Check Python dependencies:**
```bash
pip3 install pymysql
```

**Check database connection:**
```bash
mysql -u root -p fuel_copilot -e "SHOW TABLES;"
```

### No data appearing in tables

**Check service logs:**
```bash
tail -f wialon_sync.log
```

**Verify Wialon connection:**
```bash
mysql -h 20.127.200.135 -u wialonro -p wialon_collect -e "SELECT COUNT(*) FROM sensors;"
```

### Slow API responses

**Check cache freshness:**
```sql
SELECT truck_id, cache_timestamp, 
       TIMESTAMPDIFF(SECOND, cache_timestamp, NOW()) as age_seconds
FROM truck_sensors_cache
ORDER BY cache_timestamp DESC
LIMIT 10;
```

If `age_seconds > 120`, the sync service may be stopped.

### High CPU/Memory usage

**Reduce sync frequency** in `wialon_full_sync_service.py`:
```python
time.sleep(60)  # Change from 30 to 60 seconds

if self.sync_count % 4 == 0:  # Change from % 2 to % 4 (every 2 minutes)
```

---

## 📈 Monitoring

**Check service health:**
```bash
# Is service running?
ps aux | grep wialon_full_sync_service

# Check logs for errors
grep "❌" wialon_sync.log | tail -20

# Check sync cycle count
grep "Sync Cycle" wialon_sync.log | tail -5
```

**Database metrics:**
```sql
-- Sync freshness
SELECT 
    'sensors' as table_name,
    COUNT(*) as records,
    MAX(cache_timestamp) as last_sync,
    TIMESTAMPDIFF(SECOND, MAX(cache_timestamp), NOW()) as age_seconds
FROM truck_sensors_cache
UNION ALL
SELECT 
    'trips' as table_name,
    COUNT(*) as records,
    MAX(created_at) as last_sync,
    TIMESTAMPDIFF(SECOND, MAX(created_at), NOW()) as age_seconds
FROM truck_trips
UNION ALL
SELECT 
    'speeding' as table_name,
    COUNT(*) as records,
    MAX(created_at) as last_sync,
    TIMESTAMPDIFF(SECOND, MAX(created_at), NOW()) as age_seconds
FROM truck_speeding_events;
```

---

## 🎯 Next Steps

1. **Update Frontend** - Add UI components to display:
   - Trip history timeline
   - Speeding event map/list
   - Driver safety scorecard
   - Fleet-wide behavior rankings

2. **Add Alerts** - Create notifications for:
   - Severe speeding events (real-time)
   - Driver safety score drops
   - Excessive harsh events

3. **Analytics** - Build reports for:
   - Monthly driver behavior trends
   - Cost impact of poor driving
   - Route efficiency analysis

4. **Gamification** - Driver leaderboards and incentives

---

## 📚 Related Files

- `wialon_full_sync_service.py` - Main sync service
- `migrations/create_wialon_sync_tables.py` - Table creation
- `api_v2.py` - API endpoints (lines 1197-1480)
- `sensor_cache_updater.py` - Legacy (sensor-only, can be deprecated)

---

## ✅ Deployment Checklist

- [ ] Migration script run successfully
- [ ] All 3 tables created (trips, speeding_events, ignition_events)
- [ ] Sync service started and running
- [ ] Logs showing successful sync cycles
- [ ] Data appearing in tables (verify with SQL queries)
- [ ] API endpoints responding correctly
- [ ] Frontend updated to consume new endpoints
- [ ] Service configured to start on server reboot

---

**Questions?** Check logs at `wialon_sync.log` or contact the development team.
