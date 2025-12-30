# 📂 Estructura del Proyecto - Fuel Copilot Backend

## 🗂️ Organización de Directorios

```
Fuel-Analytics-Backend/
│
├── 📁 Core Application Files (raíz)
│   ├── main.py                          # Entry point del API (FastAPI/Uvicorn)
│   ├── api_v2.py                        # API endpoints principales
│   ├── wialon_sync_enhanced.py          # Servicio de sync Wialon → MySQL
│   ├── database.py, database_mysql.py   # Conexiones y queries a MySQL
│   ├── estimator.py                     # Kalman filter para fuel estimation
│   ├── requirements.txt                 # Python dependencies
│   └── .env                             # Variables de entorno (NO commiteado)
│
├── 📁 docs/                             # 📚 Documentación completa
│   ├── deployment/                      # Guías de deploy (VM, staging, prod)
│   ├── testing/                         # Reportes de testing y coverage
│   ├── audit/                           # Auditorías y análisis de código
│   └── implementation/                  # Documentos de implementación features
│
├── 📁 scripts/                          # 🔧 Scripts utilitarios
│   ├── database/                        # Migrations, fixes, schema updates
│   ├── diagnostics/                     # Scripts de análisis y debug
│   ├── deployment/                      # Scripts de deploy e instalación
│   └── maintenance/                     # Cleanup, reset, auto-updates
│
├── 📁 tests/                            # ✅ Test suite completo
│   ├── fixtures/                        # Test fixtures y mocks
│   └── async/                           # Tests de async endpoints
│
├── 📁 services/                         # 🚀 Service launchers (24/7)
│   ├── com.fuelanalytics.backend.plist  # macOS LaunchAgent - API
│   ├── com.fuelanalytics.wialon.plist   # macOS LaunchAgent - Wialon Sync
│   └── README.md                        # Instrucciones de servicios
│
├── 📁 archive/                          # 🗄️ Archivos históricos (NO commiteado)
│   ├── backups/                         # SQL backups, code backups
│   ├── old_tests/                       # Tests deprecados
│   └── deprecated/                      # Código legacy (.bak, .old)
│
├── 📁 data/                             # 💾 Runtime data
│   ├── mpg_states.json                  # Estados Kalman por truck
│   ├── sensor_issues.json               # Registro de issues de sensores
│   └── predictive_maintenance_state.json
│
├── 📁 cache/                            # ⚡ Cache files
│   └── fleet_sensors.json               # Cache de sensores Wialon
│
├── 📁 logs/                             # 📝 Application logs
│   ├── api.log                          # API requests/responses
│   ├── wialon_sync.log                  # Wialon sync activity
│   └── backend.log                      # General backend logs
│
└── 📁 migrations/                       # 🗃️ Database migrations
    └── SQL scripts para schema updates

```

## 🎯 Core Python Modules (Root Directory)

### **APIs y Endpoints**
- `main.py` - Entry point, FastAPI app initialization
- `api_v2.py` - REST API endpoints (trucks, metrics, alerts, DTC)
- `api_middleware.py` - CORS, rate limiting, auth middleware
- `routers.py` - Route definitions

### **Data Sync & Processing**
- `wialon_sync_enhanced.py` - Main sync service (Wialon → MySQL)
- `wialon_reader.py` - Wialon API client wrapper
- `database_mysql.py` - MySQL connection pool y queries
- `database_enhanced.py` - Enhanced DB operations con retry logic

### **Fuel Analytics Core**
- `estimator.py` - Extended Kalman Filter (fuel level/MPG)
- `mpg_engine.py` - MPG calculation engine
- `refuel_prediction.py` - Refuel detection algorithms

### **Monitoring & Alerts**
- `alert_service.py` - Alert generation y notification engine
- `fleet_command_center.py` - Fleet-wide analytics y anomaly detection
- `predictive_maintenance_engine.py` - Predictive maintenance models

### **DTC & Diagnostics**
- `dtc_analyzer.py` - DTC code parsing y analysis
- `dtc_database.py` - SPN/FMI database lookup
- `spn_decoder.py` - SAE J1939 SPN decoder

### **Driver Behavior**
- `driver_behavior_engine.py` - Driver scoring algorithms
- `driver_scoring_engine.py` - Gamification y leaderboards

### **Utilities**
- `config.py` - Configuration management
- `logger_config.py` - Structured logging setup
- `auth.py` - API authentication/authorization
- `cache_service.py` - Redis/memory caching

## 📚 Documentation Organization

### `docs/deployment/`
- Deployment guides (VM, staging, production)
- Service configuration (systemd, launchd)
- Database setup instructions

### `docs/testing/`
- Test coverage reports
- E2E testing summaries
- Performance benchmarks

### `docs/audit/`
- Code audits (security, performance)
- Sensor mapping analyses
- Database schema reviews

### `docs/implementation/`
- Feature implementation reports
- Algorithm improvements documentation
- Integration guides (Kalman, DTC, ML)

## 🔧 Scripts Organization

### `scripts/database/`
- `add_*.sql` - Schema additions (columns, tables)
- `migrate_*.py` - Data migrations
- `create_*.sql` - Table creation scripts
- `fix_*.sql` - Schema fixes

### `scripts/diagnostics/`
- `check_*.py` - Health checks (sensors, DB, services)
- `analyze_*.py` - Data analysis scripts
- `diagnose_*.py` - Problem diagnosis tools
- `debug_*.py` - Debug utilities

### `scripts/deployment/`
- `deploy_*.sh` - Deployment automation
- `install_*.sh` - Service installation
- `quick_*.sh` - Quick start/stop scripts

### `scripts/maintenance/`
- `cleanup_*.py` - Data cleanup utilities
- `reset_*.py` - State reset scripts
- `auto_*.py` - Automated maintenance tasks

## 🚀 Quick Start

```bash
# 1. Instalar dependencias
pip install -r requirements.txt

# 2. Configurar variables de entorno
cp .env.example .env
# Editar .env con credenciales correctas

# 3. Iniciar servicios
cd services && ./install_services.sh

# 4. Verificar estado
./services/status.sh
```

## 📊 Testing

```bash
# Run all tests
pytest tests/

# Coverage report
pytest --cov=. --cov-report=html tests/
```

## 🔗 Related Projects

- **Frontend:** [fuel-copilot-staging-frontend](https://github.com/ruiztomas88/fuel-copilot-staging-frontend)
- **Backend:** [fuel-copilot-staging-backend](https://github.com/ruiztomas88/fuel-copilot-staging-backend)
