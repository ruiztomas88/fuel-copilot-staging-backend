@echo off
REM ============================================
REM Fuel Analytics Backend - All Services
REM Single launcher for NSSM service
REM ============================================

cd /d C:\Users\devteam\Proyectos\fuel-analytics-backend

echo [%TIME%] Starting all backend services...

REM Activate venv and launch components
call venv\Scripts\activate.bat

REM Start wialon_sync_enhanced (15s intervals)
start /B python wialon_sync_enhanced.py >> logs\backend-all.log 2>> logs\backend-errors.log

REM Wait 5 seconds for wialon_sync to initialize
timeout /t 5 /nobreak >nul

REM Start Uvicorn API (port 8000)
start /B venv\Scripts\uvicorn.exe main:app --host 0.0.0.0 --port 8000 >> logs\backend-all.log 2>> logs\backend-errors.log

REM Start auto_update_daily_metrics (15-min updates)
start /B python auto_update_daily_metrics.py >> logs\backend-all.log 2>> logs\backend-errors.log

REM Start auto_backup_db (6-hour backups)
start /B python auto_backup_db.py >> logs\backend-all.log 2>> logs\backend-errors.log

echo [%TIME%] All services started successfully
echo Check logs\backend-all.log for output
echo Check logs\backend-errors.log for errors

REM Keep this process alive (required for NSSM)
:loop
timeout /t 60 /nobreak >nul
goto loop
