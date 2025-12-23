# ============================================================================
# REINSTALAR SERVICIOS FUEL ANALYTICS - DESDE CERO
# ============================================================================
# Este script elimina TODOS los servicios existentes y los recrea con
# la configuracion correcta de variables de entorno
#
# Ejecutar como Administrador

Write-Host "===========================================================================" -ForegroundColor Cyan
Write-Host "  FUEL ANALYTICS - REINSTALACION COMPLETA DE SERVICIOS" -ForegroundColor Cyan
Write-Host "===========================================================================" -ForegroundColor Cyan
Write-Host ""

# ============================================================================
# PASO 1: MATAR TODOS LOS PROCESOS PYTHON DEL BACKEND
# ============================================================================
Write-Host "[1/6] Deteniendo procesos Python..." -ForegroundColor Yellow
$pythonProcs = Get-Process python -ErrorAction SilentlyContinue | Where-Object { 
    $_.Path -like "*fuel-analytics-backend*" 
}

if ($pythonProcs) {
    $pythonProcs | ForEach-Object {
        Write-Host "  >> Matando PID $($_.Id)" -ForegroundColor Red
        Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep -Seconds 2
    Write-Host "  [OK] Procesos detenidos" -ForegroundColor Green
}
else {
    Write-Host "  [OK] No hay procesos Python ejecutandose" -ForegroundColor Green
}
Write-Host ""

# ============================================================================
# PASO 2: DETECTAR NSSM
# ============================================================================
Write-Host "[2/6] Detectando NSSM..." -ForegroundColor Yellow
$nssmPaths = @(
    "C:\ProgramData\chocolatey\bin\nssm.exe",
    "C:\Program Files\NSSM\win64\nssm.exe",
    ".\nssm.exe"
)

$nssm = $null
foreach ($path in $nssmPaths) {
    if (Test-Path $path) {
        $nssm = $path
        Write-Host "  [OK] NSSM encontrado: $nssm" -ForegroundColor Green
        break
    }
}

if (-not $nssm) {
    Write-Host "  [ERROR] NSSM no encontrado" -ForegroundColor Red
    Write-Host "    Instalar con: choco install nssm -y" -ForegroundColor Yellow
    exit 1
}
Write-Host ""

# ============================================================================
# PASO 3: ELIMINAR SERVICIOS EXISTENTES
# ============================================================================
Write-Host "[3/6] Eliminando servicios existentes..." -ForegroundColor Yellow
$services = Get-Service FuelAnalytics-* -ErrorAction SilentlyContinue

if ($services) {
    foreach ($svc in $services) {
        Write-Host "  >> Deteniendo: $($svc.Name)" -ForegroundColor Yellow
        & $nssm stop $svc.Name 2>$null
        Start-Sleep -Seconds 2
        
        Write-Host "  >> Eliminando: $($svc.Name)" -ForegroundColor Red
        & $nssm remove $svc.Name confirm 2>$null
        Start-Sleep -Seconds 1
    }
    Write-Host "  [OK] Servicios eliminados" -ForegroundColor Green
}
else {
    Write-Host "  [OK] No hay servicios previos" -ForegroundColor Green
}
Write-Host ""

# ============================================================================
# PASO 4: CONFIGURAR RUTAS
# ============================================================================
Write-Host "[4/6] Configurando rutas..." -ForegroundColor Yellow
$workDir = "c:\Users\devteam\Proyectos\fuel-analytics-backend"
$python = "$workDir\venv\Scripts\python.exe"
$logDir = "$workDir\logs"

# Crear directorio de logs si no existe
if (-not (Test-Path $logDir)) {
    New-Item -ItemType Directory -Path $logDir -Force | Out-Null
}

Write-Host "  [OK] Directorio de trabajo: $workDir" -ForegroundColor Green
Write-Host "  [OK] Python: $python" -ForegroundColor Green
Write-Host "  [OK] Logs: $logDir" -ForegroundColor Green
Write-Host ""

# ============================================================================
# PASO 5: CREAR SERVICIO FUELANALYTICS-API
# ============================================================================
Write-Host "[5/6] Creando servicio FuelAnalytics-API..." -ForegroundColor Yellow

# Instalar servicio
& $nssm install FuelAnalytics-API $python main.py
& $nssm set FuelAnalytics-API AppDirectory $workDir

# Variables de entorno para API
$apiEnvVars = "ENVIRONMENT=production`0ADMIN_PASSWORD=FuelAdmin2025!`0SKYLORD_PASSWORD=Skylord2025!`0SKYLORD_VIEWER_PASSWORD=Viewer2025!"
& $nssm set FuelAnalytics-API AppEnvironmentExtra $apiEnvVars

# Configurar logs
& $nssm set FuelAnalytics-API AppStdout "$logDir\api-stdout.log"
& $nssm set FuelAnalytics-API AppStderr "$logDir\api-stderr.log"

# Rotacion de logs
& $nssm set FuelAnalytics-API AppStdoutCreationDisposition 4
& $nssm set FuelAnalytics-API AppStderrCreationDisposition 4
& $nssm set FuelAnalytics-API AppRotateFiles 1
& $nssm set FuelAnalytics-API AppRotateOnline 1
& $nssm set FuelAnalytics-API AppRotateSeconds 86400
& $nssm set FuelAnalytics-API AppRotateBytes 10485760

# Auto-reinicio
& $nssm set FuelAnalytics-API AppExit Default Restart
& $nssm set FuelAnalytics-API AppRestartDelay 5000

Write-Host "  [OK] Servicio FuelAnalytics-API creado" -ForegroundColor Green
Write-Host ""

# ============================================================================
# PASO 6: CREAR SERVICIO FUELANALYTICS-WIALONSSYNC
# ============================================================================
Write-Host "[6/6] Creando servicio FuelAnalytics-WialonSync..." -ForegroundColor Yellow

# Instalar servicio
& $nssm install FuelAnalytics-WialonSync $python wialon_sync_enhanced.py
& $nssm set FuelAnalytics-WialonSync AppDirectory $workDir

# Variables de entorno para WialonSync (CRITICO: MYSQL_PASSWORD)
$syncEnvVars = "MYSQL_PASSWORD=FuelCopilot2025!"
& $nssm set FuelAnalytics-WialonSync AppEnvironmentExtra $syncEnvVars

# Configurar logs
& $nssm set FuelAnalytics-WialonSync AppStdout "$logDir\wialon-sync-stdout.log"
& $nssm set FuelAnalytics-WialonSync AppStderr "$logDir\wialon-sync-stderr.log"

# Rotacion de logs
& $nssm set FuelAnalytics-WialonSync AppStdoutCreationDisposition 4
& $nssm set FuelAnalytics-WialonSync AppStderrCreationDisposition 4
& $nssm set FuelAnalytics-WialonSync AppRotateFiles 1
& $nssm set FuelAnalytics-WialonSync AppRotateOnline 1
& $nssm set FuelAnalytics-WialonSync AppRotateSeconds 86400
& $nssm set FuelAnalytics-WialonSync AppRotateBytes 10485760

# Auto-reinicio
& $nssm set FuelAnalytics-WialonSync AppExit Default Restart
& $nssm set FuelAnalytics-WialonSync AppRestartDelay 5000

Write-Host "  [OK] Servicio FuelAnalytics-WialonSync creado" -ForegroundColor Green
Write-Host ""

# ============================================================================
# INICIAR SERVICIOS
# ============================================================================
Write-Host "===========================================================================" -ForegroundColor Cyan
Write-Host "  INICIANDO SERVICIOS" -ForegroundColor Cyan
Write-Host "===========================================================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "Iniciando FuelAnalytics-API..." -ForegroundColor Yellow
& $nssm start FuelAnalytics-API
Start-Sleep -Seconds 3

Write-Host "Iniciando FuelAnalytics-WialonSync..." -ForegroundColor Yellow
& $nssm start FuelAnalytics-WialonSync
Start-Sleep -Seconds 5

Write-Host ""
Write-Host "===========================================================================" -ForegroundColor Cyan
Write-Host "  VERIFICACION DE ESTADO" -ForegroundColor Cyan
Write-Host "===========================================================================" -ForegroundColor Cyan
Write-Host ""

$apiStatus = (Get-Service FuelAnalytics-API).Status
$syncStatus = (Get-Service FuelAnalytics-WialonSync).Status

Write-Host "FuelAnalytics-API: $apiStatus" -ForegroundColor $(if ($apiStatus -eq "Running") { "Green" } else { "Red" })
Write-Host "FuelAnalytics-WialonSync: $syncStatus" -ForegroundColor $(if ($syncStatus -eq "Running") { "Green" } else { "Red" })

Write-Host ""
Write-Host "===========================================================================" -ForegroundColor Green
Write-Host "  [OK] INSTALACION COMPLETADA" -ForegroundColor Green
Write-Host "===========================================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Verificar logs en:" -ForegroundColor Yellow
Write-Host "  >> API stdout: $logDir\api-stdout.log" -ForegroundColor Cyan
Write-Host "  >> API stderr: $logDir\api-stderr.log" -ForegroundColor Cyan
Write-Host "  >> Sync stdout: $logDir\wialon-sync-stdout.log" -ForegroundColor Cyan
Write-Host "  >> Sync stderr: $logDir\wialon-sync-stderr.log" -ForegroundColor Cyan
Write-Host ""
Write-Host "Para ver logs en tiempo real:" -ForegroundColor Yellow
Write-Host "  Get-Content logs\wialon-sync-stderr.log -Wait -Tail 20" -ForegroundColor Cyan
Write-Host ""
