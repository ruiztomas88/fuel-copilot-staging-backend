# ============================================================================
# 🛑 DESINSTALACIÓN DE SERVICIOS NSSM - FUEL ANALYTICS BACKEND
# ============================================================================
# Este script remueve los servicios NSSM de Fuel Analytics
#
# REQUISITOS:
#   - Ejecutar como Administrador
#
# EJECUTAR:
#   .\uninstall-nssm-services.ps1
# ============================================================================

# Verificar que se ejecuta como Administrador
if (-NOT ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")) {
    Write-Host "❌ ERROR: Este script debe ejecutarse como Administrador" -ForegroundColor Red
    exit 1
}

Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host "🛑 DESINSTALACIÓN DE SERVICIOS NSSM - FUEL ANALYTICS BACKEND" -ForegroundColor Cyan
Write-Host "============================================================================`n" -ForegroundColor Cyan

$NSSM_EXE = "C:\Program Files\nssm\nssm.exe"
$services = @("FuelAnalytics-API", "FuelAnalytics-WialonSync")

foreach ($serviceName in $services) {
    $service = Get-Service -Name $serviceName -ErrorAction SilentlyContinue
    
    if ($service) {
        Write-Host "🛑 Deteniendo $serviceName..." -ForegroundColor Yellow
        Stop-Service -Name $serviceName -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 2
        
        Write-Host "🗑️  Removiendo $serviceName..." -ForegroundColor Yellow
        & $NSSM_EXE remove $serviceName confirm | Out-Null
        Write-Host "   ✅ $serviceName removido`n" -ForegroundColor Green
    } else {
        Write-Host "⚠️  $serviceName no existe, saltando...`n" -ForegroundColor Gray
    }
}

Write-Host "✅ DESINSTALACIÓN COMPLETADA`n" -ForegroundColor Green
Write-Host "   Ahora puedes volver a usar start-services.ps1 si lo necesitas`n" -ForegroundColor Yellow
