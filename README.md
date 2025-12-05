# Fuel Analytics Backend

FastAPI backend for Fuel Copilot Dashboard v3.12.27

## Features

- Real-time fleet monitoring
- Fuel consumption analytics
- Refuel detection with anti-noise filtering
- **Intelligent Fuel Event Classification** - Differentiates theft from sensor issues using recovery detection
- **Truck Health Monitoring** - Statistical sensor analysis with Nelson Rules
- **ML Predictions** - Fuel consumption forecasting
- **Customizable Dashboard** - Personalized widget layouts
- **GPS Tracking** - Real-time truck positions with geofencing
- **Push Notifications** - Alert system with subscription management
- **Scheduled Reports** - Automated report generation
- JWT Authentication
- Role-based Rate Limiting

## Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
.\venv\Scripts\Activate.ps1  # Windows

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your database credentials

# Run
uvicorn main:app --host 0.0.0.0 --port 8000
```

## Environment Variables

```env
MYSQL_HOST=20.127.200.135
MYSQL_PORT=3306
MYSQL_USER=tomas
MYSQL_PASSWORD=Tomas2025
MYSQL_DATABASE=wialon_collect

# Fuel Event Classification (new in v3.12.27)
RECOVERY_WINDOW_MINUTES=10      # Time window to check for fuel recovery
RECOVERY_TOLERANCE_PCT=5.0      # Tolerance % for recovery detection
DROP_THRESHOLD_PCT=10.0         # Minimum drop to consider significant
REFUEL_THRESHOLD_PCT=8.0        # Minimum increase to detect refuel
SENSOR_VOLATILITY_THRESHOLD=8.0 # Max volatility for sensor issues
```

## API Documentation

Once running, access Swagger docs at:
- http://localhost:8000/docs
- http://localhost:8000/fuelanalytics/docs (with prefix)

## Testing

```bash
# Run all tests
python -m pytest tests/ -v

# Run with coverage
python -m pytest tests/ --cov=. --cov-report=html

