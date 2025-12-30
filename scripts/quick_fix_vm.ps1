# ============================================================================
# Quick Fix Script for Wialon Sync Issues
# Run this if sensors show N/A or empty data
# ============================================================================

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "WIALON SYNC QUICK FIX" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

# ============================================================================
# STEP 1: Install dependencies
# ============================================================================
Write-Host "[1] Installing PyMySQL if missing..." -ForegroundColor Green
pip install pymysql --quiet
Write-Host "✅ PyMySQL ready`n" -ForegroundColor Green

# ============================================================================
# STEP 2: Stop any existing sync processes
# ============================================================================
Write-Host "[2] Stopping existing sync processes..." -ForegroundColor Green

# Stop NSSM service if exists
$service = Get-Service -Name "WialonSync" -ErrorAction SilentlyContinue
if ($service -and $service.Status -eq "Running") {
    Stop-Service WialonSync
    Write-Host "✅ Stopped WialonSync service" -ForegroundColor Green
}

# Stop scheduled task if running
$task = Get-ScheduledTask -TaskName "WialonSyncService" -ErrorAction SilentlyContinue
if ($task) {
    Stop-ScheduledTask -TaskName "WialonSyncService" -ErrorAction SilentlyContinue
    Write-Host "✅ Stopped WialonSyncService task" -ForegroundColor Green
}

# Kill any Python processes running the sync
Get-Process | Where-Object {$_.ProcessName -eq "python" -and $_.Path -like "*wialon_full_sync_service*"} | Stop-Process -Force -ErrorAction SilentlyContinue
Write-Host "✅ Killed stale Python processes`n" -ForegroundColor Green

# ============================================================================
# STEP 3: Test database connections
# ============================================================================
Write-Host "[3] Testing database connections..." -ForegroundColor Green

$testScript = @"
import pymysql
import sys

print('Testing local database...')
try:
    conn = pymysql.connect(
        host='localhost',
        port=3306,
        user='root',
        password='tomas',
        database='fuel_copilot'
    )
    print('✅ Local database: OK')
    conn.close()
except Exception as e:
    print(f'❌ Local database: FAILED - {e}')
    sys.exit(1)

print('Testing Wialon database...')
try:
    conn = pymysql.connect(
        host='20.127.200.135',
        port=3306,
        user='wialonro',
        password='KjmAqwertY1#2024!@Wialon',
        database='wialon_collect',
        connect_timeout=10
    )
    with conn.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM sensors")
        count = cursor.fetchone()[0]
        print(f'✅ Wialon database: OK ({count} sensor readings)')
    conn.close()
except Exception as e:
    print(f'❌ Wialon database: FAILED - {e}')
    print('   Check network/firewall to 20.127.200.135:3306')
    sys.exit(1)

print('✅ All database connections working')
"@

$testScript | python
if ($LASTEXITCODE -ne 0) {
    Write-Host "`n❌ Database connection test failed. Fix connections before continuing." -ForegroundColor Red
    exit 1
}

Write-Host ""

# ============================================================================
# STEP 4: Run migration to ensure tables exist
# ============================================================================
Write-Host "[4] Ensuring all tables exist..." -ForegroundColor Green
python migrations\create_wialon_sync_tables.py
Write-Host ""

# ============================================================================
# STEP 5: Start sync service in foreground for testing
# ============================================================================
Write-Host "[5] Starting sync service..." -ForegroundColor Green
Write-Host "   This will run in foreground for 2 minutes to verify it works" -ForegroundColor Yellow
Write-Host "   Press Ctrl+C after you see a few successful sync cycles`n" -ForegroundColor Yellow

# Start the service
Start-Process -NoNewWindow -FilePath "python" -ArgumentList "wialon_full_sync_service.py"

Write-Host "`n✅ Sync service started!" -ForegroundColor Green
Write-Host "`nMonitoring logs for 30 seconds..." -ForegroundColor Cyan

Start-Sleep -Seconds 5

