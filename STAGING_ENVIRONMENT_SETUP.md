# 🧪 STAGING ENVIRONMENT SETUP
**Propósito:** Testear todas las features nuevas en ambiente idéntico a producción ANTES de deployment

---

## 🎯 CONCEPTO

```
┌─────────────────┐         ┌─────────────────┐
│   PRODUCCIÓN    │         │    STAGING      │
│                 │         │                 │
│ ✅ Código estable│         │ 🧪 Features nuevas│
│ ✅ Datos reales │         │ ✅ Datos reales │
│ ✅ 24/7 uptime  │         │ ⚙️  Testing safe│
└─────────────────┘         └─────────────────┘
        ↑                            │
        │                            │
        └────── Deploy solo si ──────┘
                tests pasan 100%
```

**Beneficios:**
- ✅ Testear con datos reales sin riesgo
- ✅ Detectar bugs antes de afectar producción  
- ✅ Validar performance con carga real
- ✅ Rollback instantáneo si algo falla
- ✅ Stakeholders pueden ver features antes de release

---

## 🏗️ ARQUITECTURA PROPUESTA

### Opción A: VM Separada para Staging (RECOMENDADO)
```
VM Producción (20.127.200.135)     VM Staging (nueva)
├── Backend (puerto 8001)          ├── Backend (puerto 8001)
├── WialonSync service             ├── WialonSync service  
├── MySQL local (fuel_copilot)     ├── MySQL local (fuel_copilot_staging)
└── Wialon DB (remoto, read-only)  └── Wialon DB (MISMO remoto, read-only)
                                   
Frontend Producción                Frontend Staging
├── fuelanalytics.fleetbooster.net ├── staging.fuelanalytics.fleetbooster.net
└── API: fleetbooster.net/fuel...  └── API: staging.fleetbooster.net/fuel...
```

### Opción B: Mismo VM, Puertos Diferentes (más barato)
```
VM (20.127.200.135)
├── PRODUCCIÓN
│   ├── Backend puerto 8001
│   ├── MySQL fuel_copilot
│   └── Servicios: FuelAnalytics-API, FuelAnalytics-WialonSync
│
└── STAGING
    ├── Backend puerto 8002  
    ├── MySQL fuel_copilot_staging
    └── Servicios: FuelAnalytics-API-Staging, FuelAnalytics-WialonSync-Staging
```

**Para esta guía, usaremos Opción B (mismo VM, DBs separadas)**

---

## 📋 PASO A PASO: SETUP STAGING

### PASO 1: Crear Base de Datos Staging (5 min)

```powershell
# En VM: Crear DB staging vacía
$env:MYSQL_PWD='FuelCopilot2025!'
mysql -u fuel_admin -e "CREATE DATABASE fuel_copilot_staging CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"

# Copiar estructura de producción (SIN datos, solo schema)
mysql -u fuel_admin fuel_copilot -e "SHOW CREATE TABLE fuel_metrics\G" | 
  mysql -u fuel_admin fuel_copilot_staging

mysql -u fuel_admin fuel_copilot -e "SHOW CREATE TABLE refuel_events\G" | 
  mysql -u fuel_admin fuel_copilot_staging

mysql -u fuel_admin fuel_copilot -e "SHOW CREATE TABLE trucks\G" | 
  mysql -u fuel_admin fuel_copilot_staging

# Copiar últimos 7 días de datos para testing (opcional)
mysql -u fuel_admin fuel_copilot_staging -e "
  INSERT INTO fuel_metrics 
  SELECT * FROM fuel_copilot.fuel_metrics 
  WHERE timestamp_utc > DATE_SUB(NOW(), INTERVAL 7 DAY);
"

# Copiar trucks catalog
mysql -u fuel_admin fuel_copilot_staging -e "
  INSERT INTO trucks 
  SELECT * FROM fuel_copilot.trucks;
"
```

**Verificación:**
```sql
-- Debe mostrar las 3 tablas con datos recientes
USE fuel_copilot_staging;
SHOW TABLES;
SELECT COUNT(*) FROM fuel_metrics;
SELECT COUNT(*) FROM trucks;
```

---

### PASO 2: Clonar Backend a Directorio Staging (10 min)

