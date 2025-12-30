# ============================================================================
# 🔄 AUTO-RESTART BACKEND (Simple Version)
# ============================================================================
# This script keeps the backend running and auto-restarts if it crashes
# No need to install as Windows Service
#
# Usage:
#   .\run-with-auto-restart.ps1
# ============================================================================

$ScriptPath = "$PSScriptRoot\main.py"
$RestartDelay = 5  # seconds

Write-Host "🚀 Fuel Analytics Backend - Auto-Restart Monitor" -ForegroundColor Cyan
Write-Host "   Press Ctrl+C to stop" -ForegroundColor Yellow
Write-Host ""

$restartCount = 0
$lastRestartTime = $null

while ($true) {
    try {
        $now = Get-Date
        
        # Log restart info
        if ($restartCount -gt 0) {
            $timeSinceLastRestart = ($now - $lastRestartTime).TotalSeconds
            Write-Host ""
            Write-Host "⚠️  BACKEND CRASHED - Auto-restarting... (Restart #$restartCount)" -ForegroundColor Yellow
            Write-Host "   Time since last restart: $([math]::Round($timeSinceLastRestart, 2)) seconds" -ForegroundColor Gray
            Write-Host "   Waiting $RestartDelay seconds..." -ForegroundColor Gray
            Start-Sleep -Seconds $RestartDelay
        }
        
        $lastRestartTime = Get-Date
        Write-Host "[$($lastRestartTime.ToString('HH:mm:ss'))] 🚀 Starting backend..." -ForegroundColor Green
        
        # Run Python script
        python $ScriptPath
        
        # If we get here, the script exited (crash or manual stop)
        $restartCount++
        
    } catch {
        Write-Host "❌ ERROR: $_" -ForegroundColor Red
        $restartCount++
        Start-Sleep -Seconds $RestartDelay
    }
}
