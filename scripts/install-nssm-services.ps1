# ============================================================================
# 🔧 INSTALACIÓN DE SERVICIOS NSSM - FUEL ANALYTICS BACKEND
# ============================================================================
# Este script instala 2 servicios de Windows usando NSSM:
#   1. FuelAnalytics-API       → FastAPI Backend (main.py)
#   2. FuelAnalytics-WialonSync → Wialon Sync Enhanced
#
# REQUISITOS:
#   - NSSM instalado (https://nssm.cc/download)
#   - Ejecutar como Administrador
#   - Python venv configurado en el proyecto
#
# EJECUTAR:
#   .\install-nssm-services.ps1
# ============================================================================

# Verificar que se ejecuta como Administrador
if (-NOT ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")) {
    Write-Host "❌ ERROR: Este script debe ejecutarse como Administrador" -ForegroundColor Red
    Write-Host "   → Click derecho → 'Ejecutar como administrador'" -ForegroundColor Yellow
    exit 1
}

Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host "🔧 INSTALACIÓN DE SERVICIOS NSSM - FUEL ANALYTICS BACKEND" -ForegroundColor Cyan
Write-Host "============================================================================`n" -ForegroundColor Cyan

# ============================================================================
# CONFIGURACIÓN
# ============================================================================
$PROJECT_DIR = "C:\Users\devteam\Proyectos\fuel-analytics-backend"
$PYTHON_EXE = "$PROJECT_DIR\venv\Scripts\python.exe"

# Buscar NSSM en ubicaciones comunes
$NSSM_PATHS = @(
    "C:\ProgramData\chocolatey\bin\nssm.exe",  # Chocolatey
    "C:\Program Files\nssm\nssm.exe",           # Instalación manual
    "C:\nssm\nssm.exe"                          # Instalación portable
)

$NSSM_EXE = $null
foreach ($path in $NSSM_PATHS) {
    if (Test-Path $path) {
        $NSSM_EXE = $path
        Write-Host "✅ NSSM encontrado en: $NSSM_EXE" -ForegroundColor Green
        break
    }
}

# Verificar que NSSM existe
if (-not $NSSM_EXE) {
    Write-Host "❌ ERROR: NSSM no encontrado" -ForegroundColor Red
    Write-Host "   Instalar con Chocolatey: choco install nssm" -ForegroundColor Yellow
    Write-Host "   O descargar desde: https://nssm.cc/download" -ForegroundColor Yellow
    exit 1
}

# Verificar que el proyecto existe
if (-not (Test-Path $PROJECT_DIR)) {
    Write-Host "❌ ERROR: Directorio del proyecto no encontrado: $PROJECT_DIR" -ForegroundColor Red
    exit 1
}

# Verificar que Python existe
if (-not (Test-Path $PYTHON_EXE)) {
    Write-Host "❌ ERROR: Python venv no encontrado: $PYTHON_EXE" -ForegroundColor Red
    Write-Host "   Crear venv primero: python -m venv venv" -ForegroundColor Yellow
    exit 1
}

Write-Host "✅ Verificaciones iniciales completadas`n" -ForegroundColor Green

# ============================================================================
# DETENER Y REMOVER SERVICIOS EXISTENTES (SI EXISTEN)
# ============================================================================
Write-Host "🛑 1. Deteniendo y removiendo servicios existentes..." -ForegroundColor Yellow

$services = @("FuelAnalytics-API", "FuelAnalytics-WialonSync")
foreach ($serviceName in $services) {
    $service = Get-Service -Name $serviceName -ErrorAction SilentlyContinue
    if ($service) {
        Write-Host "   → Deteniendo $serviceName..." -ForegroundColor Gray
        Stop-Service -Name $serviceName -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 2
        
        Write-Host "   → Removiendo $serviceName..." -ForegroundColor Gray
        & $NSSM_EXE remove $serviceName confirm | Out-Null
    }
}

Write-Host "   ✅ Servicios existentes removidos`n" -ForegroundColor Green