```powershell
# En VM
cd C:\Users\devteam\Proyectos

# Clonar repo a nuevo directorio
git clone https://github.com/fleetbooster/Fuel-Analytics-Backend.git fuel-analytics-backend-staging

cd fuel-analytics-backend-staging

# Crear virtualenv separado
python -m venv venv_staging
.\venv_staging\Scripts\Activate.ps1

# Instalar dependencias
pip install -r requirements.txt
```

---

### PASO 3: Configurar .env para Staging (5 min)

```powershell
# Copiar .env de producción y modificar
cp ..\fuel-analytics-backend\.env .env.staging

# Editar .env.staging (cambiar solo estas líneas):
```

```bash
# .env.staging
# ============ DATABASE - STAGING ============
DB_HOST=localhost
DB_PORT=3306
DB_USER=fuel_admin
DB_PASSWORD=FuelCopilot2025!
DB_NAME=fuel_copilot_staging  # ← CAMBIO PRINCIPAL

# ============ API - STAGING ============
API_PORT=8002  # ← Diferente de producción (8001)
API_BASE_URL=http://20.127.200.135:8002

# ============ WIALON (mismo de producción) ============
WIALON_DB_HOST=20.127.200.135
WIALON_DB_PORT=3306
WIALON_DB_USER=consult_user
WIALON_DB_PASSWORD=C0nsult_2024!
WIALON_DB_NAME=wialon

# ============ ENVIRONMENT ============
ENVIRONMENT=staging  # ← Para identificar en logs

# ============ RESTO IGUAL ============
# (Twilio, SMTP, etc - mismo config)
```

---

### PASO 4: Crear Servicios de Windows para Staging (10 min)

```powershell
# Script para crear servicios staging
# Guardar como: setup_staging_services.ps1

$serviceName1 = "FuelAnalytics-API-Staging"
$serviceName2 = "FuelAnalytics-WialonSync-Staging"
$workingDir = "C:\Users\devteam\Proyectos\fuel-analytics-backend-staging"
$pythonExe = "$workingDir\venv_staging\Scripts\python.exe"

# Servicio 1: API Staging
nssm install $serviceName1 $pythonExe
nssm set $serviceName1 AppDirectory $workingDir
nssm set $serviceName1 AppParameters "api_v2.py"
nssm set $serviceName1 DisplayName "Fuel Analytics API - Staging"
nssm set $serviceName1 Description "API staging para testing de nuevas features"
nssm set $serviceName1 Start SERVICE_AUTO_START
nssm set $serviceName1 AppEnvironmentExtra "ENVIRONMENT=staging"
nssm set $serviceName1 AppStdout "$workingDir\logs\api-staging-stdout.log"
nssm set $serviceName1 AppStderr "$workingDir\logs\api-staging-stderr.log"

# Servicio 2: WialonSync Staging
nssm install $serviceName2 $pythonExe
nssm set $serviceName2 AppDirectory $workingDir
nssm set $serviceName2 AppParameters "wialon_sync_enhanced.py"
nssm set $serviceName2 DisplayName "Fuel Analytics Wialon Sync - Staging"
nssm set $serviceName2 Description "Sync service staging para testing"
nssm set $serviceName2 Start SERVICE_AUTO_START
nssm set $serviceName2 AppEnvironmentExtra "ENVIRONMENT=staging"
nssm set $serviceName2 AppStdout "$workingDir\logs\wialon-sync-staging-stdout.log"
nssm set $serviceName2 AppStderr "$workingDir\logs\wialon-sync-staging-stderr.log"

Write-Host "✅ Servicios staging creados!" -ForegroundColor Green
Write-Host "Iniciar con: Start-Service $serviceName1; Start-Service $serviceName2"
```

**Ejecutar:**
```powershell
# Crear carpeta logs
mkdir C:\Users\devteam\Proyectos\fuel-analytics-backend-staging\logs

# Ejecutar script (como Administrador)
.\setup_staging_services.ps1

# Iniciar servicios
Start-Service FuelAnalytics-API-Staging
Start-Service FuelAnalytics-WialonSync-Staging

# Verificar
Get-Service FuelAnalytics-*-Staging
```

---

### PASO 5: Clonar Frontend a Staging (10 min)

```bash
# En Mac (tu máquina de desarrollo)
cd ~/Desktop
cp -r Fuel-Analytics-Frontend Fuel-Analytics-Frontend-Staging

cd Fuel-Analytics-Frontend-Staging

# Modificar .env para apuntar a staging
```

