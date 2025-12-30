# 📋 CHANGELOG - Fuel Copilot Staging Environment

> Registro completo de todos los cambios, mejoras y features desde la creación del entorno de staging.

---

## 🚀 DEC 30, 2025 - Repository Organization & Production Sync

### Database
- 📦 **Database Backup**: Export completo de `fuel_copilot_local` subido a GitHub (3.7MB comprimido)

### Repository Structure  
- 🗂️ **Reorganización masiva**: 500+ archivos movidos a estructura organizada
  - `docs/` - Toda la documentación (.md files)
  - `scripts/database/` - Migraciones y scripts de schema
  - `scripts/diagnostics/` - Scripts de diagnóstico y análisis
  - `scripts/deployment/` - Scripts de deploy e instalación
  - `scripts/maintenance/` - Scripts de limpieza y reset
  - `tests/` - Suite de tests
  - `ml_engines/` - A/B testing, anomaly detection, benchmarks
  - `archive/` - Backups, logs, archivos temporales (gitignored)

### MPG Engine Sync with Production
- 🔧 **MPGConfig actualizado** para coincidir con producción:
  - `min_fuel_gal`: 1.5 → **2.5** (requiere más consumo para calcular MPG)
  - `ema_alpha`: 0.25 → **0.20** (suavizado más conservador)

### Bug Fixes
- 🐛 **Import Errors**: Corregidos todos los imports después de reorganización
  - `ml_engines.adaptive_refuel_thresholds`
  - `ml_engines.anomaly_detection_v2`
- 🧹 **Python Cache**: Limpieza de `__pycache__` para evitar imports obsoletos

---

## 🔧 DEC 30, 2025 - GitHub Staging Repos Setup

### Infrastructure
- 🌐 **GitHub Repos Creados**:
  - Backend: `ruiztomas88/fuel-copilot-staging-backend`
  - Frontend: `ruiztomas88/fuel-copilot-staging-frontend`
- 🔗 Configuración de remotes y push inicial

---

## 🚀 DEC 29-30, 2025 - fuel_lvl Sensor Fix & Sensor Mappings

### Critical Fix
- 🔧 **fuel_lvl Conversion**: Descubierto que `fuel_lvl` de Wialon retorna **GALONES** no porcentaje
  - Fix aplicado en `wialon_sync_enhanced.py`
  - Ahora convierte correctamente: `fuel_pct = (fuel_lvl / tank_capacity) * 100`

### Sensor Mappings
- 📊 **Nuevos sensores mapeados** en `wialon_reader.py`:
  - `oil_lvl` - Nivel de aceite (%)
  - `gear` - Marcha actual
  - `barometer` - Presión barométrica
  - `intk_t` → `ambient_temp_f` - Temperatura ambiente
  - `pto_hours` - Horas de PTO

---

## 🏗️ DEC 27-28, 2025 - Advanced Services Implementation

### Repository-Service-Orchestrator Architecture
- ✅ **FASE 11 COMPLETE**: Arquitectura RSO implementada
- 📋 Commits 190h + 245h extraídos y documentados

### Testing Infrastructure
- 🧪 **Playwright E2E Tests**: Configuración completa
- 📊 **Coverage Reports**: 56%+ baseline establecido

---

## 🔐 DEC 22-26, 2025 - Security & Audit Fixes

### Security Updates (v7.0.0)
- 🔐 **Rate Limiting**: Implementado en todos los endpoints
- 🔐 **API Key Auth**: Sistema de autenticación mejorado
- 🔐 **CORS**: Configuración segura

### Audit Fixes
- ✅ 7 bugs P0/P1 resueltos
- ✅ 26 bugs identificados y categorizados (4 P0, 5 P1, 7 P2, 10 P3)
- 📋 Auditoría completa documentada

### MPG Fixes
- 🔧 **MPG V2.0 Redesign**:
  - Max MPG: 8.5
  - Hierarchical sensors
  - GPS validation
- 🔧 Thresholds conservadores restaurados: 8.0mi/1.2gal

---

## ⚡ DEC 19-21, 2025 - Quick Wins Implementation

### Adaptive Thresholds
- 🎯 **Per-truck calibration** basada en histórico
- 🎯 **Confidence Scoring** para detección de refuels

### Smart Notifications
- 📱 **Rate limiting** de alertas a 24hrs (excepto refuels)
- 📱 **Alertas agrupadas** para evitar spam

### Sensor Health Monitor
- 🏥 **Monitoreo continuo** de salud de sensores
- 🏥 **Auto-detección** de sensores defectuosos

---

## 🧠 DEC 17-18, 2025 - ML & Predictive Features

### Predictive Maintenance Engine
- 🔮 **Weibull TTF**: Time-to-failure predictions
- 🔮 **Trend-Based Predictions**: Análisis de tendencias
- 🔮 **RUL Predictor**: Remaining Useful Life

### Anomaly Detection
- 🔍 **Slow Siphoning Detector**: Detecta robos lentos
- 🔍 **MPG Context Engine**: Contexto para valores anómalos
- 🔍 **DTW Pattern Analyzer**: Análisis de patrones

### Kalman Filter Improvements
- 📈 **Conservative Q_r**: Mejor estimación de ruido
- 📈 **Resync Cooldown**: Evita oscilaciones
- 📈 **Innovation-based K**: Ganancia adaptativa

