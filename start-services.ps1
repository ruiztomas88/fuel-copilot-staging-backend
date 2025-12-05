# ============================================================================
# 🚀 FUEL ANALYTICS BACKEND - STARTUP SCRIPT
# ============================================================================
# Este script levanta todos los servicios necesarios para el backend
# Ejecutar como: .\start-services.ps1
# ============================================================================

Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host "🚀 FUEL ANALYTICS BACKEND - STARTUP SCRIPT" -ForegroundColor Cyan
Write-Host "============================================================================`n" -ForegroundColor Cyan

# 1. Ir al directorio del proyecto
Write-Host "📁 1. Navegando al directorio del proyecto..." -ForegroundColor Yellow
Set-Location "C:\Users\devteam\Proyectos\fuel-analytics-backend"

# 2. Hacer pull de los últimos cambios
Write-Host "📥 2. Actualizando código desde GitHub..." -ForegroundColor Yellow
Write-Host "   → Guardando cambios locales temporalmente..." -ForegroundColor Gray
git stash push -m "Auto-stash before pull $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" 2>&1 | Out-Null
git pull origin main
# Aplicar stash de vuelta si había cambios
$stashList = git stash list
if ($stashList -match "Auto-stash before pull") {
    Write-Host "   → Restaurando cambios locales..." -ForegroundColor Gray
    git stash pop 2>&1 | Out-Null
}

# 3. Detener cualquier job anterior
Write-Host "`n🛑 3. Deteniendo jobs anteriores..." -ForegroundColor Yellow
Get-Job | Stop-Job -PassThru | Remove-Job -Force -ErrorAction SilentlyContinue

# Detener procesos Python existentes del proyecto
Write-Host "🛑    Deteniendo procesos Python anteriores..." -ForegroundColor Yellow
Get-Process python -ErrorAction SilentlyContinue | Where-Object { 
    $_.Path -like "*fuel-analytics-backend*" 
} | Stop-Process -Force

Start-Sleep -Seconds 2

# 4. SERVICIO 1: FastAPI Backend
Write-Host "`n🔷 4. Iniciando SERVICIO 1: FastAPI Backend (main.py)..." -ForegroundColor Green
Write-Host "   → API REST, Filtro Kalman, MPG, Predicciones, Alertas" -ForegroundColor Gray
Start-Job -Name "FastAPI" -ScriptBlock { 
    Set-Location "C:\Users\devteam\Proyectos\fuel-analytics-backend"
    & ".\venv\Scripts\python.exe" main.py 
} | Out-Null

# 5. SERVICIO 2: Wialon Sync Enhanced
Write-Host "`n🔷 5. Iniciando SERVICIO 2: Wialon Sync Enhanced..." -ForegroundColor Green
Write-Host "   → Sincroniza datos de Wialon → MySQL + detecta refuels" -ForegroundColor Gray
Start-Job -Name "WialonSync" -ScriptBlock { 
    Set-Location "C:\Users\devteam\Proyectos\fuel-analytics-backend"
    & ".\venv\Scripts\python.exe" wialon_sync_enhanced.py 
} | Out-Null

# 6. Esperar que arranquen
Write-Host "`n⏳ 6. Esperando que los servicios arranquen..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

# 7. Verificar estado
Write-Host "`n📊 7. Estado de los servicios:" -ForegroundColor Cyan
Get-Job | Format-Table Id, Name, State -AutoSize

# 8. Mostrar logs iniciales de FastAPI
Write-Host "`n📋 8. Logs iniciales de FastAPI:" -ForegroundColor Cyan
Write-Host "─────────────────────────────────────────────────────────────" -ForegroundColor Gray
Receive-Job -Name "FastAPI" -Keep | Select-Object -First 15
Write-Host "─────────────────────────────────────────────────────────────" -ForegroundColor Gray

# Resumen final
Write-Host "`n✅ SERVICIOS INICIADOS CORRECTAMENTE" -ForegroundColor Green
Write-Host "─────────────────────────────────────────────────────────────" -ForegroundColor Gray
Write-Host "   🌐 API Local:    http://localhost:8000" -ForegroundColor Yellow
Write-Host "   📖 Docs:         http://localhost:8000/docs" -ForegroundColor Yellow
Write-Host "   🌍 API Externa:  https://fleetbooster.net/fuelanalytics" -ForegroundColor Yellow
Write-Host "─────────────────────────────────────────────────────────────" -ForegroundColor Gray

Write-Host "`n📌 COMANDOS ÚTILES:" -ForegroundColor Cyan
Write-Host "   Ver logs FastAPI:    Receive-Job -Name 'FastAPI' -Keep" -ForegroundColor White
Write-Host "   Ver logs WialonSync: Receive-Job -Name 'WialonSync' -Keep" -ForegroundColor White
Write-Host "   Ver estado:          Get-Job" -ForegroundColor White
Write-Host "   Detener todo:        .\stop-services.ps1" -ForegroundColor White
Write-Host "`n============================================================================`n" -ForegroundColor Cyan