# ============================================================================
# SERVICIO 1: FUELANALYTICS-API (FastAPI Backend)
# ============================================================================
Write-Host "🔷 2. Instalando SERVICIO 1: FuelAnalytics-API (FastAPI Backend)..." -ForegroundColor Cyan

# Instalar servicio
& $NSSM_EXE install FuelAnalytics-API $PYTHON_EXE main.py | Out-Null

# Configurar directorio de trabajo
& $NSSM_EXE set FuelAnalytics-API AppDirectory $PROJECT_DIR | Out-Null

# Configurar nombre y descripción
& $NSSM_EXE set FuelAnalytics-API DisplayName "Fuel Analytics - FastAPI Backend" | Out-Null
& $NSSM_EXE set FuelAnalytics-API Description "API REST para Fuel Copilot Dashboard. Incluye MPG Engine, Kalman Filter, Predictive Maintenance, Theft Detection y alertas." | Out-Null

# Configurar inicio automático
& $NSSM_EXE set FuelAnalytics-API Start SERVICE_AUTO_START | Out-Null

# Configurar logs
$logDir = "$PROJECT_DIR\logs"
if (-not (Test-Path $logDir)) {
    New-Item -ItemType Directory -Path $logDir -Force | Out-Null
}
& $NSSM_EXE set FuelAnalytics-API AppStdout "$logDir\api-stdout.log" | Out-Null
& $NSSM_EXE set FuelAnalytics-API AppStderr "$logDir\api-stderr.log" | Out-Null

# Configurar reinicio automático en caso de fallo
& $NSSM_EXE set FuelAnalytics-API AppExit Default Restart | Out-Null
& $NSSM_EXE set FuelAnalytics-API AppRestartDelay 5000 | Out-Null  # 5 segundos

# Configurar variables de entorno (REQUERIDAS para producción)
$envVars = "ENVIRONMENT=production`0ADMIN_PASSWORD=FuelAdmin2025!`0SKYLORD_PASSWORD=Skylord2025!`0SKYLORD_VIEWER_PASSWORD=Viewer2025!"
& $NSSM_EXE set FuelAnalytics-API AppEnvironmentExtra $envVars | Out-Null

Write-Host "   ✅ FuelAnalytics-API instalado`n" -ForegroundColor Green

# ============================================================================
# SERVICIO 2: FUELANALYTICS-WIALONSYNC (Wialon Data Sync)
# ============================================================================
Write-Host "🔷 3. Instalando SERVICIO 2: FuelAnalytics-WialonSync (Wialon Sync)..." -ForegroundColor Cyan

# Instalar servicio
& $NSSM_EXE install FuelAnalytics-WialonSync $PYTHON_EXE wialon_sync_enhanced.py | Out-Null

# Configurar directorio de trabajo
& $NSSM_EXE set FuelAnalytics-WialonSync AppDirectory $PROJECT_DIR | Out-Null

# Configurar nombre y descripción
& $NSSM_EXE set FuelAnalytics-WialonSync DisplayName "Fuel Analytics - Wialon Sync" | Out-Null
& $NSSM_EXE set FuelAnalytics-WialonSync Description "Sincroniza datos de Wialon a MySQL. Detecta refuels, actualiza métricas y calcula MPG en tiempo real." | Out-Null

# Configurar inicio automático (DESPUÉS del servicio API)
& $NSSM_EXE set FuelAnalytics-WialonSync Start SERVICE_AUTO_START | Out-Null
& $NSSM_EXE set FuelAnalytics-WialonSync DependOnService FuelAnalytics-API | Out-Null

# Configurar delay de inicio (esperar 10 segundos después de la API)
& $NSSM_EXE set FuelAnalytics-WialonSync AppStartDelay 10000 | Out-Null

# Configurar logs
& $NSSM_EXE set FuelAnalytics-WialonSync AppStdout "$logDir\wialon-stdout.log" | Out-Null
& $NSSM_EXE set FuelAnalytics-WialonSync AppStderr "$logDir\wialon-stderr.log" | Out-Null

# Configurar reinicio automático en caso de fallo
& $NSSM_EXE set FuelAnalytics-WialonSync AppExit Default Restart | Out-Null
& $NSSM_EXE set FuelAnalytics-WialonSync AppRestartDelay 5000 | Out-Null

