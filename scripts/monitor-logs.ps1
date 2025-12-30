# ==============================================================================
# 馃搳 FUEL ANALYTICS - LOG MONITOR
# ==============================================================================
# Monitor logs in real-time to debug crashes and errors
# ==============================================================================

Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host "馃搳 FUEL ANALYTICS LOG MONITOR" -ForegroundColor Green
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host ""

$logFile = "fuel_analytics.log"

if (-not (Test-Path $logFile)) {
    Write-Host "鉀?Esperando que se cree el archivo de log..." -ForegroundColor Yellow
    Write-Host ""
}

Write-Host "馃憞 Mostrando logs en tiempo real (presiona CTRL+C para salir)..." -ForegroundColor White
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host ""

# Follow the log file in real-time
Get-Content -Path $logFile -Wait -Tail 50 | ForEach-Object {
    $line = $_
    
    # Color coding based on log level
    if ($line -match "ERROR|CRITICAL|馃毃") {
        Write-Host $line -ForegroundColor Red
    }
    elseif ($line -match "WARNING|鈿狅笍") {
        Write-Host $line -ForegroundColor Yellow
    }
    elseif ($line -match "INFO|鉁?|馃殌|馃搳") {
        Write-Host $line -ForegroundColor Green
    }
    elseif ($line -match "DEBUG") {
        Write-Host $line -ForegroundColor Gray
    }
    else {
        Write-Host $line -ForegroundColor White
    }
}
