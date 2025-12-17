# Sensor Cache System Deployment Guide

## Overview

The sensor cache system optimizes dashboard performance by pre-processing Wialon sensor data every 30 seconds and storing it in a local cache table. This eliminates slow direct queries to Wialon on every API request.

**Performance improvement: 40-60x faster** (from 2-3 seconds to <50ms)

## Architecture

```
┌─────────────┐     Every 30s     ┌──────────────────────┐
│   Wialon    │ ◄─────────────────┤ sensor_cache_updater │
│  Database   │                   │   (background)       │
└─────────────┘                   └──────────┬───────────┘
                                             │
                                             │ UPSERT
                                             ▼
                                  ┌─────────────────────┐
                                  │  fuel_copilot DB    │
    ┌──────────────┐              │ truck_sensors_cache │
    │  Dashboard   │              └──────────┬──────────┘
    │   (users)    │                         │
    └──────┬───────┘                         │
           │                                 │
           │  API call (< 50ms)              │
           │                                 │
           ▼                                 │
    ┌─────────────┐     SELECT 1 row        │
    │  FastAPI    │ ◄───────────────────────┘
    │  Endpoint   │
    └─────────────┘
```

## Deployment Steps

### 1. Create Cache Table

```bash
cd /path/to/Fuel-Analytics-Backend
python migrations/create_truck_sensors_cache.py
```

Expected output:
```
Creating truck_sensors_cache table...
✅ Created truck_sensors_cache table
Table structure:
  truck_id: varchar(20)
  unit_id: int
  timestamp: datetime
  ...
✅ Migration complete!
```

### 2. Start Cache Updater Service

#### Option A: Run in screen/tmux (testing)

```bash
# Start in screen
screen -S sensor-cache
python sensor_cache_updater.py

# Detach: Ctrl+A, D
# Reattach: screen -r sensor-cache
```

#### Option B: Systemd service (production)

Create `/etc/systemd/system/sensor-cache-updater.service`:

```ini
[Unit]
Description=Sensor Cache Updater Service
After=network.target mysql.service

[Service]
Type=simple
User=fuel_admin
WorkingDirectory=/home/fuel_admin/Fuel-Analytics-Backend
Environment="PATH=/usr/bin:/usr/local/bin"
ExecStart=/usr/bin/python3 /home/fuel_admin/Fuel-Analytics-Backend/sensor_cache_updater.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable sensor-cache-updater
sudo systemctl start sensor-cache-updater

# Check status
sudo systemctl status sensor-cache-updater

# View logs
sudo journalctl -u sensor-cache-updater -f
```

### 3. Deploy API Changes

The API endpoint changes are already in `api_v2.py`. Just restart the FastAPI service:

```bash
sudo systemctl restart fuel-analytics-api
# or
sudo systemctl restart gunicorn
```

### 4. Verify Operation

#### Check cache table is populating:

```bash
mysql -u fuel_admin -p fuel_copilot -e "
SELECT truck_id, timestamp, data_age_seconds, oil_pressure_psi, rpm, def_level_pct 
FROM truck_sensors_cache 
ORDER BY last_updated DESC 
LIMIT 5;"
```

Expected output (after 30 seconds):
```
+----------+---------------------+------------------+------------------+------+--------------+
| truck_id | timestamp           | data_age_seconds | oil_pressure_psi | rpm  | def_level_pct|
+----------+---------------------+------------------+------------------+------+--------------+
| FF7702   | 2025-12-17 10:30:15 |               12 |            22.60 |  704 |        66.00 |
| VD3579   | 2025-12-17 10:30:10 |               17 |            35.20 | 1250 |        78.50 |
| ...      | ...                 |              ... |              ... |  ... |          ... |
+----------+---------------------+------------------+------------------+------+--------------+
```

#### Test API endpoint:

```bash
curl http://localhost:8000/fuelAnalytics/api/v2/trucks/FF7702/sensors | jq .
```

Should return instantly (<50ms) with full sensor data.

#### Monitor service logs:

```bash
# Systemd
sudo journalctl -u sensor-cache-updater -f

# Screen
screen -r sensor-cache
```

Expected log output:
```
2025-12-17 10:30:00 [INFO] 🚀 Starting Sensor Cache Updater Service
2025-12-17 10:30:00 [INFO] Update interval: 30 seconds
2025-12-17 10:30:00 [INFO] --- Iteration 1 ---
2025-12-17 10:30:03 [INFO] ✅ Updated 39 trucks, 0 errors
2025-12-17 10:30:03 [INFO] Update completed in 2.85s
2025-12-17 10:30:30 [INFO] --- Iteration 2 ---
...
```

## Monitoring

### Key Metrics

1. **Update frequency**: Should update every 30 seconds
2. **Update duration**: Should complete in 2-5 seconds for 39 trucks
3. **Error count**: Should be 0 or very low
4. **Data age**: Should be < 60 seconds for active trucks

### Check data freshness:

```sql
SELECT 
    COUNT(*) as total_trucks,
    AVG(data_age_seconds) as avg_age_sec,
    MAX(data_age_seconds) as max_age_sec,
    COUNT(CASE WHEN data_age_seconds < 60 THEN 1 END) as fresh_data_count
FROM truck_sensors_cache;
```

### Troubleshooting

**Problem: Cache not updating**
```bash
# Check service status
sudo systemctl status sensor-cache-updater

# Check if process is running
ps aux | grep sensor_cache_updater

# Check database connection
mysql -u fuel_admin -p fuel_copilot -e "SELECT 1;"
```

**Problem: Data age too high (> 300 seconds)**
- Check Wialon database connectivity
- Check if trucks are actually sending data
- Verify tanks.yaml has correct unit_id mappings

**Problem: High error count**
- Check logs for specific error messages
- Verify Wialon credentials in .env file
- Check network connectivity to Wialon server

## Maintenance

### Update truck configuration

When adding/removing trucks in `tanks.yaml`, the service will automatically pick up changes on the next iteration (30 seconds).

### Restart service

```bash
sudo systemctl restart sensor-cache-updater
```

### Clean old data (optional)

The cache table only stores the latest snapshot for each truck. No cleanup needed.

### Performance tuning

To change update interval, edit `sensor_cache_updater.py`:

```python
UPDATE_INTERVAL = 30  # seconds (increase to reduce load)
```

## Rollback Plan

If issues occur, revert to direct Wialon queries:

1. Stop the cache updater service:
   ```bash
   sudo systemctl stop sensor-cache-updater
   ```

2. Revert API endpoint changes (use previous git commit)

3. Restart API service

The old endpoint code is still available in git history (commit before 3c4d66b).
