# ============================================================================
# 📋 FUEL ANALYTICS BACKEND - STATUS CHECK
# ============================================================================
# Este script verifica el estado de todos los servicios
# Ejecutar como: .\check-services.ps1
# ============================================================================

Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host "📋 FUEL ANALYTICS BACKEND - STATUS CHECK" -ForegroundColor Cyan
Write-Host "============================================================================`n" -ForegroundColor Cyan

# 1. Verificar Jobs de PowerShell
Write-Host "🔷 PowerShell Jobs:" -ForegroundColor Yellow
$jobs = Get-Job
if ($jobs) {
    $jobs | Format-Table Id, Name, State, HasMoreData -AutoSize
} else {
    Write-Host "   ❌ No hay jobs activos" -ForegroundColor Red
}

# 2. Verificar procesos Python
Write-Host "`n🔷 Procesos Python del proyecto:" -ForegroundColor Yellow
$pythonProcesses = Get-Process python -ErrorAction SilentlyContinue | Where-Object { 
    $_.Path -like "*fuel-analytics-backend*" 
}

if ($pythonProcesses) {
    $pythonProcesses | Format-Table Id, ProcessName, StartTime, CPU -AutoSize
} else {
    Write-Host "   ❌ No hay procesos Python activos" -ForegroundColor Red
}

# 3. Test de conectividad local
Write-Host "`n🔷 Test de conectividad:" -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -Uri "http://localhost:8000/fuelAnalytics/api/health" -UseBasicParsing -TimeoutSec 5
    if ($response.StatusCode -eq 200) {
        Write-Host "   ✅ API Local: http://localhost:8000 - ONLINE" -ForegroundColor Green
    }
} catch {
    Write-Host "   ❌ API Local: http://localhost:8000 - OFFLINE" -ForegroundColor Red
}

# 4. Mostrar logs recientes
Write-Host "`n🔷 Últimos logs de FastAPI:" -ForegroundColor Yellow
Write-Host "─────────────────────────────────────────────────────────────" -ForegroundColor Gray
try {
    Receive-Job -Name "FastAPI" -Keep -ErrorAction SilentlyContinue | Select-Object -Last 10
} catch {
    Write-Host "   ℹ No hay logs disponibles" -ForegroundColor Gray
}
Write-Host "─────────────────────────────────────────────────────────────" -ForegroundColor Gray

Write-Host "`n🔷 Últimos logs de WialonSync:" -ForegroundColor Yellow
Write-Host "─────────────────────────────────────────────────────────────" -ForegroundColor Gray
try {
    Receive-Job -Name "WialonSync" -Keep -ErrorAction SilentlyContinue | Select-Object -Last 10
} catch {
    Write-Host "   ℹ No hay logs disponibles" -ForegroundColor Gray
}
Write-Host "─────────────────────────────────────────────────────────────" -ForegroundColor Gray

Write-Host "`n============================================================================`n" -ForegroundColor Cyan