```bash
# .env.staging
VITE_API_BASE_URL=http://20.127.200.135:8002
VITE_ENVIRONMENT=staging
```

```bash
# Instalar y correr localmente
npm install
npm run dev -- --port 5174  # Diferente del 5173 de producción
```

**O deployar a subdomain:**
```bash
# Si usas Azure Static Web Apps
# Crear nuevo Static Web App: staging-fuelanalytics

# Modificar staticwebapp.config.json
{
  "routes": [...],
  "navigationFallback": {
    "rewrite": "/index.html"
  },
  "globalHeaders": {
    "X-Environment": "Staging"
  }
}

# Deploy
npm run build
# Subir a staging-fuelanalytics.azurestaticapps.net
```

---

## 🔄 WORKFLOW DE DESARROLLO

### 1. Implementar Feature en Staging

```bash
# En Mac
cd ~/Desktop/Fuel-Analytics-Backend

# Crear feature branch
git checkout -b feature/benchmarking-engine

# Desarrollar feature
# - Escribir código
# - Escribir tests
# - Commit changes

git add .
git commit -m "feat: Implement benchmarking engine with tests"
git push origin feature/benchmarking-engine
```

---

### 2. Deploy a Staging para Testing

```powershell
# En VM
cd C:\Users\devteam\Proyectos\fuel-analytics-backend-staging

# Pull feature branch
git fetch origin
git checkout feature/benchmarking-engine
git pull origin feature/benchmarking-engine

# Restart servicios staging
Restart-Service FuelAnalytics-API-Staging
Restart-Service FuelAnalytics-WialonSync-Staging

# Monitorear logs
Get-Content logs\wialon-sync-staging-stderr.log -Tail 50 -Wait
```

---

### 3. Testing Completo en Staging

```bash
# Tests automatizados
cd ~/Desktop/Fuel-Analytics-Backend
pytest tests/ -v --cov=. --cov-report=html

# Tests de integración
pytest tests/integration/ -v

# Tests manuales en staging frontend
# Abrir: http://localhost:5174 (staging frontend)
# Verificar que API staging responde: http://20.127.200.135:8002/api/health
```

**Checklist de Testing:**
- [ ] Unit tests pasan 100%
- [ ] Integration tests pasan 100%
- [ ] Frontend staging conecta a backend staging
- [ ] Datos se ven correctos en dashboard
- [ ] No hay errores en logs (24h monitoring)
- [ ] Performance aceptable (queries <1s)
- [ ] Nueva feature funciona como esperado
- [ ] Código viejo sigue funcionando (no breaking changes)

---

### 4. Promoción a Producción (solo si tests pasan)

```bash
# Merge feature branch a main
git checkout main
git merge feature/benchmarking-engine
git push origin main

# Tag release
git tag v3.13.0
git push origin v3.13.0
```

```powershell
# En VM - Deploy a producción
cd C:\Users\devteam\Proyectos\fuel-analytics-backend

# Pull latest
git pull origin main

# Restart servicios PRODUCCIÓN
Restart-Service FuelAnalytics-API
Restart-Service FuelAnalytics-WialonSync

# Monitorear logs primeros 15 minutos
Get-Content logs\wialon-sync-stderr.log -Tail 100 -Wait
```

---

## 🔍 MONITORING: Staging vs Producción

### Dashboard de Comparación

```sql
-- Comparar métricas entre staging y producción
-- Query en staging
USE fuel_copilot_staging;
SELECT 
    COUNT(*) as total_records,
    COUNT(DISTINCT truck_id) as active_trucks,
    AVG(estimated_pct) as avg_fuel_pct,
    AVG(mpg_current) as avg_mpg
FROM fuel_metrics
WHERE timestamp_utc > DATE_SUB(NOW(), INTERVAL 1 DAY);

-- Mismo query en producción
USE fuel_copilot;
-- (repetir query)
```

**Esperado:** Números similares pero staging puede tener menos datos

---

### Logs Diferenciados

```powershell
# Ver logs staging
Get-Content C:\Users\devteam\Proyectos\fuel-analytics-backend-staging\logs\wialon-sync-staging-stderr.log -Tail 50

# Ver logs producción
Get-Content C:\Users\devteam\Proyectos\fuel-analytics-backend\logs\wialon-sync-stderr.log -Tail 50

# Comparar errores
Select-String "ERROR|CRITICAL" C:\Users\devteam\Proyectos\fuel-analytics-backend-staging\logs\*.log
```

