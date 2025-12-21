#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Quick Stop - Fuel Analytics Backend
.DESCRIPTION
    Detiene todos los procesos Python del backend
.EXAMPLE
    .\quick_stop.ps1
#>

Write-Host "`n🛑 Deteniendo Fuel Analytics Backend..." -ForegroundColor Yellow

$pythonProcesses = Get-Process python -ErrorAction SilentlyContinue

if ($pythonProcesses) {
    Write-Host "   Procesos encontrados: $($pythonProcesses.Count)" -ForegroundColor Cyan
    $pythonProcesses | Stop-Process -Force
    Start-Sleep -Seconds 2
    Write-Host "✅ Todos los procesos detenidos`n" -ForegroundColor Green
} else {
    Write-Host "ℹ️  No hay procesos Python corriendo`n" -ForegroundColor DarkGray
}