---

## 🚛 DEC 15-16, 2025 - Fleet Command Center

### Command Center v1.5.0
- 🎛️ **Unified Dashboard**: Vista consolidada de flota
- 🎛️ **Caching & Trend Tracking**: Performance optimizado
- 🎛️ **Database Alerts**: engine_health, dtc_events

### Driver Behavior Engine
- 👨‍✈️ **Behavior Detection**: Detección de comportamiento
- 👨‍✈️ **Coaching Tips**: Consejos personalizados
- 👨‍✈️ **Score History**: Historial de puntuaciones

---

## 🔧 DEC 12-14, 2025 - Sensor & Database Fixes

### Sensor Mapping Fixes
- ✅ **28 nuevos SPNs** agregados desde J1939 estándar
- ✅ **Universal Sensor Fix**: Todos los sensores Wialon soportados
- ✅ **Deep Search**: Búsqueda extendida hasta 48h para sensores lentos

### Database Schema
- 📊 **34 tablas** replicadas desde DB histórica
- 📊 **truck_sensors_cache**: Nueva tabla con 16+ columnas de sensores
- 📊 **Indexes optimizados** para performance

---

## 🚀 DEC 8-11, 2025 - API v2 & Performance

### API Versioning
- 🔀 **API v2**: Nueva versión con mejores responses
- 🔀 **Router Migration**: Endpoints modulares

### Performance Improvements
- ⚡ **Redis Caching**: Distributed caching
- ⚡ **Connection Pooling**: MySQL pool optimizado
- ⚡ **Rate Limiting**: Protección contra abuse

### Theft Detection v4.1.0
- 🔒 **Multi-factor Detection**: Speed gating, geofence, patterns
- 🔒 **80% FP Reduction**: Menos falsos positivos
- 🔒 **Safe-zone Detection**: Geofences para confianza

---

## 📊 DEC 5-7, 2025 - Analytics & Dashboards

### Cost Per Mile Engine
- 💰 **Real-time Cost Calculation**: Costo por milla actualizado
- 💰 **Fleet Utilization**: Métricas de utilización

### Loss Analysis V2
- 📉 **ROI & Enhanced Insights**: Análisis de pérdidas mejorado
- 📉 **Per-Truck Refuel Calibration**: Calibración individual

### Sensor Health Dashboard
- 🏥 **Voltage Trending**: Historial de voltaje
- 🏥 **GPS Quality**: Calidad de señal GPS
- 🏥 **Idle Validation**: Validación contra ECU

---

## 🛠️ DEC 1-4, 2025 - Infrastructure & Services

### Windows VM Deployment
- 🖥️ **NSSM Services**: Servicios Windows configurados
- 🖥️ **PowerShell Scripts**: Automatización de deploy
- 🖥️ **Auto-restart**: Recuperación automática

### Wialon Integration
- 🔄 **wialon_sync_enhanced.py**: Sincronización mejorada
- 🔄 **Trips, Speeding, Driver Behavior**: Nuevos datos sincronizados
- 🔄 **sensor_cache_updater**: Actualización cada 30s

---

## 🎯 NOV 25-30, 2025 - Core Features

### Refuel Detection
- ⛽ **Improved Detection**: Thresholds ajustados
- ⛽ **Duplicate Prevention**: Evita inserts duplicados
- ⛽ **SMS/Email Notifications**: Alertas automáticas

### DTC Management
- 🔧 **Spanish Descriptions**: DTCs en español
- 🔧 **J1939 Database**: 200+ códigos soportados
- 🔧 **SPN/FMI Parsing**: Decodificación completa

### Gamification
- 🏆 **Driver Leaderboard**: Rankings de conductores
- 🏆 **Fleet Score**: Puntuación de flota
- 🏆 **Efficiency Metrics**: Métricas de eficiencia

---

## 📦 Initial Setup - NOV 2025

### Base Infrastructure
- 🏗️ **Backend Framework**: FastAPI + MySQL
- 🏗️ **Kalman Filter**: Estimación de consumo
- 🏗️ **Wialon Reader**: Lectura de datos telemáticos

### Core Tables
- `fuel_metrics` - Métricas de combustible
- `refuel_events` - Eventos de recarga
- `truck_history` - Historial de camiones
- `dtc_events` - Eventos de diagnóstico
- `truck_sensors_cache` - Cache de sensores

### Initial Trucks
- 🚛 43 camiones configurados en `tanks.yaml`
- 🚛 Unit IDs mapeados desde Wialon

---

## 📊 Statistics Summary

| Metric | Value |
|--------|-------|
| Total Commits | 300+ |
| Features Added | 50+ |
| Bugs Fixed | 100+ |
| Tables Created | 34 |
| Endpoints | 80+ |
| Test Coverage | 56%+ |
| Trucks Monitored | 43 |

---

## 🔗 Quick Links

- **Backend Repo**: https://github.com/ruiztomas88/fuel-copilot-staging-backend
- **Frontend Repo**: https://github.com/ruiztomas88/fuel-copilot-staging-frontend
- **Structure Doc**: [STRUCTURE.md](STRUCTURE.md)

---

*Last Updated: December 30, 2025*
