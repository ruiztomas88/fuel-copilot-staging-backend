# Script para comparar estructuras de las dos bases de datos
# Requiere acceso a ambos directorios de MySQL

Write-Host "=== COMPARACIÓN DE BASES DE DATOS ===" -ForegroundColor Cyan

# Base actual
Write-Host "`n1. BASE ACTUAL (C:\ProgramData\MySQL\data\)" -ForegroundColor Yellow
$currentDir = "C:\ProgramData\MySQL\data\fuel_copilot"
if (Test-Path $currentDir) {
    Write-Host "Directorio existe: SI" -ForegroundColor Green
    $currentFiles = Get-ChildItem $currentDir -Filter "*.ibd" | Select-Object Name, Length, LastWriteTime
    Write-Host "Archivos .ibd encontrados:" -ForegroundColor White
    $currentFiles | Format-Table -AutoSize
} else {
    Write-Host "Directorio NO existe" -ForegroundColor Red
}

# Base histórica
Write-Host "`n2. BASE HISTÓRICA (C:\ProgramData\MySQL\MySQL Server 8.0\Data\)" -ForegroundColor Yellow
$historicDir = "C:\ProgramData\MySQL\MySQL Server 8.0\Data\fuel_copilot"
if (Test-Path $historicDir) {
    Write-Host "Directorio existe: SI" -ForegroundColor Green
    $historicFiles = Get-ChildItem $historicDir -Filter "*.ibd" | Select-Object Name, Length, LastWriteTime
    Write-Host "Archivos .ibd encontrados:" -ForegroundColor White
    $historicFiles | Format-Table -AutoSize
} else {
    Write-Host "Directorio NO existe" -ForegroundColor Red
}

# Comparación de tamaños
Write-Host "`n3. COMPARACIÓN DE TAMAÑOS fuel_metrics.ibd" -ForegroundColor Yellow
$currentFuelMetrics = Get-Item "$currentDir\fuel_metrics.ibd" -ErrorAction SilentlyContinue
$historicFuelMetrics = Get-Item "$historicDir\fuel_metrics.ibd" -ErrorAction SilentlyContinue

if ($currentFuelMetrics -and $historicFuelMetrics) {
    $currentMB = [math]::Round($currentFuelMetrics.Length / 1MB, 2)
    $historicMB = [math]::Round($historicFuelMetrics.Length / 1MB, 2)
    
    Write-Host "Actual:    $currentMB MB (última modificación: $($currentFuelMetrics.LastWriteTime))" -ForegroundColor White
    Write-Host "Histórica: $historicMB MB (última modificación: $($historicFuelMetrics.LastWriteTime))" -ForegroundColor White
    Write-Host "Diferencia: $([math]::Round($historicMB - $currentMB, 2)) MB" -ForegroundColor Cyan
}

Write-Host "`n=== FIN COMPARACIÓN ===" -ForegroundColor Cyan
