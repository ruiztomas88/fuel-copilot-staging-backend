# ============================================================================
# 🪟 INSTALL FUEL ANALYTICS BACKEND AS WINDOWS SERVICE
# ============================================================================
# This script creates a Windows Service that:
# - Auto-starts on boot
# - Auto-restarts if it crashes (WinError 64, etc.)
# - Runs in background
#
# Usage:
#   Run as Administrator:
#   .\install-windows-service.ps1
# ============================================================================

# Requires NSSM (Non-Sucking Service Manager)
# Download from: https://nssm.cc/download

$ServiceName = "FuelAnalyticsBackend"
$PythonExe = "python.exe"  # Or full path: "C:\Python311\python.exe"
$ScriptPath = "$PSScriptRoot\main.py"
$WorkingDir = $PSScriptRoot

Write-Host "🔧 Installing Fuel Analytics Backend as Windows Service..." -ForegroundColor Cyan
Write-Host ""

# Check if NSSM is installed
$nssmPath = Get-Command nssm -ErrorAction SilentlyContinue
if (-not $nssmPath) {
    Write-Host "❌ NSSM not found. Installing via Chocolatey..." -ForegroundColor Red
    Write-Host "   Run: choco install nssm -y" -ForegroundColor Yellow
    Write-Host "   Or download from: https://nssm.cc/download" -ForegroundColor Yellow
    exit 1
}

# Stop and remove existing service if it exists
$existingService = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
if ($existingService) {
    Write-Host "⚠️  Removing existing service..." -ForegroundColor Yellow
    Stop-Service -Name $ServiceName -Force -ErrorAction SilentlyContinue
    nssm remove $ServiceName confirm
    Start-Sleep -Seconds 2
}

# Install the service
Write-Host "📦 Installing service: $ServiceName" -ForegroundColor Green
nssm install $ServiceName $PythonExe $ScriptPath

# Configure service
Write-Host "⚙️  Configuring service..." -ForegroundColor Cyan

# Set working directory
nssm set $ServiceName AppDirectory $WorkingDir

# Set environment variables
nssm set $ServiceName AppEnvironmentExtra "DEV_MODE=false"

# Auto-restart on failure
nssm set $ServiceName AppExit Default Restart
nssm set $ServiceName AppRestartDelay 5000  # Wait 5 seconds before restart

# Restart after 3 failures within 1 minute
nssm set $ServiceName AppThrottle 60000

# Log configuration
$LogDir = "$WorkingDir\logs"
if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir | Out-Null
}
nssm set $ServiceName AppStdout "$LogDir\backend-stdout.log"
nssm set $ServiceName AppStderr "$LogDir\backend-stderr.log"

# Start service automatically on boot
nssm set $ServiceName Start SERVICE_AUTO_START

# Start the service
Write-Host "🚀 Starting service..." -ForegroundColor Green
nssm start $ServiceName

Start-Sleep -Seconds 3

# Check status
$status = nssm status $ServiceName
Write-Host ""
Write-Host "=================================================================================" -ForegroundColor Cyan
Write-Host "✅ Service installed successfully!" -ForegroundColor Green
Write-Host "=================================================================================" -ForegroundColor Cyan
Write-Host "Service Name:    $ServiceName" -ForegroundColor White
Write-Host "Status:          $status" -ForegroundColor White
Write-Host "Python:          $PythonExe" -ForegroundColor White
Write-Host "Script:          $ScriptPath" -ForegroundColor White
Write-Host "Logs:            $LogDir" -ForegroundColor White
Write-Host ""
Write-Host "Commands:" -ForegroundColor Yellow
Write-Host "  Start:   nssm start $ServiceName" -ForegroundColor Gray
Write-Host "  Stop:    nssm stop $ServiceName" -ForegroundColor Gray
Write-Host "  Restart: nssm restart $ServiceName" -ForegroundColor Gray
Write-Host "  Status:  nssm status $ServiceName" -ForegroundColor Gray
Write-Host "  Remove:  nssm remove $ServiceName confirm" -ForegroundColor Gray
Write-Host ""
Write-Host "🔧 Service will auto-restart on crashes (WinError 64, etc.)" -ForegroundColor Green
Write-Host "=================================================================================" -ForegroundColor Cyan