# Monitor logs
$timeout = 30
$elapsed = 0
while ($elapsed -lt $timeout) {
    if (Test-Path "wialon_sync.log") {
        $lastLines = Get-Content "wialon_sync.log" -Tail 5
        Clear-Host
        Write-Host "`n========== LIVE SYNC LOG (Last 5 lines) ==========" -ForegroundColor Cyan
        $lastLines | ForEach-Object {
            if ($_ -match "❌") {
                Write-Host $_ -ForegroundColor Red
            } elseif ($_ -match "✅") {
                Write-Host $_ -ForegroundColor Green
            } elseif ($_ -match "🔄") {
                Write-Host $_ -ForegroundColor Yellow
            } else {
                Write-Host $_ -ForegroundColor Gray
            }
        }
        Write-Host "===================================================`n" -ForegroundColor Cyan
    }
    Start-Sleep -Seconds 5
    $elapsed += 5
}

# ============================================================================
# STEP 6: Check if data is being synced
# ============================================================================
Write-Host "`n[6] Checking if data is being synced..." -ForegroundColor Green

$dataCheckScript = @"
import pymysql
from datetime import datetime, timedelta

conn = pymysql.connect(
    host='localhost',
    port=3306,
    user='root',
    password='tomas',
    database='fuel_copilot'
)

with conn.cursor() as cursor:
    # Check sensor cache
    cursor.execute("SELECT COUNT(*), MAX(last_updated) FROM truck_sensors_cache")
    sensor_count, last_update = cursor.fetchone()
    
    if sensor_count > 0:
        age = (datetime.now() - last_update).total_seconds()
        print(f'✅ Sensors: {sensor_count} trucks cached, last update {int(age)} seconds ago')
        if age > 120:
            print(f'   ⚠️  Data is stale (> 2 minutes old). Service may not be running.')
    else:
        print('❌ Sensors: No data in cache yet')
        print('   Wait 30-60 seconds for first sync cycle')
    
    # Check trips
    cursor.execute("SELECT COUNT(*) FROM truck_trips")
    trips_count = cursor.fetchone()[0]
    print(f'ℹ️  Trips: {trips_count} records')
    
    # Check speeding events
    cursor.execute("SELECT COUNT(*) FROM truck_speeding_events")
    speeding_count = cursor.fetchone()[0]
    print(f'ℹ️  Speeding events: {speeding_count} records')

conn.close()
"@

$dataCheckScript | python
Write-Host ""

# ============================================================================
# STEP 7: Instructions
# ============================================================================
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "NEXT STEPS" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

Write-Host "If you see '✅ Sensors: X trucks cached':" -ForegroundColor Green
Write-Host "  → Data is syncing! Check your dashboard." -ForegroundColor Gray
Write-Host "  → If still showing N/A, restart your FastAPI backend." -ForegroundColor Gray
Write-Host "  → The sync service will keep running in the background.`n" -ForegroundColor Gray

Write-Host "If you see '❌ Sensors: No data':" -ForegroundColor Red
Write-Host "  → Check the logs: Get-Content wialon_sync.log -Tail 50" -ForegroundColor Gray
Write-Host "  → Look for ❌ error messages" -ForegroundColor Gray
Write-Host "  → Most common issue: Wialon network connection blocked by firewall`n" -ForegroundColor Gray

Write-Host "To check logs anytime:" -ForegroundColor Yellow
Write-Host "  Get-Content wialon_sync.log -Wait -Tail 20`n" -ForegroundColor Gray

Write-Host "To stop the sync service:" -ForegroundColor Yellow
Write-Host "  Get-Process | Where-Object {`$_.ProcessName -eq 'python'} | Stop-Process`n" -ForegroundColor Gray

Write-Host "To install as permanent service:" -ForegroundColor Yellow
Write-Host "  See VM_DEPLOYMENT_GUIDE.md Step 7 (NSSM or Scheduled Task)`n" -ForegroundColor Gray