Write-Host "   ✅ FuelAnalytics-WialonSync instalado`n" -ForegroundColor Green

# ============================================================================
# INICIAR SERVICIOS
# ============================================================================
Write-Host "🚀 4. Iniciando servicios..." -ForegroundColor Yellow

Start-Sleep -Seconds 2

# Iniciar API primero
Write-Host "   → Iniciando FuelAnalytics-API..." -ForegroundColor Gray
Start-Service -Name "FuelAnalytics-API"
Start-Sleep -Seconds 5

# Iniciar WialonSync
Write-Host "   → Iniciando FuelAnalytics-WialonSync..." -ForegroundColor Gray
Start-Service -Name "FuelAnalytics-WialonSync"
Start-Sleep -Seconds 3

Write-Host "   ✅ Servicios iniciados`n" -ForegroundColor Green

# ============================================================================
# VERIFICAR ESTADO
# ============================================================================
Write-Host "📊 5. Estado de los servicios:" -ForegroundColor Cyan
Write-Host "─────────────────────────────────────────────────────────────" -ForegroundColor Gray

$services = Get-Service -Name "FuelAnalytics-*"
foreach ($service in $services) {
    $status = if ($service.Status -eq "Running") { "✅ RUNNING" } else { "❌ STOPPED" }
    $color = if ($service.Status -eq "Running") { "Green" } else { "Red" }
    Write-Host "   $($service.DisplayName): " -NoNewline
    Write-Host $status -ForegroundColor $color
}

Write-Host "─────────────────────────────────────────────────────────────`n" -ForegroundColor Gray

# ============================================================================
# RESUMEN FINAL
# ============================================================================
Write-Host "✅ INSTALACIÓN COMPLETADA" -ForegroundColor Green
Write-Host "─────────────────────────────────────────────────────────────" -ForegroundColor Gray
Write-Host "   🌐 API Local:    http://localhost:8000" -ForegroundColor Yellow
Write-Host "   📖 Docs:         http://localhost:8000/docs" -ForegroundColor Yellow
Write-Host "   📁 Logs:         $logDir" -ForegroundColor Yellow
Write-Host "─────────────────────────────────────────────────────────────`n" -ForegroundColor Gray

Write-Host "📌 COMANDOS ÚTILES:" -ForegroundColor Cyan
Write-Host "   Ver servicios:           Get-Service FuelAnalytics-*" -ForegroundColor White
Write-Host "   Iniciar servicio:        Start-Service FuelAnalytics-API" -ForegroundColor White
Write-Host "   Detener servicio:        Stop-Service FuelAnalytics-API" -ForegroundColor White
Write-Host "   Reiniciar servicio:      Restart-Service FuelAnalytics-API" -ForegroundColor White
Write-Host "   Ver logs en tiempo real: Get-Content $logDir\api-stdout.log -Wait" -ForegroundColor White
Write-Host "   Configurar servicio:     nssm edit FuelAnalytics-API" -ForegroundColor White
Write-Host "   Remover servicio:        nssm remove FuelAnalytics-API confirm" -ForegroundColor White
Write-Host "`n============================================================================`n" -ForegroundColor Cyan

# Mostrar logs iniciales de la API
Write-Host "📋 6. Logs iniciales de FuelAnalytics-API (últimas 20 líneas):" -ForegroundColor Cyan
Write-Host "─────────────────────────────────────────────────────────────" -ForegroundColor Gray
Start-Sleep -Seconds 3
if (Test-Path "$logDir\api-stdout.log") {
    Get-Content "$logDir\api-stdout.log" -Tail 20
}
else {
    Write-Host "   (Logs aún no disponibles, esperar unos segundos...)" -ForegroundColor Yellow
}
Write-Host "─────────────────────────────────────────────────────────────`n" -ForegroundColor Gray

Write-Host "🎉 Los servicios están configurados para iniciarse automáticamente con Windows" -ForegroundColor Green
Write-Host "   → Ya no necesitas ejecutar start-services.ps1 manualmente`n" -ForegroundColor Yellow