# Run specific test file
python -m pytest tests/test_api_middleware.py -v
```

## Changelog

### v3.12.27 (Intelligent Fuel Event Classification)

#### New Features
- **Fuel Event Classifier** (`alert_service.py`): New `FuelEventClassifier` class that intelligently differentiates between:
  - `THEFT_CONFIRMED` - Real fuel theft (no recovery within time window)
  - `SENSOR_ISSUE` - Fuel sensor malfunction (fuel recovers within 10-15 min)
  - `THEFT_SUSPECTED` - Pending evaluation (waiting for recovery window)
  - `REFUEL` - Normal fuel addition

- **Recovery Detection** (`database_mysql.py`): Enhanced `get_fuel_theft_analysis()` with SQL LEAD columns to check next 3 readings:
  - Detects fuel recovery within configurable time window
  - Returns `recovered`, `recovery_to_pct`, `recovery_time_min` fields
  - Automatically classifies events as SENSOR_ISSUE when fuel recovers

- **Differentiated Alerting**:
  - `THEFT_CONFIRMED`: SMS + Email with urgent priority
  - `SENSOR_ISSUE`: Email-only notification (not urgent)
  - Different message templates for each event type

#### Configuration
New `.env` variables for fine-tuning classification:
```env
RECOVERY_WINDOW_MINUTES=10
RECOVERY_TOLERANCE_PCT=5.0
DROP_THRESHOLD_PCT=10.0
SENSOR_VOLATILITY_THRESHOLD=8.0
```

#### Frontend Updates (Fuel-Analytics-Frontend)
- **RefuelsAdvanced.tsx**: Visual differentiation for event types
  - SENSOR_ISSUE shows blue badge instead of red
  - "🔧 Recuperado → X%" text for recovered events
  - Faded opacity (60%) for sensor issues
- **LanguageContext.tsx**: Added 26 missing translations for security tab

#### Bug Fixes
- Fixed false positive theft alerts (e.g., DO9356) that were actually sensor glitches
- Fixed missing translation keys: `refuelsAdv.whyItMatters`, `refuelsAdv.potentialLoss`, etc.

---

### v3.12.21 (Phase 3-4 Complete)

#### New Features
- **#11 Dashboard Customization**: Personalized widget layouts per user
- **#12 Historical Comparison**: Compare metrics between time periods
- **#13 Scheduled Reports**: Automated report generation and delivery
- **#14 Role-based Rate Limiting**: Different limits for admin/viewer/anonymous
- **#17 GPS Tracking**: Real-time positions and geofencing
- **#19 Push Notifications**: Subscription-based alert system

#### Code Improvements
- **#7 Database Module Consolidation**: New `db/__init__.py` unifies all database handlers
- **#8 Dead Code Removal**: Removed unused TODO comments and implemented pending features
- **#9 Centralized Error Handling**: New `errors.py` with custom exceptions and handlers

#### Testing
- 305+ tests passing
- New test files:
  - `test_dashboard_endpoints.py` (14 tests)
  - `test_gps_notifications.py` (15 tests)

### v3.12.20 (Phase 1-2 Complete)

#### Bug Fixes (Phase 1)
- #1 Fixed alert field names (idle_gph → consumption_gph)
- #2 Fixed fleet diff field (trucks → truck_details)
- #3 Removed duplicate endpoints
- #4 Fixed async test configuration
- #5 Fixed deprecated Config class in Pydantic models
- #6 Fixed lifespan handler deprecation

#### New Features (Phase 2)
- ML-based fuel consumption predictions
- Excel/CSV export functionality
- SMS alerts integration
- Fuel theft detection algorithm

## API Endpoints

### Fleet & Analytics
- `GET /fuelAnalytics/api/fleet` - Fleet summary
- `GET /fuelAnalytics/api/trucks/{truck_id}` - Truck details
- `GET /fuelAnalytics/api/efficiency` - Efficiency rankings
- `GET /fuelAnalytics/api/analytics/historical-comparison` - Period comparison

### Dashboard & Preferences
- `GET /fuelAnalytics/api/dashboard/widgets/available` - Available widgets
- `GET/POST /fuelAnalytics/api/dashboard/layout/{user_id}` - Dashboard layout
- `GET/PUT /fuelAnalytics/api/user/preferences/{user_id}` - User preferences

### GPS Tracking
- `GET /fuelAnalytics/api/gps/trucks` - All truck positions
- `GET /fuelAnalytics/api/gps/truck/{truck_id}/history` - Route history
- `GET/POST /fuelAnalytics/api/gps/geofence` - Geofence management

### Notifications
- `POST /fuelAnalytics/api/notifications/subscribe` - Push subscription
- `GET /fuelAnalytics/api/notifications/{user_id}` - User notifications
- `POST /fuelAnalytics/api/notifications/send` - Send notification

### Reports
- `GET /fuelAnalytics/api/reports/scheduled/{user_id}` - Scheduled reports
- `POST /fuelAnalytics/api/reports/schedule` - Create scheduled report
- `POST /fuelAnalytics/api/reports/run/{report_id}` - Run report now

## Architecture

```
Backend/
├── main.py              # FastAPI app with all endpoints
├── models.py            # Pydantic models for validation
├── errors.py            # Centralized error handling
├── auth.py              # JWT authentication
├── api_middleware.py    # Rate limiting, security headers
├── database.py          # CSV/MySQL database handler
├── database_mysql.py    # MySQL-specific operations (theft analysis with recovery detection)
├── database_enhanced.py # Advanced MySQL features
├── db/                  # Unified database module
│   └── __init__.py
├── alert_service.py     # FuelEventClassifier + SMS/Email alerts
├── mpg_engine.py        # MPG calculation engine
├── idle_engine.py       # Idle detection
├── estimator.py         # Fuel level estimation
├── truck_health_monitor.py # Nelson Rules health monitoring
├── wialon_reader.py     # Wialon API integration
├── wialon_sync_enhanced.py # Sync service with event classification
└── tests/               # 319+ unit tests
```

## Fuel Event Classification Flow

```
┌─────────────────────┐
│   Wialon Sync       │
│   (wialon_sync_     │
│    enhanced.py)     │
└─────────┬───────────┘
          │ fuel drop detected
          ▼
┌─────────────────────┐
│  FuelEventClassifier│
│  (alert_service.py) │
└─────────┬───────────┘
          │
    ┌─────┴─────┐
    │           │
    ▼           ▼
┌────────┐  ┌────────────┐
│PENDING │  │IMMEDIATE   │
│BUFFER  │  │REFUEL      │
└────┬───┘  └────────────┘
     │ wait recovery window
     ▼
┌─────────────────────┐
│ Check Recovery      │
│ (SQL LEAD columns)  │
└─────────┬───────────┘
          │
    ┌─────┴─────┐
    │           │
    ▼           ▼
┌─────────┐  ┌────────────┐
│RECOVERED│  │NO RECOVERY │
│→SENSOR  │  │→THEFT      │
│ ISSUE   │  │ CONFIRMED  │
└─────────┘  └────────────┘
```

## License

MIT

