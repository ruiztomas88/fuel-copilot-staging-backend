# Fuel Copilot Backend

FastAPI backend for Fuel Copilot Fleet Management Dashboard.

Designed to run on Azure VM Windows with reverse proxy from fleetbooster.net.

## Quick Start

### Windows (Azure VM)
```powershell
.\start.bat
```

### Linux/Mac
```bash
chmod +x start.sh
./start.sh
```

## Configuration

Copy `.env.example` to `.env` and configure:

```env
HOST=0.0.0.0
PORT=8000
MYSQL_HOST=20.127.200.135
MYSQL_USER=tomas
MYSQL_PASSWORD=your-password
MYSQL_DATABASE=fuel_copilot
```

## API Documentation

Once running, access:
- Swagger UI: http://localhost:8000/fuelanalytics/docs
- ReDoc: http://localhost:8000/fuelanalytics/redoc

## Endpoints

All endpoints are prefixed with `/fuelanalytics`:

| Endpoint | Description |
|----------|-------------|
| `/fuelanalytics/api/fleet` | Fleet summary |
| `/fuelanalytics/api/trucks` | List trucks |
| `/fuelanalytics/api/trucks/{id}` | Truck details |
| `/fuelanalytics/api/efficiency` | Efficiency rankings |
| `/fuelanalytics/api/alerts` | Active alerts |
| `/fuelanalytics/api/kpis` | KPI metrics |
| `/fuelanalytics/api/refuels` | Refuel events |
| `/fuelanalytics/api/auth/login` | Authentication |
| `/fuelanalytics/api/analytics/*` | Advanced analytics |

## Project Structure

```
fuel-copilot-backend/
├── main.py              # FastAPI app entry point
├── requirements.txt     # Python dependencies
├── .env.example         # Environment template
├── start.bat            # Windows startup script
├── start.sh             # Linux/Mac startup script
└── routers/
    ├── fleet.py         # Fleet endpoints
    ├── trucks.py        # Truck endpoints
    ├── efficiency.py    # Efficiency endpoints
    ├── alerts.py        # Alert endpoints
    ├── kpis.py          # KPI endpoints
    ├── refuels.py       # Refuel endpoints
    ├── analytics.py     # Analytics endpoints
    ├── auth.py          # Authentication
    └── admin.py         # Admin endpoints
```

## Integration with fleetbooster.net

This backend is designed to run behind a reverse proxy:

```
https://fleetbooster.net/fuelanalytics/* → http://172.210.11.234:8000/fuelanalytics/*
```

The reverse proxy handles SSL termination.
