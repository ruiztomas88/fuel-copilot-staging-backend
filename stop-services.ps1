# ============================================================================
# 🛑 FUEL ANALYTICS BACKEND - STOP SCRIPT
# ============================================================================
# Este script detiene todos los servicios del backend
# Ejecutar como: .\stop-services.ps1
# ============================================================================

Write-Host "============================================================================" -ForegroundColor Red
Write-Host "🛑 FUEL ANALYTICS BACKEND - STOP SCRIPT" -ForegroundColor Red
Write-Host "============================================================================`n" -ForegroundColor Red

Write-Host "🛑 Deteniendo jobs de PowerShell..." -ForegroundColor Yellow
$jobs = Get-Job
if ($jobs) {
    $jobs | Stop-Job -PassThru | Remove-Job -Force
    Write-Host "   ✓ Jobs detenidos: $($jobs.Count)" -ForegroundColor Green
} else {
    Write-Host "   ℹ No hay jobs activos" -ForegroundColor Gray
}

Write-Host "`n🛑 Deteniendo procesos Python del proyecto..." -ForegroundColor Yellow
$pythonProcesses = Get-Process python -ErrorAction SilentlyContinue | Where-Object { 
    $_.Path -like "*fuel-analytics-backend*" 
}

if ($pythonProcesses) {
    $pythonProcesses | Stop-Process -Force
    Write-Host "   ✓ Procesos Python detenidos: $($pythonProcesses.Count)" -ForegroundColor Green
} else {
    Write-Host "   ℹ No hay procesos Python del proyecto" -ForegroundColor Gray
}

Write-Host "`n✅ Todos los servicios han sido detenidos" -ForegroundColor Green
Write-Host "============================================================================`n" -ForegroundColor Red
