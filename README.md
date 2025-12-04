# Fuel Analytics Backend

FastAPI backend for Fuel Copilot Dashboard v3.12.21

## Features

- Real-time fleet monitoring
- Fuel consumption analytics
- Refuel detection with anti-noise filtering
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
├── database_mysql.py    # MySQL-specific operations
├── database_enhanced.py # Advanced MySQL features
├── db/                  # Unified database module
│   └── __init__.py
├── mpg_engine.py        # MPG calculation engine
├── idle_engine.py       # Idle detection
├── estimator.py         # Fuel level estimation
├── truck_health_monitor.py # Nelson Rules health monitoring
├── wialon_reader.py     # Wialon API integration
└── tests/               # 319+ unit tests
```

## License

MIT

