#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Quick Start - Fuel Analytics Backend
.DESCRIPTION
    Inicia todos los componentes del backend en ventanas separadas
.EXAMPLE
    .\quick_start.ps1
#>

$ErrorActionPreference = "Stop"
$BackendPath = "C:\Users\devteam\Proyectos\fuel-analytics-backend"

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  Fuel Analytics Backend - Quick Start" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

# Verificar que estamos en el directorio correcto
if (-not (Test-Path "$BackendPath\venv\Scripts\python.exe")) {
    Write-Host "❌ Error: No se encuentra el venv en $BackendPath" -ForegroundColor Red
    exit 1
}

cd $BackendPath

# Matar procesos existentes
Write-Host "[1/5] Deteniendo procesos existentes..." -ForegroundColor Yellow
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 2

# Iniciar Wialon Sync
Write-Host "[2/5] Iniciando Wialon Sync..." -ForegroundColor Green
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "cd '$BackendPath'; `$host.ui.RawUI.WindowTitle='🔄 WIALON SYNC'; .\venv\Scripts\python.exe wialon_sync_enhanced.py"
) -WindowStyle Minimized

Start-Sleep -Seconds 5

# Iniciar API REST
Write-Host "[3/5] Iniciando API REST (puerto 8000)..." -ForegroundColor Green
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "cd '$BackendPath'; `$host.ui.RawUI.WindowTitle='🌐 API REST :8000'; .\venv\Scripts\uvicorn.exe main:app --host 0.0.0.0 --port 8000"
) -WindowStyle Minimized

Start-Sleep -Seconds 3

# Iniciar Daily Metrics
Write-Host "[4/5] Iniciando Daily Metrics Updater..." -ForegroundColor Green
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "cd '$BackendPath'; `$host.ui.RawUI.WindowTitle='📊 DAILY METRICS'; .\venv\Scripts\python.exe auto_update_daily_metrics.py"
) -WindowStyle Minimized

# Iniciar Auto Backup
Write-Host "[5/5] Iniciando Auto Backup (6h)..." -ForegroundColor Green
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "cd '$BackendPath'; `$host.ui.RawUI.WindowTitle='💾 AUTO BACKUP'; .\venv\Scripts\python.exe auto_backup_db.py"
) -WindowStyle Minimized

# Verificar API
Write-Host "`n⏳ Esperando API..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

try {
    $response = Invoke-WebRequest -Uri "http://localhost:8000/" -Method GET -UseBasicParsing -ErrorAction Stop
    Write-Host "`n✅ BACKEND INICIADO CORRECTAMENTE`n" -ForegroundColor Green
    Write-Host "   🔄 Wialon Sync    : Corriendo (15s intervals)" -ForegroundColor Cyan
    Write-Host "   🌐 API REST       : http://localhost:8000 (Status $($response.StatusCode))" -ForegroundColor Cyan
    Write-Host "   📊 Daily Metrics  : Corriendo (15min updates)" -ForegroundColor Cyan
    Write-Host "   💾 Auto Backup    : Corriendo (6h backups)" -ForegroundColor Cyan
    Write-Host "`n📝 Para detener: Get-Process python | Stop-Process -Force" -ForegroundColor DarkGray
}
catch {
    Write-Host "`n⚠️  API no responde todavía (puede tomar 10-15s)" -ForegroundColor Yellow
    Write-Host "   Verifica manualmente: http://localhost:8000" -ForegroundColor DarkGray
}

Write-Host "`n========================================`n" -ForegroundColor Cyan