---

## 🎯 CASOS DE USO ESPECÍFICOS

### Caso 1: Testear Benchmarking Engine

```bash
# 1. Implementar en staging branch
# 2. Deploy a staging
# 3. Esperar 24h de datos
# 4. Verificar benchmarks se calculan correctamente
# 5. Verificar NO afecta sync normal
# 6. Si todo OK → merge a main → deploy producción
```

### Caso 2: Testear Driver Scoring

```bash
# 1. Implementar en staging
# 2. Verificar que datos de hard_brake existen en Wialon
# 3. Calcular scores en staging
# 4. Comparar con comportamiento esperado
# 5. Ajustar parámetros si es necesario
# 6. Cuando scores son razonables → producción
```

### Caso 3: A/B Testing de EKF vs KF

```python
# En staging: configurar 50% trucks con EKF, 50% con KF
# Comparar precisión después de 1 semana
# Solo deploy EKF a producción si mejora >20%

# wialon_sync_enhanced.py (staging only)
USE_EKF = truck_id in ['RA9250', 'FF7702', ...]  # 50% de trucks
estimator = EKF() if USE_EKF else KalmanFilter()
```

---

## 💾 BACKUPS Y ROLLBACK

### Backup Automático antes de Deploy

```powershell
# Script: backup_before_deploy.ps1
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backupDir = "C:\Backups\fuel-analytics"

# Backup DB producción
mysqldump -u fuel_admin -p fuel_copilot > "$backupDir\fuel_copilot_$timestamp.sql"

# Backup código
Copy-Item -Recurse "C:\Users\devteam\Proyectos\fuel-analytics-backend" "$backupDir\backend_$timestamp"

Write-Host "✅ Backup completado: $backupDir\*_$timestamp" -ForegroundColor Green
```

### Rollback Rápido

```powershell
# Si algo sale mal en producción después de deploy
cd C:\Users\devteam\Proyectos\fuel-analytics-backend

# Opción A: Git revert
git revert HEAD
git push origin main
Restart-Service FuelAnalytics-*

# Opción B: Checkout versión anterior
git checkout v3.12.32  # Última versión estable
Restart-Service FuelAnalytics-*

# Opción C: Restaurar desde backup
Stop-Service FuelAnalytics-*
mysql -u fuel_admin fuel_copilot < C:\Backups\fuel-analytics\fuel_copilot_TIMESTAMP.sql
# Restaurar código desde backup
Start-Service FuelAnalytics-*
```

---

## 📊 RESUMEN: STAGING vs PRODUCCIÓN

| Aspecto | Producción | Staging |
|---------|-----------|---------|
| **Base de datos** | fuel_copilot | fuel_copilot_staging |
| **API Puerto** | 8001 | 8002 |
| **Servicios** | FuelAnalytics-* | FuelAnalytics-*-Staging |
| **Frontend URL** | fuelanalytics.fleetbooster.net | localhost:5174 o staging.fuelanalytics... |
| **Git Branch** | main | feature/* branches |
| **Datos** | Todos (históricos) | Últimos 7-30 días |
| **Uptime** | 24/7 crítico | Puede reiniciar para tests |
| **Testing** | Smoke tests solo | Tests completos, experimentación |

---

## ✅ CHECKLIST DE SETUP (Primera Vez)

- [ ] DB staging creada (fuel_copilot_staging)
- [ ] Últimos 7 días de datos copiados
- [ ] Directorio staging clonado (fuel-analytics-backend-staging)
- [ ] .env.staging configurado (puerto 8002, DB staging)
- [ ] Virtualenv staging creado
- [ ] Servicios Windows staging creados (nssm)
- [ ] Servicios staging iniciados y running
- [ ] Frontend staging clonado
- [ ] Frontend staging apunta a API staging
- [ ] Logs staging funcionando
- [ ] Smoke test: API staging responde en puerto 8002
- [ ] Smoke test: WialonSync staging escribe a DB staging

---

## 🚀 PRÓXIMOS PASOS

**Ahora que tienes staging setup:**

1. **Esta semana:** Implementar Benchmarking Engine en staging
2. **Testear 2-3 días** en staging con datos reales
3. **Si pasa todos los tests:** Deploy a producción
4. **Siguiente feature:** Repetir proceso (staging → testing → producción)

---

*Staging Environment Guide - v1.0 - 23 Dic 2025*
