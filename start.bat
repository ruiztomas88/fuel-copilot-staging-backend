@echo off
REM ============================================================================
REM FUEL COPILOT BACKEND - WINDOWS STARTUP SCRIPT
REM ============================================================================
REM Run this script to start the backend server on Azure VM

echo ========================================
echo   FUEL COPILOT BACKEND - Azure VM
echo ========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.11+ from https://www.python.org/downloads/
    pause
    exit /b 1
)

REM Check if virtual environment exists
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Install dependencies
echo Installing dependencies...
pip install -r requirements.txt

REM Check if .env exists
if not exist ".env" (
    echo.
    echo WARNING: .env file not found!
    echo Please copy .env.example to .env and configure your settings.
    echo.
    copy .env.example .env
    echo Created .env from template. Please edit it with your settings.
    pause
)

REM Start the server
echo.
echo Starting Fuel Copilot API...
echo.
echo API will be available at:
echo   - Local: http://localhost:8000/fuelanalytics/docs
echo   - External: https://fleetbooster.net/fuelanalytics/docs
echo.
echo Press Ctrl+C to stop the server
echo.

python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload

pause
