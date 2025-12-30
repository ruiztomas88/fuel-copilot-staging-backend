# FleetBooster Integration Status - Dec 30, 2025

## ✅ Stack Status
- **Backend API**: Running on http://0.0.0.0:8000
- **Frontend**: Running on http://localhost:3000
- **Wialon Sync**: Running in background (PID in nohup)

## 🚀 Integration Features

### 1. Fuel Level Updates
**Endpoint**: `https://fleetbooster.net/fuel/send_push_notification`
**Frequency**: Every 60 seconds per truck
**Method**: POST (changed from PUT)

#### ✅ Successfully Sending:
- **PC1280**: ✓ Fuel updated (30.4%, 60.9 gal, kalman)

#### ⚠️ Trucks Without Tokens (HTTP 404):
- RH1522, GP9677, CO0681, MR7679, DR6664, FM3363, JP3281, NQ6975, etc.

**Payload Structure:**
```json
{
  "user": "",
  "unitId": "PC1280",
  "title": "Fuel Level Update",
  "body": "Tank at 30.4%, 60.9 gallons (kalman)",
  "data": {
    "type": "fuel_update",
    "screen": "fuel",
    "unitId": "PC1280",
    "fuel_pct": 30.4,
    "fuel_gallons": 60.9,
    "fuel_liters": 230.5,
    "fuel_source": "kalman",
    "timestamp": "2025-12-30T08:37:57"
  }
}
```

### 2. DTC Alerts
**Endpoint**: `https://fleetbooster.net/fuel/send_push_notification`
**Method**: POST
**Trigger**: When new DTC codes are detected

#### ✅ Processing:
- **JB6858**: Processing 1 DTC(s): 3226.4 (SPN 3226 FMI 4)

**Payload Structure:**
```json
{
  "user": "",
  "unitId": "JB6858",
  "title": "⚠️ WARNING: Engine Alert",
  "body": "DTC 3226.4 detected on JB6858: [Spanish description]",
  "data": {
    "type": "dtc_alert",
    "screen": "alerts",
    "unitId": "JB6858",
    "dtc_code": "3226.4",
    "description": "Spanish DTC description from FuelCopilotDTCHandler",
    "severity": "WARNING",
    "system": "Engine",
    "timestamp": "2025-12-30T08:37:59"
  }
}
```

## 📊 Rate Limiting
- **Fuel Updates**: Once per 60 seconds per truck
- **DTC Alerts**: Only sent when DTC changes (deduplication)

## 🔧 Code References
- Integration code: `fleetbooster_integration.py`
- Wialon sync: `wialon_sync_enhanced.py` (lines 80, 3395-3437, 3634)
- Alert service: `alert_service.py`

## ⚠️ Known Issues
1. **Missing Tokens**: Many trucks return 404 error - need to register tokens in FleetBooster
2. **Empty User Field**: `FLEETBOOSTER_USER = ""` as instructed by uncle

## 🎯 Next Steps
To enable more trucks:
1. Register truck tokens in FleetBooster backend
2. Verify token mapping for each truck_id
3. Monitor logs for successful deliveries

## 📝 Log Monitoring
```bash
# Monitor FleetBooster messages in real-time
tail -f wialon_sync.log | grep FLEETBOOSTER

# See successful sends only
grep "FLEETBOOSTER.*✓" wialon_sync.log

# See DTC processing
grep "DTC" wialon_sync.log
```
