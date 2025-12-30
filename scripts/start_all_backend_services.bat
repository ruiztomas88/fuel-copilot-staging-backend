@echo off
REM ============================================
REM Fuel Analytics Backend - All Services
REM Quick launcher without log redirection issues
REM ============================================

cd /d C:\Users\devteam\Proyectos\fuel-analytics-backend

echo.
echo ========================================
echo   Fuel Analytics Backend Launcher
echo ========================================
echo.
echo [%TIME%] Iniciando servicios...
echo.

REM Crear directorio de logs si no existe
if not exist logs mkdir logs

REM Iniciar wialon_sync en ventana minimizada
echo [1/4] Iniciando Wialon Sync...
start "WIALON_SYNC" /MIN cmd /c "venv\Scripts\python.exe wialon_sync_enhanced.py"

REM Esperar 5 segundos para que Wialon inicialice
timeout /t 5 /nobreak >nul

REM Iniciar API REST en ventana minimizada
echo [2/4] Iniciando API REST (puerto 8000)...
start "API_REST" /MIN cmd /c "venv\Scripts\uvicorn.exe main:app --host 0.0.0.0 --port 8000"

REM Esperar 3 segundos
timeout /t 3 /nobreak >nul

REM Iniciar actualizador de métricas en ventana minimizada
echo [3/4] Iniciando Daily Metrics Updater...
start "DAILY_METRICS" /MIN cmd /c "venv\Scripts\python.exe auto_update_daily_metrics.py"

REM Iniciar auto backup en ventana minimizada
echo [4/4] Iniciando Auto Backup...
start "AUTO_BACKUP" /MIN cmd /c "venv\Scripts\python.exe auto_backup_db.py"

echo.
echo ========================================
echo   SERVICIOS INICIADOS CORRECTAMENTE
echo ========================================
echo.
echo   Wialon Sync       : Ventana "WIALON_SYNC"
echo   API REST          : http://localhost:8000
echo   Daily Metrics     : Ventana "DAILY_METRICS"
echo   Auto Backup       : Ventana "AUTO_BACKUP"
echo.
echo Presiona cualquier tecla para salir...
pause >nul
