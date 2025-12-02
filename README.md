# Fuel Analytics Backend

FastAPI backend for Fuel Copilot Dashboard v3.12.0

## Features

- Real-time fleet monitoring
- Fuel consumption analytics
- Refuel detection with anti-noise filtering
- **Truck Health Monitoring** (NEW) - Statistical sensor analysis with Nelson Rules
- JWT Authentication
- WebSocket support

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
