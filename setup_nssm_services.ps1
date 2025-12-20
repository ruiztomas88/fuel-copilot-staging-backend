# ============================================
# CONFIGURAR SERVICIOS CON NSSM
# ============================================

$pythonPath = "C:\Users\devteam\Proyectos\fuel-analytics-backend\venv\Scripts\python.exe"
$uvicornPath = "C:\Users\devteam\Proyectos\fuel-analytics-backend\venv\Scripts\uvicorn.exe"
$workDir = "C:\Users\devteam\Proyectos\fuel-analytics-backend"

Write-Host "🔧 CONFIGURANDO SERVICIOS CON NSSM..." -ForegroundColor Cyan

# 1. wialon_sync_enhanced
Write-Host "`n1️⃣  Configurando wialon_sync_enhanced..." -ForegroundColor Yellow
nssm remove wialon_sync_enhanced confirm 2>$null
nssm install wialon_sync_enhanced "$pythonPath" "wialon_sync_enhanced.py"
nssm set wialon_sync_enhanced AppDirectory "$workDir"
nssm set wialon_sync_enhanced DisplayName "Wialon Sync Enhanced"
nssm set wialon_sync_enhanced Description "Sincroniza datos de Wialon a fuel_copilot"
nssm set wialon_sync_enhanced Start SERVICE_AUTO_START
nssm start wialon_sync_enhanced
Write-Host "✅ wialon_sync_enhanced configurado" -ForegroundColor Green

# 2. uvicorn API
Write-Host "`n2️⃣  Configurando uvicorn API..." -ForegroundColor Yellow
nssm remove uvicorn_api confirm 2>$null
nssm install uvicorn_api "$uvicornPath" "main:app --host 0.0.0.0 --port 8000"
nssm set uvicorn_api AppDirectory "$workDir"
nssm set uvicorn_api DisplayName "Fuel Analytics API"
nssm set uvicorn_api Description "API REST para Fuel Analytics Dashboard"
nssm set uvicorn_api Start SERVICE_AUTO_START
nssm start uvicorn_api
Write-Host "✅ uvicorn_api configurado" -ForegroundColor Green

# 3. auto_update_daily_metrics
Write-Host "`n3️⃣  Configurando auto_update_daily_metrics..." -ForegroundColor Yellow
nssm remove daily_metrics confirm 2>$null
nssm install daily_metrics "$pythonPath" "auto_update_daily_metrics.py"
nssm set daily_metrics AppDirectory "$workDir"
nssm set daily_metrics DisplayName "Daily Metrics Updater"
nssm set daily_metrics Description "Actualiza daily_truck_metrics cada 15 min"
nssm set daily_metrics Start SERVICE_AUTO_START
nssm start daily_metrics
Write-Host "✅ daily_metrics configurado" -ForegroundColor Green

# 4. auto_backup_db
Write-Host "`n4️⃣  Configurando auto_backup_db..." -ForegroundColor Yellow
nssm remove auto_backup confirm 2>$null
nssm install auto_backup "$pythonPath" "auto_backup_db.py"
nssm set auto_backup AppDirectory "$workDir"
nssm set auto_backup DisplayName "Auto Backup Database"
nssm set auto_backup Description "Backup automático cada 6 horas"
nssm set auto_backup Start SERVICE_AUTO_START
nssm start auto_backup
Write-Host "✅ auto_backup configurado" -ForegroundColor Green

Write-Host "`n" -NoNewline
Write-Host "=" * 50 -ForegroundColor Cyan
Write-Host "✅ TODOS LOS SERVICIOS CONFIGURADOS" -ForegroundColor Green
Write-Host "=" * 50 -ForegroundColor Cyan

# Verificar estado
Write-Host "`n📊 ESTADO DE SERVICIOS:" -ForegroundColor Cyan
$services = @("wialon_sync_enhanced", "uvicorn_api", "daily_metrics", "auto_backup")
foreach ($svc in $services) {
    $status = nssm status $svc
    if ($status -eq "SERVICE_RUNNING") {
        Write-Host "  ✅ $svc : RUNNING" -ForegroundColor Green
    }
    else {
        Write-Host "  ❌ $svc : $status" -ForegroundColor Red
    }
}

# Probar API
Write-Host "`n🧪 PROBANDO API..." -ForegroundColor Cyan
Start-Sleep -Seconds 5
try {
    $response = Invoke-WebRequest -Uri "http://localhost:8000/fuelAnalytics/api/alerts" -UseBasicParsing -TimeoutSec 10
    Write-Host "✅ API funcionando - Status: $($response.StatusCode)" -ForegroundColor Green
}
catch {
    Write-Host "❌ API no responde: $($_.Exception.Message)" -ForegroundColor Red
}
