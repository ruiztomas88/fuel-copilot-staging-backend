# 🔍 VM Idle Configuration Checker
# Run this ON THE VM to verify the fix was applied

Write-Host "=" -NoNewline -ForegroundColor Cyan
Write-Host ("=" * 79) -ForegroundColor Cyan
Write-Host "🔍 CHECKING IDLE ENGINE CONFIGURATION ON VM" -ForegroundColor Yellow
Write-Host "=" -NoNewline -ForegroundColor Cyan
Write-Host ("=" * 79) -ForegroundColor Cyan

# 1. Check git status
Write-Host "`n📌 GIT STATUS:" -ForegroundColor Cyan
git log --oneline -3

Write-Host "`n🔍 Current branch:" -ForegroundColor Cyan
git branch --show-current

# 2. Check idle_engine.py config values
Write-Host "`n⚙️ IDLE_ENGINE.PY CONFIGURATION:" -ForegroundColor Cyan
Write-Host "   fuel_rate_min_lph (should be 0.4):" -ForegroundColor Yellow
Select-String -Path "idle_engine.py" -Pattern "fuel_rate_min_lph.*=.*0\.[0-9]" | Select-Object -First 1

Write-Host "`n   idle_gph_raw range check (should be 0.1 <= x <= 5.0):" -ForegroundColor Yellow
Select-String -Path "idle_engine.py" -Pattern "if.*0\.[0-9].*<=.*idle_gph_raw.*<=.*5\.0" | Select-Object -First 1

# 3. Check WialonSync service status
Write-Host "`n🔧 WIALON SYNC SERVICE STATUS:" -ForegroundColor Cyan
nssm status WialonSyncService

# 4. Check when service was last restarted
Write-Host "`n⏰ SERVICE UPTIME:" -ForegroundColor Cyan
$service = Get-Service -Name "WialonSyncService" -ErrorAction SilentlyContinue
if ($service) {
    $process = Get-Process -Name "python" -ErrorAction SilentlyContinue | Where-Object {
        $_.CommandLine -like "*wialon_sync*"
    }
    if ($process) {
        $uptime = (Get-Date) - $process.StartTime
        Write-Host "   Started: $($process.StartTime)" -ForegroundColor Green
        Write-Host "   Uptime: $($uptime.ToString('hh\:mm\:ss'))" -ForegroundColor Green
    } else {
        Write-Host "   ❌ Process not found" -ForegroundColor Red
    }
}

# 5. Check recent logs for idle calculations
Write-Host "`n📋 RECENT IDLE CALCULATIONS (last 20 lines with 'idle'):" -ForegroundColor Cyan
if (Test-Path "logs\wialon-sync-stdout.log") {
    Get-Content "logs\wialon-sync-stdout.log" -Tail 100 | Select-String -Pattern "idle|STOPPED|fuel_rate" | Select-Object -Last 20
} else {
    Write-Host "   ⚠️ Log file not found" -ForegroundColor Yellow
}

# 6. Check for truck filtering
Write-Host "`n🎯 TRUCK FILTERING (should show 41 configured):" -ForegroundColor Cyan
Get-Content "logs\wialon-sync-stdout.log" -Tail 200 | Select-String -Pattern "Configured trucks|Processing:" | Select-Object -Last 3

Write-Host "`n" -NoNewline
Write-Host "=" -NoNewline -ForegroundColor Cyan
Write-Host ("=" * 79) -ForegroundColor Cyan
Write-Host "🔧 ACTIONS TO FIX:" -ForegroundColor Yellow
Write-Host "   1. If fuel_rate_min_lph != 0.4 → Run: git pull origin main" -ForegroundColor White
Write-Host "   2. If logs show old values → Run: nssm restart WialonSyncService" -ForegroundColor White
Write-Host "   3. Wait 1 minute, then check dashboard" -ForegroundColor White
Write-Host "=" -NoNewline -ForegroundColor Cyan
Write-Host ("=" * 79) -ForegroundColor Cyan
